"""Queries a DB del módulo categories."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.categories.models import Category


async def list_categories(db: AsyncSession, user_id: uuid.UUID) -> list[Category]:
    """Lista todas las categorías del usuario."""
    result = await db.execute(
        select(Category).where(Category.user_id == user_id).order_by(Category.name)
    )
    return list(result.scalars().all())


async def get_category_by_id(
    db: AsyncSession, category_id: uuid.UUID, user_id: uuid.UUID
) -> Category | None:
    """Obtiene una categoría por ID, filtrando por user_id."""
    result = await db.execute(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_category(db: AsyncSession, category: Category) -> Category:
    """Persiste una nueva categoría."""
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return category


async def delete_category(db: AsyncSession, category: Category) -> None:
    """Elimina una categoría."""
    await db.delete(category)
    await db.flush()
