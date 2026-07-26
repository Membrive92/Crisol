"""Router de análisis (PHASE-44.7, ARCHITECTURE §5).

`analysis_runs` es scoped por usuario. El run es síncrono (<1s con datos ya
ingeridos); si no hay estados, 409 con instrucción de ingerir.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.investment.analysis.engine.stress import StressParams
from app.modules.investment.analysis.schemas import (
    AnalysisRunListResponse,
    AnalysisRunResponse,
    AnalysisRunSummary,
    RunRequest,
    StressParamsRequest,
)
from app.modules.investment.analysis.service import get_run, list_runs, run_analysis

router = APIRouter(prefix="/analysis", tags=["investment:analysis"])


def _to_stress_params(request: StressParamsRequest | None) -> StressParams | None:
    """Overrides del request → `StressParams`. Sin overrides → `None` (defaults
    del engine)."""
    if request is None:
        return None
    kwargs: dict[str, object] = {}
    if request.revenue_drops is not None:
        kwargs["revenue_drops"] = tuple(request.revenue_drops)
    if request.rate_shocks_bps is not None:
        kwargs["rate_shocks_bps"] = tuple(request.rate_shocks_bps)
    if request.pct_variable_debt is not None:
        kwargs["pct_variable_debt"] = request.pct_variable_debt
    return StressParams(**kwargs) if kwargs else None  # type: ignore[arg-type]


# `/runs/{run_id}` antes de `/{security_id}/runs` (mismo motivo de orden que en
# los otros routers: "runs" no debe parsearse como un UUID de security).
@router.get("/runs/{run_id}", response_model=AnalysisRunResponse)
async def get_run_endpoint(
    run_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AnalysisRunResponse:
    """Un análisis por id (con todo el desglose)."""
    run = await get_run(db, run_id, user.id)
    return AnalysisRunResponse.model_validate(run)


@router.post("/{security_id}/run", response_model=AnalysisRunResponse)
async def run_endpoint(
    security_id: uuid.UUID,
    body: RunRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AnalysisRunResponse:
    """Ejecuta el engine sobre los estados ingeridos y persiste el análisis.

    404 si el valor no está en el catálogo; 409 si no hay estados financieros
    ingeridos (hay que lanzar la ingesta primero).
    """
    run = await run_analysis(
        db,
        security_id=security_id,
        user_id=user.id,
        stress_params=_to_stress_params(body.stress_params),
    )
    await db.commit()
    return AnalysisRunResponse.model_validate(run)


@router.get("/{security_id}/runs", response_model=AnalysisRunListResponse)
async def list_runs_endpoint(
    security_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AnalysisRunListResponse:
    """Histórico de análisis de un valor (del más reciente al más antiguo)."""
    runs = await list_runs(db, security_id, user.id)
    return AnalysisRunListResponse(items=[AnalysisRunSummary.model_validate(r) for r in runs])
