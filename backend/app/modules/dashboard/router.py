"""Router del módulo dashboard.

Todos los endpoints son GET (read-only). El `user_id` viene del JWT vía
`CurrentUser`. La moneda por defecto es USD (se puede cambiar con
`?currency=EUR`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.dashboard.schemas import (
    CategoryBreakdownItem,
    MonthlyBucket,
    SummaryResponse,
    TopExpenseItem,
)
from app.modules.dashboard.service import (
    get_breakdown_by_category,
    get_monthly_breakdown,
    get_summary,
    get_top_expenses,
)
from app.modules.personal_finance.categories.models import CategoryKind

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_DEFAULT_CURRENCY = "USD"


@router.get("/summary", response_model=SummaryResponse)
async def summary_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    currency: str = Query(default=_DEFAULT_CURRENCY, min_length=3, max_length=3),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> SummaryResponse:
    """Balance, ingresos, gastos y total de movimientos."""
    return await get_summary(
        db,
        user.id,
        currency.upper(),
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/by-category", response_model=list[CategoryBreakdownItem])
async def by_category_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    currency: str = Query(default=_DEFAULT_CURRENCY, min_length=3, max_length=3),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    kind: CategoryKind | None = None,
) -> list[CategoryBreakdownItem]:
    """Totales por categoría (incluye bucket "Sin categoría" si `kind` es None)."""
    return await get_breakdown_by_category(
        db,
        user.id,
        currency.upper(),
        date_from=date_from,
        date_to=date_to,
        kind=kind,
    )


@router.get("/by-month", response_model=list[MonthlyBucket])
async def by_month_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    year: int = Query(default_factory=lambda: datetime.now().year, ge=1970, le=2999),
    currency: str = Query(default=_DEFAULT_CURRENCY, min_length=3, max_length=3),
) -> list[MonthlyBucket]:
    """12 buckets mensuales (ingresos, gastos, balance) para el año pedido."""
    return await get_monthly_breakdown(db, user.id, currency.upper(), year)


@router.get("/top-expenses", response_model=list[TopExpenseItem])
async def top_expenses_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    currency: str = Query(default=_DEFAULT_CURRENCY, min_length=3, max_length=3),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=10, ge=1, le=50),
) -> list[TopExpenseItem]:
    """Top N gastos ordenados por importe desc."""
    return await get_top_expenses(
        db,
        user.id,
        currency.upper(),
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
