"""Schemas Pydantic del módulo receipts."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.modules.ai.schemas import ReceiptExtraction
from app.modules.personal_finance.receipts.models import ReceiptStatus


class ReceiptResponse(BaseModel):
    """Respuesta pública de un recibo, incluida la extracción."""

    id: uuid.UUID
    user_id: uuid.UUID
    status: ReceiptStatus
    blob_key: str
    content_type: str
    extraction: dict[str, Any]
    transaction_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReceiptListResponse(BaseModel):
    """Listado paginado de recibos."""

    items: list[ReceiptResponse]
    total: int
    limit: int
    offset: int


class ReceiptExtractResponse(BaseModel):
    """Respuesta tras subir e invocar al modelo: receipt + extracción tipada."""

    receipt: ReceiptResponse
    extraction: ReceiptExtraction


class ReceiptConfirmRequest(BaseModel):
    """Datos editados por el usuario al confirmar el recibo.

    Se permite reemplazar los valores extraídos para corregir errores
    del modelo. La transacción se crea con estos valores definitivos.
    """

    amount: Decimal = Field(gt=0)
    occurred_at: datetime
    currency: str = Field(min_length=3, max_length=3)
    description: str | None = Field(default=None, max_length=500)
    category_id: uuid.UUID | None = None
