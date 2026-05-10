"""Lógica de negocio del módulo accounts (PHASE-19.1, PHASE-19.4)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.models import (
    Account,
    AccountNature,
)
from app.modules.personal_finance.accounts.repository import (
    count_transactions_for_account,
    create_account as persist_account,
    delete_account as remove_account,
    get_account_by_id,
    get_account_by_name,
    get_balances_for_user,
    list_accounts as list_all,
)
from app.modules.personal_finance.accounts.schemas import (
    ASSET_ACCOUNT_TYPES,
    AccountBalance,
    AccountBalancesResponse,
    AccountCreate,
    AccountUpdate,
)

DEFAULT_REFERENCE_CURRENCY = "EUR"


async def list_accounts(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    include_archived: bool = False,
) -> list[Account]:
    """Lista las cuentas del usuario."""
    return await list_all(db, user_id, include_archived=include_archived)


async def get_account(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID
) -> Account:
    """Obtiene una cuenta o lanza 404."""
    account = await get_account_by_id(db, account_id, user_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cuenta no encontrada"
        )
    return account


async def ensure_account_exists(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID
) -> Account:
    """Igual que `get_account` — alias semántico para callers (transactions,
    imports) que sólo quieren validar pertenencia antes de asociar.
    """
    return await get_account(db, account_id, user_id)


async def create_account(
    db: AsyncSession, user_id: uuid.UUID, data: AccountCreate
) -> Account:
    """Crea una nueva cuenta para el usuario.

    Validaciones:
    - El nombre no puede repetirse (case-insensitive) entre cuentas
      del mismo usuario.
    - En PHASE-19.1 sólo se permiten tipos `asset` (los `liability`
      llegarán en PHASE-20).
    """
    if data.type not in ASSET_ACCOUNT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de cuenta no soportado todavía.",
        )
    duplicate = await get_account_by_name(db, user_id, name=data.name)
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya tienes una cuenta con ese nombre.",
        )
    account = Account(
        user_id=user_id,
        name=data.name,
        type=data.type,
        nature=AccountNature.ASSET,
        currency=data.currency.upper(),
        color=data.color,
        icon=data.icon,
        opening_balance=data.opening_balance,
        opening_balance_date=data.opening_balance_date,
        display_order=data.display_order,
    )
    return await persist_account(db, account)


async def update_account(
    db: AsyncSession,
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    data: AccountUpdate,
) -> Account:
    """Actualiza campos de la cuenta. `nature` no se cambia — viene
    determinada por `type` y se sincroniza al inicio (en PHASE-19.1
    todas son `asset`).
    """
    account = await get_account(db, account_id, user_id)
    payload = data.model_dump(exclude_unset=True)
    if "type" in payload and payload["type"] is not None:
        new_type = payload["type"]
        if new_type not in ASSET_ACCOUNT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tipo de cuenta no soportado todavía.",
            )
    if "name" in payload and payload["name"] is not None:
        duplicate = await get_account_by_name(db, user_id, name=payload["name"])
        if duplicate is not None and duplicate.id != account.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya tienes una cuenta con ese nombre.",
            )
    if "currency" in payload and payload["currency"] is not None:
        payload["currency"] = payload["currency"].upper()
    for field, value in payload.items():
        setattr(account, field, value)
    await db.flush()
    await db.refresh(account)
    return account


async def delete_account(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Borra una cuenta sin transacciones; si tiene, fuerza al caller
    a archivarla en su lugar.

    `ON DELETE CASCADE` en `transactions.account_id` borraría también
    el histórico de la cuenta — no queremos que el usuario lo haga
    accidentalmente. La política aquí es: archivar si hay datos,
    DELETE real sólo si está completamente vacía.
    """
    account = await get_account(db, account_id, user_id)
    tx_count = await count_transactions_for_account(db, account_id, user_id)
    if tx_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"La cuenta tiene {tx_count} transacciones. "
                "Archívala en lugar de borrarla para conservar el histórico."
            ),
        )
    await remove_account(db, account)


async def get_balances(
    db: AsyncSession, user_id: uuid.UUID
) -> AccountBalancesResponse:
    """Saldo por cuenta + agregados de patrimonio (PHASE-19.4).

    Sólo cuentas no archivadas entran en los totales agregados, pero
    `items` incluye también las archivadas (display sólo). Si las
    monedas activas no son homogéneas, `mixed_currencies=True` y los
    totales son suma cruda — la UI debe avisarlo.
    """
    accounts = await list_all(db, user_id, include_archived=True)
    movements = await get_balances_for_user(db, user_id)

    items: list[AccountBalance] = []
    active_currencies: set[str] = set()
    total_assets = Decimal("0")
    total_liabilities = Decimal("0")

    for account in accounts:
        movements_balance = movements.get(account.id, Decimal("0"))
        current_balance = account.opening_balance + movements_balance
        items.append(
            AccountBalance(
                account_id=account.id,
                name=account.name,
                type=account.type,
                nature=account.nature,
                currency=account.currency,
                color=account.color,
                icon=account.icon,
                opening_balance=account.opening_balance,
                movements_balance=movements_balance,
                current_balance=current_balance,
            )
        )
        if account.is_archived:
            continue
        active_currencies.add(account.currency)
        if account.nature == AccountNature.LIABILITY:
            total_liabilities += current_balance
        else:
            total_assets += current_balance

    mixed_currencies = len(active_currencies) > 1
    if active_currencies:
        # Determinista: el primero por display_order/name de la lista
        # es la primera cuenta activa.
        for account in accounts:
            if not account.is_archived:
                reference_currency = account.currency
                break
        else:
            reference_currency = DEFAULT_REFERENCE_CURRENCY
    else:
        reference_currency = DEFAULT_REFERENCE_CURRENCY

    return AccountBalancesResponse(
        items=items,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        net_worth=total_assets - total_liabilities,
        mixed_currencies=mixed_currencies,
        reference_currency=reference_currency,
    )
