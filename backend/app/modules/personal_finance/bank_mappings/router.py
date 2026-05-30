"""Router del módulo bank_mappings."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.bank_mappings.schemas import (
    BankCategoryMappingCreate,
    BankCategoryMappingListResponse,
    BankCategoryMappingResponse,
)
from app.modules.personal_finance.bank_mappings.service import (
    delete_user_mapping,
    list_user_mappings,
    upsert_user_mapping,
)

router = APIRouter(prefix="/bank-mappings", tags=["bank-mappings"])


@router.get("", response_model=BankCategoryMappingListResponse)
async def list_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BankCategoryMappingListResponse:
    """Lista las equivalencias del usuario."""
    items = await list_user_mappings(db, user.id)
    return BankCategoryMappingListResponse(
        items=[BankCategoryMappingResponse.model_validate(m) for m in items]
    )


@router.post(
    "",
    response_model=BankCategoryMappingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_endpoint(
    body: BankCategoryMappingCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BankCategoryMappingResponse:
    """Crea o actualiza una equivalencia (UPSERT por bank_concept)."""
    mapping = await upsert_user_mapping(db, user.id, body)
    await db.commit()
    return BankCategoryMappingResponse.model_validate(mapping)


@router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_endpoint(
    mapping_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Elimina una equivalencia."""
    await delete_user_mapping(db, user.id, mapping_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
