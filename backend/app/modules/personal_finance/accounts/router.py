"""Router del módulo accounts (PHASE-19.1)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.accounts.schemas import (
    AccountBalancesResponse,
    AccountCreate,
    AccountResponse,
    AccountUpdate,
)
from app.modules.personal_finance.accounts.service import (
    create_account,
    delete_account,
    get_account,
    get_balances,
    list_accounts,
    update_account,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountResponse])
async def list_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    include_archived: Annotated[bool, Query()] = False,
) -> list[AccountResponse]:
    """Lista las cuentas del usuario.

    Por defecto excluye archivadas. Pasa `?include_archived=true`
    para verlas todas (útil en pantallas de gestión).
    """
    accounts = await list_accounts(db, user.id, include_archived=include_archived)
    return [AccountResponse.model_validate(a) for a in accounts]


@router.get("/balances", response_model=AccountBalancesResponse)
async def balances_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountBalancesResponse:
    """Saldo actual de cada cuenta + agregado de patrimonio (PHASE-19.4).

    Cada cuenta devuelve `opening_balance + Σ(income − expense)` en su
    moneda nativa. Sólo cuentas activas suman a los totales. Si las
    monedas activas no son homogéneas, `mixed_currencies=true`.
    """
    return await get_balances(db, user.id)


@router.get("/{account_id}", response_model=AccountResponse)
async def get_endpoint(
    account_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountResponse:
    """Obtiene una cuenta por ID."""
    account = await get_account(db, account_id, user.id)
    return AccountResponse.model_validate(account)


@router.post("", response_model=AccountResponse, status_code=201)
async def create_endpoint(
    body: AccountCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountResponse:
    """Crea una nueva cuenta. 409 si el nombre ya existe para el usuario."""
    account = await create_account(db, user.id, body)
    await db.commit()
    return AccountResponse.model_validate(account)


@router.put("/{account_id}", response_model=AccountResponse)
async def update_endpoint(
    account_id: uuid.UUID,
    body: AccountUpdate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountResponse:
    """Actualiza una cuenta (parcial). Permite archivar via `is_archived=true`."""
    account = await update_account(db, account_id, user.id, body)
    await db.commit()
    return AccountResponse.model_validate(account)


@router.delete("/{account_id}", status_code=204, response_class=Response)
async def delete_endpoint(
    account_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Borra una cuenta sin transacciones. Si tiene histórico, 409 —
    el usuario debe archivarla en su lugar.
    """
    await delete_account(db, account_id, user.id)
    await db.commit()
    return Response(status_code=204)
