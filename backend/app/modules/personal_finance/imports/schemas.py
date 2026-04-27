"""Schemas Pydantic del módulo imports."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.modules.personal_finance.imports.models import ImportJobStatus

# Campos del CSV/XLSX que el cliente puede mapear.
TARGET_FIELDS = ("amount", "occurred_at", "description", "category_name")


class ImportColumnMappings(BaseModel):
    """Mapeo de campos del dominio → nombre de columna en el fichero.

    Sólo `amount` y `occurred_at` son obligatorios. `description` y
    `category_name` son opcionales.
    """

    amount: str = Field(min_length=1, max_length=255)
    occurred_at: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    category_name: str | None = Field(default=None, max_length=255)


class ImportErrorEntry(BaseModel):
    """Entrada del log de errores. Capada a 100 elementos en el job."""

    row: int
    error: str


class ImportJobResponse(BaseModel):
    """Respuesta pública de un job de importación."""

    id: uuid.UUID
    user_id: uuid.UUID
    filename: str
    status: ImportJobStatus
    rows_total: int
    rows_ok: int
    rows_failed: int
    rows_skipped: int
    column_mappings: dict[str, Any]
    error_log: list[ImportErrorEntry]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ImportJobListResponse(BaseModel):
    """Respuesta paginada de jobs."""

    items: list[ImportJobResponse]
    total: int
    limit: int
    offset: int
