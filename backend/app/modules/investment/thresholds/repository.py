"""Queries a DB de umbrales (PHASE-44.7).

`scoring_thresholds` es GLOBAL (sin `user_id`): la calibración es objetiva.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.investment.enums import AccountingStd, SectorInternal
from app.modules.investment.thresholds.models import ScoringThresholds


async def list_for(
    db: AsyncSession, sector: SectorInternal, accounting_std: AccountingStd
) -> list[ScoringThresholds]:
    stmt = select(ScoringThresholds).where(
        ScoringThresholds.sector == sector,
        ScoringThresholds.accounting_std == accounting_std,
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_one(
    db: AsyncSession, sector: SectorInternal, accounting_std: AccountingStd, metric_key: str
) -> ScoringThresholds | None:
    stmt = select(ScoringThresholds).where(
        ScoringThresholds.sector == sector,
        ScoringThresholds.accounting_std == accounting_std,
        ScoringThresholds.metric_key == metric_key,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def count(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(ScoringThresholds))).scalar_one()


async def existing_keys(db: AsyncSession) -> set[tuple[SectorInternal, AccountingStd, str]]:
    """Los tripletes ya sembrados, en UNA consulta.

    El sembrado incremental (PHASE-44.18) necesita saber qué falta sobre ~2.300
    combinaciones; preguntarlo fila a fila con `get_one` serían otras tantas
    consultas en cada arranque. La clave es el triplete completo y no sólo la
    `metric_key` porque el día que se añada un sector o una norma contable, las
    filas nuevas de una métrica YA sembrada también harían falta.
    """
    stmt = select(
        ScoringThresholds.sector,
        ScoringThresholds.accounting_std,
        ScoringThresholds.metric_key,
    )
    return {(sector, std, key) for sector, std, key in (await db.execute(stmt)).all()}
