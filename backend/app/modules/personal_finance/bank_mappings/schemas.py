"""Schemas Pydantic del módulo bank_mappings."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BankCategoryMappingCreate(BaseModel):
    """Crea o actualiza una equivalencia concepto banco → categoría.

    Si ya existe una equivalencia para `bank_concept` en este usuario,
    se reemplaza la `category_id` (UPSERT). El `bank_concept` se
    normaliza con `casefold` antes de guardar para que el matching
    sea consistente.
    """

    bank_concept: str = Field(min_length=1, max_length=255)
    category_id: uuid.UUID


class BankCategoryMappingResponse(BaseModel):
    """Respuesta pública de una equivalencia."""

    id: uuid.UUID
    user_id: uuid.UUID
    bank_concept: str
    category_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BankCategoryMappingListResponse(BaseModel):
    items: list[BankCategoryMappingResponse]
