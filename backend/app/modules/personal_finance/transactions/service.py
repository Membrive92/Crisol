"""Lógica de negocio del módulo transactions."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.dashboard.service import ensure_rates_for_user_scope
from app.modules.personal_finance.transactions.models import Transaction
from app.modules.personal_finance.transactions.repository import (
    create_transaction as persist_transaction,
)
from app.modules.personal_finance.transactions.repository import (
    delete_transaction as remove_transaction,
)
from app.modules.personal_finance.transactions.repository import (
    get_transaction_by_id,
)
from app.modules.personal_finance.transactions.repository import (
    list_transactions as list_all,
)
from app.modules.personal_finance.transactions.schemas import TransactionCreate, TransactionUpdate


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
    """Lista transacciones del usuario con filtros.

    Cuando se pasa `target_currency`, dispara el backfill on-demand de
    tasas (mismo helper que el dashboard) antes de listar para que las
    fechas históricas queden cubiertas.
    """
    if target_currency is not None:
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target_currency,
            date_from=date_from,
            date_to=date_to,
        )
    return await list_all(
        db,
        user_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        target_currency=target_currency,
        limit=limit,
        offset=offset,
    )


async def get_transaction(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID
) -> Transaction:
    """Obtiene una transacción o lanza 404."""
    transaction = await get_transaction_by_id(db, transaction_id, user_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transacción no encontrada"
        )
    return transaction


async def create_transaction(
    db: AsyncSession, user_id: uuid.UUID, data: TransactionCreate
) -> Transaction:
    """Crea una nueva transacción."""
    transaction = Transaction(
        user_id=user_id,
        category_id=data.category_id,
        amount=data.amount,
        currency=data.currency,
        occurred_at=data.occurred_at,
        description=data.description,
        source=data.source,
    )
    return await persist_transaction(db, transaction)


async def update_transaction(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID, data: TransactionUpdate
) -> Transaction:
    """Actualiza una transacción existente."""
    transaction = await get_transaction(db, transaction_id, user_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(transaction, field, value)
    await db.flush()
    await db.refresh(transaction)
    return transaction


async def delete_transaction(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Elimina una transacción del usuario."""
    transaction = await get_transaction(db, transaction_id, user_id)
    await remove_transaction(db, transaction)
