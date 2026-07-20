"""Tests de modelo del módulo Inversión (PHASE-44.1).

Dos bloques:

- **Offline** (sin BD): invariantes estructurales — qué tablas son globales vs
  scoped, presencia de las 48 partidas canónicas, valores persistidos de los
  enums. Corren sin Postgres.
- **Integración** (con BD): defaults de servidor, round-trip de enums nativos
  (se persiste el `.value`, no el nombre del miembro), `CheckConstraint` de
  cantidad positiva y `UniqueConstraint`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.investment.analysis.models import AnalysisRun
from app.modules.investment.catalog.models import Security
from app.modules.investment.enums import (
    AccountingStd,
    CorpActionType,
    JobStatus,
    SectorInternal,
    SecurityType,
)
from app.modules.investment.fundamentals.models import (
    FinancialStatement,
    IngestionJob,
)
from app.modules.investment.portfolio.models import CorporateAction, Lot
from app.modules.investment.pricing.models import PriceQuote
from app.modules.investment.thresholds.models import ScoringThresholds
from app.modules.users.models import User

# Las 48 partidas monetarias canónicas §4 del DESIGN (deben existir TODAS y ser
# NULLABLE: hueco ≠ cero). Se listan aquí para cazar cualquier omisión futura.
CANONICAL_MONEY_ITEMS = {
    # Balance (23)
    "cash", "current_financial_assets", "receivables", "inventory",
    "current_assets", "ppe_net", "goodwill", "intangibles",
    "deferred_tax_assets", "total_assets", "short_term_debt",
    "ltd_current_portion", "accounts_payable", "lease_liabilities_current",
    "current_liabilities", "long_term_debt", "lease_liabilities_noncurrent",
    "deferred_tax_liabilities", "total_liabilities", "share_premium",
    "retained_earnings", "treasury_stock", "equity",
    # Cuenta de resultados (11 + acciones 4)
    "revenue", "cogs", "sga_expense", "rd_expense",
    "depreciation_amortization", "impairments", "gains_on_sale_of_business",
    "ebit", "interest_expense", "taxes", "net_income",
    "shares_basic", "shares_diluted", "shares_outstanding_eop", "sbc_expense",
    # Flujo de caja (10)
    "cfo", "wc_change_inventory", "capex", "acquisitions", "divestitures",
    "dividends_paid", "buybacks", "share_issuance", "debt_change", "taxes_paid",
}  # fmt: skip


# ─────────────────────────── Offline (sin BD) ───────────────────────────


def test_global_tables_have_no_user_id() -> None:
    """Catálogo, fundamentales, umbrales y precios son GLOBALES (ADR-0007): NO
    llevan `user_id`. Meter uno aquí sería el error, no olvidarlo."""
    for model in (Security, FinancialStatement, ScoringThresholds, PriceQuote):
        cols = {c.name for c in model.__table__.columns}
        assert "user_id" not in cols, f"{model.__tablename__} no debe tener user_id"


def test_scoped_tables_have_user_id() -> None:
    """Cartera, análisis y los jobs de ingesta SÍ van scoped por usuario."""
    for model in (Lot, CorporateAction, AnalysisRun, IngestionJob):
        cols = {c.name for c in model.__table__.columns}
        assert "user_id" in cols, f"{model.__tablename__} debe tener user_id"


def test_financial_statement_has_all_canonical_items_nullable() -> None:
    """Las 48 partidas canónicas existen y son NULLABLE (hueco ≠ cero)."""
    cols = {c.name: c for c in FinancialStatement.__table__.columns}
    missing = CANONICAL_MONEY_ITEMS - cols.keys()
    assert not missing, f"Partidas canónicas ausentes: {sorted(missing)}"
    for name in CANONICAL_MONEY_ITEMS:
        assert cols[name].nullable, f"{name} debe ser NULLABLE (hueco ≠ cero)"


def test_native_enum_persists_dot_value() -> None:
    """`pg_enum` persiste el `.value` del miembro, no su nombre. Los sectores y
    los estados de job son minúsculas; las normas y tipos, mayúsculas."""
    assert [s.value for s in SectorInternal][:2] == ["technology", "healthcare"]
    assert SectorInternal.UNKNOWN.value == "unknown"
    assert JobStatus.PENDING.value == "pending"
    assert AccountingStd.GAAP.value == "GAAP"
    assert SecurityType.STOCK.value == "STOCK"
    assert CorpActionType.STOCK_DIVIDEND.value == "stock_dividend"


# ─────────────────────────── Integración (BD) ───────────────────────────


@pytest_asyncio.fixture
async def session_factory(test_engine):  # type: ignore[no-untyped-def]
    return async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)


async def _mk_security(db, ticker: str = "MMM", exchange: str = "NYSE") -> Security:
    sec = Security(
        ticker=ticker,
        exchange=exchange,
        name="Test Corp",
        accounting_std=AccountingStd.GAAP,
        currency="USD",
    )
    db.add(sec)
    await db.flush()
    return sec


async def test_security_defaults_and_enum_roundtrip(session_factory) -> None:  # type: ignore[no-untyped-def]
    """Defaults de servidor (sector=unknown, type=STOCK, flags=False) y que el
    enum se guarda y relee como el `.value` (raw SQL = 'unknown')."""
    async with session_factory() as db:
        sec = await _mk_security(db)
        await db.commit()
        sec_id = sec.id
        assert sec.sector is SectorInternal.UNKNOWN
        assert sec.security_type is SecurityType.STOCK
        assert sec.is_financial is False and sec.is_reit is False

    async with session_factory() as db:
        raw = await db.execute(
            text("SELECT sector, security_type FROM securities WHERE id = :id"),
            {"id": sec_id},
        )
        assert tuple(raw.one()) == ("unknown", "STOCK")


async def test_security_ticker_exchange_unique(session_factory) -> None:  # type: ignore[no-untyped-def]
    """Una security es única por (ticker, exchange)."""
    async with session_factory() as db:
        await _mk_security(db, "AAPL", "NASDAQ")
        await db.commit()
    async with session_factory() as db:
        with pytest.raises(IntegrityError):
            await _mk_security(db, "AAPL", "NASDAQ")
            await db.commit()


async def test_financial_statement_holes_persist_as_null(session_factory) -> None:  # type: ignore[no-untyped-def]
    """Una partida sin dato se persiste como NULL (no 0), y `raw_source_ref` y
    `is_latest_view` toman sus defaults de servidor."""
    async with session_factory() as db:
        sec = await _mk_security(db, "UTIL", "NYSE")
        stmt = FinancialStatement(
            security_id=sec.id,
            fiscal_year=2025,
            fiscal_year_end=date(2025, 12, 31),
            filing_accession="0000000000-25-000001",
            filing_date=date(2026, 2, 15),
            source="EDGAR_XBRL",
            accounting_std=AccountingStd.GAAP,
            currency="USD",
            revenue=Decimal("1000.0000"),
            # cash/goodwill deliberadamente ausentes → NULL
        )
        db.add(stmt)
        await db.commit()
        stmt_id = stmt.id
        assert stmt.is_latest_view is False
        assert stmt.raw_source_ref == {}

    async with session_factory() as db:
        row = await db.execute(
            text("SELECT cash, goodwill, revenue FROM financial_statements WHERE id = :id"),
            {"id": stmt_id},
        )
        cash, goodwill, revenue = row.one()
        assert cash is None and goodwill is None
        assert revenue == Decimal("1000.0000")


async def test_ingestion_job_status_defaults_pending(session_factory) -> None:  # type: ignore[no-untyped-def]
    """El estado por defecto de un job es 'pending' (default de servidor)."""
    uid = uuid.uuid4()
    async with session_factory() as db:
        db.add(User(id=uid, email=f"j_{uid.hex[:8]}@x.com", password_hash="x", display_name="J"))
        sec = await _mk_security(db, "JOB", "NYSE")
        job = IngestionJob(security_id=sec.id, user_id=uid, params={"filings_back": 5})
        db.add(job)
        await db.commit()
        assert job.status is JobStatus.PENDING
        job_id = job.id

    async with session_factory() as db:
        raw = await db.execute(
            text("SELECT status FROM ingestion_jobs WHERE id = :id"), {"id": job_id}
        )
        assert raw.scalar_one() == "pending"


async def test_lot_quantity_must_be_positive(session_factory) -> None:  # type: ignore[no-untyped-def]
    """El `CheckConstraint` rechaza una cantidad ≤ 0."""
    uid = uuid.uuid4()
    async with session_factory() as db:
        db.add(User(id=uid, email=f"l_{uid.hex[:8]}@x.com", password_hash="x", display_name="L"))
        sec = await _mk_security(db, "LOT", "NYSE")
        await db.flush()
        db.add(
            Lot(
                user_id=uid,
                security_id=sec.id,
                trade_date=date(2025, 1, 1),
                quantity=Decimal("0"),
                price=Decimal("100"),
            )
        )
        with pytest.raises(IntegrityError):
            await db.commit()


async def test_analysis_run_array_and_jsonb_roundtrip(session_factory) -> None:  # type: ignore[no-untyped-def]
    """`years_covered` (ARRAY) y los desgloses JSONB persisten y releen."""
    uid = uuid.uuid4()
    async with session_factory() as db:
        db.add(User(id=uid, email=f"r_{uid.hex[:8]}@x.com", password_hash="x", display_name="R"))
        sec = await _mk_security(db, "RUN", "NYSE")
        await db.flush()
        run = AnalysisRun(
            security_id=sec.id,
            user_id=uid,
            run_date=datetime(2026, 1, 1, tzinfo=UTC),
            engine_version="1.0.0",
            thresholds_version="seed-v1",
            years_covered=[2021, 2022, 2023, 2024, 2025],
            confidence=Decimal("0.8500"),
            scores_detail={"m_score": -2.5},
            dividend_analysis={},
            evolution={},
            flags=[{"key": "C7", "severity": "amber"}],
            verdict={"profile": "watch"},
            data_completeness={"core": 0.9},
        )
        db.add(run)
        await db.commit()
        run_id = run.id

    async with session_factory() as db:
        got = await db.get(AnalysisRun, run_id)
        assert got is not None
        assert got.years_covered == [2021, 2022, 2023, 2024, 2025]
        assert got.flags == [{"key": "C7", "severity": "amber"}]
        assert got.confidence == Decimal("0.8500")


async def test_scoring_thresholds_unique_per_sector_std_metric(session_factory) -> None:  # type: ignore[no-untyped-def]
    """Un umbral es único por (sector × norma × metric_key)."""
    async with session_factory() as db:
        db.add(
            ScoringThresholds(
                sector=SectorInternal.UTILITIES,
                accounting_std=AccountingStd.GAAP,
                metric_key="S4",
                direction="lower_better",
                high_ok=Decimal("2"),
                high_alarm=Decimal("3.5"),
            )
        )
        await db.commit()
    async with session_factory() as db:
        db.add(
            ScoringThresholds(
                sector=SectorInternal.UTILITIES,
                accounting_std=AccountingStd.GAAP,
                metric_key="S4",
                direction="lower_better",
            )
        )
        with pytest.raises(IntegrityError):
            await db.commit()
