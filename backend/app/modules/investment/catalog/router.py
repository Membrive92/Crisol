"""Router del catálogo de valores (PHASE-44.7, ARCHITECTURE §5).

`securities` es global, pero los endpoints exigen usuario autenticado igual que
el resto de la API (no hay lectura anónima). Lo que NO hacen es filtrar por
usuario: el catálogo es compartido.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.investment.catalog.capabilities import capabilities_for
from app.modules.investment.catalog.schemas import (
    SecurityResolveRequest,
    SecurityResponse,
    SecuritySearchHit,
    SecuritySearchResponse,
)
from app.modules.investment.catalog.service import (
    get_security,
    resolve_security,
    search_securities,
)
from app.modules.investment.fundamentals.adapters.base import FundamentalsAdapter
from app.modules.investment.fundamentals.adapters.edgar import (
    EdgarIdentityMissingError,
    EdgarUnavailableError,
)
from app.modules.investment.fundamentals.adapters.factory import get_fundamentals_adapter

router = APIRouter(prefix="/securities", tags=["investment:catalog"])

FundAdapter = Annotated[FundamentalsAdapter, Depends(get_fundamentals_adapter)]


# `/search` DEBE declararse antes de `/{security_id}` (que es un UUID): si no,
# FastAPI intenta parsear "search" como UUID y devuelve 422 (misma trampa que en
# transactions con `/available-periods`).
@router.get("/search", response_model=SecuritySearchResponse)
async def search_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str, Query(min_length=1, max_length=64)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SecuritySearchResponse:
    """Busca valores en el catálogo local por ticker o nombre.

    La búsqueda externa multi-mercado (symbol-search del `PriceAdapter`) requiere
    Finnhub y aún no está activa: `external_search_available=false`. Hasta
    entonces sólo se ven los valores ya resueltos en el catálogo.
    """
    rows = await search_securities(db, q=q, limit=limit)
    return SecuritySearchResponse(
        results=[
            SecuritySearchHit(
                id=s.id,
                ticker=s.ticker,
                exchange=s.exchange,
                name=s.name,
                in_catalog=True,
                # La regla NO se reescribe aquí: sale de `capabilities_for`, que es
                # su única implementación (PHASE-44.8 E1). Duplicarla fue lo que
                # permitió que `cik is not None` conviviera en tres sitios diciendo
                # algo falso.
                analysis_available=capabilities_for(
                    cik=s.cik, analysis_status=s.analysis_status
                ).analysis_available,
            )
            for s in rows
        ],
        external_search_available=False,
    )


@router.post("/resolve", response_model=SecurityResponse, status_code=201)
async def resolve_endpoint(
    body: SecurityResolveRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    adapter: FundAdapter,
) -> SecurityResponse:
    """Crea (o reutiliza) un `Security` a partir de su ticker.

    Resuelve la identidad contra EDGAR (CIK, sector, is_reit/is_financial).
    404 si la SEC no conoce el ticker; 503 si falta `EDGAR_IDENTITY`.

    `exchange` es opcional y sólo una etiqueta: la identidad la fija el servidor
    (PHASE-44.8 E1). Un ticker ya conocido se devuelve tal cual en vez de
    duplicarse por venir con otra plaza en el body.
    """
    try:
        security = await resolve_security(
            db, ticker=body.ticker, exchange=body.exchange, adapter=adapter
        )
    except EdgarIdentityMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except EdgarUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await db.commit()
    return SecurityResponse.model_validate(security)


@router.get("/{security_id}", response_model=SecurityResponse)
async def get_endpoint(
    security_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SecurityResponse:
    """Un valor del catálogo por id."""
    security = await get_security(db, security_id)
    return SecurityResponse.model_validate(security)
