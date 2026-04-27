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

    `pending` solo se usa transitoriamente al crear el job; en el flujo
    síncrono actual el job pasa directamente a `processing` y termina
    en `completed` o `failed`.
    """

    PENDING = "pending"
    PROCESSING = "processing"
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
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ImportJobStatus] = mapped_column(nullable=False)
    rows_total: Mapped[int] = mapped_column(nullable=False, default=0)
    rows_ok: Mapped[int] = mapped_column(nullable=False, default=0)
    rows_failed: Mapped[int] = mapped_column(nullable=False, default=0)
    rows_skipped: Mapped[int] = mapped_column(nullable=False, default=0)
    column_mappings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error_log: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
