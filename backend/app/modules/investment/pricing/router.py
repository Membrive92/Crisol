"""Router de precios + summary (PHASE-44.7, ARCHITECTURE §5).

Sin prefijo propio: sirve `/pricing/refresh` y `/portfolio/summary` bajo el
prefijo `/investment` del agregador. El summary vive aquí (no en portfolio)
porque necesita los precios; así portfolio no depende de pricing.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.investment.pricing.adapters.base import PriceAdapter
from app.modules.investment.pricing.adapters.factory import get_price_adapter
from app.modules.investment.pricing.schemas import (
    PortfolioSummaryResponse,
    RefreshRequest,
    RefreshResponse,
)
from app.modules.investment.pricing.service import (
    compute_portfolio_summary,
    pricing_enabled,
    refresh_portfolio,
)

router = APIRouter(tags=["investment:pricing"])

Db = Annotated[AsyncSession, Depends(get_db)]
PriceAdapterDep = Annotated[PriceAdapter, Depends(get_price_adapter)]


@router.post("/pricing/refresh", response_model=RefreshResponse)
async def refresh_endpoint(
    body: RefreshRequest, user: CurrentUser, db: Db, adapter: PriceAdapterDep
) -> RefreshResponse:
    """Fuerza el refresh de las cotizaciones de la cartera (botón manual)."""
    refreshed = await refresh_portfolio(db, adapter, user.id, security_ids=body.security_ids)
    await db.commit()
    return RefreshResponse(refreshed=refreshed, pricing_enabled=pricing_enabled())


@router.get("/portfolio/summary", response_model=PortfolioSummaryResponse)
async def summary_endpoint(
    user: CurrentUser, db: Db, adapter: PriceAdapterDep
) -> PortfolioSummaryResponse:
    """Resumen de la cartera con valor de mercado. Las posiciones sin cotización
    salen con `market_value=null` y quedan fuera de los totales; refresca las
    cotizaciones caducadas en la misma petición."""
    summary = await compute_portfolio_summary(db, adapter, user.id)
    await db.commit()  # el refresh on-access puede haber upserteado cotizaciones
    return PortfolioSummaryResponse.model_validate(summary)
