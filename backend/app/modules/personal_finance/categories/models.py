"""Modelo ORM de categorías."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CategoryKind(enum.StrEnum):
    """Tipo de categoría: ingreso o gasto.

    El kind determina el SIGNO con el que la tx afecta al balance de
    la cuenta. La marca "transferencia interna" (que excluye del
    cashflow pero conserva el signo en el balance) vive en el flag
    `Category.is_transfer` — separar ambas responsabilidades (signo
    vs. exclusión) evita que las transferencias rompan el cálculo de
    saldos (PHASE-23.1).
    """

    INCOME = "income"
    EXPENSE = "expense"


class CategoryRole(enum.StrEnum):
    """PHASE-30.1 — Rol semántico de la categoría dentro del producto.

    Sustituye al frozenset `INTEREST_CATEGORY_NAMES` (acoplado a strings
    en español) y absorbe el flag `is_transfer` en un único atributo
    declarativo. Los callers que necesitan "todas las categorías de
    deuda" (debt_health, debt_history, /debt/category-summary) filtran
    por `role IN (DEBT_PAYMENT, DEBT_INTEREST)`.

    Mientras el módulo de deuda en dos capas (PHASE-30) está en
    desarrollo, `is_transfer` se mantiene en la columna por
    compatibilidad — la migración lo replica en `role=TRANSFER`. Su
    eliminación queda como follow-up cuando todos los callers
    consuman `role`.
    """

    GENERIC = "GENERIC"
    """Categoría normal — la mayoría."""
    TRANSFER = "TRANSFER"
    """Transferencia interna — fuera del cashflow."""
    DEBT_PAYMENT = "DEBT_PAYMENT"
    """Pago de cuota de deuda (capital + intereses mezclados)."""
    DEBT_INTEREST = "DEBT_INTEREST"
    """Intereses puros + comisiones financieras de deuda."""


class Category(Base):
    """Tabla de categorías de gasto/ingreso por usuario."""

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    kind: Mapped[CategoryKind] = mapped_column(nullable=False)
    # PHASE-23.1: si True, las txs con esta categoría son transferencias
    # internas y quedan fuera de cashflow (dashboard, presupuestos), pero
    # SIGUEN contribuyendo al saldo de la cuenta con el signo dictado
    # por `kind`. Sustituye al difunto `CategoryKind.TRANSFER`.
    is_transfer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    role: Mapped[CategoryRole] = mapped_column(
        Enum(CategoryRole, name="categoryrole", native_enum=True),
        nullable=False,
        server_default=CategoryRole.GENERIC.value,
    )
    """PHASE-30.1 — rol semántico (ver `CategoryRole`). El backfill de
    la migración lo deriva de `is_transfer` y de los nombres del seed
    (Intereses *, Préstamos e hipotecas, Tarjeta de crédito)."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
