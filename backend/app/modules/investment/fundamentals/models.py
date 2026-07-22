"""Modelos de fundamentales (PHASE-44.1, ARCHITECTURE §2.2).

- `FinancialStatement` (GLOBAL): un año fiscal según UN filing concreto
  (`filing_accession`) [Dec.6]. Las 43 partidas canónicas §4 del DESIGN, TODAS
  NULLABLE (hueco ≠ cero [Dec.4]). Persistidas SIEMPRE en unidades absolutas de
  la divisa (la ingesta normaliza el `scale` XBRL). `raw_source_ref` guarda los
  conceptos originales sin colapsar [Dec.13]. `is_latest_view` marca la versión
  vigente de cada año.
- `RestatementFlag` (GLOBAL): divergencia >1% en una partida entre dos filings
  del mismo año [Dec.6] — la reexpresión es señal forense.
- `IngestionJob` (auditado por usuario): estado de una descarga EDGAR
  (BackgroundTask, single-user local).

Convención de signos canónica (todas positivas, semántica fija: capex>0 =
inversión; dividends_paid>0 = pago; buybacks>0 = recompra) — la fija la ingesta.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.investment.enums import (
    AccountingStd,
    JobStatus,
    PeriodType,
    StatementSource,
    pg_enum,
)


def _money() -> Mapped[Decimal | None]:
    """Partida monetaria/de acciones canónica: NUMERIC(20,4), nullable (hueco ≠
    cero). Función (no constante): cada columna necesita su propia instancia."""
    return mapped_column(Numeric(20, 4), nullable=True)


class FinancialStatement(Base):
    __tablename__ = "financial_statements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    security_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("securities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_year_end: Mapped[date] = mapped_column(Date, nullable=False)
    """Fecha real de cierre [Dec.12]: los fiscales partidos (jun, sep) rompen la
    comparación por año natural y el cálculo de staleness."""
    period_type: Mapped[PeriodType] = mapped_column(
        pg_enum(PeriodType, "period_type"),
        nullable=False,
        default=PeriodType.ANNUAL,
        server_default="ANNUAL",
    )
    filing_accession: Mapped[str] = mapped_column(String(25), nullable=False)
    """Accession number del filing SEC — clave de versión [Dec.6]."""
    is_latest_view: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[StatementSource] = mapped_column(
        pg_enum(StatementSource, "statement_source"), nullable=False
    )
    accounting_std: Mapped[AccountingStd] = mapped_column(
        pg_enum(AccountingStd, "accounting_std"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    # ── Balance (23) ──────────────────────────────────────────────
    cash: Mapped[Decimal | None] = _money()
    current_financial_assets: Mapped[Decimal | None] = _money()
    receivables: Mapped[Decimal | None] = _money()
    inventory: Mapped[Decimal | None] = _money()
    current_assets: Mapped[Decimal | None] = _money()
    ppe_net: Mapped[Decimal | None] = _money()
    goodwill: Mapped[Decimal | None] = _money()
    intangibles: Mapped[Decimal | None] = _money()
    deferred_tax_assets: Mapped[Decimal | None] = _money()
    total_assets: Mapped[Decimal | None] = _money()
    short_term_debt: Mapped[Decimal | None] = _money()
    ltd_current_portion: Mapped[Decimal | None] = _money()
    accounts_payable: Mapped[Decimal | None] = _money()
    lease_liabilities_current: Mapped[Decimal | None] = _money()
    current_liabilities: Mapped[Decimal | None] = _money()
    long_term_debt: Mapped[Decimal | None] = _money()
    lease_liabilities_noncurrent: Mapped[Decimal | None] = _money()
    deferred_tax_liabilities: Mapped[Decimal | None] = _money()
    total_liabilities: Mapped[Decimal | None] = _money()
    share_premium: Mapped[Decimal | None] = _money()
    retained_earnings: Mapped[Decimal | None] = _money()
    treasury_stock: Mapped[Decimal | None] = _money()
    equity: Mapped[Decimal | None] = _money()

    # ── Cuenta de resultados (13 + acciones) ──────────────────────
    revenue: Mapped[Decimal | None] = _money()
    cogs: Mapped[Decimal | None] = _money()
    sga_expense: Mapped[Decimal | None] = _money()
    rd_expense: Mapped[Decimal | None] = _money()
    depreciation_amortization: Mapped[Decimal | None] = _money()
    impairments: Mapped[Decimal | None] = _money()
    gains_on_sale_of_business: Mapped[Decimal | None] = _money()
    ebit: Mapped[Decimal | None] = _money()
    interest_expense: Mapped[Decimal | None] = _money()
    pretax_income: Mapped[Decimal | None] = _money()
    taxes: Mapped[Decimal | None] = _money()
    net_income: Mapped[Decimal | None] = _money()
    shares_basic: Mapped[Decimal | None] = _money()
    shares_diluted: Mapped[Decimal | None] = _money()
    shares_outstanding_eop: Mapped[Decimal | None] = _money()
    sbc_expense: Mapped[Decimal | None] = _money()

    # ── Flujo de caja (10) ────────────────────────────────────────
    cfo: Mapped[Decimal | None] = _money()
    wc_change_inventory: Mapped[Decimal | None] = _money()
    capex: Mapped[Decimal | None] = _money()
    acquisitions: Mapped[Decimal | None] = _money()
    divestitures: Mapped[Decimal | None] = _money()
    dividends_paid: Mapped[Decimal | None] = _money()
    buybacks: Mapped[Decimal | None] = _money()
    share_issuance: Mapped[Decimal | None] = _money()
    debt_change: Mapped[Decimal | None] = _money()
    taxes_paid: Mapped[Decimal | None] = _money()

    raw_source_ref: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    """Conceptos XBRL originales que alimentaron cada partida + payload, sin
    colapsar [Dec.13]: auditar el mapeo siempre posible."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "security_id",
            "fiscal_year",
            "period_type",
            "filing_accession",
            name="uq_fs_security_year_period_filing",
        ),
        Index(
            "ix_fs_latest",
            "security_id",
            "fiscal_year",
            postgresql_where=text("is_latest_view"),
        ),
    )


class RestatementFlag(Base):
    __tablename__ = "restatement_flags"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    security_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("securities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    filing_a: Mapped[str] = mapped_column(String(25), nullable=False)
    filing_b: Mapped[str] = mapped_column(String(25), nullable=False)
    divergences: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    """[{item, value_a, value_b, pct}] — partidas que difieren >1% entre filings."""
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "security_id",
            "fiscal_year",
            "filing_a",
            "filing_b",
            name="uq_restatement_security_year_filings",
        ),
    )


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    security_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("securities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    """Quién pidió la ingesta (auditoría). La tabla-destino es global, pero el
    job se atribuye a un usuario."""
    status: Mapped[JobStatus] = mapped_column(
        pg_enum(JobStatus, "job_status"),
        nullable=False,
        default=JobStatus.PENDING,
        server_default="pending",
    )
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    """{filings_back: int}."""
    progress: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    """{step, filings_done, total}."""
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
