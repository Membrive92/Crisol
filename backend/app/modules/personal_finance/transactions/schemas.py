"""Schemas Pydantic del módulo transactions."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.personal_finance.transactions.models import TransactionSource


class BudgetAlertSchema(BaseModel):
    """Alerta de presupuesto en estado warning/over (PHASE-14.5).

    Devuelta en `TransactionResponse.budget_alert` cuando una nueva
    tx empuja la categoría afectada al límite. `None` si no hay
    budget aplicable o si está en `ok`.
    """

    budget_id: uuid.UUID
    category_id: uuid.UUID | None
    status: Literal["warning", "over"]
    percent_used: float
    spent_this_month: Decimal
    amount: Decimal
    currency: str
    next_due_label: str = Field(
        description="Texto legible para el toast: 'Comida está al 95%' o similar."
    )


class TransactionCreate(BaseModel):
    """Datos para crear una transacción."""

    account_id: uuid.UUID
    category_id: uuid.UUID | None = None
    amount: Decimal = Field(decimal_places=2, ge=Decimal("0.01"))
    currency: str = Field(default="EUR", max_length=3)
    occurred_at: datetime
    description: str | None = Field(default=None, max_length=500)
    source: TransactionSource = TransactionSource.MANUAL


class TransactionUpdate(BaseModel):
    """Datos para actualizar una transacción (parcial)."""

    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    amount: Decimal | None = Field(default=None, decimal_places=2, ge=Decimal("0.01"))
    currency: str | None = Field(default=None, max_length=3)
    occurred_at: datetime | None = None
    description: str | None = None


class TransactionResponse(BaseModel):
    """Respuesta pública de una transacción.

    `converted_amount` y `converted_currency` se rellenan sólo cuando
    el caller pasa `?target_currency=` al endpoint de listado: el
    backend convierte cada fila con la tasa del día de su `occurred_at`
    y la UI puede pintar el equivalente sin lanzar un fetch por fecha.
    En modo legacy o lecturas individuales, ambos son `None`.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    category_id: uuid.UUID | None
    transfer_pair_id: uuid.UUID | None = None
    amount: Decimal
    currency: str
    occurred_at: datetime
    description: str | None
    source: TransactionSource
    receipt_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    # NULL en activas. Timestamp en papelera (PHASE-10.1) — el endpoint
    # `/transactions/trash` rellena este campo; el listado normal lo
    # devuelve siempre None porque excluye soft-deleted.
    deleted_at: datetime | None = None
    converted_amount: Decimal | None = None
    converted_currency: str | None = None
    # PHASE-14.5: sólo viene en la respuesta del POST cuando la tx
    # creada empuja la categoría a warning/over. None en cualquier
    # otro endpoint (list, get, put).
    budget_alert: BudgetAlertSchema | None = None

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    """Respuesta paginada de transacciones."""

    items: list[TransactionResponse]
    total: int
    limit: int
    offset: int
