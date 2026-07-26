"""Refresh de cotizaciones on-access con TTL (PHASE-44.7, ARCHITECTURE §8.1).

Al pedir el summary, las cotizaciones más viejas que `PRICE_TTL_HOURS` se
refrescan en la misma request, SERIALIZADAS (respetan el rate limit de Finnhub;
no hay scheduler: local-first, solo hacen falta precios cuando alguien mira). Un
fallo del proveedor no rompe la vista: se conserva la última cotización y el
summary la marca `quote_stale`.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.investment.pricing import repository as repo
from app.modules.investment.pricing.adapters.base import PriceAdapter


@dataclass(frozen=True)
class RefreshTarget:
    security_id: uuid.UUID
    ticker: str
    currency: str


async def refresh_quotes(
    db: AsyncSession,
    adapter: PriceAdapter,
    targets: Sequence[RefreshTarget],
    *,
    ttl_hours: int,
    now: datetime,
    force: bool = False,
) -> int:
    """Refresca las cotizaciones caducadas (o todas si `force`). Devuelve cuántas
    se refrescaron. Serializado a propósito."""
    ttl = timedelta(hours=ttl_hours)
    refreshed = 0
    for target in targets:
        existing = await repo.get_quote(db, target.security_id)
        if not force and existing is not None and (now - existing.fetched_at) < ttl:
            continue
        quote = await adapter.quote(target.ticker)
        if quote is None:
            continue  # sin cobertura/credencial → se conserva lo que hubiera (stale)
        await repo.upsert_quote(
            db,
            security_id=target.security_id,
            price=quote.price,
            prev_close=quote.prev_close,
            currency=target.currency,
            as_of=quote.as_of,
            fetched_at=now,
            provider=settings.price_provider,
        )
        refreshed += 1
    return refreshed
