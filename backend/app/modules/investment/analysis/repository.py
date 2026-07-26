"""Queries a DB de análisis (PHASE-44.7).

`analysis_runs` es SCOPED por usuario: cada run es de quien lo lanzó.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.investment.analysis.models import AnalysisRun


async def add_run(db: AsyncSession, run: AnalysisRun) -> AnalysisRun:
    db.add(run)
    await db.flush()
    await db.refresh(run)
    return run


async def list_runs(
    db: AsyncSession, security_id: uuid.UUID, user_id: uuid.UUID
) -> list[AnalysisRun]:
    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.security_id == security_id, AnalysisRun.user_id == user_id)
        .order_by(AnalysisRun.run_date.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_run(db: AsyncSession, run_id: uuid.UUID, user_id: uuid.UUID) -> AnalysisRun | None:
    stmt = select(AnalysisRun).where(AnalysisRun.id == run_id, AnalysisRun.user_id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()
