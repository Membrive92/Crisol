"""Modelo del catálogo de valores — `Security` (PHASE-44.1, ARCHITECTURE §2.2).

Tabla **GLOBAL** (sin `user_id`) [Dec.11]: la identidad de un valor de mercado
es objetiva; duplicarla por usuario no tiene sentido. Ver ADR-0007.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.investment.enums import (
    AccountingStd,
    SectorInternal,
    SecurityType,
    pg_enum,
)


class Security(Base):
    """Identidad de un valor cotizado. `sector` (interno, derivado de SIC) y
    `accounting_std` gobiernan qué umbrales y modelos aplican. `is_financial`
    excluye del scoring forense; `is_reit` activa la variante FFO."""

    __tablename__ = "securities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(12), nullable=False)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    cik: Mapped[str | None] = mapped_column(String(10), nullable=True)
    """Central Index Key de la SEC, zero-padded a 10 dígitos. NULL para valores
    no-US (sin filing EDGAR → análisis no disponible hasta adapter EU)."""
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True)
    sector: Mapped[SectorInternal] = mapped_column(
        pg_enum(SectorInternal, "sector_internal"),
        nullable=False,
        default=SectorInternal.UNKNOWN,
        server_default="unknown",
    )
    accounting_std: Mapped[AccountingStd] = mapped_column(
        pg_enum(AccountingStd, "accounting_std"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    security_type: Mapped[SecurityType] = mapped_column(
        pg_enum(SecurityType, "security_type"),
        nullable=False,
        default=SecurityType.STOCK,
        server_default="STOCK",
    )
    is_financial: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_reit: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    analysis_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    """Evidencia de si el motor puede correr sobre este valor (PHASE-44.8).

    Valores en `catalog.capabilities.AnalysisStatus`: `ok`, `no_annual`,
    `non_gaap`, `not_supported`. NULL = no comprobado, y entonces la regla
    responde lo mismo que antes de existir la columna.

    Es una FOTO, no una verdad eterna: quien hoy no presenta 10-K puede
    presentarlo mañana. Por eso un veredicto que BLOQUEA (`no_annual`,
    `non_gaap`, `not_supported`) se vuelve a comprobar cada vez que alguien
    resuelve ese valor, mientras que un `ok` se conserva. Sin ese refresco sería
    una premisa escrita que caduca en silencio (lección PHASE-43) con forma de
    columna."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("ticker", "exchange", name="uq_securities_ticker_exchange"),
        Index("ix_securities_cik", "cik", postgresql_where=text("cik IS NOT NULL")),
    )
