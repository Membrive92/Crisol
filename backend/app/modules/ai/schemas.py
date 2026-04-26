"""Schemas Pydantic del módulo ai."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AiHealthResponse(BaseModel):
    """Respuesta del endpoint /ai/health."""

    status: str
    ollama: str
    model: str
    model_available: bool


class ReceiptLineItem(BaseModel):
    """Línea individual del ticket extraída por el modelo."""

    description: str = Field(min_length=1, max_length=255)
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    total: Decimal


class ReceiptExtraction(BaseModel):
    """Resultado de la extracción de un ticket por el modelo de visión.

    Estructura validada con Pydantic — si el modelo devuelve algo que no
    encaja, `ai.service.extract_receipt` lanza `AiInvalidOutputError`.
    """

    model_config = ConfigDict(extra="ignore")

    merchant: str | None = Field(default=None, max_length=255)
    occurred_at: datetime | None = None
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    total: Decimal
    tax: Decimal | None = None
    line_items: list[ReceiptLineItem] = Field(default_factory=list)
    raw_text: str | None = Field(default=None, max_length=5000)
