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

    PHASE-43.1 — la ventana de recurrencia son los `RECURRENCE_WINDOW_MONTHS`
    meses naturales COMPLETOS terminados en `min(date_to, hoy)` (el mes en
    curso o cortado por el rango se excluye). `recurrence_available` y
    `window_months_with_data` hacen explícito cuándo la regla 3 no puede
    clasificar por falta de histórico — antes degradaba a las reglas 1+2 en
    silencio (bug A).
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
    window_start: date
    """Primer día del primer mes completo de la ventana de recurrencia."""
    window_end: date
    """Último día del último mes completo de la ventana de recurrencia."""
    window_months_with_data: int
    """Nº de meses de la ventana con algún gasto registrado."""
    recurrence_available: bool
    """`False` si `window_months_with_data < RECURRENCE_MIN_MONTHS`: la regla
    3 no puede clasificar y sólo actúan las reglas 1+2 (gastos fijos + deuda).
    La UI debe avisarlo en vez de mostrar una tasa estructural engañosa."""


StructureReason = Literal[
    "override_category",  # expense_nature != auto (gana a la heurística)
    "rule_1_fixed_expense",  # gasto fijo confirmado apunta a la categoría
    "rule_2_debt_role",  # rol DEBT_PAYMENT / DEBT_INTEREST
    "rule_3_recurrence",  # recurre con importe estable
    "not_recurring",  # evaluada por la regla 3 y no cumple
    "insufficient_history",  # < RECURRENCE_MIN_MONTHS meses activos en la ventana
]


class CategoryStructureExplain(BaseModel):
    """PHASE-43.2 — por qué una categoría es Fija o Variable (bug D).

    Explica la clasificación a nivel de CATEGORÍA (la que pinta el desglose).
    `tx_overrides` indica cuántas transacciones de la categoría llevan su
    propio override — que gana sobre esta clasificación caso a caso."""

    category_id: uuid.UUID
    category_name: str
    is_structural: bool
    reason: StructureReason
    months_active: int
    """Meses de la ventana de recurrencia con gasto en la categoría."""
    months_in_band: int
    """De los activos, cuántos dentro de ±banda de la mediana (regla 3)."""
    median_monthly: Decimal | None
    """Mediana de los totales mensuales activos; `None` si no hay actividad."""
    tx_overrides: int
    """Nº de tx de la categoría en el rango con `is_exceptional` fijado."""


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
