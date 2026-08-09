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

# AUDIT — jpy-zero-decimal-rounding: el redondeo fijo a 2 decimales asume que
# toda moneda tiene céntimos. JPY (y otras como KRW) son monedas de 0
# decimales: "100,50 ¥" no existe. Mapeamos los dígitos por moneda y el
# default cae a 2. El quantize se construye dinámicamente
# (`Decimal("1")` para 0 dígitos, `Decimal("0.01")` para 2).
_CURRENCY_DECIMALS: dict[str, int] = {
    "JPY": 0,
    "KRW": 0,
}
_DEFAULT_DECIMALS = 2

# Conjunto canónico de monedas que pre-cargamos cuando hacemos un fetch
# lazy. Coincide con el snapshot embebido y con `CURRENCY_SYMBOL` del
# `currency-menu.tsx` del frontend. Mantener sincronizado.
COMMON_QUOTES: tuple[str, ...] = (
    "USD",
    "GBP",
    "JPY",
    "CHF",
    "CAD",
    "AUD",
    "MXN",
    "BRL",
    "CNY",
)


def _normalize(code: str) -> str:
    return code.strip().upper()


def _quantum_for(currency: str) -> Decimal:
    """Devuelve el `Decimal` exponente (`1` / `0.01`) según los dígitos de la moneda."""
    decimals = _CURRENCY_DECIMALS.get(_normalize(currency), _DEFAULT_DECIMALS)
    if decimals == 0:
        return Decimal("1")
    # `Decimal(1).scaleb(-n)` → 0.01 para n=2, generaliza a cualquier n.
    return Decimal(1).scaleb(-decimals)


def _round_money(value: Decimal, currency: str = CANONICAL_BASE) -> Decimal:
    """Redondea con ROUND_HALF_EVEN a los decimales de `currency`.

    AUDIT — jpy-zero-decimal-rounding: monedas de 0 decimales (JPY, KRW)
    se redondean a entero; el resto a 2. `currency` por defecto EUR para
    no romper callers que no pasen moneda.
    """
    return value.quantize(_quantum_for(currency), rounding=ROUND_HALF_EVEN)


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

    exact = await repository.get_rate(db, rate_date=at_date, base=CANONICAL_BASE, quote=quote)
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
            amount=_round_money(amount, dst),
            rate=Decimal("1"),
            rate_date=at_date,
            fallback="same",
        )

    src_resolved = await _resolve_eur_rate(db, quote=src, at_date=at_date)
    dst_resolved = await _resolve_eur_rate(db, quote=dst, at_date=at_date)

    if src_resolved is None or dst_resolved is None:
        # `amount` se devuelve sin convertir (en `src`), así que el redondeo
        # se hace con los decimales de la moneda ORIGEN, no la destino.
        return ConversionResult(
            amount=_round_money(amount, src),
            rate=Decimal("1"),
            rate_date=at_date,
            fallback="missing",
        )

    src_rate, src_date, src_fallback = src_resolved
    dst_rate, dst_date, dst_fallback = dst_resolved

    # AUDIT-2026-05: en una cross-rate real (ninguna pata es EUR) las dos
    # piernas EUR→X se resuelven con ventanas de fallback independientes y
    # podían acabar en fechas distintas — componiendo una tasa fresca con
    # una rancia. Re-anclamos ambas a la fecha común más antigua para que
    # la composición sea coherente; el resultado se marca como "previous".
    reanchored = False
    if src != CANONICAL_BASE and dst != CANONICAL_BASE and src_date != dst_date:
        common = min(src_date, dst_date)
        src_common = await _resolve_eur_rate(db, quote=src, at_date=common)
        dst_common = await _resolve_eur_rate(db, quote=dst, at_date=common)
        if src_common is not None and dst_common is not None:
            src_rate, src_date, _ = src_common
            dst_rate, dst_date, _ = dst_common
            reanchored = True

    # AUDIT-2026-05: si tras intentar re-anclar las dos patas siguen en
    # fechas distintas (datos con huecos: una divisa sin tasa en la fecha
    # común), la composición es necesariamente de fechas mezcladas →
    # marca "previous" explícitamente en vez de arriesgar un "exact"
    # engañoso. En la práctica una fecha distinta ya implica una pata
    # "previous", pero lo hacemos explícito por si cambia `_resolve`.
    if src != CANONICAL_BASE and dst != CANONICAL_BASE and src_date != dst_date:
        reanchored = True

    # rate(FROM→TO) = rate(EUR→TO) / rate(EUR→FROM)
    # Operamos a precisión completa de Decimal y redondeamos al final.
    composed_rate = dst_rate / src_rate
    converted = amount * composed_rate

    # Si alguna pierna usó fallback (o re-anclamos), el resultado completo
    # es "previous" — el peor caso domina.
    fallback: RateFallback = (
        "previous" if reanchored or "previous" in (src_fallback, dst_fallback) else "exact"
    )
    # Reportamos la fecha más antigua de las dos: la pierna más
    # rancia es la que limita la frescura del resultado. El caso EUR
    # self-shortcut tiene `rate_date == at_date` sintético (no es una
    # tasa real), así que el `min` con la pierna real devuelve la
    # fecha correcta.
    effective_date = min(src_date, dst_date)

    return ConversionResult(
        amount=_round_money(converted, dst),
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
    timeout: float | None = None,
) -> int:
    """Pide tasas a frankfurter para `target_date` y persiste en BD.

    Devuelve el número de filas insertadas/actualizadas. Si frankfurter
    falla, propaga la excepción correspondiente — el caller decide si
    es un error duro o un swallow silencioso (background task).

    `timeout` se pasa tal cual al cliente (ver su docstring): `None` usa el del
    camino de request; el cron pasa el suyo, más generoso.
    """
    base_norm = _normalize(base)
    quotes_norm = sorted({_normalize(q) for q in quotes if _normalize(q) != base_norm})
    if not quotes_norm:
        return 0

    try:
        fetched = await client.fetch_rates(
            target_date=target_date, base=base_norm, quotes=quotes_norm, timeout=timeout
        )
    except (FrankfurterUnavailableError, FrankfurterInvalidResponseError):
        raise

    if not fetched:
        return 0

    rows = [(target_date, base_norm, quote, rate, "frankfurter") for quote, rate in fetched.items()]
    return await repository.upsert_rates(db, rows)


async def missing_exact_rates(
    db: AsyncSession,
    *,
    on: date,
    quotes: Iterable[str],
    base: str = CANONICAL_BASE,
) -> list[str]:
    """De `quotes`, cuáles NO tienen tasa **exacta** para `on`.

    Lectura pura, sin red. La expone el servicio —y no se deja que cada módulo
    consulte el repositorio— porque `currency` es transversal y su frontera es
    `service` ([ADR-0009](../../../internal_docs/decisions/0009-single-fx-source-currency-transversal.md)).

    Existe para quien necesita frescura ESTRICTA y no le sirve el fallback de
    `ensure_rates_for_dates`, que da por buena cualquier tasa dentro de su
    ventana: valorar una cartera a día de hoy con el tipo de hace dos semanas es
    correcto según esa política y engañoso en pantalla. Quien la use decide qué
    hacer con las que faltan (normalmente `refresh_rates`); esta función no
    cambia nada.
    """
    base_norm = _normalize(base)
    wanted = sorted({_normalize(q) for q in quotes if _normalize(q) != base_norm})
    missing: list[str] = []
    for quote in wanted:
        if await repository.get_rate(db, rate_date=on, base=base_norm, quote=quote) is None:
            missing.append(quote)
    return missing


async def ensure_exact_rates_for_dates(
    db: AsyncSession,
    dates: Iterable[date],
    *,
    base: str = CANONICAL_BASE,
    quotes: Iterable[str] | None = None,
    timeout: float | None = None,
) -> int:
    """Hermana ESTRICTA de `ensure_rates_for_dates`: exige tasa exacta.

    La diferencia está en el canario, y es la que decide si se pide algo o no:
    `ensure_rates_for_dates` da por buena cualquier tasa dentro de la ventana de
    fallback de 14 días, así que **el día que se guarda una tasa deja de pedir
    durante dos semanas**. Esa política es correcta para convertir movimientos
    PASADOS —el último día hábil publicado *es* el dato bueno— y es un desastre
    para quien refresca a diario: el cron nocturno (PHASE-11.1) llevaba desde
    entonces sin traer nada, y por eso una compra del viernes 24-jul se valoró
    con el tipo del 18.

    Aquí se pide fecha a fecha lo que falte de forma exacta. Devuelve el número
    de fechas para las que se hizo una petición.

    Best-effort igual que su hermana: el BCE no publica fines de semana ni
    festivos, así que "no hay tasa de hoy" un domingo es lo NORMAL y se traga.
    Nótese que Frankfurter responde a una fecha no hábil con la última publicada
    y la persistimos bajo la fecha PEDIDA — que es justo lo que hace que
    `convert(at_date=domingo)` resuelva, porque la tasa de referencia del BCE
    sigue vigente hasta la siguiente publicación.

    Commitea por dentro, como `ensure_rates_for_dates` ([ADR-0009](../../../internal_docs/decisions/0009-single-fx-source-currency-transversal.md)):
    no la llames en mitad de un upsert ajeno o confirmarás trabajo a medias.
    """
    base_norm = _normalize(base)
    quote_list = tuple(quotes) if quotes is not None else COMMON_QUOTES

    fetched = 0
    for target in sorted(set(dates)):
        missing = await missing_exact_rates(db, on=target, quotes=quote_list, base=base_norm)
        if not missing:
            continue
        try:
            await refresh_rates(
                db, target_date=target, quotes=missing, base=base_norm, timeout=timeout
            )
            await db.commit()
            fetched += 1
        except (FrankfurterUnavailableError, FrankfurterInvalidResponseError):
            await db.rollback()
            continue
    return fetched


async def ensure_rates_for_dates(
    db: AsyncSession,
    dates: Iterable[date],
    *,
    base: str = CANONICAL_BASE,
    quotes: Iterable[str] | None = None,
) -> int:
    """Garantiza que cada fecha tenga tasas en BD; si no, las trae.

    Pensado para modo cross-currency del dashboard: antes de agregar,
    rellenamos huecos para las fechas concretas de las transacciones
    del scope. Best-effort: errores de red por fecha se tragan.

    No re-fetcha si la fecha tiene al menos una tasa con la base
    canónica dentro del rango exacto, o si hay una tasa anterior
    suficientemente cercana (la ventana de fallback del repository
    cubre el caso).

    **Elige a conciencia entre ésta y `ensure_exact_rates_for_dates`**: esa
    ventana de 14 días hace que ésta calle durante dos semanas tras un fetch.
    Es lo que quieres al rellenar huecos de fechas PASADAS —evita 50
    round-trips para 50 fechas— y NO lo que quieres para refrescar el día en
    curso. Ahí va la estricta.

    Devuelve el número de fechas efectivamente fetcheadas (útil para
    métricas / logs futuros).
    """
    base_norm = _normalize(base)
    quote_list = tuple(quotes) if quotes is not None else COMMON_QUOTES

    fetched = 0
    for target in sorted(set(dates)):
        # Si ya hay tasa exacta o reciente (dentro de ventana), saltar.
        # Usamos USD como canario porque las fechas reales del ECB tienen
        # USD siempre, y el snapshot también.
        existing = await repository.get_rate_with_fallback(
            db, rate_date=target, base=base_norm, quote="USD"
        )
        if existing is not None:
            continue
        try:
            await refresh_rates(db, target_date=target, quotes=quote_list, base=base_norm)
            await db.commit()
            fetched += 1
        except (FrankfurterUnavailableError, FrankfurterInvalidResponseError):
            continue
    return fetched
