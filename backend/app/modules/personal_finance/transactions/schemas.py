"""Schemas Pydantic del módulo transactions."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.modules.personal_finance.transactions.models import TransactionFlow, TransactionSource


class BudgetAlertSchema(BaseModel):
    """Alerta de presupuesto en estado warning/over (PHASE-14.5).

    Devuelta en `TransactionResponse.budget_alert` cuando una nueva
    tx empuja la categoría afectada al límite. `None` si no hay
    budget aplicable o si está en `ok`.
    """

    budget_id: uuid.UUID
    category_id: uuid.UUID | None
    status: Literal["warning", "over"]
    percent_used: float
    spent_this_month: Decimal
    amount: Decimal
    currency: str
    next_due_label: str = Field(
        description="Texto legible para el toast: 'Comida está al 95%' o similar."
    )


class TransactionCreate(BaseModel):
    """Datos para crear una transacción."""

    account_id: uuid.UUID
    category_id: uuid.UUID | None = None
    amount: Decimal = Field(decimal_places=2, ge=Decimal("0.01"))
    currency: str = Field(default="EUR", max_length=3)
    occurred_at: datetime
    description: str | None = Field(default=None, max_length=500)
    source: TransactionSource = TransactionSource.MANUAL
    # PHASE-34: dirección + transfer-ness del movimiento. Si el form la
    # envía ([Gasto]/[Ingreso]/[Entre mis cuentas]), manda; si no, el
    # service la deriva de la categoría (puente de transición).
    flow: TransactionFlow | None = None
    # PHASE-37.3: override de la clasificación estructural/puntual. NULL =
    # heurística decide (lo normal al crear), TRUE = puntual, FALSE =
    # estructural.
    is_exceptional: bool | None = None

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str) -> str:
        # AUDIT — normalizar la divisa a mayúsculas (las cuentas ya la
        # guardan upper). El saldo por cuenta sólo agrega tx cuya
        # `currency == account.currency`; sin normalizar, una "eur"
        # minúscula quedaría invisible al saldo y al reassign.
        return v.upper()


class TransactionUpdate(BaseModel):
    """Datos para actualizar una transacción (parcial)."""

    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    amount: Decimal | None = Field(default=None, decimal_places=2, ge=Decimal("0.01"))
    currency: str | None = Field(default=None, max_length=3)
    occurred_at: datetime | None = None
    description: str | None = None
    flow: TransactionFlow | None = None
    # PHASE-37.3 — override tri-estado. Con `exclude_unset` en el service,
    # enviar `is_exceptional: null` EXPLÍCITO resetea a heurística; omitir
    # el campo no lo toca. TRUE = puntual, FALSE = estructural.
    is_exceptional: bool | None = None

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str | None) -> str | None:
        return v.upper() if v is not None else v


class TransactionResponse(BaseModel):
    """Respuesta pública de una transacción.

    `converted_amount` y `converted_currency` se rellenan sólo cuando
    el caller pasa `?target_currency=` al endpoint de listado: el
    backend convierte cada fila con la tasa del día de su `occurred_at`
    y la UI puede pintar el equivalente sin lanzar un fetch por fecha.
    En modo legacy o lecturas individuales, ambos son `None`.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    category_id: uuid.UUID | None
    transfer_pair_id: uuid.UUID | None = None
    amount: Decimal
    currency: str
    occurred_at: datetime
    description: str | None
    source: TransactionSource
    # PHASE-34: fuente de verdad de la dirección del dinero. La UI pinta
    # el signo/color y clasifica gasto/ingreso/transferencia desde aquí.
    flow: TransactionFlow | None = None
    # PHASE-37.3: override de la clasificación estructural/puntual (tri-estado).
    # NULL = automático (heurística), TRUE = puntual, FALSE = estructural.
    # La UI del detalle pinta el toggle "Gasto puntual" desde aquí.
    is_exceptional: bool | None = None
    receipt_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    # NULL en activas. Timestamp en papelera (PHASE-10.1) — el endpoint
    # `/transactions/trash` rellena este campo; el listado normal lo
    # devuelve siempre None porque excluye soft-deleted.
    deleted_at: datetime | None = None
    converted_amount: Decimal | None = None
    converted_currency: str | None = None
    # True cuando la tx es una pata de un par de conversión a deuda
    # (activo↔pasivo): la UI la marca "Deuda" en vez de "Transferencia"
    # y pinta el importe en neutro (coherente con el fix activo-fantasma,
    # que hace que la pata-activo aporte 0 al patrimonio). Sólo el
    # endpoint de LISTADO lo computa; el resto de endpoints devuelven
    # `False` (no consumen esta señal).
    is_debt_pair: bool = False
    # PHASE-14.5: sólo viene en la respuesta del POST cuando la tx
    # creada empuja la categoría a warning/over. None en cualquier
    # otro endpoint (list, get, put).
    budget_alert: BudgetAlertSchema | None = None

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    """Respuesta paginada de transacciones."""

    items: list[TransactionResponse]
    total: int
    limit: int
    offset: int
