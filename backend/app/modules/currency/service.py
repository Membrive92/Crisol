"""Servicio del módulo currency.

Encapsula la conversión entre monedas y el refresco de tasas. Otros
módulos del backend (`dashboard`, `transactions` futuros) usan
`convert(...)` y reciben `ConversionResult` tipado, sin tocar
`httpx` ni la tabla `exchange_rates`.

Reglas de aritmética monetaria:

- Todo importe es `Decimal` — `float` está prohibido en este proyecto.
- Composición no-EUR (USD→GBP) se hace a precisión interna alta y se
  redondea SOLO al final con `ROUND_HALF_EVEN` (banker's rounding).
- Resultado redondeado a 2 decimales: encaja con `NUMERIC(14, 2)` de
  `transactions.amount` y con la mayoría de monedas fiat. JPY usa 0
  decimales en producción real; ese matiz queda como follow-up.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.currency import client, repository
from app.modules.currency.exceptions import (
    FrankfurterInvalidResponseError,
    FrankfurterUnavailableError,
)
from app.modules.currency.schemas import ConversionResult, RateFallback

CANONICAL_BASE = "EUR"
_QUANTIZE = Decimal("0.01")


def _normalize(code: str) -> str:
    return code.strip().upper()


def _round_money(value: Decimal) -> Decimal:
    """Redondea a 2 decimales con ROUND_HALF_EVEN."""
    return value.quantize(_QUANTIZE, rounding=ROUND_HALF_EVEN)


async def _resolve_eur_rate(
    db: AsyncSession, *, quote: str, at_date: date
) -> tuple[Decimal, date, RateFallback] | None:
    """Devuelve `(rate, rate_date, fallback)` para EUR→quote.

    Si `quote == EUR`, devuelve tasa 1 con fallback "exact".
    Lookup primero la fecha exacta y, si no, la última anterior dentro
    de la ventana del repository. Si no hay nada, devuelve None.
    """
    if quote == CANONICAL_BASE:
        return Decimal("1"), at_date, "exact"

    exact = await repository.get_rate(
        db, rate_date=at_date, base=CANONICAL_BASE, quote=quote
    )
    if exact is not None:
        return exact.rate, exact.rate_date, "exact"

    fallback = await repository.get_rate_with_fallback(
        db, rate_date=at_date, base=CANONICAL_BASE, quote=quote
    )
    if fallback is not None:
        return fallback.rate, fallback.rate_date, "previous"

    return None


async def convert(
    db: AsyncSession,
    *,
    amount: Decimal,
    from_currency: str,
    to_currency: str,
    at_date: date,
) -> ConversionResult:
    """Convierte `amount` de `from_currency` a `to_currency` en `at_date`.

    Composición vía EUR cuando ninguna de las monedas es EUR:
        amount(FROM) → amount(EUR) → amount(TO)
    Es matemáticamente equivalente a tener tasas FROM↔TO directas
    porque las tasas EUR→FROM y EUR→TO se publican consistentes el
    mismo día.

    Si no hay tasa para alguna pierna (ni exacta ni en el fallback),
    devuelve un `ConversionResult` con `fallback="missing"`,
    `rate=Decimal("1")` y `amount` sin convertir. La capa que llama
    decide cómo señalizarlo (UI con tag "sin tasa", logs, etc.).

    No lanza excepciones de red — `service.refresh_rates` es el único
    punto que toca el cliente HTTP.
    """
    src = _normalize(from_currency)
    dst = _normalize(to_currency)

    if src == dst:
        return ConversionResult(
            amount=_round_money(amount),
            rate=Decimal("1"),
            rate_date=at_date,
            fallback="same",
        )

    src_resolved = await _resolve_eur_rate(db, quote=src, at_date=at_date)
    dst_resolved = await _resolve_eur_rate(db, quote=dst, at_date=at_date)

    if src_resolved is None or dst_resolved is None:
        return ConversionResult(
            amount=_round_money(amount),
            rate=Decimal("1"),
            rate_date=at_date,
            fallback="missing",
        )

    src_rate, src_date, src_fallback = src_resolved
    dst_rate, dst_date, dst_fallback = dst_resolved

    # rate(FROM→TO) = rate(EUR→TO) / rate(EUR→FROM)
    # Operamos a precisión completa de Decimal y redondeamos al final.
    composed_rate = dst_rate / src_rate
    converted = amount * composed_rate

    # Si alguna pierna usó fallback, el resultado completo es
    # "previous" — el peor caso domina.
    fallback: RateFallback = (
        "previous" if "previous" in (src_fallback, dst_fallback) else "exact"
    )
    # Reportamos la fecha más antigua de las dos: la pierna más
    # rancia es la que limita la frescura del resultado. El caso EUR
    # self-shortcut tiene `rate_date == at_date` sintético (no es una
    # tasa real), así que el `min` con la pierna real devuelve la
    # fecha correcta.
    effective_date = min(src_date, dst_date)

    return ConversionResult(
        amount=_round_money(converted),
        # La tasa expuesta en el resultado es la composición
        # (amount destino / amount origen). La cuantizamos a 8
        # decimales para que el HTTP response sea legible.
        rate=composed_rate.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN),
        rate_date=effective_date,
        fallback=fallback,
    )


async def refresh_rates(
    db: AsyncSession,
    *,
    target_date: date,
    quotes: Iterable[str],
    base: str = CANONICAL_BASE,
) -> int:
    """Pide tasas a frankfurter para `target_date` y persiste en BD.

    Devuelve el número de filas insertadas/actualizadas. Si frankfurter
    falla, propaga la excepción correspondiente — el caller decide si
    es un error duro o un swallow silencioso (background task).
    """
    base_norm = _normalize(base)
    quotes_norm = sorted({_normalize(q) for q in quotes if _normalize(q) != base_norm})
    if not quotes_norm:
        return 0

    try:
        fetched = await client.fetch_rates(
            target_date=target_date, base=base_norm, quotes=quotes_norm
        )
    except (FrankfurterUnavailableError, FrankfurterInvalidResponseError):
        raise

    if not fetched:
        return 0

    rows = [
        (target_date, base_norm, quote, rate, "frankfurter")
        for quote, rate in fetched.items()
    ]
    return await repository.upsert_rates(db, rows)


async def ensure_rate(
    db: AsyncSession, *, quote: str, at_date: date, base: str = CANONICAL_BASE
) -> bool:
    """Garantiza que existe tasa `base→quote` para `at_date`.

    Si ya hay tasa exacta, no hace nada. Si no, intenta refrescar desde
    frankfurter. Devuelve True si tras el refresco hay tasa exacta;
    False en cualquier otro caso (incluido fallo de red).

    Pensado para llamarse en background (al crear una transacción) o
    de forma lazy desde la capa de presentación.
    """
    base_norm = _normalize(base)
    quote_norm = _normalize(quote)
    if quote_norm == base_norm:
        return True

    existing = await repository.get_rate(
        db, rate_date=at_date, base=base_norm, quote=quote_norm
    )
    if existing is not None:
        return True

    try:
        await refresh_rates(
            db, target_date=at_date, quotes=[quote_norm], base=base_norm
        )
    except (FrankfurterUnavailableError, FrankfurterInvalidResponseError):
        return False

    refreshed = await repository.get_rate(
        db, rate_date=at_date, base=base_norm, quote=quote_norm
    )
    return refreshed is not None
