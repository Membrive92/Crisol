"""Router del módulo deuda (PHASE-30.2)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.debt.schemas import (
    DebtCategorySummary,
    DebtTimeRange,
)
from app.modules.personal_finance.debt.service import compute_category_summary

router = APIRouter(prefix="/debt", tags=["debt"])


@router.get("/category-summary", response_model=DebtCategorySummary)
async def category_summary_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    range: Annotated[DebtTimeRange, Query()] = "ytd",
) -> DebtCategorySummary:
    """Capa 1 del módulo deuda: KPIs derivados del flujo de
    categorías marcadas como deuda (PHASE-30.2).

    No requiere liability accounts — basta con que el usuario
    categorice sus pagos. Los liability accounts existentes se
    integran como capa de detalle vía `/accounts/debt-health` y la
    capa 2 de la UI.
    """
    return await compute_category_summary(db, user.id, range_=range)
