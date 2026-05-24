"""Modelo ORM de cuentas del usuario (PHASE-19.1)."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AccountType(enum.StrEnum):
    """Tipo de cuenta. Los `liability` quedan reservados para PHASE-20.

    El enum se declara completo desde 19.1 (incluyendo los de deuda)
    para evitar una migración Alembic adicional cuando llegue PHASE-20.
    Los routers/UI sólo exponen los `asset` por ahora.
    """

    BANK = "bank"
    SAVINGS = "savings"
    BROKERAGE = "brokerage"
    CRYPTO = "crypto"
    CASH = "cash"
    # Reservados para PHASE-20 (módulo deuda).
    CREDIT_CARD = "credit_card"
    LOAN = "loan"
    MORTGAGE = "mortgage"


class AccountNature(enum.StrEnum):
    """Naturaleza de la cuenta. Determina el signo del saldo.

    - `asset` → saldo positivo aumenta patrimonio.
    - `liability` → saldo positivo representa deuda (resta del patrimonio).

    Patrimonio neto = Σ(asset balances) − Σ(liability balances).
    """

    ASSET = "asset"
    LIABILITY = "liability"


class Account(Base):
    """Cuenta del usuario.

    `currency` es la divisa nativa de la cuenta (ej. cuenta BBVA EUR,
    broker IBKR USD). Una transacción puede estar en otra divisa que
    la de la cuenta — la conversión vive en el módulo de tipos de
    cambio. La currency es informativa para la UI y por defecto las
    transacciones de esta cuenta se asumen en esta divisa.

    `opening_balance` (+ `opening_balance_date`) permiten que el saldo
    calculado coincida con el saldo real desde el día que el usuario
    empieza a registrar transacciones. Por defecto 0.

    `is_archived` permite ocultar cuentas que ya no se usan sin perder
    el histórico de transacciones asociadas (esas se conservan; sólo
    desaparece la cuenta del selector y de los agregados activos).
    """

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[AccountType] = mapped_column(nullable=False)
    nature: Mapped[AccountNature] = mapped_column(
        nullable=False, default=AccountNature.ASSET, server_default="ASSET"
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    opening_balance_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # PHASE-22.3: cuadro de amortización opcional para liabilities tipo
    # `loan` / `mortgage`. Con APR + plazo + fecha de inicio, el backend
    # genera la tabla francesa (cuota constante, intereses decrecientes,
    # principal creciente). Tarjetas no usan estos campos — su saldo es
    # arrastrado sin plan fijo. NULLABLE en todos para no romper assets.
    apr: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4), nullable=True
    )
    """TIN — tipo de interés nominal anual como decimal
    (0.035 = 3.5% TIN). Se usa para calcular cuota e intereses del
    cuadro francés. NULL = sin cuadro. Mantenemos el nombre `apr`
    por compatibilidad con migraciones previas; el label en la UI es
    "TIN"."""
    tae: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4), nullable=True
    )
    """PHASE-24.2 — TAE: tasa anual equivalente (informativa, no
    afecta al cálculo). Obligatoria por regulación bancaria española;
    incluye comisiones + capitalización. NULL = no declarada."""
    term_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """Plazo total en meses. NULL = sin cuadro."""
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    """Fecha de inicio del préstamo. NULL = sin cuadro."""
    total_to_pay: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    """PHASE-24.3 — total contractualizado por el banco (incluye
    posibles comisiones/cargos no desglosados). Si está, la diferencia
    con `Σ(cuotas) + interest_only_first_payment` aflora como
    'cargos extra' en el cuadro de amortización. NULL = el cuadro
    teórico es exacto, sin cargos ocultos."""
    interest_only_first_payment: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    """PHASE-24.3 — primera cuota especial sólo de intereses cuando el
    contrato no arranca en una fecha de cuota (ej. financias el 15 y
    las cuotas son día 5 → mes 1 sólo paga intereses del medio mes).
    NULL = no aplica."""
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
