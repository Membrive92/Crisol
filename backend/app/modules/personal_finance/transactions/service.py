"""Lógica de negocio del módulo transactions."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.service import ensure_account_exists
from app.modules.personal_finance.dashboard.service import ensure_rates_for_user_scope
from app.modules.personal_finance.transactions.models import Transaction
from app.modules.personal_finance.transactions.repository import (
    bulk_purge_trashed as bulk_purge_trashed_in_db,
)
from app.modules.personal_finance.transactions.repository import (
    bulk_restore_trashed as bulk_restore_trashed_in_db,
)
from app.modules.personal_finance.transactions.repository import (
    bulk_soft_delete_transactions as bulk_soft_delete_in_db,
)
from app.modules.personal_finance.transactions.repository import (
    create_transaction as persist_transaction,
)
from app.modules.personal_finance.transactions.repository import (
    get_transaction_by_id,
)
from app.modules.personal_finance.transactions.repository import (
    list_transactions as list_all,
)
from app.modules.personal_finance.transactions.repository import (
    list_trashed_transactions as list_trashed_in_db,
)
from app.modules.personal_finance.transactions.repository import (
    purge_transaction as purge_in_db,
)
from app.modules.personal_finance.transactions.repository import (
    restore_transaction as restore_in_db,
)
from app.modules.personal_finance.transactions.repository import (
    soft_delete_transaction as soft_delete_in_db,
)
from app.modules.personal_finance.transactions.schemas import TransactionCreate, TransactionUpdate


async def list_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    target_currency: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Transaction, Decimal | None]], int]:
    """Lista transacciones del usuario con filtros (sólo activas).

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
        account_id=account_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        target_currency=target_currency,
        limit=limit,
        offset=offset,
    )


async def list_trashed_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Transaction], int]:
    """Lista transacciones del usuario que están en papelera."""
    return await list_trashed_in_db(db, user_id, limit=limit, offset=offset)


async def list_available_periods(
    db: AsyncSession, user_id: uuid.UUID
) -> list[tuple[int, list[int]]]:
    """Devuelve los `(año, [meses])` con transacciones activas del
    usuario (excluye papelera). Años ordenados descendente; meses
    ordenados ascendente (1-12).

    Alimenta el selector temporal de la UI para que sólo se muestren
    los periodos con datos reales — el usuario no puede caer en un
    mes vacío por error. Lista vacía si el usuario aún no tiene nada.
    """
    query = (
        select(
            func.extract("year", Transaction.occurred_at).label("year"),
            func.extract("month", Transaction.occurred_at).label("month"),
        )
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .distinct()
    )
    rows = (await db.execute(query)).all()
    months_by_year: dict[int, set[int]] = {}
    for year, month in rows:
        if year is None or month is None:
            continue
        months_by_year.setdefault(int(year), set()).add(int(month))
    return [(year, sorted(months_by_year[year])) for year in sorted(months_by_year, reverse=True)]


async def get_transaction(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID
) -> Transaction:
    """Obtiene una transacción activa o lanza 404."""
    transaction = await get_transaction_by_id(db, transaction_id, user_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transacción no encontrada"
        )
    return transaction


async def get_trashed_transaction(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID
) -> Transaction:
    """Obtiene una transacción que esté EN PAPELERA o lanza 404.

    Usado por restore/purge — si el caller pide restaurar una tx que ya
    está activa (o no existe), 404 en lugar de no-op silencioso.
    """
    transaction = await get_transaction_by_id(db, transaction_id, user_id, deleted="trashed")
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transacción no encontrada en papelera",
        )
    return transaction


async def create_transaction(
    db: AsyncSession, user_id: uuid.UUID, data: TransactionCreate
) -> Transaction:
    """Crea una nueva transacción.

    PHASE-19.1: el `account_id` es obligatorio y debe pertenecer al
    mismo usuario (lo valida `ensure_account_exists` lanzando 404 si
    no es el dueño — no exponemos diferencia entre "no existe" y
    "es de otro usuario").
    """
    await ensure_account_exists(db, data.account_id, user_id)
    transaction = Transaction(
        user_id=user_id,
        account_id=data.account_id,
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
    """Actualiza una transacción existente (sólo activas).

    Si se incluye `account_id` en el payload, valida que la nueva
    cuenta pertenece al usuario antes de reasignar.
    """
    transaction = await get_transaction(db, transaction_id, user_id)
    payload = data.model_dump(exclude_unset=True)
    if "account_id" in payload and payload["account_id"] is not None:
        await ensure_account_exists(db, payload["account_id"], user_id)
    for field, value in payload.items():
        setattr(transaction, field, value)
    await db.flush()
    await db.refresh(transaction)
    return transaction


async def delete_transaction(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID
) -> Transaction:
    """Soft-delete: mueve la transacción a papelera (PHASE-10.1).

    Cambio de comportamiento respecto a pre-PHASE-10.1, que hacía
    DELETE real. La fila sigue existiendo con `deleted_at` no-NULL y
    deja de aparecer en list/dashboard. Recuperar via `restore`.
    """
    transaction = await get_transaction(db, transaction_id, user_id)
    return await soft_delete_in_db(db, transaction)


async def bulk_delete_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    category_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
) -> int:
    """Mueve a papelera todas las transacciones del usuario que
    matcheen los filtros. Devuelve cuántas se afectaron.

    Si no se pasa ningún filtro, afecta a todas las transacciones
    activas del usuario.
    """
    return await bulk_soft_delete_in_db(
        db,
        user_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )


async def restore_transaction(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID
) -> Transaction:
    """Saca una transacción de la papelera (vuelve a estar activa)."""
    transaction = await get_trashed_transaction(db, transaction_id, user_id)
    return await restore_in_db(db, transaction)


async def purge_transaction(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Elimina permanente (DELETE real) una transacción que ya esté
    en papelera. No se puede purgar una transacción activa — primero
    soft-delete, luego purge.
    """
    transaction = await get_trashed_transaction(db, transaction_id, user_id)
    await purge_in_db(db, transaction)


async def bulk_restore_trashed_transactions(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Restaura TODAS las transacciones que el usuario tiene en papelera.

    Devuelve cuántas se restauraron (0 si la papelera está vacía).
    """
    return await bulk_restore_trashed_in_db(db, user_id)


async def bulk_purge_trashed_transactions(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Elimina permanente TODAS las transacciones que el usuario tiene
    en papelera. Operación IRREVERSIBLE.

    Devuelve cuántas se eliminaron (0 si la papelera está vacía).
    """
    return await bulk_purge_trashed_in_db(db, user_id)
