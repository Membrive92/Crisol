"""Queries a DB de análisis (PHASE-44.7).

`analysis_runs` es SCOPED por usuario: cada run es de quien lo lanzó.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.investment.analysis.models import AnalysisRun
from app.modules.investment.fundamentals.models import RestatementFlag


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


async def get_latest_run(
    db: AsyncSession, security_id: uuid.UUID, user_id: uuid.UUID
) -> AnalysisRun | None:
    """El análisis más reciente de un valor, con todo su desglose.

    Sirve el primer píxel de la pantalla de informe: sin esto habría que pedir
    el histórico (que NO trae los JSONB) y encadenar una segunda petición por
    el id del primero.
    """
    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.security_id == security_id, AnalysisRun.user_id == user_id)
        .order_by(AnalysisRun.run_date.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalars().first()


async def list_restatements_between(
    db: AsyncSession,
    security_id: uuid.UUID,
    since: datetime,
    until: datetime,
) -> list[dict[str, Any]]:
    """Reexpresiones detectadas ENTRE dos fechas de análisis (PHASE-44.24.F).

    `restatement_flags` es GLOBAL (no scoped por usuario, ADR-0007): describe lo
    que la SEC publicó, no lo que hizo un usuario. El scoping lo aporta el
    `security_id`, que el llamador ya ha validado contra sus runs.

    Se acotan a la ventana porque una reexpresión anterior al primer análisis ya
    está DENTRO de los dos: incluirla la presentaría como causa de un cambio que
    no causó.
    """
    stmt = (
        select(RestatementFlag)
        .where(
            RestatementFlag.security_id == security_id,
            RestatementFlag.detected_at > since,
            RestatementFlag.detected_at <= until,
        )
        .order_by(RestatementFlag.fiscal_year.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "fiscal_year": row.fiscal_year,
            "filing_a": row.filing_a,
            "filing_b": row.filing_b,
            "divergences": row.divergences,
        }
        for row in rows
    ]
