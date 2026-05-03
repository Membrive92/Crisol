"""Modelo ORM de tasas de cambio."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExchangeRate(Base):
    """Tasa de cambio diaria.

    Convención: `base` es siempre EUR. Para convertir USD↔GBP se
    componen las dos tasas EUR→USD y EUR→GBP (ver `service.convert`).

    Sin `user_id`: las tasas son datos públicos globales (ECB), no
    aplica aislamiento multi-tenant.
    """

    __tablename__ = "exchange_rates"

    rate_date: Mapped[date] = mapped_column(Date, nullable=False, primary_key=True)
    base: Mapped[str] = mapped_column(String(3), nullable=False, primary_key=True)
    quote: Mapped[str] = mapped_column(String(3), nullable=False, primary_key=True)
    # Precisión alta (8 decimales) para encajar pares con tasas pequeñas
    # (JPY ≈ 0,006 EUR/JPY si se invirtiera). El redondeo final a 2
    # decimales lo hace `service.convert` con ROUND_HALF_EVEN.
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="frankfurter"
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_exchange_rates_quote_date", "quote", "rate_date"),
    )
