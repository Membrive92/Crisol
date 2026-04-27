"""Router del módulo transactions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
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
    update_transaction,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=TransactionListResponse)
async def list_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    category_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TransactionListResponse:
    """Lista transacciones con filtros opcionales."""
    items, total = await list_transactions(
        db,
        user.id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        limit=limit,
        offset=offset,
    )
    return TransactionListResponse(
        items=[TransactionResponse.model_validate(t) for t in items],
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
    """Obtiene una transacción por ID."""
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
    """Elimina una transacción."""
    await delete_transaction(db, transaction_id, user.id)
    await db.commit()
    return Response(status_code=204)
