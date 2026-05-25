"""Schemas Pydantic de Capa 1 del módulo deuda (PHASE-30.2)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

DebtTimeRange = Literal["ytd", "12m", "month"]
EffortStatus = Literal["healthy", "caution", "stressed", "unknown"]
DebtTypeBucket = Literal["mortgage", "loan", "credit_card", "other"]


class DebtTypeBreakdown(BaseModel):
    """Pagos a deuda agregados por tipo aproximado (PHASE-30.2).

    El "tipo" se infiere del role + nombre de la categoría: las
    categorías DEBT_PAYMENT que contienen "hipoteca" caen en
    `mortgage`, "tarjeta" → `credit_card`, "préstamo" → `loan`, el
    resto → `other`. No es 100% perfecto pero refleja la composición
    semántica que el usuario reconoce en el donut.
    """

    type: DebtTypeBucket
    amount: Decimal
    percent: float
    """`amount / total_payments` en [0, 1]. 0 cuando no hay pagos."""


class MonthlyDebtPoint(BaseModel):
    """Un punto de la serie mensual: pagos, intereses, capital."""

    month: str
    """`YYYY-MM`."""
    payments: Decimal
    """Σ flujo de categorías DEBT_PAYMENT + DEBT_INTEREST ese mes."""
    interests: Decimal
    """Σ flujo de categorías DEBT_INTEREST ese mes."""
    capital: Decimal
    """`payments - interests`."""


class RecurringQuotaRef(BaseModel):
    """Referencia cross-link a un `fixed_expense` con categoría de deuda."""

    fixed_expense_id: uuid.UUID
    merchant: str
    amount: Decimal
    """Cuota mensual estimada (positiva)."""
    currency: str
    category_id: uuid.UUID | None
    category_name: str | None


class DebtCategorySummary(BaseModel):
    """KPIs de Capa 1 — flujo derivado de categorías marcadas como
    deuda (PHASE-30.2).

    Independiente de liability accounts. Un usuario que aún no
    declaró su hipoteca como `liability` pero sí categoriza los pagos
    como "Préstamos e hipotecas" obtiene ya los KPIs principales.
    """

    reference_currency: str
    range: DebtTimeRange
    range_start: date
    range_end: date

    total_payments: Decimal
    """Σ flujo de categorías con `role IN (DEBT_PAYMENT, DEBT_INTEREST)`
    durante el rango."""
    interests_and_fees: Decimal
    """Σ flujo de DEBT_INTEREST sólo."""
    capital_amortized: Decimal
    """`total_payments − interests_and_fees`."""

    by_type: list[DebtTypeBreakdown]
    """Composición agregada por tipo aproximado para el donut."""

    monthly_series: list[MonthlyDebtPoint]
    """12 puntos cuando range=12m; meses sin actividad en 0. Para `ytd`
    es desde enero al mes actual; para `month` el único punto del mes
    en curso (longitud 1)."""

    monthly_income_avg: Decimal
    """Igual que en `/accounts/debt-health` — promedio últimos 6 meses
    cerrados de la categoría INCOME, excluyendo transferencias internas."""
    effort_ratio_strict: float | None
    """`monthly_debt_payment / monthly_income_avg`. Sólo pagos de deuda
    en el numerador. `null` cuando no hay ingresos."""
    effort_ratio_strict_status: EffortStatus
    effort_ratio_extended: float | None
    """Como `strict` pero sumando las cuotas de `fixed_expenses` con
    `status=confirmed`. Si un fixed_expense ya está vinculado a una
    categoría de deuda no se cuenta dos veces."""
    effort_ratio_extended_status: EffortStatus

    recurring_quotas: list[RecurringQuotaRef]
    """Cuotas recurrentes detectadas con categoría de deuda — la UI
    las muestra como "Cuotas recurrentes detectadas" en Capa 1."""
