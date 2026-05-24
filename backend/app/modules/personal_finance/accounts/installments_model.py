"""Modelo ORM de cuotas persistidas de liabilities (PHASE-24.1).

Las cuotas se generan al crear/registrar una liability con `apr +
term_months + start_date`. A partir de ahí el usuario puede:
- Editar el importe / fecha de cuotas concretas (BBVA cobra algo
  ligeramente distinto al cuadro francés ideal).
- Marcar cuotas como pagadas (opcionalmente enlazando la tx que las
  pagó del extracto).

Las ediciones NO recomputan las cuotas siguientes — son overrides
puntuales. El cuadro mantiene la estructura original (intereses
decrecientes, principal creciente) salvo donde el usuario ajustó.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LiabilityInstallment(Base):
    """Cuota individual del cuadro de amortización de una liability."""

    __tablename__ = "liability_installments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    installment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    """1..term_months. Determina el orden en la UI."""
    due_date: Mapped[date] = mapped_column(nullable=False)
    payment: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    interest: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    principal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    remaining_balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """NULL = pendiente. Timestamp = pagada."""
    paid_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    """Tx del extracto que liquidó la cuota — opcional, sólo informativo."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        # Una cuota número N por cada cuenta — evita duplicados al
        # regenerar el cuadro y permite UPSERT por (account_id, index).
        UniqueConstraint(
            "account_id",
            "installment_index",
            name="uq_liability_installments_account_index",
        ),
    )
