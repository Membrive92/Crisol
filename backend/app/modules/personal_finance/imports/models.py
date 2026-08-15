"""Modelo ORM de jobs de importación."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ImportJobStatus(enum.StrEnum):
    """Estado de un job de importación.

    `pending` solo se usa transitoriamente al crear el job. El flujo
    directo (POST /imports) pasa por `processing` → `completed`/`failed`.
    El flujo en dos pasos (POST /imports/preview → POST /imports/{id}/commit)
    crea el job en `preview` para que el usuario revise; al confirmar
    pasa a `processing` → `completed`. Si el usuario abandona, el job
    queda en `preview` (no se purga automáticamente — puede listarse
    y reanudarse).
    """

    PENDING = "pending"
    PROCESSING = "processing"
    PREVIEW = "preview"
    COMPLETED = "completed"
    FAILED = "failed"


class ImportJob(Base):
    """Job de importación de transacciones desde un fichero CSV/XLSX."""

    __tablename__ = "import_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # PHASE-19.1: cuenta a la que se imputaron las txs de este lote.
    # Nullable: jobs antiguos / fallidos / preview sin cuenta elegida
    # quedan en NULL. Las txs persistidas conservan su `account_id`
    # propio en `transactions.account_id` — este campo es para
    # auditoría/UX (filtrar imports por cuenta).
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ImportJobStatus] = mapped_column(nullable=False)
    rows_total: Mapped[int] = mapped_column(nullable=False, default=0)
    rows_ok: Mapped[int] = mapped_column(nullable=False, default=0)
    rows_failed: Mapped[int] = mapped_column(nullable=False, default=0)
    rows_skipped: Mapped[int] = mapped_column(nullable=False, default=0)
    column_mappings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error_log: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    # Payload del preview (PHASE-18+): filas parseadas + metadata para el
    # commit posterior. NULL en jobs antiguos y en jobs creados por el
    # flujo directo (POST /imports). Estructura:
    #   {
    #     "rows": [{"amount": "29,66", "occurred_at": "25/02/2026", ...}],
    #     "effective_mappings": {...},
    #     "currency": "EUR",
    #     "default_category_id": "uuid|null",
    #     "source": "pdfplumber_smart" | "pdfplumber_legacy" | "vision",
    #   }
    preview_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    header_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """PHASE-47.A — SHA-256 de la cabecera normalizada del fichero. Identifica
    el FORMATO (qué producto del banco lo exportó), no el contenido, para poder
    avisar cuando un fichero con el formato de otra cuenta se está importando
    a ésta. NULL en jobs anteriores a 47.A que el backfill no pudo derivar y en
    los que fallaron antes de parsear."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
