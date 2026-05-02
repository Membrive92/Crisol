"""Lógica de negocio del módulo dashboard.

El dashboard es read-only: no comita, no muta, sólo agrega sobre las tablas
`transactions` y `categories`. El user_id se recibe como parámetro (vía
`CurrentUser` en el router).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.categories.models import CategoryKind
from app.modules.personal_finance.dashboard import repository
from app.modules.personal_finance.dashboard.schemas import (
    CategoryBreakdownItem,
    MonthlyBucket,
    SummaryResponse,
    TopExpenseItem,
)

_UNCATEGORIZED_NAME = "Sin categoría"


async def list_user_currencies(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[str]:
    """Monedas distintas presentes en las transacciones del usuario."""
    return await repository.list_user_currencies(db, user_id)


async def get_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> SummaryResponse:
    """Balance global (ingresos, gastos, neto) y cuenta de transacciones.

    Si llegan `date_from` y `date_to`, se calcula además el rango previo
    de igual longitud (terminando justo antes de `date_from`) para que el
    frontend pueda pintar deltas vs periodo anterior.
    """
    totals = await repository.get_totals_by_kind(
        db, user_id, currency, date_from=date_from, date_to=date_to
    )
    income = totals.get(CategoryKind.INCOME, Decimal("0"))
    expenses = totals.get(CategoryKind.EXPENSE, Decimal("0"))
    count = await repository.count_transactions(
        db, user_id, currency, date_from=date_from, date_to=date_to
    )

    prev_income: Decimal | None = None
    prev_expenses: Decimal | None = None
    prev_balance: Decimal | None = None
    if date_from is not None and date_to is not None:
        # Periodo previo de la misma duración, terminando justo antes de date_from.
        # Ej.: rango "2026-01-01..2026-12-31" → previo "2025-01-01..2025-12-31".
        period_length = date_to - date_from
        prev_to = date_from
        prev_from = date_from - period_length
        prev_totals = await repository.get_totals_by_kind(
            db, user_id, currency, date_from=prev_from, date_to=prev_to
        )
        prev_income = prev_totals.get(CategoryKind.INCOME, Decimal("0"))
        prev_expenses = prev_totals.get(CategoryKind.EXPENSE, Decimal("0"))
        prev_balance = prev_income - prev_expenses

    return SummaryResponse(
        income=income,
        expenses=expenses,
        balance=income - expenses,
        transaction_count=count,
        currency=currency,
        previous_period_income=prev_income,
        previous_period_expenses=prev_expenses,
        previous_period_balance=prev_balance,
    )


async def get_breakdown_by_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    kind: CategoryKind | None = None,
) -> list[CategoryBreakdownItem]:
    """Desglose por categoría. Bucket "Sin categoría" si `kind` es None."""
    rows = await repository.get_breakdown_by_category(
        db, user_id, currency, date_from=date_from, date_to=date_to, kind=kind
    )
    items = [
        CategoryBreakdownItem(
            category_id=cat_id,
            category_name=cat_name if cat_name is not None else _UNCATEGORIZED_NAME,
            category_kind=cat_kind.value if cat_kind is not None else None,
            total=total,
            count=count,
        )
        for cat_id, cat_name, cat_kind, total, count in rows
    ]
    items.sort(key=lambda i: i.total, reverse=True)
    return items


async def get_monthly_breakdown(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    year: int,
) -> list[MonthlyBucket]:
    """12 buckets (uno por mes) con ingresos, gastos y balance del año pedido."""
    rows = await repository.get_totals_by_month(db, user_id, currency, year)

    income_per_month: dict[int, Decimal] = {m: Decimal("0") for m in range(1, 13)}
    expenses_per_month: dict[int, Decimal] = {m: Decimal("0") for m in range(1, 13)}

    for month, kind, total in rows:
        if kind == CategoryKind.INCOME:
            income_per_month[month] = total
        elif kind == CategoryKind.EXPENSE:
            expenses_per_month[month] = total

    return [
        MonthlyBucket(
            month=f"{year:04d}-{m:02d}",
            income=income_per_month[m],
            expenses=expenses_per_month[m],
            balance=income_per_month[m] - expenses_per_month[m],
        )
        for m in range(1, 13)
    ]


async def get_top_expenses(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 10,
) -> list[TopExpenseItem]:
    """Top N gastos por importe desc dentro del rango."""
    rows = await repository.get_top_expenses(
        db, user_id, currency, date_from=date_from, date_to=date_to, limit=limit
    )
    return [
        TopExpenseItem(
            transaction_id=tx.id,
            description=tx.description,
            amount=tx.amount,
            occurred_at=tx.occurred_at,
            category_id=tx.category_id,
            category_name=category_name,
        )
        for tx, category_name in rows
    ]
