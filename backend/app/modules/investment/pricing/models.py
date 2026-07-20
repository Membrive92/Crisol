"""Modelo de cotizaciones — `PriceQuote` (PHASE-44.1, ARCHITECTURE §2.2).

Tabla **GLOBAL**: una fila VIVA por security (UNIQUE `security_id`), refrescada
on-access con TTL. El histórico de precios NO es objetivo del módulo (charts de
cotización = otra fase, otra tabla). `as_of` es el instante del dato según el
proveedor; `fetched_at` es cuándo lo trajimos (gobierna la caducidad del TTL).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PriceQuote(Base):
    __tablename__ = "price_quotes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    security_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("securities.id", ondelete="CASCADE"), nullable=False
    )
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    prev_close: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    """Cierre anterior — para el cambio diario (%). NULL si el proveedor no lo da."""
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    """Timestamp del dato según el proveedor (para mostrar staleness)."""
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    """Cuándo lo trajimos — gobierna el TTL del refresh on-access."""
    provider: Mapped[str] = mapped_column(String(24), nullable=False)

    __table_args__ = (UniqueConstraint("security_id", name="uq_price_quotes_security"),)
