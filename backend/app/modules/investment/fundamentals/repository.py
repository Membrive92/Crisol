"""Queries a DB de fundamentales (PHASE-44.7).

`financial_statements` y `restatement_flags` son GLOBALES (sin `user_id`).
`ingestion_jobs` se atribuye a un usuario (auditoría): sus lecturas SÍ filtran
por `user_id`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.investment.fundamentals.models import (
    FinancialStatement,
    IngestionJob,
    RestatementFlag,
)


async def get_statement(
    db: AsyncSession, security_id: uuid.UUID, fiscal_year: int, filing_accession: str
) -> FinancialStatement | None:
    stmt = select(FinancialStatement).where(
        FinancialStatement.security_id == security_id,
        FinancialStatement.fiscal_year == fiscal_year,
        FinancialStatement.filing_accession == filing_accession,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_statements(
    db: AsyncSession, security_id: uuid.UUID, *, latest_only: bool
) -> list[FinancialStatement]:
    """Estados de un valor, en orden ascendente por ejercicio. `latest_only`
    filtra a la vista vigente de cada año (`is_latest_view`)."""
    stmt = select(FinancialStatement).where(FinancialStatement.security_id == security_id)
    if latest_only:
        stmt = stmt.where(FinancialStatement.is_latest_view.is_(True))
    stmt = stmt.order_by(FinancialStatement.fiscal_year)
    return list((await db.execute(stmt)).scalars().all())


async def mark_other_views_stale(
    db: AsyncSession, security_id: uuid.UUID, fiscal_year: int, *, keep_accession: str
) -> None:
    """`is_latest_view=False` para las otras versiones del mismo ejercicio.

    La ingesta colapsa cada año a su vista vigente (un filing por año), así que en
    la práctica esto es defensivo: si una ingesta previa dejó ese año anclado a
    otro accession, se degrada aquí para que quede una sola vista viva por año.
    """
    stmt = (
        update(FinancialStatement)
        .where(
            FinancialStatement.security_id == security_id,
            FinancialStatement.fiscal_year == fiscal_year,
            FinancialStatement.filing_accession != keep_accession,
            FinancialStatement.is_latest_view.is_(True),
        )
        .values(is_latest_view=False)
    )
    await db.execute(stmt)


async def add_statement(db: AsyncSession, statement: FinancialStatement) -> FinancialStatement:
    db.add(statement)
    await db.flush()
    return statement


async def get_restatement(
    db: AsyncSession, security_id: uuid.UUID, fiscal_year: int, filing_a: str, filing_b: str
) -> RestatementFlag | None:
    stmt = select(RestatementFlag).where(
        RestatementFlag.security_id == security_id,
        RestatementFlag.fiscal_year == fiscal_year,
        RestatementFlag.filing_a == filing_a,
        RestatementFlag.filing_b == filing_b,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_restatements(db: AsyncSession, security_id: uuid.UUID) -> list[RestatementFlag]:
    stmt = (
        select(RestatementFlag)
        .where(RestatementFlag.security_id == security_id)
        .order_by(RestatementFlag.fiscal_year)
    )
    return list((await db.execute(stmt)).scalars().all())


async def add_restatement(db: AsyncSession, flag: RestatementFlag) -> RestatementFlag:
    db.add(flag)
    await db.flush()
    return flag


async def add_job(db: AsyncSession, job: IngestionJob) -> IngestionJob:
    db.add(job)
    await db.flush()
    return job


async def get_job(db: AsyncSession, job_id: uuid.UUID, user_id: uuid.UUID) -> IngestionJob | None:
    """Job por id, scoped al usuario que lo pidió."""
    stmt = select(IngestionJob).where(IngestionJob.id == job_id, IngestionJob.user_id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()
