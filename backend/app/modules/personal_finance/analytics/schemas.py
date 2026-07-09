"""Schemas Pydantic del módulo analytics (PHASE-37.3 + 37.4)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

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


class CommittedItem(BaseModel):
    """Un cargo comprometido pendiente este mes (gasto fijo o cuota)."""

    name: str
    amount: Decimal
    expected_date: date
    """Día de cargo estimado (`fixed_expense.next_due` o `installment.due_date`)."""
    overdue: bool = False
    """`True` si `expected_date` ya pasó y sigue sin cargarse/pagarse."""
    kind: Literal["fixed", "installment"]


class MonthOutlookResponse(BaseModel):
    """Proyección de fin de mes + runway (PHASE-37.4).

    `committed_remaining` = gastos fijos confirmados + cuotas de deuda que
    aún se cargarán en lo que queda de mes (más los atrasados sin pagar).
    `runway_months` = colchón líquido / gasto estructural mensual medio
    (base de 37.3): cuántos meses cubre tu liquidez tu coste de vida.
    """

    reference_currency: str
    committed_remaining: Decimal
    committed_items: list[CommittedItem]
    days_remaining: int
    liquid_balance: Decimal
    """Σ saldo de cuentas líquidas (bank/savings/cash) no archivadas."""
    runway_months: float | None
    """`liquid_balance / structural_monthly_avg`; `None` si no hay base
    de gasto estructural (usuario nuevo sin histórico)."""
