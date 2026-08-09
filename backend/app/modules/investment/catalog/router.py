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
from app.modules.investment.catalog.listing_key import InvalidListingKeyError
from app.modules.investment.catalog.schemas import (
    SecurityAdoptRequest,
    SecurityResolveRequest,
    SecurityResponse,
    SecuritySearchResponse,
)
from app.modules.investment.catalog.service import (
    ExternalListingResolver,
    adopt_listing,
    get_listing_resolver,
    get_security,
    resolve_security,
    search_layered,
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
    q: Annotated[str, Query(min_length=2, max_length=64)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SecuritySearchResponse:
    """Busca valores por ticker o nombre, en local.

    Dos capas, ninguna con red (PHASE-44.8 E2): el catálogo del usuario y el
    índice de los ~10.400 emisores que conoce la SEC. Antes sólo había la
    primera, así que buscar por nombre sólo funcionaba si ya habías dado de alta
    el valor — y `Macdonald` daba cero.

    La capa multi-mercado externa (Entrega 5) sigue apagada:
    `external_search_available=false`.
    """
    found = await search_layered(db, q=q, limit=limit)
    return SecuritySearchResponse(
        results=found.hits,
        external_search_available=False,
        index_ready=found.index_ready,
        notice=found.notice,
        directory_seeded_at=found.directory_seeded_at,
    )


@router.post("/adopt", response_model=SecurityResponse, status_code=201)
async def adopt_endpoint(
    body: SecurityAdoptRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    adapter: FundAdapter,
    resolver: Annotated[ExternalListingResolver, Depends(get_listing_resolver)],
) -> SecurityResponse:
    """Materializa un resultado del buscador como valor del catálogo.

    El cliente devuelve la `listing_key` que le dio el buscador y el servidor la
    vuelve a resolver. Es lo que impide que el cliente decida el mercado, que es
    el defecto que abrió PHASE-44.8.

    Para claves `ext:` (directorio FIRDS, PHASE-44.14) el alta es VALIDADA:
    resolución ISIN→símbolo, cross-check sufijo↔plaza y una cotización real
    antes de persistir. 422 con `code='ticker_required'` cuando el proveedor no
    reconoce el ISIN — el cliente reintenta con `ticker`.

    404 si la SEC no reconoce el ticker (o el listing dejó el directorio); 422
    si la clave está mal formada; 503 si falta `EDGAR_IDENTITY`.
    """
    try:
        security = await adopt_listing(
            db,
            listing_key=body.listing_key,
            adapter=adapter,
            resolver=resolver,
            ticker=body.ticker,
        )
    except InvalidListingKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except EdgarIdentityMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except EdgarUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await db.commit()
    return SecurityResponse.model_validate(security)


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
