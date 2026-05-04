"""Router del módulo dashboard.

Todos los endpoints son GET (read-only). El `user_id` viene del JWT vía
`CurrentUser`.

Modo de moneda: dos parámetros mutuamente excluyentes (gana
`target_currency` si llegan ambos).

- `?currency=EUR` (legacy) — filtra por esa moneda y agrega importes
  crudos. Comportamiento pre-PHASE-8.3.
- `?target_currency=EUR` (PHASE-8.3) — no filtra; convierte cada
  transacción al destino con la tasa **del día de su `occurred_at`** y
  agrega después. Las transacciones sin tasa se cuentan en
  `unconvertible_count` (sólo `summary` lo expone).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.categories.models import CategoryKind
from app.modules.personal_finance.dashboard.schemas import (
    CategoryBreakdownItem,
    MonthlyBucket,
    SummaryResponse,
    TopExpenseItem,
)
from app.modules.personal_finance.dashboard.service import (
    get_breakdown_by_category,
    get_monthly_breakdown,
    get_summary,
    get_top_expenses,
    list_user_currencies,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_DEFAULT_CURRENCY = "USD"


def _resolve_currency_params(
    currency: str | None, target_currency: str | None
) -> tuple[str | None, str | None]:
    """Si no llega ninguno, default a `currency=USD` (legacy)."""
    if target_currency is None and currency is None:
        return _DEFAULT_CURRENCY, None
    return currency, target_currency


@router.get("/currencies", response_model=list[str])
async def currencies_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[str]:
    """Monedas distintas presentes en las transacciones del usuario."""
    return await list_user_currencies(db, user.id)


@router.get("/summary", response_model=SummaryResponse)
async def summary_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> SummaryResponse:
    """Balance, ingresos, gastos y total de movimientos."""
    cur, target = _resolve_currency_params(currency, target_currency)
    return await get_summary(
        db,
        user.id,
        currency=cur,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/by-category", response_model=list[CategoryBreakdownItem])
async def by_category_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    kind: CategoryKind | None = None,
) -> list[CategoryBreakdownItem]:
    """Totales por categoría."""
    cur, target = _resolve_currency_params(currency, target_currency)
    return await get_breakdown_by_category(
        db,
        user.id,
        currency=cur,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        kind=kind,
    )


@router.get("/by-month", response_model=list[MonthlyBucket])
async def by_month_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    year: int = Query(default_factory=lambda: datetime.now().year, ge=1970, le=2999),
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> list[MonthlyBucket]:
    """12 buckets mensuales para el año."""
    cur, target = _resolve_currency_params(currency, target_currency)
    return await get_monthly_breakdown(
        db, user.id, year=year, currency=cur, target_currency=target
    )


@router.get("/top-expenses", response_model=list[TopExpenseItem])
async def top_expenses_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=10, ge=1, le=50),
) -> list[TopExpenseItem]:
    """Top N gastos por importe (convertido si target_currency)."""
    cur, target = _resolve_currency_params(currency, target_currency)
    return await get_top_expenses(
        db,
        user.id,
        currency=cur,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
