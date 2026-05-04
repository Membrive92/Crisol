"""Queries a DB del módulo transactions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import Select, func, null, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.dashboard.conversion import converted_amount_expr
from app.modules.personal_finance.transactions.models import Transaction

# `active`  → `deleted_at IS NULL`  (default — listado normal, dashboard).
# `trashed` → `deleted_at IS NOT NULL` (endpoint /trash, restore, purge).
# `any`     → sin filtro (uso interno, p.ej. lookup para restore/purge
#             que ya saben qué transacción quieren).
DeletedScope = Literal["active", "trashed", "any"]


def _scope[Q: Select[Any]](
    query: Q,
    user_id: uuid.UUID,
    *,
    category_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    deleted: DeletedScope = "active",
) -> Q:
    """Filtros comunes (user_id obligatorio + opcionales)."""
    query = query.where(Transaction.user_id == user_id)
    if deleted == "active":
        query = query.where(Transaction.deleted_at.is_(None))
    elif deleted == "trashed":
        query = query.where(Transaction.deleted_at.is_not(None))
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
    """Lista transacciones activas filtradas + total count.

    Las soft-deleted no aparecen — para verlas usar `list_trashed_transactions`.

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


async def list_trashed_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Transaction], int]:
    """Lista transacciones en papelera del usuario, ordenadas por
    `deleted_at DESC` (las más recientemente borradas primero).

    No acepta filtros adicionales — la papelera es una vista plana de
    "qué borré recientemente". Si crece y hace falta buscar, añadir
    filtros entonces.
    """
    count_query = select(func.count()).select_from(Transaction)
    count_query = _scope(count_query, user_id, deleted="trashed")
    total = (await db.execute(count_query)).scalar_one()

    items_query = (
        _scope(select(Transaction), user_id, deleted="trashed")
        .order_by(Transaction.deleted_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(items_query)
    return list(result.scalars().all()), total


async def get_transaction_by_id(
    db: AsyncSession,
    transaction_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    deleted: DeletedScope = "active",
) -> Transaction | None:
    """Obtiene una transacción por ID, filtrando por user_id.

    Por defecto sólo devuelve activas. Para restore/purge el caller
    pide `deleted="trashed"` (sólo papelera) o `deleted="any"`
    (cualquiera, p.ej. para reads internas).
    """
    query = select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.id == transaction_id,
    )
    if deleted == "active":
        query = query.where(Transaction.deleted_at.is_(None))
    elif deleted == "trashed":
        query = query.where(Transaction.deleted_at.is_not(None))
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def create_transaction(db: AsyncSession, transaction: Transaction) -> Transaction:
    """Persiste una nueva transacción."""
    db.add(transaction)
    await db.flush()
    await db.refresh(transaction)
    return transaction


async def soft_delete_transaction(
    db: AsyncSession, transaction: Transaction
) -> Transaction:
    """Marca la transacción como borrada (mueve a papelera).

    Usa `datetime.now(UTC)` (Python-side) en lugar de `func.now()` por
    coherencia con el typing del campo (`Mapped[datetime | None]`); la
    diferencia de microsegundos vs server-clock es irrelevante para el
    uso de papelera (ordenar deleted_at desc).
    """
    transaction.deleted_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(transaction)
    return transaction


async def restore_transaction(
    db: AsyncSession, transaction: Transaction
) -> Transaction:
    """Quita la marca de borrado (saca de papelera)."""
    transaction.deleted_at = None
    await db.flush()
    await db.refresh(transaction)
    return transaction


async def purge_transaction(db: AsyncSession, transaction: Transaction) -> None:
    """Elimina la transacción de forma permanente (DELETE real)."""
    await db.delete(transaction)
    await db.flush()
