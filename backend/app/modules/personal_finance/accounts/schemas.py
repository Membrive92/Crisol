"""Schemas Pydantic del módulo accounts (PHASE-19.1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.modules.personal_finance.accounts.models import AccountNature, AccountType

# Tipos `asset` exponibles al usuario.
ASSET_ACCOUNT_TYPES: frozenset[AccountType] = frozenset(
    {
        AccountType.BANK,
        AccountType.SAVINGS,
        AccountType.BROKERAGE,
        AccountType.CRYPTO,
        AccountType.CASH,
    }
)

# PHASE-22: tipos `liability` (deuda). El service asigna nature
# automáticamente según el type.
LIABILITY_ACCOUNT_TYPES: frozenset[AccountType] = frozenset(
    {
        AccountType.CREDIT_CARD,
        AccountType.LOAN,
        AccountType.MORTGAGE,
    }
)


class AccountCreate(BaseModel):
    """Datos para crear una cuenta."""

    name: str = Field(min_length=1, max_length=100)
    type: AccountType
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    color: str | None = Field(default=None, max_length=7)
    icon: str | None = Field(default=None, max_length=50)
    opening_balance: Decimal = Field(default=Decimal("0"), decimal_places=2)
    opening_balance_date: date | None = None
    # PHASE-22.3 + PHASE-24.2: cuadro de amortización opcional para
    # loan/mortgage/credit_card (financiadas).
    apr: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"), decimal_places=4)
    """TIN anual como decimal (0.0350 = 3.50%). Se usa para el cuadro."""
    tae: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"), decimal_places=4)
    """PHASE-24.2 — TAE (informativa, no afecta cálculo)."""
    term_months: int | None = Field(default=None, ge=1, le=600)
    start_date: date | None = None
    total_to_pay: Decimal | None = Field(default=None, ge=Decimal("0"), decimal_places=2)
    """PHASE-24.3 — Total a pagar contractualizado por el banco."""
    interest_only_first_payment: Decimal | None = Field(
        default=None, ge=Decimal("0"), decimal_places=2
    )
    """PHASE-24.3 — Primer pago especial sólo de intereses."""
    display_order: int = Field(default=0, ge=0)
    is_default: bool = False
    """PHASE-32 — Marcar como cuenta principal al crear. Única por
    usuario: el service desmarca las demás."""
    category_id: uuid.UUID | None = None
    """PHASE-30.4 — Categoría de pagos vinculada (sólo liability +
    role DEBT_*). El service valida ambas condiciones; pasa por aquí
    NULL desde formularios donde no se haya escogido."""
    parent_account_id: uuid.UUID | None = None
    """PHASE-35 — Tarjeta padre. Si se indica, esta cuenta es una COMPRA A
    PLAZOS dentro de esa tarjeta: el service valida que el padre es una
    `credit_card` del usuario y exige plan (capital + TIN + plazo + fecha)
    para generar su propio cuadro de amortización."""


class AccountUpdate(BaseModel):
    """Datos para actualizar una cuenta (parcial)."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    type: AccountType | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    color: str | None = Field(default=None, max_length=7)
    icon: str | None = Field(default=None, max_length=50)
    opening_balance: Decimal | None = Field(default=None, decimal_places=2)
    opening_balance_date: date | None = None
    apr: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"), decimal_places=4)
    tae: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"), decimal_places=4)
    term_months: int | None = Field(default=None, ge=1, le=600)
    start_date: date | None = None
    total_to_pay: Decimal | None = Field(default=None, ge=Decimal("0"), decimal_places=2)
    interest_only_first_payment: Decimal | None = Field(
        default=None, ge=Decimal("0"), decimal_places=2
    )
    display_order: int | None = Field(default=None, ge=0)
    is_archived: bool | None = None
    is_default: bool | None = None
    """PHASE-32 — `true` marca esta cuenta como principal y desmarca las
    demás (lo fuerza el service). `false` la desmarca. `null` no toca."""
    category_id: uuid.UUID | None = None
    """PHASE-30.4 — Mismo contrato que en `AccountCreate`. Para
    desvincular, enviar explícitamente `null`."""


class ReconcileBalanceRequest(BaseModel):
    """PHASE-34 — 'Cuadrar saldo'. El usuario declara el saldo REAL actual de
    una cuenta (lo que dice su banco hoy) y el service ajusta
    `opening_balance` para que el saldo mostrado coincida, sin reconstruir el
    histórico ni emparejar transferencias. Vale para fijar el saldo inicial y
    para re-cuadrar cuando se descuadre. Solo cuentas de activo (la deuda se
    gestiona en su módulo)."""

    current_balance: Decimal = Field(decimal_places=2)


class AccountResponse(BaseModel):
    """Respuesta pública de una cuenta."""

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    type: AccountType
    nature: AccountNature
    currency: str
    color: str | None
    icon: str | None
    opening_balance: Decimal
    opening_balance_date: date | None
    apr: Decimal | None = None
    tae: Decimal | None = None
    term_months: int | None = None
    start_date: date | None = None
    total_to_pay: Decimal | None = None
    interest_only_first_payment: Decimal | None = None
    display_order: int
    is_archived: bool
    is_default: bool = False
    """PHASE-32 — Cuenta principal del usuario (pre-seleccionada en
    formularios). Única por usuario."""
    category_id: uuid.UUID | None = None
    parent_account_id: uuid.UUID | None = None
    """PHASE-35 — Tarjeta padre si esta cuenta es una compra a plazos. NULL
    en cuentas normales. La UI agrupa las hijas bajo el padre."""
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccountBalance(BaseModel):
    """Saldo calculado de una cuenta (PHASE-19.4)."""

    account_id: uuid.UUID
    name: str
    type: AccountType
    nature: AccountNature
    currency: str
    color: str | None
    icon: str | None
    parent_account_id: uuid.UUID | None = None
    """PHASE-35 — Tarjeta padre si es una compra a plazos (para agrupar)."""
    opening_balance: Decimal
    movements_balance: Decimal
    """Suma neta de movimientos en la moneda nativa de la cuenta
    (income suma, expense resta). Excluye papelera y txs en otra
    moneda; las transferencias internas SÍ cuentan al saldo de su
    cuenta."""
    current_balance: Decimal
    """`opening_balance + movements_balance`."""
    monthly_payment: Decimal | None = None
    """PHASE-37 — Cuota mensual del cuadro de amortización
    (`installments[0].payment`) para liabilities CON cuadro. `None` para
    activos y liabilities sin cuadro. La lista de deuda pinta la "Cuota est."
    real de las tarjetas financiadas (cuyo `opening_balance` es 0 y no se
    puede recomputar la cuota francesa)."""
    is_unvalued: bool = False
    """PHASE-31.4 — `True` para cuentas cuyo saldo NO entra al agregado
    de patrimonio neto porque su valoración real depende del mercado y
    no se computa por `Σ(movimientos)` (hoy: brokerage y crypto).
    Siguen apareciendo en `items` para que el usuario las vea y para
    que sigan siendo destino válido de transferencias. Cuando exista
    un módulo de inversión real con valoración propia, se
    reincorporarán al patrimonio."""


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


class PositionPoint(BaseModel):
    """PHASE-37.1 — Un punto de la serie temporal de patrimonio.

    `is_projection=False` para meses cerrados reales; `True` para la
    proyección (activos planos + deuda por cuadro teórico).
    """

    month: date
    """Primer día del mes."""
    total_assets: Decimal
    total_liabilities: Decimal
    """Deuda agregada con signo positivo."""
    net_worth: Decimal
    """`total_assets − total_liabilities`."""
    is_projection: bool = False


class PositionHistoryResponse(BaseModel):
    """PHASE-37.1 — Serie temporal de patrimonio + Δ del periodo pedido.

    Mono-divisa (`reference_currency`), misma limitación que
    `/accounts/balances`. `delta_period` = neto actual (último punto
    histórico) − neto al inicio del rango; `None` si no hay ≥2 puntos
    históricos.
    """

    reference_currency: str
    points: list[PositionPoint]
    delta_period: Decimal | None = None
    delta_period_pct: float | None = None


class AccountBalancesResponse(BaseModel):
    """Snapshot de patrimonio del usuario por cuenta (PHASE-19.4).

    `total_assets` y `total_liabilities` agregan los saldos por
    `nature`. `net_worth = total_assets − total_liabilities`. En
    PHASE-19.4 sólo hay cuentas `asset` (los `liability` llegan en
    PHASE-20), así que `total_liabilities = 0` y
    `net_worth = total_assets`.

    `mixed_currencies` es `True` si las cuentas activas no comparten
    moneda; en ese caso los totales son suma cruda y la UI debe
    advertir. Una próxima fase puede convertir a una divisa de
    referencia.
    """

    items: list[AccountBalance]
    total_assets: Decimal
    total_liabilities: Decimal
    net_worth: Decimal
    mixed_currencies: bool
    reference_currency: str
