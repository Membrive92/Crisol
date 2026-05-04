"""Queries a DB del módulo transactions."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, null, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.dashboard.conversion import converted_amount_expr
from app.modules.personal_finance.transactions.models import Transaction


def _scope[Q: Select[Any]](
    query: Q,
    user_id: uuid.UUID,
    *,
    category_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
) -> Q:
    """Filtros comunes (user_id obligatorio + opcionales)."""
    query = query.where(Transaction.user_id == user_id)
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
    target_currency: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Transaction, Decimal | None]], int]:
    """Lista transacciones filtradas + total count.

    Cuando se pasa `target_currency`, cada fila incluye el importe
    convertido a esa moneda con la tasa **del día de su `occurred_at`**
    (vía `converted_amount_expr`). NULL si no hay tasa disponible. En
    modo legacy (`target_currency=None`) la segunda parte de la tupla
    es siempre `None`.
    """
    count_query = select(func.count()).select_from(Transaction)
    count_query = _scope(
        count_query,
        user_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    total = (await db.execute(count_query)).scalar_one()

    if target_currency is not None:
        converted_col = converted_amount_expr(target_currency).label("converted_amount")
    else:
        converted_col = null().label("converted_amount")

    items_query = select(Transaction, converted_col)
    items_query = _scope(
        items_query,
        user_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    items_query = (
        items_query.order_by(Transaction.occurred_at.desc()).limit(limit).offset(offset)
    )

    result = await db.execute(items_query)
    items: list[tuple[Transaction, Decimal | None]] = []
    for tx, converted in result.all():
        items.append((tx, Decimal(converted) if converted is not None else None))
    return items, total


async def get_transaction_by_id(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID
) -> Transaction | None:
    """Obtiene una transacción por ID, filtrando por user_id."""
    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.id == transaction_id)
    )
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
