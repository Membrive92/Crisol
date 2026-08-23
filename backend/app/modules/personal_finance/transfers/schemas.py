"""Schemas Pydantic del módulo transfers (PHASE-19.3)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.core.civil_dates import CivilDatetime


class TransferLinkRequest(BaseModel):
    """Body de POST /transfers/link — enlazar manualmente dos txs.

    Load-bearing: lo usa el asistente de pago de deuda para crear el par
    principal. El emparejado heurístico (match/candidates) se retiró en
    PHASE-41 (ADR-0005) — la verdad del dinero vive en `transactions.flow`.
    """

    out_transaction_id: uuid.UUID
    in_transaction_id: uuid.UUID


class TransferPairResponse(BaseModel):
    """Vista compacta de un par ya emparejado."""

    out_transaction_id: uuid.UUID
    in_transaction_id: uuid.UUID
    amount: Decimal
    currency: str
    out_account_id: uuid.UUID
    in_account_id: uuid.UUID
    out_occurred_at: CivilDatetime
    in_occurred_at: CivilDatetime
    delta_days: int


class MisclassifiedTransfer(BaseModel):
    """PHASE-31.2 — tx con categoría is_transfer cuyo kind no encaja
    con la dirección que indica la descripción. Candidata a recategorización
    en bloque desde la UI.
    """

    transaction_id: uuid.UUID
    amount: Decimal
    currency: str
    account_id: uuid.UUID
    occurred_at: CivilDatetime
    description: str | None
    current_category_id: uuid.UUID
    current_category_name: str
    current_category_kind: str
    suggested_kind: str
    """`income` si la descripción es entrante, `expense` si es saliente."""


class FinancingMatchResponse(BaseModel):
    """PHASE-46 — un abono de financiación y la deuda a la que parece pertenecer.

    Lo que el banco te abona cuando aplaza algo NO es un ingreso, y además tiene
    una deuda detrás. Esta propuesta une las dos mitades: la transacción que
    entró en la cuenta y el cuadro de amortización que el usuario ya dio de
    alta, reconocidos por el capital y no por la redacción del extracto.
    """

    transaction_id: uuid.UUID
    description: str | None
    amount: Decimal
    currency: str
    occurred_at: CivilDatetime
    counted_as_income: bool
    """`True` si HOY está sumando en la gráfica de ingresos — el estado a corregir."""
    liability_id: uuid.UUID
    liability_name: str
    schedule_principal: Decimal
    reason: str
    """Por qué se propone, en lenguaje llano, para que la pantalla explique."""


class ReclassifyBulkRequest(BaseModel):
    """PHASE-31.2 — recategorizar en bloque tx detectadas como
    mal direccionadas. Si no se pasa `target_category_id`, el service
    busca/crea la categoría is_transfer del kind opuesto al actual de
    cada tx (uno a uno: una tx entrante mal puesta en EXPENSE va a
    INCOME; una saliente mal puesta en INCOME va a EXPENSE).
    """

    transaction_ids: list[uuid.UUID]
    target_category_id: uuid.UUID | None = None


class ReclassifyBulkResponse(BaseModel):
    reclassified: int
    errors: list[str]


class TransferFromSourceRequest(BaseModel):
    """PHASE-23.1: convertir una tx existente en una transferencia
    interna entre dos cuentas del usuario.

    El usuario marca explícitamente quién es la cuenta **ordenante**
    (de donde sale el dinero) y quién la **beneficiaria** (donde
    entra). El backend valida que la tx origen pertenezca a una de
    las dos y deriva los signos a partir de ahí — esto corrige
    el bug en que la dirección se infería de `category.kind` y
    fallaba cuando un import asignaba "Transferencias (Gasto)" a
    abonos por igual que a cargos.

    Reglas:
      - `source_tx.account_id` debe ser `originating_account_id`
        o `beneficiary_account_id` (si no, 400).
      - Las dos cuentas deben ser distintas, del mismo usuario y de
        la misma moneda que la tx (cross-currency es follow-up).
      - La categoría de la tx origen se fuerza a la kind correcta
        (INCOME si es beneficiaria, EXPENSE si es ordenante) para
        que el saldo de su cuenta refleje el signo real.
    """

    source_transaction_id: uuid.UUID
    originating_account_id: uuid.UUID
    beneficiary_account_id: uuid.UUID


class NewLiabilityForDebt(BaseModel):
    """PHASE-24: datos para crear una cuenta liability al vuelo cuando
    se convierte una tx en operación financiada. Mismos campos que
    `AccountCreate` pero limitados a lo relevante para deuda.
    """

    name: str = Field(min_length=1, max_length=100)
    type: str  # AccountType StrEnum value (credit_card | loan | mortgage)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    parent_account_id: uuid.UUID | None = None
    """PHASE-35 — si se indica, la nueva deuda se crea como compra a plazos
    anidada bajo esa tarjeta de crédito (con su propio cuadro). Fuerza
    `type=credit_card` y exige TIN + plazo."""
    color: str | None = Field(default=None, max_length=7)
    icon: str | None = Field(default=None, max_length=50)
    apr: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"), decimal_places=4)
    """TIN — usado para el cálculo del cuadro."""
    tae: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"), decimal_places=4)
    """PHASE-24.2 — TAE (informativa)."""
    term_months: int | None = Field(default=None, ge=1, le=600)
    start_date: date | None = None
    total_to_pay: Decimal | None = Field(default=None, ge=Decimal("0"), decimal_places=2)
    """PHASE-24.3 — Total contractualizado (banco)."""
    interest_only_first_payment: Decimal | None = Field(
        default=None, ge=Decimal("0"), decimal_places=2
    )
    """PHASE-24.3 — Primera cuota especial sólo de intereses."""


class AmortizationRequest(BaseModel):
    """PHASE-45: declarar que un movimiento del banco amortiza una deuda.

    `counts_as_expense` es EXPLÍCITO y no se infiere del tipo de cuenta: la
    misma operación es gasto o no según si ese dinero YA se contó al comprar
    (generaliza la lección de PHASE-28, "la dirección se declara, no se
    adivina"). En `dry_run` puede omitirse y el servidor devuelve su sugerencia
    con el motivo; al aplicar es obligatorio.
    """

    source_transaction_id: uuid.UUID
    liability_account_id: uuid.UUID
    counts_as_expense: bool | None = None
    dry_run: bool = False


class AmortizationEffect(BaseModel):
    """Qué le pasa (o le pasaría) a la deuda con esta amortización."""

    source_transaction_id: uuid.UUID
    liability_account_id: uuid.UUID
    liability_account_name: str
    amount: Decimal
    currency: str
    counts_as_expense: bool
    """El valor EFECTIVO: lo que declaró el usuario, o la sugerencia en dry-run."""
    suggested_counts_as_expense: bool
    suggestion_reason: str
    """Por qué el servidor sugiere eso — se pinta al lado de la elección."""
    mode: str
    """`schedule` (la deuda baja marcando cuotas) | `movement` (baja por el
    movimiento contrario en la cuenta de deuda)."""
    installments_marked: int
    """0 en modo `movement`. En modo `schedule`, cuántas cuotas cubre el pago."""
    principal_covered: Decimal
    """Capital que amortiza de verdad. En modo `schedule` es Σ del principal de
    las cuotas cubiertas (NO el importe pagado: los intereses no amortizan)."""
    principal_uncovered: Decimal
    """Lo que sobra sin llegar a completar la siguiente cuota (modo `schedule`).
    Igual al importe entero cuando el pago no cubre ni una: ahí el saldo NO baja."""
    outstanding_before: Decimal
    outstanding_after: Decimal
    counterpart_transaction_id: uuid.UUID | None = None
    """La pata creada en la cuenta de deuda (modo `movement`). `None` en modo
    `schedule` — ahí manda el cuadro y un movimiento sería invisible."""
    paired: bool = False
    """True si las dos patas quedaron emparejadas (sólo cuando NO es gasto)."""
    dry_run: bool = False


class TransferFromSourceDebtRequest(BaseModel):
    """PHASE-24: convertir una tx en operación financiada.

    Exactamente uno de los dos debe venir:
    - `destination_account_id`: liability existente del usuario.
    - `new_liability`: crear una nueva cuenta liability al vuelo
      (típicamente para registrar un préstamo/tarjeta financiada por
      primera vez).
    """

    source_transaction_id: uuid.UUID
    destination_account_id: uuid.UUID | None = None
    new_liability: NewLiabilityForDebt | None = None
