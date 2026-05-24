"""Schemas Pydantic del módulo imports."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.modules.personal_finance.imports.models import ImportJobStatus

# Campos del CSV/XLSX que el cliente puede mapear.
TARGET_FIELDS = ("amount", "occurred_at", "description", "category_name")


class ImportSource(enum.StrEnum):
    """Cómo se obtuvieron las filas del preview.

    `pdfplumber_smart` — heurística sobre tablas extraídas (extractos
    bancarios reales con varias tablas). Mapping ignorado.
    `pdfplumber_legacy` — extracción cruda concatenando todas las
    tablas; el usuario aporta el mapping de columnas.
    `vision` — fallback a IA local cuando pdfplumber no extrae nada.
    `csv` / `xlsx` — formatos tabulares simples con mapping del usuario.
    """

    PDFPLUMBER_SMART = "pdfplumber_smart"
    PDFPLUMBER_LEGACY = "pdfplumber_legacy"
    VISION = "vision"
    CSV = "csv"
    XLSX = "xlsx"
    XLSX_SMART = "xlsx_smart"


class ImportColumnMappings(BaseModel):
    """Mapeo de campos del dominio → nombre de columna en el fichero.

    Sólo `amount` y `occurred_at` son obligatorios. `description` y
    `category_name` son opcionales.
    """

    amount: str = Field(min_length=1, max_length=255)
    occurred_at: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    category_name: str | None = Field(default=None, max_length=255)


class ImportPreviewRow(BaseModel):
    """Fila parseada lista para mostrar al usuario en preview.

    Los importes ya vienen como string en el formato original del
    fichero (con coma o punto decimal, con o sin signo). El frontend
    los muestra tal cual. La validación final ocurre en el commit.
    """

    amount: str
    occurred_at: str
    description: str | None = None
    category_name: str | None = None


class ImportPreviewBankConceptGroup(BaseModel):
    """Grupo de filas con el mismo concepto del banco para mapeo masivo.

    El frontend muestra un dropdown por concepto único; al confirmar,
    el commit recibe el mapping `concept → category_id` y aplica la
    categoría a todas las filas del grupo + guarda la equivalencia.

    Campos de sugerencia (en orden de prioridad — el frontend usa el
    primer no-null):

    - `suggested_category_id` — sugerencia automática del backend.
      Viene de: equivalencia exacta `bank_category_mappings` previa,
      o de la regla que matchea (rules engine). El frontend lo
      preselecciona en el dropdown.
    - `suggestion_source` — etiqueta de procedencia para la UI
      (`saved_mapping` | `rule` | `ai`). `None` si no hay sugerencia.
    - `has_mixed_rule_matches` — `True` cuando las filas del grupo
      resuelven a categorías DIFERENTES por reglas (típicamente porque
      la `description` matchea reglas distintas entre filas). En ese
      caso, `suggested_category_id` es `None` y el frontend explica
      al usuario que las reglas se aplicarán fila a fila en el commit.
    """

    concept: str
    count: int
    suggested_category_id: uuid.UUID | None = None
    suggestion_source: str | None = None
    has_mixed_rule_matches: bool = False


class ImportPreviewResponse(BaseModel):
    """Respuesta del endpoint POST /imports/preview.

    El frontend usa `job_id` para confirmar (POST /imports/{id}/commit).
    `source` indica de qué pipeline vienen las filas — útil para
    el toggle de "reintentar con IA" en la UI.
    `bank_concept_groups` agrupa las filas por su `category_name`
    (concepto del banco) para mapeo masivo a categorías del usuario.
    Vacío si las filas no traen concepto (CSV sin columna categoría).
    """

    job_id: uuid.UUID
    source: ImportSource
    total_rows: int
    rows: list[ImportPreviewRow]
    bank_concept_groups: list[ImportPreviewBankConceptGroup] = Field(
        default_factory=list
    )
    error_sample: list[str] = Field(default_factory=list)


class ImportCommitRequest(BaseModel):
    """Body opcional del endpoint POST /imports/{id}/commit.

    `category_overrides` mapea `concepto banco normalizado → category_id`.
    Cualquier fila cuyo concepto matchee se importa con esa categoría
    y la equivalencia se guarda para futuras importaciones.
    """

    category_overrides: dict[str, uuid.UUID] = Field(default_factory=dict)


class ImportErrorEntry(BaseModel):
    """Entrada del log de errores. Capada a 100 elementos en el job."""

    row: int
    error: str


class ImportJobResponse(BaseModel):
    """Respuesta pública de un job de importación."""

    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID | None
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
