"""Router del módulo budgets (PHASE-12.1)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.budgets.schemas import (
    BudgetCreate,
    BudgetResponse,
    BudgetStatusResponse,
    BudgetUpdate,
)
from app.modules.personal_finance.budgets.service import (
    close_budget,
    create_budget,
    get_budget,
    get_budgets_status,
    list_budgets,
    update_budget,
)

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=list[BudgetResponse])
async def list_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[BudgetResponse]:
    """Lista los presupuestos activos del usuario."""
    budgets = await list_budgets(db, user.id)
    return [BudgetResponse.model_validate(b) for b in budgets]


@router.get("/status", response_model=BudgetStatusResponse)
async def status_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BudgetStatusResponse:
    """Estado de cada presupuesto activo vs gasto del mes en curso.

    Devuelve `items[].{budget, spent_this_month, remaining,
    percent_used, status}` + `month_start`/`month_end` (UTC).
    """
    return await get_budgets_status(db, user.id)


@router.get("/{budget_id}", response_model=BudgetResponse)
async def get_endpoint(
    budget_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BudgetResponse:
    """Obtiene un presupuesto por ID."""
    budget = await get_budget(db, budget_id, user.id)
    return BudgetResponse.model_validate(budget)


@router.post("", response_model=BudgetResponse, status_code=201)
async def create_endpoint(
    body: BudgetCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BudgetResponse:
    """Crea un nuevo presupuesto. 409 si ya existe activo para esa
    categoría (o global).
    """
    budget = await create_budget(db, user.id, body)
    await db.commit()
    return BudgetResponse.model_validate(budget)


@router.put("/{budget_id}", response_model=BudgetResponse)
async def update_endpoint(
    budget_id: uuid.UUID,
    body: BudgetUpdate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BudgetResponse:
    """Actualiza amount/currency. `effective_from` y `category_id`
    son inmutables — para cambiarlos, cerrar y crear nuevo.
    """
    budget = await update_budget(db, budget_id, user.id, body)
    await db.commit()
    return BudgetResponse.model_validate(budget)


@router.delete("/{budget_id}", status_code=204, response_class=Response)
async def delete_endpoint(
    budget_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Cierra el presupuesto (`effective_to = today`). Si ya estaba
    cerrado en el pasado, hace DELETE real para limpiar.
    """
    await close_budget(db, budget_id, user.id)
    await db.commit()
    return Response(status_code=204)
