"""Modelo ORM de presupuestos mensuales (PHASE-12.1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Budget(Base):
    """Presupuesto mensual del usuario, opcionalmente ligado a una categoría.

    `category_id IS NULL` significa "presupuesto global mensual" — cubre
    el gasto total del usuario en el mes. `category_id IS NOT NULL`
    cubre solo gastos de esa categoría.

    `effective_from` / `effective_to` permiten cerrar y crear nuevos
    presupuestos sin perder histórico. Un presupuesto activo tiene
    `effective_to IS NULL` o `>= today`. La política de "un solo
    activo por (user, category) a la vez" se hace en el service —
    sin constraint a nivel BD por simplicidad (el solapamiento podría
    ser válido en futuros casos: presupuestos parciales).
    """

    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
