"""Schemas Pydantic del módulo subscriptions (PHASE-13.1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.modules.personal_finance.subscriptions.models import SubscriptionStatus


class SubscriptionResponse(BaseModel):
    """Respuesta pública de una subscripción."""

    id: uuid.UUID
    user_id: uuid.UUID
    merchant: str
    raw_description: str
    amount: Decimal
    currency: str
    cadence_days: int
    next_due: date
    status: SubscriptionStatus
    category_id: uuid.UUID | None
    first_seen_at: date
    last_seen_at: date
    occurrence_count: int
    confidence: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScanResponse(BaseModel):
    """Resultado de un scan manual.

    `created` y `updated` separan candidatos nuevos (que el usuario
    debe revisar) vs subscripciones existentes con datos refrescados
    (next_due, occurrence_count, last_seen_at).
    """

    created: int
    updated: int
    total_active_after: int
