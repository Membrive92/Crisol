"""Schemas Pydantic del módulo budgets (PHASE-12.1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

BudgetStatus = Literal["ok", "warning", "over"]


class BudgetCreate(BaseModel):
    """Datos para crear un presupuesto."""

    category_id: uuid.UUID | None = None
    amount: Decimal = Field(decimal_places=2, ge=Decimal("0.01"))
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    effective_from: date
    # PHASE-16: opt-in cross-currency.
    convert_other_currencies: bool = False


class BudgetUpdate(BaseModel):
    """Datos para actualizar un presupuesto (parcial).

    `effective_from` no se puede cambiar — para cambiar la fecha de
    inicio, cerrar el actual con DELETE y crear uno nuevo. Esto
    preserva el histórico real de qué presupuesto estuvo vigente
    en qué momento.
    """

    amount: Decimal | None = Field(default=None, decimal_places=2, ge=Decimal("0.01"))
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    convert_other_currencies: bool | None = None


class BudgetResponse(BaseModel):
    """Respuesta pública de un presupuesto."""

    id: uuid.UUID
    user_id: uuid.UUID
    category_id: uuid.UUID | None
    amount: Decimal
    currency: str
    effective_from: date
    effective_to: date | None
    convert_other_currencies: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BudgetStatusItem(BaseModel):
    """Estado de un presupuesto vs gasto del mes en curso.

    `spent_this_month` se calcula sobre transacciones activas
    (excluye soft-deleted) cuya `occurred_at` cae en el mes
    calendario actual y la categoría coincide. Para budgets
    globales (`category_id IS NULL`) suma todas las categorías de
    `kind='expense'`.

    Si `budget.convert_other_currencies=True` (PHASE-16), suma
    también txs en otras monedas convertidas a `budget.currency` con
    la tasa del día de la tx; las txs sin tasa disponible se
    excluyen de la suma y se reportan en `unconvertible_count`.

    `percent_used` puede pasar de 100; el frontend lo cap en barra
    de progreso pero el dato crudo es informativo.

    Status:
    - `ok`        → percent_used < 80
    - `warning`   → 80 <= percent_used <= 100
    - `over`      → percent_used > 100
    """

    budget: BudgetResponse
    spent_this_month: Decimal
    remaining: Decimal
    percent_used: float
    status: BudgetStatus
    # PHASE-16: número de txs en otras monedas que se quedaron fuera
    # del SUM por falta de tasa. Siempre 0 cuando convert_other_currencies
    # es False (no se intenta convertir).
    unconvertible_count: int = 0


class BudgetStatusResponse(BaseModel):
    """Lista de estados de los presupuestos activos del usuario."""

    items: list[BudgetStatusItem]
    month_start: date
    month_end: date
