"""Queries a DB de cotizaciones (PHASE-44.7).

`price_quotes` es GLOBAL: una fila viva por security (UNIQUE). Sin histórico.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.investment.pricing.models import PriceQuote


async def get_quote(db: AsyncSession, security_id: uuid.UUID) -> PriceQuote | None:
    stmt = select(PriceQuote).where(PriceQuote.security_id == security_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_quotes(
    db: AsyncSession, security_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, PriceQuote]:
    if not security_ids:
        return {}
    stmt = select(PriceQuote).where(PriceQuote.security_id.in_(security_ids))
    return {q.security_id: q for q in (await db.execute(stmt)).scalars()}


async def upsert_quote(
    db: AsyncSession,
    *,
    security_id: uuid.UUID,
    price: Decimal,
    prev_close: Decimal | None,
    currency: str,
    as_of: datetime,
    fetched_at: datetime,
    provider: str,
) -> PriceQuote:
    """Inserta o actualiza la fila viva del security (UNIQUE `security_id`)."""
    existing = await get_quote(db, security_id)
    if existing is not None:
        existing.price = price
        existing.prev_close = prev_close
        existing.currency = currency
        existing.as_of = as_of
        existing.fetched_at = fetched_at
        existing.provider = provider
        await db.flush()
        return existing
    quote = PriceQuote(
        security_id=security_id,
        price=price,
        prev_close=prev_close,
        currency=currency,
        as_of=as_of,
        fetched_at=fetched_at,
        provider=provider,
    )
    db.add(quote)
    await db.flush()
    return quote
