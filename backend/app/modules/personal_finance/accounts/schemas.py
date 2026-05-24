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
    opening_balance: Decimal
    movements_balance: Decimal
    """Suma neta de movimientos en la moneda nativa de la cuenta
    (income suma, expense resta). Excluye papelera y txs en otra
    moneda; las transferencias internas SÍ cuentan al saldo de su
    cuenta."""
    current_balance: Decimal
    """`opening_balance + movements_balance`."""


class DebtHealthKpis(BaseModel):
    """KPIs de salud financiera basados en deudas activas (PHASE-22.4).

    Todas las cifras vienen en `reference_currency` (la moneda
    dominante entre cuentas activas, igual que en `/accounts/balances`).
    `null` cuando no hay datos suficientes para computar (ej. sin
    ingresos no se puede DTI).

    `dti_status` interpreta `dti_ratio`:
    - `healthy`   → < 0.36
    - `caution`   → 0.36 a 0.43
    - `stressed`  → > 0.43
    - `unknown`   → no calculable

    `time_to_payoff_months` proyecta el ritmo actual de amortización
    de principal hacia adelante (lineal, sin asumir cuadro fijo).
    Cuenta sólo los pagos `transfer` netos del último período hacia
    cuentas liability.
    """

    total_liabilities: Decimal
    total_assets: Decimal
    net_worth: Decimal
    debt_to_assets_ratio: float | None
    """`total_liabilities / total_assets` cuando assets > 0."""
    dti_ratio: float | None
    """Cuota mensual estimada / ingreso mensual medio."""
    dti_status: str
    """`healthy | caution | stressed | unknown`."""
    monthly_debt_payment: Decimal
    """Suma de cuotas mensuales recurrentes (cuadros + tarjetas
    estimadas). Tarjetas estiman con la cuota teórica del último mes."""
    monthly_income_avg: Decimal
    """Ingreso mensual medio de los últimos 6 meses (excluye
    transferencias internas)."""
    interest_paid_ytd: Decimal
    """Intereses pagados desde el 1 de enero hasta hoy
    (categorías de intereses)."""
    weighted_apr: float | None
    """APR medio ponderado por saldo entre liabilities con apr
    declarado. `null` si ninguna lo tiene."""
    time_to_payoff_months: int | None
    """Meses restantes si mantienes el ritmo medio de amortización
    actual. `null` si no hay actividad reciente."""
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
