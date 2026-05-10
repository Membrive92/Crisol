"""Router del módulo category_rules."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.category_rules.schemas import (
    CategoryRuleCreate,
    CategoryRuleListResponse,
    CategoryRuleResponse,
    CategoryRuleUpdate,
)
from app.modules.personal_finance.category_rules.service import (
    create_rule,
    delete_rule,
    list_rules,
    update_rule,
)

router = APIRouter(prefix="/category-rules", tags=["category-rules"])


@router.get("", response_model=CategoryRuleListResponse)
async def list_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CategoryRuleListResponse:
    items = await list_rules(db, user.id)
    return CategoryRuleListResponse(
        items=[CategoryRuleResponse.model_validate(r) for r in items]
    )


@router.post(
    "",
    response_model=CategoryRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_endpoint(
    body: CategoryRuleCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CategoryRuleResponse:
    rule = await create_rule(db, user.id, body)
    await db.commit()
    return CategoryRuleResponse.model_validate(rule)


@router.put("/{rule_id}", response_model=CategoryRuleResponse)
async def update_endpoint(
    rule_id: uuid.UUID,
    body: CategoryRuleUpdate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CategoryRuleResponse:
    rule = await update_rule(db, user.id, rule_id, body)
    await db.commit()
    return CategoryRuleResponse.model_validate(rule)


@router.delete(
    "/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response
)
async def delete_endpoint(
    rule_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await delete_rule(db, user.id, rule_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
