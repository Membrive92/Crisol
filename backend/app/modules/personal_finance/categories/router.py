"""Router del módulo categories."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.categories.schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
)
from app.modules.personal_finance.categories.service import (
    create_category,
    delete_category,
    get_category,
    list_categories,
    update_category,
)

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryResponse])
async def list_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CategoryResponse]:
    """Lista las categorías del usuario autenticado."""
    categories = await list_categories(db, user.id)
    return [CategoryResponse.model_validate(c) for c in categories]


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_endpoint(
    category_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CategoryResponse:
    """Obtiene una categoría por ID."""
    category = await get_category(db, category_id, user.id)
    return CategoryResponse.model_validate(category)


@router.post("", response_model=CategoryResponse, status_code=201)
async def create_endpoint(
    body: CategoryCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CategoryResponse:
    """Crea una nueva categoría."""
    category = await create_category(db, user.id, body)
    await db.commit()
    return CategoryResponse.model_validate(category)


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_endpoint(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CategoryResponse:
    """Actualiza una categoría existente."""
    category = await update_category(db, category_id, user.id, body)
    await db.commit()
    return CategoryResponse.model_validate(category)


@router.delete("/{category_id}", status_code=204, response_class=Response)
async def delete_endpoint(
    category_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Elimina una categoría."""
    await delete_category(db, category_id, user.id)
    await db.commit()
    return Response(status_code=204)
