"""Schemas Pydantic del módulo analytics (PHASE-37.3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TxRef(BaseModel):
    """Referencia ligera a una transacción, para listas del análisis."""

    id: uuid.UUID
    description: str | None
    amount: Decimal
    converted_amount: Decimal | None = None
    currency: str
    occurred_at: datetime
    category_id: uuid.UUID | None
    category_name: str | None


class CategoryAmount(BaseModel):
    """Total agregado por categoría (con color/icon para pintar chips)."""

    category_id: uuid.UUID | None
    category_name: str | None
    color: str | None
    icon: str | None
    total: Decimal


class ExpenseStructureResponse(BaseModel):
    """Gasto estructural vs puntual + tasa de ahorro dual (PHASE-37.3).

    `structural_monthly_avg` es la media mensual del gasto estructural en
    la ventana de recurrencia (no del rango pedido) — base estable para el
    runway de 37.4, independiente del período que el usuario esté viendo.
    """

    reference_currency: str
    income_total: Decimal
    structural_total: Decimal
    exceptional_total: Decimal
    structural_monthly_avg: Decimal
    savings_rate_gross: float | None
    savings_rate_structural: float | None
    top_exceptional: list[TxRef]
    exceptional_by_category: list[CategoryAmount]
