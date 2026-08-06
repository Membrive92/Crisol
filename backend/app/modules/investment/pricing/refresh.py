"""Refresh de cotizaciones on-access con TTL (PHASE-44.7, batch en 44.11.B).

Al pedir el summary, las cotizaciones más viejas que `PRICE_TTL_HOURS` se
refrescan en la misma request. No hay scheduler: local-first, sólo hacen falta
precios cuando alguien mira. Un fallo del proveedor no rompe la vista: se
conserva la última cotización y el summary la marca `quote_stale`.

**La divisa que se persiste es la del proveedor** (PHASE-44.11 D4). Antes se
guardaba `Security.currency` junto a un precio que venía de fuera, lo que
convertía una suposición en un dato: un valor de Londres catalogado como `GBP`
cuyo proveedor devuelve peniques se guardaba como libras y su valor de mercado
salía 100 veces mayor. Ahora manda el proveedor, y si no declara divisa
(Finnhub) se cae a la del catálogo — pero eso se sabe y se marca.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.investment.pricing import repository as repo
from app.modules.investment.pricing.adapters.base import (
    PriceAdapter,
    Quote,
    QuoteError,
    QuoteRequest,
)

#: Subunidades que jamás pueden llegar a la columna `currency`. Es el assert de
#: la regla dura nº 2 del plan: si una de éstas se cuela, el valor de mercado
#: sale multiplicado por 100 y nada más abajo lo detecta.
_FORBIDDEN_CURRENCIES = frozenset({"GBX", "ZAC", "ILA"})


@dataclass(frozen=True)
class RefreshTarget:
    security_id: uuid.UUID
    ticker: str
    exchange: str
    currency: str
    """Divisa del CATÁLOGO. Sólo se usa como respaldo cuando el proveedor no
    declara la suya, y para detectar discrepancias."""


@dataclass(frozen=True)
class RefreshOutcome:
    """Qué pasó en el intento de refresco."""

    refreshed: int
    errors: dict[uuid.UUID, str]
    """`security_id → motivo`, sólo de los símbolos que se intentaron AHORA.

    Es lo que permite que una posición sin cotización diga POR QUÉ ("el
    proveedor sólo cubre EE. UU.", "plaza sin equivalencia") en vez de un
    genérico "sin cotización". Funciona sin persistir el motivo porque una
    posición sin fila entra al lote en **cada** petición: si no hay precio,
    siempre hay un intento fresco que lo explique.

    La discrepancia de divisa NO viaja aquí: ésa se deriva en el summary
    comparando la fila persistida con el catálogo, porque tiene que sobrevivir
    a que la cotización esté dentro del TTL y no haya nada que refrescar.
    """


async def refresh_quotes(
    db: AsyncSession,
    adapter: PriceAdapter,
    targets: Sequence[RefreshTarget],
    *,
    ttl_hours: int,
    now: datetime,
    force: bool = False,
) -> RefreshOutcome:
    """Refresca las cotizaciones caducadas (o todas si `force`).

    Un símbolo que el proveedor no cubre **conserva su fila anterior** en vez de
    borrarla: es mejor un precio viejo marcado como viejo que ninguno.
    """
    ttl = timedelta(hours=ttl_hours)
    by_key: dict[str, RefreshTarget] = {}

    for target in targets:
        existing = await repo.get_quote(db, target.security_id)
        if not force and existing is not None and (now - existing.fetched_at) < ttl:
            continue
        by_key[str(target.security_id)] = target

    if not by_key:
        return RefreshOutcome(refreshed=0, errors={})

    results = await adapter.quotes(
        [QuoteRequest(key=key, ticker=t.ticker, exchange=t.exchange) for key, t in by_key.items()]
    )

    refreshed = 0
    errors: dict[uuid.UUID, str] = {}

    for key, target in by_key.items():
        result = results.get(key)
        if isinstance(result, QuoteError):
            errors[target.security_id] = result.reason
            continue  # se conserva lo que hubiera (stale)
        if not isinstance(result, Quote):
            # El adapter incumplió el contrato "una entrada por key". No se
            # inventa un motivo bonito: se dice que el proveedor no contestó.
            errors[target.security_id] = "el proveedor no devolvió respuesta para este valor"
            continue

        await repo.upsert_quote(
            db,
            security_id=target.security_id,
            price=result.price,
            prev_close=result.prev_close,
            currency=_resolve_currency(result, target),
            as_of=result.as_of,
            fetched_at=now,
            provider=settings.price_provider,
        )
        refreshed += 1

    return RefreshOutcome(refreshed=refreshed, errors=errors)


def _resolve_currency(quote: Quote, target: RefreshTarget) -> str:
    """Divisa a persistir: la del proveedor si la declara, si no la del catálogo.

    El assert no es defensivo por costumbre: es el único punto por el que una
    subunidad podría entrar en la columna, y su efecto (×100 en el valor de
    mercado) no lo detecta nada más abajo. Que salte en tests es el objetivo.
    """
    currency = (quote.currency or target.currency).strip().upper()
    assert currency not in _FORBIDDEN_CURRENCIES, (
        f"divisa en subunidad a punto de persistirse: {currency!r} — "
        "el adapter debe normalizarla a ISO-4217 antes de devolverla"
    )
    return currency
