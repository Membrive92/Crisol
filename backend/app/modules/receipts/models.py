"""Modelo ORM de recibos extraídos por IA."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReceiptStatus(enum.StrEnum):
    """Estado del recibo en el flujo IA → confirmación → transacción.

    `pending`: recién extraído por el modelo, esperando confirmación.
    `confirmed`: el usuario validó/editó y se creó la transacción.
    `rejected`: el usuario lo descartó (no se persiste transacción).
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class Receipt(Base):
    """Recibo procesado por el módulo de IA.

    El blob original se guarda en MinIO (`blob_key`); aquí sólo
    persistimos los metadatos y la extracción para auditoría.
    """

    __tablename__ = "receipts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ReceiptStatus] = mapped_column(nullable=False)
    blob_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    extraction: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
