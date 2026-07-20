"""Modelos de la Tab Cartera (PHASE-44.1, ARCHITECTURE §2.2).

Tablas **SCOPED** por usuario (`user_id`), a diferencia del catálogo/
fundamentales (globales [Dec.11]). La **posición NO es tabla**: se deriva de
lotes − allocations (evita el bug clásico de desincronización). El FIFO es
GLOBAL por security (pool único, criterio AEAT [Dec.10]); `account_id` es
informativo/opcional.

Convención monetaria: `Decimal` en todo. Cantidades `NUMERIC(20,8)` (admiten
fracciones de acción), precios `NUMERIC(20,6)`, FX `NUMERIC(16,8)`.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.investment.enums import CorpActionType, pg_enum


class Lot(Base):
    """Compra: un lote de acciones a un precio y fecha. El FIFO consume lotes en
    orden de `trade_date` (pool global por security)."""

    __tablename__ = "inv_lots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    security_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("securities.id"), nullable=False)
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    """Cuenta de broker — informativo [Dec.10]. El FIFO es global por security,
    no por cuenta; borrar la cuenta no borra el lote (SET NULL)."""
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fx_rate_at_trade: Mapped[Decimal] = mapped_column(
        Numeric(16, 8), nullable=False, server_default="1"
    )
    """FX divisa-nativa → divisa base en la fecha de compra: permite descomponer
    el P&L en componente precio vs componente divisa."""
    fees: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_inv_lots_quantity_positive"),
        Index("ix_lots_user_sec", "user_id", "security_id", "trade_date"),
    )


class Sale(Base):
    """Venta: se casa contra lotes vía FIFO → `inv_sale_allocations`."""

    __tablename__ = "inv_sales"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    security_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("securities.id"), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fx_rate_at_trade: Mapped[Decimal] = mapped_column(
        Numeric(16, 8), nullable=False, server_default="1"
    )
    fees: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (CheckConstraint("quantity > 0", name="ck_inv_sales_quantity_positive"),)


class SaleAllocation(Base):
    """Resultado del matching FIFO: qué parte de qué lote consumió una venta.
    Persiste el coste base (en divisa nativa) y su FX, para descomponer el P&L
    realizado en precio vs divisa."""

    __tablename__ = "inv_sale_allocations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sale_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inv_sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inv_lots.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    """Coste de las `quantity` acciones en divisa nativa (precio del lote)."""
    cost_basis_fx: Mapped[Decimal] = mapped_column(Numeric(16, 8), nullable=False)
    """FX del lote consumido — el componente divisa del P&L realizado."""


class DividendReceived(Base):
    """Dividendo COBRADO (flujo real de caja en el broker), no un pronóstico."""

    __tablename__ = "inv_dividends_received"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    security_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("securities.id"), nullable=False)
    ex_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pay_date: Mapped[date] = mapped_column(Date, nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    withholding_tax: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, server_default="0"
    )
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(16, 8), nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CorporateAction(Base):
    """Split/spinoff/etc. Se REGISTRA (`applied_at` NULL) y luego se APLICA
    (ajusta lotes + deja rastro en `inv_lot_adjustments`), de forma auditada y
    reversible [Dec.9]: un split no auditado corrompe el FIFO en silencio."""

    __tablename__ = "inv_corporate_actions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    security_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("securities.id"), nullable=False)
    action_type: Mapped[CorpActionType] = mapped_column(
        pg_enum(CorpActionType, "corp_action_type"), nullable=False
    )
    action_date: Mapped[date] = mapped_column(Date, nullable=False)
    ratio: Mapped[Decimal | None] = mapped_column(Numeric(16, 8), nullable=True)
    """P. ej. split 4:1 → 4. NULL para acciones sin ratio simple."""
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    """NULL = registrada, no aplicada. Se fija al aplicar el ajuste a los lotes."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LotAdjustment(Base):
    """Rastro de auditoría de un ajuste a un lote por una acción corporativa
    [Dec.9]: campo tocado, valor viejo y nuevo. Permite revertir."""

    __tablename__ = "inv_lot_adjustments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    corporate_action_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inv_corporate_actions.id"), nullable=False, index=True
    )
    lot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inv_lots.id"), nullable=False)
    field: Mapped[str] = mapped_column(String(16), nullable=False)
    """`quantity` o `price`."""
    old_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    new_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
