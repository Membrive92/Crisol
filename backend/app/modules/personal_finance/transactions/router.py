"""Router del módulo transactions."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.transactions.models import Transaction
from app.modules.personal_finance.transactions.schemas import (
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdate,
)
from app.modules.personal_finance.transactions.service import (
    create_transaction,
    delete_transaction,
    get_transaction,
    list_transactions,
    list_trashed_transactions,
    purge_transaction,
    restore_transaction,
    update_transaction,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _build_response(
    tx: Transaction, converted: Decimal | None, target_currency: str | None
) -> TransactionResponse:
    """Construye la respuesta enriqueciendo con la conversión per-row."""
    payload = TransactionResponse.model_validate(tx)
    if target_currency is not None and converted is not None:
        payload = payload.model_copy(
            update={
                "converted_amount": converted,
                "converted_currency": target_currency.upper(),
            }
        )
    return payload


@router.get("", response_model=TransactionListResponse)
async def list_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    category_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TransactionListResponse:
    """Lista transacciones activas con filtros opcionales.

    Si se pasa `target_currency`, cada fila incluye `converted_amount`
    + `converted_currency` (PHASE-8.4) — la UI puede pintar el
    equivalente en moneda activa sin lanzar fetches por fecha.
    Las soft-deleted (PHASE-10.1) NO aparecen aquí — usar `/trash`.
    """
    items, total = await list_transactions(
        db,
        user.id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        target_currency=target_currency,
        limit=limit,
        offset=offset,
    )
    return TransactionListResponse(
        items=[_build_response(tx, conv, target_currency) for tx, conv in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/trash", response_model=TransactionListResponse)
async def list_trash_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TransactionListResponse:
    """Lista las transacciones en papelera del usuario, ordenadas por
    `deleted_at DESC`. PHASE-10.1.

    Cada fila trae `deleted_at` no-NULL para que la UI pueda pintar
    "borrada hace X días". Sin filtros adicionales — la papelera es
    una vista plana de "qué he borrado recientemente".
    """
    items, total = await list_trashed_transactions(
        db, user.id, limit=limit, offset=offset
    )
    return TransactionListResponse(
        items=[TransactionResponse.model_validate(tx) for tx in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_endpoint(
    transaction_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TransactionResponse:
    """Obtiene una transacción activa por ID."""
    transaction = await get_transaction(db, transaction_id, user.id)
    return TransactionResponse.model_validate(transaction)


@router.post("", response_model=TransactionResponse, status_code=201)
async def create_endpoint(
    body: TransactionCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TransactionResponse:
    """Crea una nueva transacción."""
    transaction = await create_transaction(db, user.id, body)
    await db.commit()
    return TransactionResponse.model_validate(transaction)


@router.put("/{transaction_id}", response_model=TransactionResponse)
async def update_endpoint(
    transaction_id: uuid.UUID,
    body: TransactionUpdate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TransactionResponse:
    """Actualiza una transacción existente."""
    transaction = await update_transaction(db, transaction_id, user.id, body)
    await db.commit()
    return TransactionResponse.model_validate(transaction)


@router.delete("/{transaction_id}", status_code=204, response_class=Response)
async def delete_endpoint(
    transaction_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Mueve la transacción a papelera (soft-delete, PHASE-10.1).

    Cambio de comportamiento respecto a pre-PHASE-10.1: ya no destruye.
    Para borrar definitivamente, usar `DELETE /transactions/{id}/purge`
    sobre una tx que ya esté en papelera.
    """
    await delete_transaction(db, transaction_id, user.id)
    await db.commit()
    return Response(status_code=204)


@router.post("/{transaction_id}/restore", response_model=TransactionResponse)
async def restore_endpoint(
    transaction_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TransactionResponse:
    """Saca una transacción de la papelera. PHASE-10.1.

    404 si la transacción no existe o no está en papelera.
    """
    transaction = await restore_transaction(db, transaction_id, user.id)
    await db.commit()
    return TransactionResponse.model_validate(transaction)


@router.delete(
    "/{transaction_id}/purge", status_code=204, response_class=Response
)
async def purge_endpoint(
    transaction_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Elimina permanente (DELETE real) una transacción que esté EN
    papelera. PHASE-10.1.

    404 si la transacción no existe o no está en papelera. Para purgar
    una activa primero hacer `DELETE /transactions/{id}` (soft) y luego
    purgar.
    """
    await purge_transaction(db, transaction_id, user.id)
    await db.commit()
    return Response(status_code=204)
