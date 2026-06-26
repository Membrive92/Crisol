"""Lógica de negocio del módulo transactions."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.service import ensure_account_exists
from app.modules.personal_finance.categories.repository import get_category_by_id
from app.modules.personal_finance.dashboard.service import ensure_rates_for_user_scope
from app.modules.personal_finance.transactions.models import Transaction
from app.modules.personal_finance.transactions.repository import (
    bulk_purge_trashed as bulk_purge_trashed_in_db,
)
from app.modules.personal_finance.transactions.repository import (
    bulk_reassign_account as bulk_reassign_in_db,
)
from app.modules.personal_finance.transactions.repository import (
    bulk_restore_trashed as bulk_restore_trashed_in_db,
)
from app.modules.personal_finance.transactions.repository import (
    bulk_soft_delete_transactions as bulk_soft_delete_in_db,
)
from app.modules.personal_finance.transactions.repository import (
    count_reassignable_skipped_by_currency as count_reassign_skipped_in_db,
)
from app.modules.personal_finance.transactions.repository import (
    create_transaction as persist_transaction,
)
from app.modules.personal_finance.transactions.repository import (
    get_transaction_by_id,
)
from app.modules.personal_finance.transactions.repository import (
    get_uncategorized_summary as repo_uncategorized_summary,
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
    uncategorized: bool = False,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    target_currency: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Transaction, Decimal | None, bool]], int]:
    """Lista transacciones del usuario con filtros (sólo activas).

    Cuando se pasa `target_currency`, dispara el backfill on-demand de
    tasas (mismo helper que el dashboard) antes de listar para que las
    fechas históricas queden cubiertas.

    `uncategorized=True` filtra las tx sin categoría (atajo del banner
    "Ver y categorizar").
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
        uncategorized=uncategorized,
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


async def _ensure_category_owned(
    db: AsyncSession, user_id: uuid.UUID, category_id: uuid.UUID
) -> None:
    """Valida que `category_id` pertenece a `user_id` o lanza 400.

    AUDIT: create/update eran el ÚNICO punto del backend que asignaba
    `category_id` sin comprobar pertenencia (rules, mappings, receipts
    sí la hacen). Sin esta validación un usuario podía referenciar una
    categoría de otro usuario, filtrando sus metadatos (nombre, color,
    kind, is_transfer) en breakdowns/respuestas y, al heredar el `kind`
    e `is_transfer` ajenos, corromper el cálculo de su propio saldo.
    Se reutiliza el mismo mensaje/código (400) que
    `category_rules._ensure_category_owned` y `receipts.confirm` para
    coherencia de la API.
    """
    cat = await get_category_by_id(db, category_id, user_id)
    if cat is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="category_id no pertenece al usuario",
        )


async def create_transaction(
    db: AsyncSession, user_id: uuid.UUID, data: TransactionCreate
) -> Transaction:
    """Crea una nueva transacción.

    PHASE-19.1: el `account_id` es obligatorio y debe pertenecer al
    mismo usuario (lo valida `ensure_account_exists` lanzando 404 si
    no es el dueño — no exponemos diferencia entre "no existe" y
    "es de otro usuario").

    AUDIT: si se pasa `category_id`, se valida que sea del usuario antes
    de asociarla (cierre de fuga multi-tenant — ver `_ensure_category_owned`).
    """
    await ensure_account_exists(db, data.account_id, user_id)
    if data.category_id is not None:
        await _ensure_category_owned(db, user_id, data.category_id)
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

    AUDIT: idem para `category_id` — si llega en el payload y no es NULL,
    se valida pertenencia antes del setattr para no reasignar la tx a
    una categoría ajena (mismo patrón que `account_id` y que
    `category_rules.update_rule`).
    """
    transaction = await get_transaction(db, transaction_id, user_id)
    payload = data.model_dump(exclude_unset=True)
    # P8 (transfers-ux) — proteger el invariante del par. Un par de
    # transferencia exige mismo amount+currency y cuentas distintas
    # (transfers.service.link_manually). Editar el importe/moneda/cuenta de
    # UNA sola pata dejaría el par descuadrado en silencio (balance roto).
    # Lo rechazamos con un mensaje que guía a deshacer el enlace primero;
    # cambiar descripción, fecha o categoría sí se permite (no rompe el par).
    if transaction.transfer_pair_id is not None:
        breaks_pair = (
            (
                "amount" in payload
                and payload["amount"] is not None
                and payload["amount"] != transaction.amount
            )
            or (
                "currency" in payload
                and payload["currency"] is not None
                and payload["currency"] != transaction.currency
            )
            or (
                "account_id" in payload
                and payload["account_id"] is not None
                and payload["account_id"] != transaction.account_id
            )
        )
        if breaks_pair:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Esta transacción es parte de una transferencia. Deshaz el "
                    "enlace (en el detalle o en Transferencias) antes de cambiar "
                    "el importe, la moneda o la cuenta."
                ),
            )
    if "account_id" in payload and payload["account_id"] is not None:
        await ensure_account_exists(db, payload["account_id"], user_id)
    if "category_id" in payload and payload["category_id"] is not None:
        await _ensure_category_owned(db, user_id, payload["category_id"])
    for field, value in payload.items():
        setattr(transaction, field, value)
    await db.flush()
    await db.refresh(transaction)
    return transaction


async def uncategorized_summary(db: AsyncSession, user_id: uuid.UUID) -> tuple[int, Decimal, str]:
    """Conteo + importe + moneda mayoritaria de tx activas sin categoría
    (AUDIT-2026-05: lógica movida del router al repository)."""
    return await repo_uncategorized_summary(db, user_id)


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


async def bulk_reassign_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    target_account_id: uuid.UUID,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
) -> tuple[int, int]:
    """PHASE-32 — Mueve en bloque las tx activas que matcheen los filtros
    a `target_account_id` (p. ej. consolidar el mes en tu cuenta
    principal). Valida que la cuenta destino es del usuario; excluye
    transferencias internas.

    HIGH#3: sólo mueve las tx cuya divisa coincide con la de la cuenta
    destino — el saldo por cuenta sólo cuenta `currency == account.currency`,
    así que mover otras las sacaría del saldo (pérdida silenciosa). Devuelve
    `(movidas, omitidas_por_divisa)` para que la UI informe de las omitidas.
    """
    target = await ensure_account_exists(db, target_account_id, user_id)
    skipped = await count_reassign_skipped_in_db(
        db,
        user_id,
        target_account_id=target_account_id,
        target_currency=target.currency,
        account_id=account_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    reassigned = await bulk_reassign_in_db(
        db,
        user_id,
        target_account_id=target_account_id,
        target_currency=target.currency,
        account_id=account_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    return reassigned, skipped


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
