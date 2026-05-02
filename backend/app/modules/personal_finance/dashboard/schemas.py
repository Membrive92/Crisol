"""Schemas Pydantic del módulo dashboard.

Sólo respuestas — dashboard es read-only. Los importes viajan como `Decimal`
para preservar precisión (serializados a string por Pydantic).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class SummaryResponse(BaseModel):
    """Balance global en el rango y moneda pedidos.

    Cuando el caller pasa `date_from` y `date_to`, se calcula también el
    rango previo de igual longitud (`previous_period_*`) para que el
    frontend pinte deltas vs periodo anterior. Si no hay rango, los
    `previous_*` quedan en `None`.
    """

    income: Decimal
    expenses: Decimal
    balance: Decimal
    transaction_count: int
    currency: str
    previous_period_income: Decimal | None = None
    previous_period_expenses: Decimal | None = None
    previous_period_balance: Decimal | None = None


class CategoryBreakdownItem(BaseModel):
    """Total agregado por categoría. `category_id=None` → bucket "Sin categoría"."""

    category_id: uuid.UUID | None
    category_name: str
    category_kind: str | None
    total: Decimal
    count: int


class MonthlyBucket(BaseModel):
    """Totales de un mes concreto. `month` con formato `YYYY-MM`."""

    month: str
    income: Decimal
    expenses: Decimal
    balance: Decimal


class TopExpenseItem(BaseModel):
    """Gasto individual dentro del ranking de mayores gastos."""

    transaction_id: uuid.UUID
    description: str | None
    amount: Decimal
    occurred_at: datetime
    category_id: uuid.UUID | None
    category_name: str | None
