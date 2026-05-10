"""Schemas Pydantic del módulo transfers (PHASE-19.3)."""

from __future__ import annotations

import uuid
from datetime import datetime
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
