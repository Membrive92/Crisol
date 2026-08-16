"""Schemas Pydantic del módulo deuda.

Capa 1 (flujo por categorías, PHASE-30.2) y — desde PHASE-47.A — los de Capa 2
(salud de deuda, cuadro de amortización, cuotas y reconciliación), que vivían en
`accounts/schemas.py` por razones históricas: la deuda nació dentro de cuentas.
Los endpoints siguen colgando de `/accounts/*` (D6: cambiar la URL rompe
contrato); lo que cambia es de dónde importan.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

# PHASE-41 — se eliminó "quarter" (sin sentido para un particular); "custom" es
# el rango libre from/to que define el usuario (p. ej. de día 15 a día 15).
DebtTimeRange = Literal["month", "year", "custom"]
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
    """Un punto de la serie mensual: pagos, intereses, capital + saldo."""

    month: str
    """`YYYY-MM`."""
    payments: Decimal
    """Σ flujo de categorías DEBT_PAYMENT + DEBT_INTEREST ese mes."""
    interests: Decimal
    """Σ flujo de categorías DEBT_INTEREST ese mes."""
    capital: Decimal
    """`payments - interests`."""
    balance: Decimal | None = None
    """PHASE-43.x — Saldo de deuda al CIERRE del mes (STOCK, dirigido por el
    cuadro: `_scheduled_remaining_at`). Es la línea que baja del combo
    saldo+pagos. `None` si el usuario no tiene deuda con cuadro."""


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
    """Composición de los PAGOS por tipo durante el rango (flujo)."""

    outstanding_at_end: Decimal = Decimal("0")
    """PHASE-43.x — Deuda viva TOTAL al CIERRE del período seleccionado (STOCK,
    dirigida por el cuadro). A período = año/hoy iguala `debt-health.total_
    liabilities`; al navegar a un mes pasado muestra la deuda de entonces
    (mayor, porque se habían hecho menos pagos)."""
    outstanding_by_type: list[DebtTypeBreakdown]
    """PHASE-43.x — Composición de la deuda viva por tipo AL CIERRE del período
    (STOCK). Reemplaza a `debt-health.debt_by_type` en el donut para que la
    composición respete el navegador de período."""

    monthly_series: list[MonthlyDebtPoint]
    """Un punto por mes del período (meses sin actividad en 0): 1 para
    `month`, hasta 12 para `year`. El período en curso sólo incluye los
    meses transcurridos."""

    daily_series: list[DailyDebtPoint] | None = None
    """Sólo poblado cuando `range='month'`: un punto por día del mes con
    la evolución del saldo de deuda (emisión ↑ / amortización ↓) + el
    saldo acumulado. `None` para `year` (se usa `monthly_series`)."""

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


class DebtTypeSlice(BaseModel):
    """PHASE-37 — Porción de la deuda viva por tipo de cuenta (para el donut
    de composición). `amount` en `reference_currency`."""

    type: str
    """`loan` | `mortgage` | `credit_card`."""
    amount: Decimal


class DebtHealthKpis(BaseModel):
    """KPIs de salud financiera basados en deudas activas (PHASE-22.4
    + PHASE-30.2).

    Todas las cifras vienen en `reference_currency` (la moneda
    dominante entre cuentas activas, igual que en `/accounts/balances`).
    `null` cuando no hay datos suficientes para computar (ej. sin
    ingresos no se puede calcular la tasa de esfuerzo).

    `dti_status` interpreta `dti_ratio` con las bandas del Banco de
    España (PHASE-30.2 recalibró las antiguas 36%/43% estadounidenses
    a 30%/35% europeas, más conservadoras y sobre ingresos netos):
    - `healthy`   → < 0.30
    - `caution`   → 0.30 a 0.35
    - `stressed`  → > 0.35
    - `unknown`   → no calculable

    Los nombres de campo siguen siendo `dti_*` por compatibilidad con
    clientes existentes; la UI nueva los renombra a "tasa de esfuerzo".

    `time_to_payoff_months` (PHASE-30.2): prefiere las cuotas restantes
    del cuadro francés cuando la liability tiene `apr + term_months
    + start_date`; fallback a proyección lineal sólo para tarjetas o
    liabilities sin schedule. Devuelve el máximo individual entre
    todas las liabilities con saldo > 0.
    """

    total_liabilities: Decimal
    total_assets: Decimal
    net_worth: Decimal
    debt_to_assets_ratio: float | None
    """`total_liabilities / total_assets` cuando assets > 0."""
    dti_ratio: float | None
    """Tasa de esfuerzo: cuota mensual estimada / ingreso mensual medio.
    Se mantiene el nombre `dti_ratio` por compatibilidad de API."""
    dti_status: str
    """`healthy | caution | stressed | unknown` con bandas BdE 30/35%
    (PHASE-30.2)."""
    monthly_debt_payment: Decimal
    """Suma de cuotas mensuales recurrentes (cuadros + tarjetas
    estimadas). Tarjetas estiman con la cuota teórica del último mes."""
    monthly_income_avg: Decimal
    """Ingreso mensual medio de los últimos 6 meses (excluye
    transferencias internas)."""
    debt_by_type: list[DebtTypeSlice] = []
    """PHASE-37 — Composición de la DEUDA VIVA por tipo de cuenta
    (loan/mortgage/credit_card), desde `schedule_outstanding` (la MISMA
    fuente que `total_liabilities` y el patrimonio neto). Alimenta el donut
    de composición de `/debt`; es un STOCK (cuánto debes), no un flujo de
    pagos. Parent cards sin cuadro aportan 0; las compras-hijas cuentan una
    vez por su propio cuadro (sin doble conteo padre/hija, PHASE-35)."""
    interest_paid_ytd: Decimal
    """Intereses pagados desde el 1 de enero hasta hoy. PHASE-37 (fix):
    MUX por pasivo — para las liabilities CON cuadro sale del cuadro
    (`liability_installments.interest` de cuotas con `paid_at` en el año);
    para las que no tienen cuadro, de sus transacciones `role=DEBT_INTEREST`
    (excluidas las cuentas con cuadro para no doblar). El banco no desglosa
    el interés como movimiento aparte, así que sin esto salía 0 pese a
    tener TIN/TAE configurados."""
    interest_scheduled_total: Decimal = Decimal("0")
    """PHASE-37 — Interés contractual total del cuadro (Σ interés de TODAS
    las cuotas de las liabilities con cuadro). El coste total del crédito."""
    interest_remaining: Decimal = Decimal("0")
    """PHASE-37 — Interés que queda por pagar (Σ interés de cuotas con
    `paid_at IS NULL`). `interest_scheduled_total − interés ya pagado`."""
    weighted_apr: float | None
    """APR medio ponderado por saldo entre liabilities con apr
    declarado. `null` si ninguna lo tiene."""
    time_to_payoff_months: int | None
    """Meses restantes hasta saldar toda la deuda. Usa el schedule
    cuando está disponible; fallback a proyección lineal para
    liabilities sin cuadro. `null` si no se puede estimar."""
    reference_currency: str


class AmortizationRowResponse(BaseModel):
    """Una fila del cuadro francés (PHASE-22.3 + PHASE-24.1).

    PHASE-24.1 añade:
    - `id`: identificador estable de la cuota persistida (necesario
      para el editor: PATCH/POST/DELETE individuales).
    - `paid_at` / `paid_transaction_id`: estado y trazabilidad.
    """

    id: uuid.UUID | None = None
    """`None` sólo en el modo legacy on-the-fly (cuentas sin cuotas
    persistidas todavía). Tras PHASE-24.1 backfill, siempre presente."""
    month: int
    due_date: date
    payment: Decimal
    interest: Decimal
    principal: Decimal
    remaining_balance: Decimal
    paid_at: datetime | None = None
    paid_transaction_id: uuid.UUID | None = None


class InstallmentUpdateRequest(BaseModel):
    """PATCH parcial de una cuota — sólo `payment` y/o `due_date`
    (PHASE-24.1). El override NO recomputa cuotas siguientes."""

    payment: Decimal | None = Field(default=None, decimal_places=2)
    due_date: date | None = None


class InstallmentPayRequest(BaseModel):
    """POST /pay — marca cuota como pagada con timestamp + tx opcional."""

    paid_at: datetime | None = None
    """`None` → `now()`."""
    paid_transaction_id: uuid.UUID | None = None
    """Tx del extracto que liquidó la cuota — opcional, informativo."""


class InstallmentBulkPayRequest(BaseModel):
    """AUDIT-2026-07 (H-05) — Marca las cuotas que un pago de principal cubre.

    Lo usa el asistente "Pagar cuota": tras crear la transferencia del
    principal, marca la(s) cuota(s) que ese importe cubre (de la más antigua
    pendiente hacia adelante) para que el saldo dirigido por el cuadro
    (PHASE-36) baje. `paid_transaction_id` es la pata que movió el dinero.
    """

    principal_amount: Decimal = Field(gt=0, decimal_places=2)
    paid_at: datetime | None = None
    paid_transaction_id: uuid.UUID | None = None


class InstallmentBulkPayResponse(BaseModel):
    """Resultado de marcar cuotas por importe de principal (H-05)."""

    marked_count: int
    """Cuántas cuotas se marcaron como pagadas."""
    covered_principal: Decimal
    """Σ del principal de las cuotas marcadas."""
    uncovered_principal: Decimal
    """Principal pagado que NO cubrió una cuota completa (0 si cuadró).
    Si `marked_count == 0` es el importe total: la UI debe avisar de que el
    pago no alcanza la cuota más antigua pendiente."""
    schedule_outstanding: Decimal | None
    """Saldo de la liability dirigido por el cuadro tras marcar (PHASE-36)."""


# AUDIT-2026-07 (LOW): esquema de respuesta tipado del plan de reconciliación
# (PHASE-36). Antes el endpoint devolvía `dict[str, object]` sin `response_model`
# — sin contrato en el boundary. Refleja `ReconcilePlan.to_dict()`.
class ReconcileActionResponse(BaseModel):
    ix: int
    due: str
    principal: str
    payment: str
    reason: str
    tx: str | None = None
    tx_desc: str | None = None
    tx_amount: str | None = None


class ReconcileLiabilityResponse(BaseModel):
    name: str
    type: str
    generate_schedule: bool
    schedule_rows: int
    anchored: int
    matched: int
    assumed_unregistered_debt: str
    outstanding_before: str | None = None
    outstanding_after: str | None = None
    actions: list[ReconcileActionResponse]


class ReconcilePlanResponse(BaseModel):
    data_window_start: str | None = None
    liabilities: list[ReconcileLiabilityResponse]
    skipped_payments: list[str]


class AmortizationScheduleResponse(BaseModel):
    """Cuadro completo + KPIs derivados (PHASE-22.3 + PHASE-24.2 + PHASE-24.3)."""

    account_id: uuid.UUID
    principal: Decimal
    apr: Decimal
    """TIN — usado para calcular las cuotas."""
    tae: Decimal | None = None
    """PHASE-24.2 — TAE (informativa). NULL si no se declaró."""
    term_months: int
    start_date: date
    monthly_payment: Decimal
    """Cuota constante (sistema francés)."""
    total_interest: Decimal
    """Intereses totales que pagarás durante el plazo completo."""
    total_paid: Decimal
    """Total a pagar según el cuadro teórico (Σ cuotas + interest_only).
    Para el "total contractualizado" del banco usar `total_to_pay`.
    """
    interest_only_first_payment: Decimal | None = None
    """PHASE-24.3 — Primera cuota especial sólo de intereses."""
    total_to_pay: Decimal | None = None
    """PHASE-24.3 — Total contractualizado por el banco. Puede ser
    mayor que `total_paid` cuando hay comisiones/cargos no
    desglosados."""
    extra_charges: Decimal | None = None
    """PHASE-24.3 — Cargos derivados dinámicamente como
    `total_to_pay − total_paid − interest_only_first_payment` cuando
    hay datos suficientes. NULL si `total_to_pay` no está informado."""
    rows: list[AmortizationRowResponse]


class DebtHistoryPoint(BaseModel):
    """Un punto de la serie temporal de evolución de deuda (PHASE-22.1).

    `kind` distingue puntos reales (`historical`) de la proyección
    (`projected`). En histórico, `total_debt` es el cierre del mes;
    `principal_paid` e `interest_paid` son lo amortizado y los
    intereses pagados durante ese mes. En proyección,
    `total_debt` es la deuda al cierre estimado y
    `principal_paid`/`interest_paid` son los flujos estimados del mes.
    """

    month: str
    """Mes en formato `YYYY-MM`."""
    total_debt: Decimal
    """Saldo total de pasivos al cierre del mes (en
    `reference_currency`)."""
    principal_paid: Decimal
    """Principal amortizado durante el mes."""
    interest_paid: Decimal
    """Intereses pagados durante el mes (categorías de intereses)."""
    kind: str
    """`historical` o `projected`."""


class DebtHistoryResponse(BaseModel):
    """Serie temporal de deuda con histórico + proyección (PHASE-22.1).

    El primer punto histórico es el primer mes con datos en la
    ventana solicitada; el último histórico es el mes anterior al
    actual (los meses cerrados). La proyección empieza en el mes en
    curso y extiende `months_ahead` meses hacia adelante usando
    cuadros francesas + cuota teórica de tarjetas.
    """

    items: list[DebtHistoryPoint]
    reference_currency: str
    months_historical: int
    months_projected: int


# ── PHASE-47.E2 · el ciclo aplazado ──────────────────────────────────


class DeferredCyclePurchase(BaseModel):
    """Una compra del ciclo que el recibo aplazó."""

    id: uuid.UUID
    occurred_at: datetime
    amount: Decimal
    description: str | None


class DeferredCyclePreview(BaseModel):
    """Qué gasto quedó aplazado por este recibo financiado.

    `closes_exactly` es lo que decide si se puede aplicar: sin cierre al
    céntimo no se marca nada, porque marcar unas cuantas repartiría el gasto
    entre categorías que no son las suyas (`debt/deferral.py`).
    """

    liability_id: uuid.UUID
    liability_name: str
    card_id: uuid.UUID | None
    card_name: str | None
    receipt_amount: Decimal
    currency: str
    purchases: list[DeferredCyclePurchase]
    total: Decimal
    closes_exactly: bool
    already_declared: bool = False
    """PHASE-47.E — el ciclo YA está marcado y esto es lo que hay guardado, no
    una propuesta. Viaja como dato y no se deduce del texto de `reason`: una
    frase se reescribe cualquier día y quien la estuviera comparando se entera
    en producción."""
    reason: str
