"""Schemas Pydantic del módulo dashboard.

Sólo respuestas — dashboard es read-only. Los importes viajan como `Decimal`
para preservar precisión (serializados a string por Pydantic).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

# PHASE-43.4 (ADR-0006) — contrato de agregación del dashboard. Cada módulo
# vertical expone su tarjeta como `veredicto + un número + un link`. El
# dashboard COMPONE estas tarjetas; no recalcula (salvo el patrimonio
# consolidado, que cruza módulos y es suyo por definición).
ModuleVerdict = Literal["healthy", "caution", "stressed", "neutral"]


class ModuleSummaryItem(BaseModel):
    """Un par etiqueta/valor secundario de la tarjeta de módulo (ya formateado
    para mostrar, p. ej. `("Ahorro", "9 %")`)."""

    label: str
    value: str


class ModuleDashboardSummary(BaseModel):
    """Tarjeta de un módulo en el dashboard (ADR-0006).

    `veredicto + un número + un link`. NO es un mini-módulo: el detalle vive
    en la superficie propia del módulo, a la que apunta `link`.
    """

    verdict: ModuleVerdict
    headline_value: Decimal
    """El número grande, con signo (p. ej. flujo del mes o −deuda viva)."""
    headline_label: str
    currency: str
    secondary: list[ModuleSummaryItem] = []
    link: str


class SummaryResponse(BaseModel):
    """Balance global en el rango y moneda pedidos.

    Cuando el caller pasa `date_from` y `date_to`, se calcula también el
    rango previo de igual longitud (`previous_period_*`) para que el
    frontend pinte deltas vs periodo anterior. Si no hay rango, los
    `previous_*` quedan en `None`.

    En modo `target_currency` (PHASE-8.3), `currency` refleja la moneda
    destino y `unconvertible_count` indica cuántas transacciones del
    rango no se pudieron convertir por falta de tasa. En modo legacy
    `currency` es el filtro y `unconvertible_count` es siempre 0.
    """

    income: Decimal
    expenses: Decimal
    balance: Decimal
    transaction_count: int
    currency: str
    unconvertible_count: int = 0
    deferred_expenses: Decimal = Decimal("0")
    """PHASE-47.E2 — parte del gasto del periodo que quedó APLAZADA por un
    recibo financiado. NO está incluida en `expenses` (el resultado del mes
    mide caja y ese dinero no salió), pero SÍ en el desglose por categorías,
    porque el gasto se hizo. Es la diferencia entre las dos lecturas, y la
    pantalla tiene que decirla: sin ella, las dos cifras no cuadran y no hay
    forma de saber por qué."""
    previous_period_income: Decimal | None = None
    previous_period_expenses: Decimal | None = None
    previous_period_balance: Decimal | None = None
    cashflow_delta: Decimal | None = None
    """PHASE-37.1 — `balance − previous_period_balance` (Δ del flujo neto vs
    periodo anterior equivalente). `None` si no hay periodo previo."""
    savings_rate_delta_pp: float | None = None
    """PHASE-37.1 — Variación de la tasa de ahorro en PUNTOS porcentuales vs
    periodo anterior. `None` si falta ingreso en el periodo actual o previo."""
    available_from: str | None = None
    """PHASE-34 — Mes (`YYYY-MM`) más antiguo con transacciones del usuario,
    global (ignora el filtro de período). Acota el navegador de período del
    Análisis. `None` si no hay transacciones."""
    available_to: str | None = None
    """PHASE-34 — Mes (`YYYY-MM`) más reciente con transacciones del usuario."""


class CategoryBreakdownItem(BaseModel):
    """Total agregado por categoría. `category_id=None` → bucket "Sin categoría"."""

    category_id: uuid.UUID | None
    category_name: str
    category_kind: str | None
    category_color: str | None = None
    category_icon: str | None = None
    total: Decimal
    count: int


class MonthlyBucket(BaseModel):
    """Totales de un mes concreto. `month` con formato `YYYY-MM`."""

    month: str
    income: Decimal
    expenses: Decimal
    balance: Decimal


class TopExpenseItem(BaseModel):
    """Gasto individual dentro del ranking de mayores gastos.

    `amount` es el importe **usado para el ranking** — convertido a la
    moneda destino en modo cross-currency, original en modo legacy.
    `original_amount` + `original_currency` (PHASE-8.4) exponen siempre
    el dato crudo de la transacción para que la UI distinga ambos sin
    consultar la transacción individual.
    """

    transaction_id: uuid.UUID
    description: str | None
    amount: Decimal
    occurred_at: datetime
    category_id: uuid.UUID | None
    category_name: str | None
    original_amount: Decimal
    original_currency: str


class CategoryMonthlyBucket(BaseModel):
    """PHASE-25 — Total mensual de UNA categoría concreta."""

    month: str
    """Formato `YYYY-MM`."""
    total: Decimal


class CategoryDetailResponse(BaseModel):
    """PHASE-25 — KPIs + evolución + top tx de una categoría concreta,
    para la pantalla de drill-down del desglose del dashboard.

    Todos los importes vienen en `currency` (la pedida por el caller).
    El rango aplicado es `[date_from, date_to]` — el caller decide
    (default: últimos 30 días en el frontend, igual que el resto).
    """

    category_id: uuid.UUID
    category_name: str
    category_kind: str
    category_color: str | None = None
    category_icon: str | None = None
    currency: str
    total: Decimal
    """Total del rango."""
    count: int
    """Número de tx en el rango."""
    average_amount: Decimal
    """Ticket medio (`total / count`). 0 si count=0."""
    by_month: list[CategoryMonthlyBucket]
    """Evolución mensual ordenada cronológicamente. Default últimos
    12 meses cerrados desde la fecha actual (el caller no lo controla
    en esta primera versión)."""
    top_transactions: list[TopExpenseItem]
    """Top 10 tx del rango ordenadas por importe desc — para que el
    usuario vea los movimientos más significativos sin abrir la lista
    completa."""


class CategoryAvailablePeriodItem(BaseModel):
    """Año + meses (1-12) con transacciones activas de una categoría."""

    year: int
    months: list[int]


class CategoryAvailablePeriodsResponse(BaseModel):
    """Periodos con datos para una categoría. Alimenta el selector
    temporal del drill-down — sólo se muestran chips para meses/años
    en los que realmente hay movimientos de esa categoría.
    """

    periods: list[CategoryAvailablePeriodItem]
