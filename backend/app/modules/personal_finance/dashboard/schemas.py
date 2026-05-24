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
    previous_period_income: Decimal | None = None
    previous_period_expenses: Decimal | None = None
    previous_period_balance: Decimal | None = None


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
