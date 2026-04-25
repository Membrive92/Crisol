"""Router del módulo imports."""

from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.imports.repository import get_job_by_id, list_jobs
from app.modules.imports.schemas import (
    ImportColumnMappings,
    ImportJobListResponse,
    ImportJobResponse,
)
from app.modules.imports.service import run_import

router = APIRouter(prefix="/imports", tags=["imports"])

# 10 MB. Suficiente para extractos bancarios típicos.
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


@router.post("", response_model=ImportJobResponse, status_code=201)
async def create_import_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File(...)],
    column_mappings: Annotated[str, Form(..., description="JSON con el mapping de columnas")],
    currency: Annotated[str, Form(min_length=3, max_length=3)] = "EUR",
    default_category_id: Annotated[str | None, Form()] = None,
) -> ImportJobResponse:
    """Sube un fichero CSV/XLSX, lo procesa síncronamente y devuelve el job."""
    try:
        mapping_data = json.loads(column_mappings)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"column_mappings no es JSON válido: {e}",
        ) from e

    try:
        mappings = ImportColumnMappings.model_validate(mapping_data)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors(),
        ) from e

    parsed_default_category: uuid.UUID | None = None
    if default_category_id:
        try:
            parsed_default_category = uuid.UUID(default_category_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="default_category_id no es un UUID válido",
            ) from e

    payload = await file.read()
    if len(payload) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Fichero demasiado grande (máx {MAX_UPLOAD_SIZE} bytes)",
        )
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El fichero está vacío",
        )

    job = await run_import(
        db,
        user.id,
        filename=file.filename or "upload.csv",
        content_type=file.content_type,
        payload=payload,
        mappings=mappings,
        currency=currency,
        default_category_id=parsed_default_category,
    )
    await db.commit()
    return ImportJobResponse.model_validate(job)


@router.get("", response_model=ImportJobListResponse)
async def list_imports_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ImportJobListResponse:
    """Lista los jobs del usuario."""
    items, total = await list_jobs(db, user.id, limit=limit, offset=offset)
    return ImportJobListResponse(
        items=[ImportJobResponse.model_validate(j) for j in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{job_id}", response_model=ImportJobResponse)
async def get_import_endpoint(
    job_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ImportJobResponse:
    """Detalle de un job."""
    job = await get_job_by_id(db, job_id, user.id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado")
    return ImportJobResponse.model_validate(job)
