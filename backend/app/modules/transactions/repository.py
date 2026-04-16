"""Queries a DB del módulo transactions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.transactions.models import Transaction


def _base_query(user_id: uuid.UUID) -> Select[tuple[Transaction]]:
    """Query base con filtro de user_id obligatorio."""
    return select(Transaction).where(Transaction.user_id == user_id)


def _apply_filters(
    query: Select[tuple[Transaction]],
    *,
    category_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
) -> Select[tuple[Transaction]]:
    """Aplica filtros opcionales a la query."""
    if category_id is not None:
        query = query.where(Transaction.category_id == category_id)
    if date_from is not None:
        query = query.where(Transaction.occurred_at >= date_from)
    if date_to is not None:
        query = query.where(Transaction.occurred_at <= date_to)
    if search:
        query = query.where(Transaction.description.ilike(f"%{search}%"))
    return query


async def list_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    category_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Transaction], int]:
    """Lista transacciones filtradas + total count."""
    base = _base_query(user_id)
    filtered = _apply_filters(
        base, category_id=category_id, date_from=date_from, date_to=date_to, search=search
    )

    count_result = await db.execute(select(func.count()).select_from(filtered.subquery()))
    total = count_result.scalar_one()

    result = await db.execute(
        filtered.order_by(Transaction.occurred_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def get_transaction_by_id(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID
) -> Transaction | None:
    """Obtiene una transacción por ID, filtrando por user_id."""
    result = await db.execute(_base_query(user_id).where(Transaction.id == transaction_id))
    return result.scalar_one_or_none()


async def create_transaction(db: AsyncSession, transaction: Transaction) -> Transaction:
    """Persiste una nueva transacción."""
    db.add(transaction)
    await db.flush()
    await db.refresh(transaction)
    return transaction


async def delete_transaction(db: AsyncSession, transaction: Transaction) -> None:
    """Elimina una transacción."""
    await db.delete(transaction)
    await db.flush()
