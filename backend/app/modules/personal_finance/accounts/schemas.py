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
    counts_as_debt: bool = True
    """PHASE-40 — `False` en tarjetas de crédito que se pagan íntegras cada mes
    (revolving): salen del módulo de deuda pero siguen en patrimonio neto."""
    category_id: uuid.UUID | None = None
    """PHASE-30.4 — Categoría de pagos vinculada (sólo liability +
    role DEBT_*). El service valida ambas condiciones; pasa por aquí
    NULL desde formularios donde no se haya escogido."""
    parent_account_id: uuid.UUID | None = None
    """PHASE-35 — Tarjeta padre. Si se indica, esta cuenta es una COMPRA A
    PLAZOS dentro de esa tarjeta: el service valida que el padre es una
    `credit_card` del usuario y exige plan (capital + TIN + plazo + fecha)
    para generar su propio cuadro de amortización."""
    settlement_account_id: uuid.UUID | None = None
    """PHASE-47.A — Cuenta de ACTIVO desde la que se cobra este pasivo. Sólo
    válida en liabilities y apuntando a una cuenta de activo del propio
    usuario; el service valida ambas condiciones."""


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
    counts_as_debt: bool | None = None
    """PHASE-40 — Toggle "esta tarjeta la pago íntegra → no es deuda"."""
    """PHASE-32 — `true` marca esta cuenta como principal y desmarca las
    demás (lo fuerza el service). `false` la desmarca. `null` no toca."""
    category_id: uuid.UUID | None = None
    """PHASE-30.4 — Mismo contrato que en `AccountCreate`. Para
    desvincular, enviar explícitamente `null`."""
    settlement_account_id: uuid.UUID | None = None
    """PHASE-47.A — Mismo contrato que en `AccountCreate`. Para desvincular,
    enviar explícitamente `null`."""


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
    counts_as_debt: bool = True
    """PHASE-40 — `False` en tarjetas revolving pagadas íntegras (fuera del
    módulo de deuda, dentro del patrimonio neto)."""
    category_id: uuid.UUID | None = None
    parent_account_id: uuid.UUID | None = None
    """PHASE-35 — Tarjeta padre si esta cuenta es una compra a plazos. NULL
    en cuentas normales. La UI agrupa las hijas bajo el padre."""
    settlement_account_id: uuid.UUID | None = None
    """PHASE-47.A — Cuenta de activo desde la que se cobra este pasivo. NULL
    en assets y en pasivos sin declarar."""
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettlementCandidateResponse(BaseModel):
    """PHASE-47.A — Propuesta de "desde qué cuenta se cobra este pasivo",
    contada sobre los cargos que el usuario YA enlazó (PHASE-45).

    No se persiste ni se aplica sola: el formulario la precarga con su motivo
    y el usuario adjudica (ADR-0011). Sin evidencia, `account_id` es `None` y
    no se propone nada — proponer sin haber contado sería adivinar, que es
    justo lo que el diseño de PHASE-45 evita."""

    account_id: uuid.UUID | None = None
    account_name: str | None = None
    reason: str | None = None
    """Frase en español con la evidencia contada, o `None` si no la hay."""
    matches: int = 0
    """Cargos que salen de la cuenta propuesta."""
    total: int = 0
    """Cargos con origen identificable examinados en total."""


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


class PositionAsOfResponse(BaseModel):
    """PHASE-41 — Patrimonio A FECHA `date_to` + Δ del patrimonio DURANTE
    `[date_from, date_to]`, para que las cards de patrimonio del Análisis
    reflejen el período seleccionado (no una foto de hoy). Mono-divisa
    (`reference_currency`), misma limitación que `compute_position_history`."""

    reference_currency: str
    # Saldos AGREGADOS a fecha `date_to`.
    total_assets: Decimal
    total_liabilities: Decimal
    net_worth: Decimal
    # Δ DURANTE el período (Σ movimientos firmados en el rango).
    delta_assets: Decimal
    delta_net_worth: Decimal


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
