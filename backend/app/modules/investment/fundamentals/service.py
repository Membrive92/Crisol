"""Servicio de ingesta de fundamentales (PHASE-44.7, ARCHITECTURE §3).

Envuelve el pipeline PURO (adapter → `build_raw_filings` → `normalize` →
`detect_restatements`) y persiste el resultado. La ingesta corre síncrona a
través de un `IngestionJob` que transiciona a `done`/`failed` dentro de la misma
request: la descarga real es de segundos y se cachea, y el contrato API (POST →
job, GET job) es idéntico al de un job en background, así que el polling del
frontend no cambia. Mismo patrón que `personal_finance.imports`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.investment.catalog.capabilities import capabilities_for
from app.modules.investment.catalog.models import Security
from app.modules.investment.catalog.service import get_security
from app.modules.investment.enums import JobStatus, PeriodType, StatementSource
from app.modules.investment.fundamentals import repository as repo
from app.modules.investment.fundamentals.adapters.annual import build_raw_filings, filing_refs
from app.modules.investment.fundamentals.adapters.base import (
    FundamentalsAdapter,
    SecurityIdentity,
    XbrlFact,
)
from app.modules.investment.fundamentals.adapters.edgar import (
    EdgarIdentityMissingError,
    EdgarUnavailableError,
)
from app.modules.investment.fundamentals.canonical import CANONICAL_ITEMS, CanonicalStatement
from app.modules.investment.fundamentals.models import (
    FinancialStatement,
    IngestionJob,
    RestatementFlag,
)
from app.modules.investment.fundamentals.normalization import RawFiling, normalize
from app.modules.investment.fundamentals.restatements import (
    RestatementComparison,
    detect_restatements,
)


async def ingest_fundamentals(
    db: AsyncSession,
    *,
    security_id: uuid.UUID,
    user_id: uuid.UUID,
    filings_back: int,
    adapter: FundamentalsAdapter,
) -> IngestionJob:
    """Descarga, normaliza y persiste los últimos `filings_back` ejercicios.

    404 si el valor no está en el catálogo. Cualquier fallo del pipeline (SEC
    caída, sin CIK, sin 10-K anuales) NO lanza 500: deja el job en `failed` con
    un `error` legible, que es lo que el frontend muestra para que el usuario
    reintente.
    """
    security = await get_security(db, security_id)

    job = IngestionJob(
        security_id=security_id,
        user_id=user_id,
        status=JobStatus.RUNNING,
        params={"filings_back": filings_back},
        progress={"step": "download"},
    )
    await repo.add_job(db, job)

    try:
        raw_filings, facts = await _download(security, filings_back, adapter)
        for raw in raw_filings:
            statement = normalize(raw)
            filing_dates = {ref.accession: ref.filing_date for ref in filing_refs(facts)}
            filing_date = filing_dates.get(statement.filing_accession, statement.fiscal_year_end)
            await _persist_statement(db, security_id, statement, filing_date)
        for comparison in detect_restatements(facts):
            await _persist_restatement(db, security_id, comparison)
        job.status = JobStatus.DONE
        job.progress = {"filings_done": len(raw_filings), "total": len(raw_filings)}
    except (EdgarUnavailableError, EdgarIdentityMissingError, ValueError) as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc) or type(exc).__name__
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = f"{type(exc).__name__}: {exc}".strip(": ") or type(exc).__name__
    job.finished_at = datetime.now(UTC)

    await db.flush()
    await db.refresh(job)
    return job


async def _download(
    security: Security, filings_back: int, adapter: FundamentalsAdapter
) -> tuple[tuple[RawFiling, ...], tuple[XbrlFact, ...]]:
    caps = capabilities_for(cik=security.cik, analysis_status=security.analysis_status)
    # El `is None` es redundante con la capacidad —sin CIK nunca es analizable—
    # pero es lo que estrecha el tipo para mypy en el `SecurityIdentity` de
    # abajo, donde `cik` es obligatorio.
    if security.cik is None or not caps.analysis_available:
        raise ValueError(caps.reason)
    identity = SecurityIdentity(
        ticker=security.ticker,
        cik=security.cik,
        name=security.name,
        is_reit=security.is_reit,
        is_financial=security.is_financial,
    )
    facts = await adapter.fetch_facts(identity)
    raw_filings = build_raw_filings(
        facts, limit=filings_back, accounting_std=security.accounting_std
    )
    if not raw_filings:
        raise ValueError("El emisor no publica estados anuales (10-K) utilizables.")
    return raw_filings, tuple(facts)


async def _persist_statement(
    db: AsyncSession,
    security_id: uuid.UUID,
    statement: CanonicalStatement,
    filing_date: object,
) -> None:
    """Upsert de un ejercicio por `(security, year, accession)`. Deja
    `is_latest_view=True` y degrada cualquier otra vista viva del mismo año."""
    values = {item: getattr(statement, item) for item in CANONICAL_ITEMS}
    existing = await repo.get_statement(
        db, security_id, statement.fiscal_year, statement.filing_accession
    )
    if existing is not None:
        for item, value in values.items():
            setattr(existing, item, value)
        existing.fiscal_year_end = statement.fiscal_year_end
        existing.filing_date = filing_date  # type: ignore[assignment]
        existing.currency = statement.currency
        existing.accounting_std = statement.accounting_std
        existing.source = StatementSource.EDGAR_XBRL
        existing.raw_source_ref = statement.raw_source_ref
        existing.is_latest_view = True
    else:
        row = FinancialStatement(
            security_id=security_id,
            fiscal_year=statement.fiscal_year,
            fiscal_year_end=statement.fiscal_year_end,
            period_type=PeriodType.ANNUAL,
            filing_accession=statement.filing_accession,
            filing_date=filing_date,  # type: ignore[arg-type]
            source=StatementSource.EDGAR_XBRL,
            accounting_std=statement.accounting_std,
            currency=statement.currency,
            is_latest_view=True,
            raw_source_ref=statement.raw_source_ref,
            **values,
        )
        await repo.add_statement(db, row)
    await db.flush()
    await repo.mark_other_views_stale(
        db, security_id, statement.fiscal_year, keep_accession=statement.filing_accession
    )


async def _persist_restatement(
    db: AsyncSession, security_id: uuid.UUID, comparison: RestatementComparison
) -> None:
    existing = await repo.get_restatement(
        db, security_id, comparison.fiscal_year, comparison.filing_a, comparison.filing_b
    )
    if existing is not None:
        existing.divergences = comparison.divergences
        existing.detected_at = datetime.now(UTC)
        return
    await repo.add_restatement(
        db,
        RestatementFlag(
            security_id=security_id,
            fiscal_year=comparison.fiscal_year,
            filing_a=comparison.filing_a,
            filing_b=comparison.filing_b,
            divergences=comparison.divergences,
            detected_at=datetime.now(UTC),
        ),
    )


async def list_statements(
    db: AsyncSession, security_id: uuid.UUID, *, latest_only: bool
) -> list[FinancialStatement]:
    return await repo.list_statements(db, security_id, latest_only=latest_only)


async def list_restatements(db: AsyncSession, security_id: uuid.UUID) -> list[RestatementFlag]:
    return await repo.list_restatements(db, security_id)


async def get_ingestion_job(
    db: AsyncSession, job_id: uuid.UUID, user_id: uuid.UUID
) -> IngestionJob:
    job = await repo.get_job(db, job_id, user_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job de ingesta no encontrado."
        )
    return job
