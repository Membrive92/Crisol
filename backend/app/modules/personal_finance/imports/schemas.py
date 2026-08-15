"""Schemas Pydantic del módulo imports."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.modules.personal_finance.imports.models import ImportJobStatus

# Campos del CSV/XLSX que el cliente puede mapear.
TARGET_FIELDS = ("amount", "occurred_at", "description", "category_name", "statement_balance")


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
    # PHASE-39 — columna Saldo del extracto (saldo de la cuenta tras cada
    # movimiento). Opcional: se usa para anclar el saldo real al confirmar.
    statement_balance: str | None = Field(default=None, max_length=255)


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
    # PHASE-39 — saldo del extracto tras el movimiento (formato original).
    statement_balance: str | None = None


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


class ImportWarningKey(enum.StrEnum):
    """PHASE-47.A — Avisos del guardarraíl de cuenta equivocada."""

    HEADER_MATCHES_OTHER_ACCOUNT = "header_matches_other_account"
    """El formato del fichero coincide con el de imports de otra cuenta."""
    ROWS_EXIST_IN_OTHER_ACCOUNT = "rows_exist_in_other_account"
    """Una parte de las filas ya existe en transacciones de otra cuenta."""


class ImportWarning(BaseModel):
    """Aviso BLOQUEABLE, no prohibición: el usuario puede tener razón.

    Confirmar exige devolver su `key` en `acknowledged_warnings` — un tick
    explícito, no un banner que se lee de reojo. `message` va en español y con
    los números dentro para que la decisión sea informada.
    """

    key: ImportWarningKey
    message: str
    account_id: uuid.UUID | None = None
    """Cuenta con la que se ha detectado el parecido, si la hay."""
    account_name: str | None = None
    matched_rows: int = 0
    total_rows: int = 0


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
    bank_concept_groups: list[ImportPreviewBankConceptGroup] = Field(default_factory=list)
    error_sample: list[str] = Field(default_factory=list)
    warnings: list[ImportWarning] = Field(default_factory=list)
    """PHASE-47.A — Sospechas de que el fichero no es de la cuenta elegida.
    Confirmar exige reconocerlas una a una (`acknowledged_warnings`)."""


class ImportCommitRequest(BaseModel):
    """Body opcional del endpoint POST /imports/{id}/commit.

    `category_overrides` mapea `concepto banco normalizado → category_id`.
    Cualquier fila cuyo concepto matchee se importa con esa categoría
    y la equivalencia se guarda para futuras importaciones.
    """

    category_overrides: dict[str, uuid.UUID] = Field(default_factory=dict)
    acknowledged_warnings: list[ImportWarningKey] = Field(default_factory=list)
    """PHASE-47.A — Avisos que el usuario declara haber leído. Si falta alguno
    de los emitidos en el preview, el commit devuelve 409 con la lista."""


class ImportErrorEntry(BaseModel):
    """Entrada del log de errores. Capada a 100 elementos en el job."""

    row: int
    error: str


class ImportBalanceAnchor(BaseModel):
    """PHASE-39 — resultado del auto-anclaje del saldo al confirmar.

    Cuando el extracto trae columna Saldo, el commit ancla el saldo de la
    cuenta al del movimiento más reciente del fichero (misma semántica que
    "Cuadrar saldo", pero a la fecha del extracto). `balance` es el saldo
    declarado por el banco; `date` la fecha (ISO) de ese movimiento.
    """

    balance: str
    date: str


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
    # PHASE-39 — presente sólo cuando el commit ancló el saldo (se rellena
    # desde `preview_payload["balance_anchor"]` en el router; no es columna).
    balance_anchor: ImportBalanceAnchor | None = None

    model_config = {"from_attributes": True}


class ImportJobListResponse(BaseModel):
    """Respuesta paginada de jobs."""

    items: list[ImportJobResponse]
    total: int
    limit: int
    offset: int
