"""Lógica de negocio del módulo categories."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.categories.models import Category
from app.modules.personal_finance.categories.repository import (
    create_category as persist_category,
)
from app.modules.personal_finance.categories.repository import (
    delete_category as remove_category,
)
from app.modules.personal_finance.categories.repository import (
    get_category_by_id,
)
from app.modules.personal_finance.categories.repository import (
    list_categories as list_all,
)
from app.modules.personal_finance.categories.schemas import CategoryCreate, CategoryUpdate


async def list_categories(db: AsyncSession, user_id: uuid.UUID) -> list[Category]:
    """Lista las categorías del usuario."""
    return await list_all(db, user_id)


async def get_category(db: AsyncSession, category_id: uuid.UUID, user_id: uuid.UUID) -> Category:
    """Obtiene una categoría o lanza 404."""
    category = await get_category_by_id(db, category_id, user_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoría no encontrada")
    return category


async def create_category(db: AsyncSession, user_id: uuid.UUID, data: CategoryCreate) -> Category:
    """Crea una nueva categoría para el usuario.

    PHASE-30.1: si la categoría se marca `is_transfer=True`, forzamos
    `role=TRANSFER` aunque el caller pase otro role distinto, para
    mantener consistencia entre las dos columnas mientras coexistan.
    """
    from app.modules.personal_finance.categories.models import CategoryRole

    role = data.role
    if data.is_transfer and role == CategoryRole.GENERIC:
        role = CategoryRole.TRANSFER
    category = Category(
        user_id=user_id,
        name=data.name,
        icon=data.icon,
        color=data.color,
        kind=data.kind,
        is_transfer=data.is_transfer,
        role=role,
    )
    return await persist_category(db, category)


async def update_category(
    db: AsyncSession, category_id: uuid.UUID, user_id: uuid.UUID, data: CategoryUpdate
) -> Category:
    """Actualiza una categoría existente."""
    category = await get_category(db, category_id, user_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    await db.flush()
    await db.refresh(category)
    return category


async def delete_category(db: AsyncSession, category_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Elimina una categoría del usuario."""
    category = await get_category(db, category_id, user_id)
    await remove_category(db, category)
