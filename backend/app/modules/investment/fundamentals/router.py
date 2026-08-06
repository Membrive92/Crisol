"""Router de fundamentales (PHASE-44.7, ARCHITECTURE §5).

`statements`/`restatements` son globales (sin filtro por usuario); el job de
ingesta se lee scoped al usuario que lo pidió.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.investment.fundamentals.adapters.base import FundamentalsAdapter
from app.modules.investment.fundamentals.adapters.factory import get_fundamentals_adapter
from app.modules.investment.fundamentals.canonical import CANONICAL_ITEM_DEFINITIONS
from app.modules.investment.fundamentals.schemas import (
    CanonicalItemCatalogResponse,
    CanonicalItemResponse,
    IngestionJobResponse,
    IngestRequest,
    RestatementListResponse,
    RestatementResponse,
    StatementListResponse,
    StatementResponse,
)
from app.modules.investment.fundamentals.service import (
    get_ingestion_job,
    ingest_fundamentals,
    list_restatements,
    list_statements,
)

router = APIRouter(prefix="/fundamentals", tags=["investment:fundamentals"])

FundAdapter = Annotated[FundamentalsAdapter, Depends(get_fundamentals_adapter)]


@router.get("/items", response_model=CanonicalItemCatalogResponse)
async def canonical_items_endpoint(user: CurrentUser) -> CanonicalItemCatalogResponse:
    """Las 49 partidas canónicas con su etiqueta en español y su bloque.

    Estático (no toca BD). Lo consume la pantalla de estados financieros para
    agrupar y rotular las columnas de `GET /{security_id}/statements`, que llegan
    como 49 claves planas en snake_case.
    """
    return CanonicalItemCatalogResponse(
        items=[CanonicalItemResponse.model_validate(d) for d in CANONICAL_ITEM_DEFINITIONS]
    )


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
async def get_job_endpoint(
    job_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IngestionJobResponse:
    """Estado de un job de ingesta (para el polling del frontend)."""
    job = await get_ingestion_job(db, job_id, user.id)
    return IngestionJobResponse.model_validate(job)


@router.post("/{security_id}/ingest", response_model=IngestionJobResponse, status_code=202)
async def ingest_endpoint(
    security_id: uuid.UUID,
    body: IngestRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    adapter: FundAdapter,
) -> IngestionJobResponse:
    """Descarga y persiste los últimos `filings_back` ejercicios del valor.

    404 si el valor no está en el catálogo. La descarga corre síncrona a través
    de un job; el job vuelve en `done` (o `failed` con un `error` legible si la
    SEC no respondió o el emisor no publica 10-K anuales).
    """
    job = await ingest_fundamentals(
        db,
        security_id=security_id,
        user_id=user.id,
        filings_back=body.filings_back,
        adapter=adapter,
    )
    await db.commit()
    return IngestionJobResponse.model_validate(job)


@router.get("/{security_id}/statements", response_model=StatementListResponse)
async def list_statements_endpoint(
    security_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    view: Annotated[Literal["latest", "all"], Query()] = "latest",
) -> StatementListResponse:
    """Estados financieros de un valor, ascendente por ejercicio. `view=latest`
    (por defecto) devuelve la vista vigente de cada año; `view=all` incluye las
    versiones reexpresadas."""
    rows = await list_statements(db, security_id, latest_only=view == "latest")
    return StatementListResponse(items=[StatementResponse.model_validate(r) for r in rows])


@router.get("/{security_id}/restatements", response_model=RestatementListResponse)
async def list_restatements_endpoint(
    security_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RestatementListResponse:
    """Reexpresiones detectadas entre filings del valor."""
    rows = await list_restatements(db, security_id)
    return RestatementListResponse(items=[RestatementResponse.model_validate(r) for r in rows])
