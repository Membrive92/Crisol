"""Acceso a datos del módulo receipts."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.receipts.models import Receipt


async def create_receipt(db: AsyncSession, receipt: Receipt) -> Receipt:
    db.add(receipt)
    await db.flush()
    await db.refresh(receipt)
    return receipt


async def get_receipt_by_id(
    db: AsyncSession, receipt_id: uuid.UUID, user_id: uuid.UUID
) -> Receipt | None:
    result = await db.execute(
        select(Receipt).where(Receipt.id == receipt_id, Receipt.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_receipts(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[Receipt], int]:
    items_result = await db.execute(
        select(Receipt)
        .where(Receipt.user_id == user_id)
        .order_by(Receipt.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list(items_result.scalars().all())

    count_result = await db.execute(
        select(func.count()).select_from(Receipt).where(Receipt.user_id == user_id)
    )
    total = int(count_result.scalar_one())
    return items, total
