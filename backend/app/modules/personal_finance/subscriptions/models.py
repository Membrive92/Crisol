"""Modelo ORM de subscripciones detectadas (PHASE-13.1)."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SubscriptionStatus(enum.StrEnum):
    """Estado de una subscripción detectada.

    `pending` → el detector la propuso, falta confirmar.
    `confirmed` → el usuario aceptó; aparece en su lista activa y
                  alimenta futuras alertas / recordatorios.
    `dismissed` → el usuario la rechazó (falso positivo); el detector
                  NO la volverá a sugerir aunque vuelva a haber
                  transacciones que matcheen el patrón.
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


class Subscription(Base):
    """Subscripción periódica detectada a partir de transacciones.

    Los campos identificativos (merchant + amount + currency +
    cadence_days) forman la "huella" del patrón. El detector usa esa
    huella para reconocer subscripciones existentes en re-scans en
    lugar de duplicarlas.

    `confidence` ∈ [0,1] mide cuán regular es la cadencia (1 =
    cadencia perfecta sin desviación, 0 = caótica). Lo emite el
    detector heurístico sin IA por ahora — el módulo `ai/` podría
    reforzarlo en una sub-fase futura.
    """

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Normalizado (lowercase + strip non-alphanumeric, primeros 30 chars).
    # Forma parte de la huella usada para reconocer matches en re-scans.
    merchant: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    # Sample sin normalizar — el frontend lo muestra como label legible
    # mientras `merchant` queda interno.
    raw_description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # Cadencia típica de los matches (~30 mensual, ~365 anual, etc.).
    cadence_days: Mapped[int] = mapped_column(Integer, nullable=False)
    # Próxima ejecución estimada (last_seen_at + cadence_days).
    next_due: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        nullable=False, default=SubscriptionStatus.PENDING, index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    first_seen_at: Mapped[date] = mapped_column(Date, nullable=False)
    last_seen_at: Mapped[date] = mapped_column(Date, nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
