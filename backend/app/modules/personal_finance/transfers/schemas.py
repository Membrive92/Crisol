"""Schemas Pydantic del módulo transfers (PHASE-19.3)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class TransferCandidate(BaseModel):
    """Par sugerido por el matcher heurístico para que el usuario lo
    confirme. La heurística no marca nada en BD por sí sola — sólo el
    enlace explícito (manual o vía endpoint match) escribe `transfer_pair_id`.
    """

    out_transaction_id: uuid.UUID
    in_transaction_id: uuid.UUID
    amount: Decimal
    currency: str
    out_account_id: uuid.UUID
    in_account_id: uuid.UUID
    out_occurred_at: datetime
    in_occurred_at: datetime
    delta_days: int


class TransferLinkRequest(BaseModel):
    """Body de POST /transfers/link — enlazar manualmente dos txs."""

    out_transaction_id: uuid.UUID
    in_transaction_id: uuid.UUID


class TransferMatchOptions(BaseModel):
    """Body opcional de POST /transfers/match — afinar la heurística."""

    window_days: int = Field(default=3, ge=0, le=14)
    """Tolerancia (en días) entre `occurred_at` de salida y entrada."""


class TransferMatchResponse(BaseModel):
    """Resultado del matcher tras enlazar todos los pares no ambiguos."""

    linked_count: int
    """Pares que el matcher pudo enlazar automáticamente (sin ambigüedad)."""
    pending_candidates: list[TransferCandidate]
    """Pares ambiguos que requieren intervención del usuario (mismo
    importe + ventana coincide pero hay >1 entrada/salida candidata
    para alguna mitad)."""


class TransferPairResponse(BaseModel):
    """Vista compacta de un par ya emparejado."""

    out_transaction_id: uuid.UUID
    in_transaction_id: uuid.UUID
    amount: Decimal
    currency: str
    out_account_id: uuid.UUID
    in_account_id: uuid.UUID
    out_occurred_at: datetime
    in_occurred_at: datetime
    delta_days: int
    # PHASE-34: importe del "cargo espejo" anulado al registrar la operación
    # financiada (el ADEUDO del mismo importe que en el banco la compensa,
    # neto 0). `None` si no se encontró espejo. La UI lo usa para avisar en
    # el toast que ese cargo se ha movido a la papelera.
    absorbed_mirror_amount: Decimal | None = None


class TransferSuspect(BaseModel):
    """PHASE-23: tx sin pareja cuya descripción matchea el patrón
    "transferencia" — candidata a ser marcada manualmente como
    transferencia interna cuando sólo se importó una pata.
    """

    transaction_id: uuid.UUID
    amount: Decimal
    currency: str
    account_id: uuid.UUID
    occurred_at: datetime
    description: str | None
    current_category_id: uuid.UUID | None
    current_category_name: str | None


class MisclassifiedTransfer(BaseModel):
    """PHASE-31.2 — tx con categoría is_transfer cuyo kind no encaja
    con la dirección que indica la descripción. Candidata a recategorización
    en bloque desde la UI.
    """

    transaction_id: uuid.UUID
    amount: Decimal
    currency: str
    account_id: uuid.UUID
    occurred_at: datetime
    description: str | None
    current_category_id: uuid.UUID
    current_category_name: str
    current_category_kind: str
    suggested_kind: str
    """`income` si la descripción es entrante, `expense` si es saliente."""


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


class TransferMarkRequest(BaseModel):
    """PHASE-23: marcar una tx como transferencia interna asignándole
    una categoría kind=transfer. Si el usuario no tiene ninguna, el
    backend crea una por defecto ("Transferencia interna").
    """

    transaction_id: uuid.UUID


class TransferMarkResponse(BaseModel):
    """Resultado de marcar una tx — devuelve la categoría asignada
    para que la UI refresque los listados."""

    transaction_id: uuid.UUID
    category_id: uuid.UUID
    category_name: str


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
