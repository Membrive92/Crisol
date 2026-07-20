"""PHASE-44.1 — Cimientos del módulo Inversión.

Green-field, PURAMENTE ADITIVA: 8 enums nativos + 13 tablas nuevas. NO toca
ninguna tabla existente. Catálogo, fundamentales, umbrales y precios son
GLOBALES (sin `user_id`) — ver ADR-0007; cartera y análisis van scoped por
usuario.

Reversible: `downgrade` elimina las 13 tablas (orden inverso de FKs; los
índices caen con su tabla) y después los 8 enums.

Revision ID: aa1b47c9d2e6f0
Revises: f9v25x7us9w8v4
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "aa1b47c9d2e6f0"
down_revision: str | None = "f9v25x7us9w8v4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ── Enums nativos: name → labels persistidos (= `.value` del StrEnum) ──
_ENUMS: dict[str, tuple[str, ...]] = {
    "sector_internal": (
        "technology",
        "healthcare",
        "financials",
        "consumer_staples",
        "consumer_discretionary",
        "industrials",
        "energy",
        "materials",
        "utilities",
        "real_estate",
        "communication",
        "unknown",
    ),
    "accounting_std": ("GAAP", "IFRS", "PGC"),
    "security_type": ("STOCK", "ADR", "ETF"),
    "period_type": ("ANNUAL", "QUARTERLY"),
    "statement_source": ("EDGAR_XBRL", "MANUAL"),
    "job_status": ("pending", "running", "done", "failed"),
    "threshold_direction": ("lower_better", "higher_better", "band"),
    "corp_action_type": ("split", "spinoff", "stock_dividend", "return_of_capital"),
}


def _enum(name: str) -> postgresql.ENUM:
    """Referencia a un enum YA creado (no lo recrea dentro del CREATE TABLE)."""
    return postgresql.ENUM(*_ENUMS[name], name=name, create_type=False)


# Partidas monetarias canónicas §4 del DESIGN (orden = modelo). Todas
# NUMERIC(20,4) NULL — hueco ≠ cero.
_MONEY_COLS: tuple[str, ...] = (
    # Balance (23)
    "cash",
    "current_financial_assets",
    "receivables",
    "inventory",
    "current_assets",
    "ppe_net",
    "goodwill",
    "intangibles",
    "deferred_tax_assets",
    "total_assets",
    "short_term_debt",
    "ltd_current_portion",
    "accounts_payable",
    "lease_liabilities_current",
    "current_liabilities",
    "long_term_debt",
    "lease_liabilities_noncurrent",
    "deferred_tax_liabilities",
    "total_liabilities",
    "share_premium",
    "retained_earnings",
    "treasury_stock",
    "equity",
    # Cuenta de resultados (11 + acciones 4)
    "revenue",
    "cogs",
    "sga_expense",
    "rd_expense",
    "depreciation_amortization",
    "impairments",
    "gains_on_sale_of_business",
    "ebit",
    "interest_expense",
    "taxes",
    "net_income",
    "shares_basic",
    "shares_diluted",
    "shares_outstanding_eop",
    "sbc_expense",
    # Flujo de caja (10)
    "cfo",
    "wc_change_inventory",
    "capex",
    "acquisitions",
    "divestitures",
    "dividends_paid",
    "buybacks",
    "share_issuance",
    "debt_change",
    "taxes_paid",
)


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Enums nativos (idempotente).
    for name, labels in _ENUMS.items():
        postgresql.ENUM(*labels, name=name).create(bind, checkfirst=True)

    # 2) Catálogo (global).
    op.create_table(
        "securities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("exchange", sa.String(length=16), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=True),
        sa.Column("isin", sa.String(length=12), nullable=True),
        sa.Column("sector", _enum("sector_internal"), nullable=False, server_default="unknown"),
        sa.Column("accounting_std", _enum("accounting_std"), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("security_type", _enum("security_type"), nullable=False, server_default="STOCK"),
        sa.Column("is_financial", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_reit", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "exchange", name="uq_securities_ticker_exchange"),
    )
    op.create_index(
        "ix_securities_cik",
        "securities",
        ["cik"],
        postgresql_where=sa.text("cik IS NOT NULL"),
    )

    # 3) Umbrales (global).
    op.create_table(
        "scoring_thresholds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sector", _enum("sector_internal"), nullable=False),
        sa.Column("accounting_std", _enum("accounting_std"), nullable=False),
        sa.Column("metric_key", sa.String(length=64), nullable=False),
        sa.Column("direction", _enum("threshold_direction"), nullable=False),
        sa.Column("low_alarm", sa.Numeric(12, 6), nullable=True),
        sa.Column("low_ok", sa.Numeric(12, 6), nullable=True),
        sa.Column("high_ok", sa.Numeric(12, 6), nullable=True),
        sa.Column("high_alarm", sa.Numeric(12, 6), nullable=True),
        sa.Column("model_variant", sa.String(length=32), nullable=True),
        sa.Column("applies", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sector",
            "accounting_std",
            "metric_key",
            name="uq_thresholds_sector_std_metric",
        ),
    )

    # 4) Precios (global; una fila viva por security).
    op.create_table(
        "price_quotes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("price", sa.Numeric(20, 6), nullable=False),
        sa.Column("prev_close", sa.Numeric(20, 6), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(["security_id"], ["securities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("security_id", name="uq_price_quotes_security"),
    )

    # 5) Fundamentales (global).
    op.create_table(
        "financial_statements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_year_end", sa.Date(), nullable=False),
        sa.Column("period_type", _enum("period_type"), nullable=False, server_default="ANNUAL"),
        sa.Column("filing_accession", sa.String(length=25), nullable=False),
        sa.Column("is_latest_view", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("source", _enum("statement_source"), nullable=False),
        sa.Column("accounting_std", _enum("accounting_std"), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        *[sa.Column(name, sa.Numeric(20, 4), nullable=True) for name in _MONEY_COLS],
        sa.Column(
            "raw_source_ref",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["security_id"], ["securities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "security_id",
            "fiscal_year",
            "period_type",
            "filing_accession",
            name="uq_fs_security_year_period_filing",
        ),
    )
    op.create_index(
        op.f("ix_financial_statements_security_id"),
        "financial_statements",
        ["security_id"],
    )
    op.create_index(
        "ix_fs_latest",
        "financial_statements",
        ["security_id", "fiscal_year"],
        postgresql_where=sa.text("is_latest_view"),
    )

    # 6) Restatements (global).
    op.create_table(
        "restatement_flags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("filing_a", sa.String(length=25), nullable=False),
        sa.Column("filing_b", sa.String(length=25), nullable=False),
        sa.Column("divergences", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["security_id"], ["securities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "security_id",
            "fiscal_year",
            "filing_a",
            "filing_b",
            name="uq_restatement_security_year_filings",
        ),
    )
    op.create_index(
        op.f("ix_restatement_flags_security_id"),
        "restatement_flags",
        ["security_id"],
    )

    # 7) Jobs de ingesta (auditado por usuario).
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", _enum("job_status"), nullable=False, server_default="pending"),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "progress",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["security_id"], ["securities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ingestion_jobs_security_id"), "ingestion_jobs", ["security_id"])
    op.create_index(op.f("ix_ingestion_jobs_user_id"), "ingestion_jobs", ["user_id"])

    # 8) Análisis (scoped).
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("run_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("engine_version", sa.String(length=16), nullable=False),
        sa.Column("thresholds_version", sa.String(length=64), nullable=False),
        sa.Column("years_covered", postgresql.ARRAY(sa.SmallInteger()), nullable=False),
        sa.Column("m_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("z_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("z_variant", sa.String(length=16), nullable=True),
        sa.Column("f_score", sa.SmallInteger(), nullable=True),
        sa.Column("accruals_ratio", sa.Numeric(10, 6), nullable=True),
        sa.Column("fcf_payout", sa.Numeric(10, 6), nullable=True),
        sa.Column("fcf_coverage", sa.Numeric(10, 4), nullable=True),
        sa.Column("dividend_verdict", sa.String(length=16), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("scores_detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dividend_analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evolution", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("verdict", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("data_completeness", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["security_id"], ["securities.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_runs_sec_user",
        "analysis_runs",
        ["security_id", "user_id", "run_date"],
    )

    # 9) Cartera (scoped).
    op.create_table(
        "inv_lots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("price", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_rate_at_trade", sa.Numeric(16, 8), nullable=False, server_default="1"),
        sa.Column("fees", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="ck_inv_lots_quantity_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["securities.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lots_user_sec", "inv_lots", ["user_id", "security_id", "trade_date"])

    op.create_table(
        "inv_sales",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("price", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_rate_at_trade", sa.Numeric(16, 8), nullable=False, server_default="1"),
        sa.Column("fees", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="ck_inv_sales_quantity_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["securities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inv_sales_user_id"), "inv_sales", ["user_id"])

    op.create_table(
        "inv_sale_allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=False),
        sa.Column("lot_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("cost_basis", sa.Numeric(20, 6), nullable=False),
        sa.Column("cost_basis_fx", sa.Numeric(16, 8), nullable=False),
        sa.ForeignKeyConstraint(["sale_id"], ["inv_sales.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lot_id"], ["inv_lots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_inv_sale_allocations_sale_id"),
        "inv_sale_allocations",
        ["sale_id"],
    )

    op.create_table(
        "inv_dividends_received",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=True),
        sa.Column("pay_date", sa.Date(), nullable=False),
        sa.Column("gross_amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("withholding_tax", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("fx_rate", sa.Numeric(16, 8), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["securities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_inv_dividends_received_user_id"),
        "inv_dividends_received",
        ["user_id"],
    )

    op.create_table(
        "inv_corporate_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", _enum("corp_action_type"), nullable=False),
        sa.Column("action_date", sa.Date(), nullable=False),
        sa.Column("ratio", sa.Numeric(16, 8), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["securities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_inv_corporate_actions_user_id"),
        "inv_corporate_actions",
        ["user_id"],
    )

    op.create_table(
        "inv_lot_adjustments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("corporate_action_id", sa.Uuid(), nullable=False),
        sa.Column("lot_id", sa.Uuid(), nullable=False),
        sa.Column("field", sa.String(length=16), nullable=False),
        sa.Column("old_value", sa.Numeric(20, 8), nullable=False),
        sa.Column("new_value", sa.Numeric(20, 8), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["corporate_action_id"], ["inv_corporate_actions.id"]),
        sa.ForeignKeyConstraint(["lot_id"], ["inv_lots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_inv_lot_adjustments_corporate_action_id"),
        "inv_lot_adjustments",
        ["corporate_action_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()

    # Tablas en orden inverso de dependencias (los índices caen con la tabla).
    for table in (
        "inv_lot_adjustments",
        "inv_corporate_actions",
        "inv_dividends_received",
        "inv_sale_allocations",
        "inv_sales",
        "inv_lots",
        "analysis_runs",
        "ingestion_jobs",
        "restatement_flags",
        "financial_statements",
        "price_quotes",
        "scoring_thresholds",
        "securities",
    ):
        op.drop_table(table)

    # Enums (tras eliminar todas las columnas que los usan).
    for name in _ENUMS:
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
