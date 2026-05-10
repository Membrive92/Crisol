"""Schemas Pydantic del módulo fixed_expenses (PHASE-13.1, renombrado
en PHASE-17.1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.modules.personal_finance.fixed_expenses.models import FixedExpenseStatus


class FixedExpenseResponse(BaseModel):
    """Respuesta pública de un gasto fijo."""

    id: uuid.UUID
    user_id: uuid.UUID
    merchant: str
    raw_description: str
    amount: Decimal
    currency: str
    cadence_days: int
    next_due: date
    status: FixedExpenseStatus
    category_id: uuid.UUID | None
    account_id: uuid.UUID | None
    first_seen_at: date
    last_seen_at: date
    occurrence_count: int
    confidence: float
    auto_post: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FixedExpenseUpdate(BaseModel):
    """Campos editables de un gasto fijo (PHASE-17.2 + PHASE-19.1).

    `auto_post` y `account_id` (la cuenta desde la que se cobra). El
    resto se deriva del detector o se cambia vía endpoints específicos
    (confirm/pause/cancel/...).
    """

    auto_post: bool | None = None
    account_id: uuid.UUID | None = None


class ScanResponse(BaseModel):
    """Resultado de un scan manual.

    `created` y `updated` separan candidatos nuevos (que el usuario
    debe revisar) vs gastos fijos existentes con datos refrescados
    (next_due, occurrence_count, last_seen_at).
    """

    created: int
    updated: int
    total_active_after: int


class AutopostResponse(BaseModel):
    """Resultado del cron de autoposteo (PHASE-17.2).

    `created` = transacciones `source=expected` creadas. `advanced`
    = nº de gastos fijos cuyo `next_due` se actualizó (uno por
    transacción creada). Para volúmenes esperados (< 50 fixed
    expenses por user) son iguales — los separamos por si en el
    futuro autopost falla parcialmente.
    """

    created: int
    advanced: int
