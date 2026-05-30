"""Modelo ORM de gastos fijos detectados (PHASE-13.1, renombrado en
PHASE-17.1).

Antes "subscriptions" — ahora "fixed_expenses" para reflejar que el
área cubre cualquier gasto recurrente con cantidad estable
(suscripciones, hipotecas, préstamos, cuotas de gym, seguros…).
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FixedExpenseStatus(enum.StrEnum):
    """Estado de un gasto fijo detectado.

    `pending` → el detector lo propuso, falta confirmar.
    `confirmed` → el usuario aceptó; gasto fijo activo.
    `paused` (PHASE-15.2) → temporalmente inactivo; el usuario lo
                pausa sin descartarlo. Mismo bloqueo de re-sugestion
                que confirmed.
    `cancelled` (PHASE-15.2) → el usuario canceló el gasto fijo
                real (cerró su cuenta / saldó el préstamo). NO es lo
                mismo que dismissed: cancelled = "sí era un gasto
                fijo, ya no lo tengo"; dismissed = "el detector se
                equivocó".
    `dismissed` → el detector se equivocó (falso positivo); NO se
                  volverá a sugerir aunque siga el patrón.
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    DISMISSED = "dismissed"


class FixedExpense(Base):
    """Gasto fijo recurrente detectado a partir de transacciones.

    Los campos identificativos (merchant + amount + currency +
    cadence_days) forman la "huella" del patrón. El detector usa esa
    huella para reconocer gastos fijos existentes en re-scans en
    lugar de duplicarlos.

    `confidence` ∈ [0,1] mide cuán regular es la cadencia (1 =
    cadencia perfecta sin desviación, 0 = caótica). Lo emite el
    detector heurístico sin IA por ahora — el módulo `ai/` podría
    reforzarlo en una sub-fase futura.
    """

    __tablename__ = "fixed_expenses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    merchant: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    raw_description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    cadence_days: Mapped[int] = mapped_column(Integer, nullable=False)
    next_due: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[FixedExpenseStatus] = mapped_column(
        nullable=False, default=FixedExpenseStatus.PENDING, index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    # PHASE-19.1: cuenta desde la que se cobra el gasto fijo. Nullable
    # porque los gastos fijos detectados antes de declarar cuentas
    # quedan sin asignar. El cron de auto-post sólo crea la tx
    # `expected` si `account_id IS NOT NULL` — sin cuenta no se puede
    # imputar la transacción.
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    first_seen_at: Mapped[date] = mapped_column(Date, nullable=False)
    last_seen_at: Mapped[date] = mapped_column(Date, nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # PHASE-17.2: si True, el cron diario crea una tx `source=expected`
    # cuando `next_due` cae en o antes de hoy y avanza `next_due` un
    # ciclo. Off por defecto al confirmar — el usuario lo activa
    # explícitamente para los gastos fijos seguros (hipoteca, gym,
    # Netflix); para cargos variables (luz/gas) lo deja off.
    auto_post: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
