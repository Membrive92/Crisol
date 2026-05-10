"""Lógica de negocio del módulo category_rules."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.categories.models import Category
from app.modules.personal_finance.category_rules.models import CategoryRule
from app.modules.personal_finance.category_rules.repository import (
    add_rule,
    get_rule_by_id,
    list_rules_for_user,
    remove_rule,
)
from app.modules.personal_finance.category_rules.schemas import (
    CategoryRuleCreate,
    CategoryRuleUpdate,
)


async def list_rules(db: AsyncSession, user_id: uuid.UUID) -> list[CategoryRule]:
    return await list_rules_for_user(db, user_id)


async def _ensure_category_owned(
    db: AsyncSession, user_id: uuid.UUID, category_id: uuid.UUID
) -> None:
    result = await db.execute(
        select(Category.id).where(
            Category.id == category_id, Category.user_id == user_id
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="category_id no pertenece al usuario",
        )


async def create_rule(
    db: AsyncSession, user_id: uuid.UUID, data: CategoryRuleCreate
) -> CategoryRule:
    await _ensure_category_owned(db, user_id, data.category_id)
    rule = CategoryRule(
        user_id=user_id,
        pattern=data.pattern.strip(),
        match_type=data.match_type,
        field=data.field,
        category_id=data.category_id,
        priority=data.priority,
        enabled=data.enabled,
    )
    return await add_rule(db, rule)


async def update_rule(
    db: AsyncSession,
    user_id: uuid.UUID,
    rule_id: uuid.UUID,
    data: CategoryRuleUpdate,
) -> CategoryRule:
    rule = await get_rule_by_id(db, rule_id, user_id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Regla no encontrada"
        )

    payload = data.model_dump(exclude_unset=True)
    if "category_id" in payload and payload["category_id"] is not None:
        await _ensure_category_owned(db, user_id, payload["category_id"])
    if "pattern" in payload and payload["pattern"] is not None:
        payload["pattern"] = payload["pattern"].strip()
    for field, value in payload.items():
        setattr(rule, field, value)
    await db.flush()
    await db.refresh(rule)
    return rule


async def delete_rule(
    db: AsyncSession, user_id: uuid.UUID, rule_id: uuid.UUID
) -> None:
    rule = await get_rule_by_id(db, rule_id, user_id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Regla no encontrada"
        )
    await remove_rule(db, rule)
