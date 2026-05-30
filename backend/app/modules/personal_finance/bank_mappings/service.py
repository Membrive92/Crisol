"""Lógica de negocio del módulo bank_mappings."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.bank_mappings.models import BankCategoryMapping
from app.modules.personal_finance.bank_mappings.repository import (
    delete_mapping as remove_mapping,
)
from app.modules.personal_finance.bank_mappings.repository import (
    get_mapping_by_id,
    list_mappings,
    upsert_mapping,
)
from app.modules.personal_finance.bank_mappings.schemas import (
    BankCategoryMappingCreate,
)
from app.modules.personal_finance.categories.models import Category


async def list_user_mappings(db: AsyncSession, user_id: uuid.UUID) -> list[BankCategoryMapping]:
    """Equivalencias del usuario."""
    return await list_mappings(db, user_id)


async def upsert_user_mapping(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: BankCategoryMappingCreate,
) -> BankCategoryMapping:
    """Crea o actualiza una equivalencia del usuario.

    Verifica que la categoría pertenece al usuario antes de guardar
    (evita FK orphan a categorías ajenas en multi-tenant).
    """
    cat_result = await db.execute(
        select(Category.id).where(Category.id == data.category_id, Category.user_id == user_id)
    )
    if cat_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="category_id no pertenece al usuario",
        )
    return await upsert_mapping(
        db,
        user_id,
        bank_concept=data.bank_concept,
        category_id=data.category_id,
    )


async def delete_user_mapping(db: AsyncSession, user_id: uuid.UUID, mapping_id: uuid.UUID) -> None:
    """Borra una equivalencia. 404 si no existe o es de otro usuario."""
    mapping = await get_mapping_by_id(db, mapping_id, user_id)
    if mapping is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equivalencia no encontrada",
        )
    await remove_mapping(db, mapping)
