"""Schemas Pydantic del módulo accounts (PHASE-19.1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.modules.personal_finance.accounts.models import AccountNature, AccountType

# Sólo los tipos `asset` se exponen al usuario en PHASE-19.1. Los
# `liability` se gestionarán cuando llegue PHASE-20 (módulo deuda).
ASSET_ACCOUNT_TYPES: frozenset[AccountType] = frozenset(
    {
        AccountType.BANK,
        AccountType.SAVINGS,
        AccountType.BROKERAGE,
        AccountType.CRYPTO,
        AccountType.CASH,
    }
)


class AccountCreate(BaseModel):
    """Datos para crear una cuenta."""

    name: str = Field(min_length=1, max_length=100)
    type: AccountType
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    color: str | None = Field(default=None, max_length=7)
    icon: str | None = Field(default=None, max_length=50)
    opening_balance: Decimal = Field(default=Decimal("0"), decimal_places=2)
    opening_balance_date: date | None = None
    display_order: int = Field(default=0, ge=0)


class AccountUpdate(BaseModel):
    """Datos para actualizar una cuenta (parcial)."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    type: AccountType | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    color: str | None = Field(default=None, max_length=7)
    icon: str | None = Field(default=None, max_length=50)
    opening_balance: Decimal | None = Field(default=None, decimal_places=2)
    opening_balance_date: date | None = None
    display_order: int | None = Field(default=None, ge=0)
    is_archived: bool | None = None


class AccountResponse(BaseModel):
    """Respuesta pública de una cuenta."""

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    type: AccountType
    nature: AccountNature
    currency: str
    color: str | None
    icon: str | None
    opening_balance: Decimal
    opening_balance_date: date | None
    display_order: int
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccountBalance(BaseModel):
    """Saldo calculado de una cuenta (PHASE-19.4)."""

    account_id: uuid.UUID
    name: str
    type: AccountType
    nature: AccountNature
    currency: str
    color: str | None
    icon: str | None
    opening_balance: Decimal
    movements_balance: Decimal
    """Suma neta de movimientos en la moneda nativa de la cuenta
    (income suma, expense resta). Excluye papelera y txs en otra
    moneda; las transferencias internas SÍ cuentan al saldo de su
    cuenta."""
    current_balance: Decimal
    """`opening_balance + movements_balance`."""


class AccountBalancesResponse(BaseModel):
    """Snapshot de patrimonio del usuario por cuenta (PHASE-19.4).

    `total_assets` y `total_liabilities` agregan los saldos por
    `nature`. `net_worth = total_assets − total_liabilities`. En
    PHASE-19.4 sólo hay cuentas `asset` (los `liability` llegan en
    PHASE-20), así que `total_liabilities = 0` y
    `net_worth = total_assets`.

    `mixed_currencies` es `True` si las cuentas activas no comparten
    moneda; en ese caso los totales son suma cruda y la UI debe
    advertir. Una próxima fase puede convertir a una divisa de
    referencia.
    """

    items: list[AccountBalance]
    total_assets: Decimal
    total_liabilities: Decimal
    net_worth: Decimal
    mixed_currencies: bool
    reference_currency: str
