"""Queries a DB del módulo bank_mappings."""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.bank_mappings.models import BankCategoryMapping


def normalize_concept(value: str) -> str:
    """Normaliza un concepto del banco para que el matching sea
    consistente. Misma función en cliente y servidor: casefold + trim.
    """
    return (value or "").strip().casefold()


async def list_mappings(db: AsyncSession, user_id: uuid.UUID) -> list[BankCategoryMapping]:
    """Lista las equivalencias del usuario, ordenadas por concepto."""
    result = await db.execute(
        select(BankCategoryMapping)
        .where(BankCategoryMapping.user_id == user_id)
        .order_by(BankCategoryMapping.bank_concept.asc())
    )
    return list(result.scalars().all())


async def get_mapping_by_id(
    db: AsyncSession, mapping_id: uuid.UUID, user_id: uuid.UUID
) -> BankCategoryMapping | None:
    """Obtiene una equivalencia filtrando por user_id."""
    result = await db.execute(
        select(BankCategoryMapping).where(
            BankCategoryMapping.id == mapping_id,
            BankCategoryMapping.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_mapping_by_concept(
    db: AsyncSession, user_id: uuid.UUID, bank_concept: str
) -> BankCategoryMapping | None:
    """Busca por (user_id, bank_concept normalizado)."""
    result = await db.execute(
        select(BankCategoryMapping).where(
            BankCategoryMapping.user_id == user_id,
            BankCategoryMapping.bank_concept == normalize_concept(bank_concept),
        )
    )
    return result.scalar_one_or_none()


async def get_mappings_for_concepts(
    db: AsyncSession, user_id: uuid.UUID, concepts: Iterable[str]
) -> dict[str, uuid.UUID]:
    """Devuelve `{concepto_normalizado: category_id}` para los
    conceptos solicitados que tengan equivalencia. Conceptos sin
    equivalencia simplemente no aparecen en el dict.
    """
    normalized = list({normalize_concept(c) for c in concepts if c})
    if not normalized:
        return {}
    result = await db.execute(
        select(
            BankCategoryMapping.bank_concept,
            BankCategoryMapping.category_id,
        ).where(
            BankCategoryMapping.user_id == user_id,
            BankCategoryMapping.bank_concept.in_(normalized),
        )
    )
    return {bc: cid for bc, cid in result.all()}


async def upsert_mapping(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    bank_concept: str,
    category_id: uuid.UUID,
) -> BankCategoryMapping:
    """Crea o actualiza la equivalencia para `bank_concept`.

    Idempotente: si existe, sobreescribe `category_id`.
    """
    normalized = normalize_concept(bank_concept)
    existing = await get_mapping_by_concept(db, user_id, normalized)
    if existing is not None:
        existing.category_id = category_id
        await db.flush()
        await db.refresh(existing)
        return existing
    mapping = BankCategoryMapping(
        user_id=user_id,
        bank_concept=normalized,
        category_id=category_id,
    )
    db.add(mapping)
    await db.flush()
    await db.refresh(mapping)
    return mapping


async def delete_mapping(db: AsyncSession, mapping: BankCategoryMapping) -> None:
    """Elimina la equivalencia."""
    await db.delete(mapping)
    await db.flush()
