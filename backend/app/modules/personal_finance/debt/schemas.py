"""Schemas Pydantic de Capa 1 del módulo deuda (PHASE-30.2)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

DebtTimeRange = Literal["month", "quarter", "year"]
EffortStatus = Literal["healthy", "caution", "stressed", "unknown"]
DebtTypeBucket = Literal["mortgage", "loan", "credit_card", "other"]


class DebtTypeBreakdown(BaseModel):
    """Pagos a deuda agregados por tipo aproximado (PHASE-30.2).

    El "tipo" se infiere primero por la cuenta vinculada a la
    categoría (PHASE-30.4): si la categoría apunta a una liability
    con `type='mortgage'`, su bucket es `mortgage`; si apunta a
    `loan`, `loan`; etc. Cuando no hay cuenta vinculada, se cae a
    matching por nombre (con `loan` chequeado antes que `mortgage`
    para que la categoría seed "Préstamos e hipotecas" no se
    interprete como hipoteca solo por contener el substring). No es
    100% perfecto pero refleja la composición
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


class DailyDebtPoint(BaseModel):
    """Un día del mes en la vista diaria (sólo `range='month'`).

    A diferencia de la serie mensual (que mira PAGOS categorizados),
    la vista diaria modela la **evolución del saldo de deuda** dentro
    del mes a partir de las cuentas-pasivo (Capa 2):

    - `emitida`: Σ cargos del día que SUBEN la deuda (gastos sobre
      cuentas-pasivo: compras a plazos, aplazamientos, disposiciones).
    - `amortizado`: Σ del día que BAJA la deuda (entradas a cuentas
      -pasivo, típicamente transferencias de pago de capital).
    - `interest`: Σ intereses pagados ese día (categorías DEBT_INTEREST,
      Capa 1) — informativo; se paga en cash y NO mueve el principal.
    - `balance`: saldo agregado de deuda al cierre del día. `None`
      cuando el usuario no tiene cuentas-pasivo declaradas (sin Capa 2
      no hay saldo que dibujar; el chart cae a barras de pagos).

    Degradación: sin cuentas-pasivo, `emitida=0`, `balance=None` y
    `amortizado` toma los pagos de capital categorizados (DEBT_PAYMENT)
    para que el chart diario siga siendo útil.
    """

    day: int
    """Día del mes (1-31)."""
    emitida: Decimal
    amortizado: Decimal
    interest: Decimal
    balance: Decimal | None


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

    available_from: str | None = None
    """`YYYY-MM` del primer mes con movimientos de deuda (o `null`).
    Límite inferior para el navegador de período (PHASE-30.8)."""
    available_to: str | None = None
    """`YYYY-MM` del último mes con movimientos de deuda (o `null`).
    Límite superior para el navegador de período (PHASE-30.8)."""

    total_payments: Decimal
    """Σ flujo de categorías con `role IN (DEBT_PAYMENT, DEBT_INTEREST)`
    durante el rango."""
    interests_and_fees: Decimal
    """Σ flujo de DEBT_INTEREST sólo."""
    capital_amortized: Decimal
    """`total_payments - interests_and_fees`."""

    by_type: list[DebtTypeBreakdown]
    """Composición agregada por tipo aproximado para el donut."""

    monthly_series: list[MonthlyDebtPoint]
    """Un punto por mes del período (meses sin actividad en 0): 1 para
    `month`, hasta 3 para `quarter`, hasta 12 para `year`. El período
    en curso sólo incluye los meses transcurridos."""

    daily_series: list[DailyDebtPoint] | None = None
    """Sólo poblado cuando `range='month'`: un punto por día del mes con
    la evolución del saldo de deuda (emisión ↑ / amortización ↓) + el
    saldo acumulado. `None` para `quarter`/`year` (se usa `monthly_series`)."""

    monthly_income_avg: Decimal
    """Ingreso medio mensual de la categoría INCOME (sin transferencias
    internas) DURANTE el período seleccionado (PHASE-30.8): Σ ingresos
    del período ÷ nº de meses. Denominador de la tasa de esfuerzo."""
    monthly_debt_payment_avg: Decimal
    """Pago a deuda medio mensual del período (PHASE-30.8): Σ pagos de
    los meses cerrados ÷ nº de meses. Numerador de la tasa de esfuerzo
    estricta — expuesto para que la card muestre cifras coherentes con
    el gauge sin derivarlas del ratio."""
    effort_ratio_strict: float | None
    """Pagos a deuda del período/mes ÷ ingreso medio del período/mes
    (PHASE-30.8, ambos sobre la misma ventana). `null` sin ingresos."""
    effort_ratio_strict_status: EffortStatus
    effort_ratio_extended: float | None
    """Como `strict` pero sumando las cuotas de `fixed_expenses` con
    `status=confirmed`. Si un fixed_expense ya está vinculado a una
    categoría de deuda no se cuenta dos veces."""
    effort_ratio_extended_status: EffortStatus

    recurring_quotas: list[RecurringQuotaRef]
    """Cuotas recurrentes detectadas con categoría de deuda — la UI
    las muestra como "Cuotas recurrentes detectadas" en Capa 1."""
