"""Lógica de negocio del módulo dashboard.

Read-only: agregaciones sobre `transactions`. El service decide entre
los dos modos de moneda:

- **legacy** (`currency` filtra): mantiene el contrato anterior a
  PHASE-8.3 — totales por una sola moneda, sin conversión.
- **cross-currency** (`target_currency`): convierte cada transacción a
  la moneda destino con la tasa **del día de su `occurred_at`** (vía
  `conversion.converted_amount_expr`) y agrega después.

Si llegan ambos parámetros, gana `target_currency` — es el modo
preferido. Si no llega ninguno, se asume legacy con `_DEFAULT_CURRENCY`.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date as SQLDate
from sqlalchemy import cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.currency import service as currency_service
from app.modules.personal_finance.categories.models import CategoryKind
from app.modules.personal_finance.dashboard import repository
from app.modules.personal_finance.dashboard.schemas import (
    CategoryBreakdownItem,
    MonthlyBucket,
    SummaryResponse,
    TopExpenseItem,
)
from app.modules.personal_finance.transactions.models import Transaction

_UNCATEGORIZED_NAME = "Sin categoría"


async def ensure_rates_for_user_scope(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    target_currency: str,
    date_from: datetime | None,
    date_to: datetime | None,
) -> None:
    """Antes de agregar en cross-currency, asegura que las tasas para
    cada día con transacciones existan en BD.

    Sin esta llamada, transacciones históricas (más antiguas que el
    snapshot embebido + ventana de 14d) quedarían fuera del SUM con
    `unconvertible_count > 0`. Con ella, el primer request de cada
    fecha dispara fetch + persist + queda cacheado para siempre.

    Reusable desde otros módulos (transactions también lo llama antes
    de listar con `target_currency`).
    """
    target = target_currency.upper()
    query = (
        select(cast(Transaction.occurred_at, SQLDate))
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.currency != target)
        .distinct()
    )
    if date_from is not None:
        query = query.where(Transaction.occurred_at >= date_from)
    if date_to is not None:
        query = query.where(Transaction.occurred_at <= date_to)

    result = await db.execute(query)
    dates: list[date] = [row[0] for row in result.all()]
    if not dates:
        return
    await currency_service.ensure_rates_for_dates(db, dates)


def _resolve_mode(
    currency: str | None, target_currency: str | None
) -> tuple[str | None, str | None, str]:
    """Devuelve `(legacy_currency, target_currency, displayed_currency)`.

    - Si `target_currency` viene → modo cross-currency. `legacy=None`.
    - Si sólo `currency` → modo legacy. `target=None`.
    - Si ninguno → usar `currency` legacy con default upstream.
    """
    if target_currency is not None:
        target = target_currency.upper()
        return None, target, target
    if currency is not None:
        cur = currency.upper()
        return cur, None, cur
    return None, None, ""


async def list_user_currencies(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[str]:
    """Monedas distintas presentes en las transacciones del usuario."""
    return await repository.list_user_currencies(db, user_id)


async def get_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> SummaryResponse:
    """Balance global. Soporta legacy (`currency`) y cross-currency (`target_currency`)."""
    legacy, target, displayed = _resolve_mode(currency, target_currency)

    if target is not None:
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target,
            date_from=date_from,
            date_to=date_to,
        )

    income, expenses, count, unconvertible = await repository.get_summary_aggregates(
        db,
        user_id,
        currency=legacy,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
    )

    prev_income: Decimal | None = None
    prev_expenses: Decimal | None = None
    prev_balance: Decimal | None = None
    if date_from is not None and date_to is not None:
        period_length = date_to - date_from
        prev_to = date_from
        prev_from = date_from - period_length
        prev_totals = await repository.get_totals_by_kind(
            db,
            user_id,
            currency=legacy,
            target_currency=target,
            date_from=prev_from,
            date_to=prev_to,
        )
        prev_income = prev_totals.get(CategoryKind.INCOME, Decimal("0"))
        prev_expenses = prev_totals.get(CategoryKind.EXPENSE, Decimal("0"))
        prev_balance = prev_income - prev_expenses

    return SummaryResponse(
        income=income,
        expenses=expenses,
        balance=income - expenses,
        transaction_count=count,
        currency=displayed,
        unconvertible_count=unconvertible,
        previous_period_income=prev_income,
        previous_period_expenses=prev_expenses,
        previous_period_balance=prev_balance,
    )


async def get_breakdown_by_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    kind: CategoryKind | None = None,
) -> list[CategoryBreakdownItem]:
    """Desglose por categoría."""
    legacy, target, _ = _resolve_mode(currency, target_currency)
    if target is not None:
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target,
            date_from=date_from,
            date_to=date_to,
        )
    rows = await repository.get_breakdown_by_category(
        db,
        user_id,
        currency=legacy,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        kind=kind,
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
    *,
    year: int,
    currency: str | None = None,
    target_currency: str | None = None,
) -> list[MonthlyBucket]:
    """12 buckets mensuales para el año."""
    legacy, target, _ = _resolve_mode(currency, target_currency)
    if target is not None:
        # `by-month` cubre el año completo, así que el rango es ese.
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target,
            date_from=datetime(year, 1, 1),
            date_to=datetime(year, 12, 31, 23, 59, 59),
        )
    rows = await repository.get_totals_by_month(
        db, user_id, year=year, currency=legacy, target_currency=target
    )

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
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 10,
) -> list[TopExpenseItem]:
    """Top N gastos por importe convertido desc."""
    legacy, target, _ = _resolve_mode(currency, target_currency)
    if target is not None:
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target,
            date_from=date_from,
            date_to=date_to,
        )
    rows = await repository.get_top_expenses(
        db,
        user_id,
        currency=legacy,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return [
        TopExpenseItem(
            transaction_id=tx.id,
            description=tx.description,
            # `converted` viene en moneda destino cuando hay target. En
            # modo legacy es el amount original.
            amount=converted if converted is not None else tx.amount,
            occurred_at=tx.occurred_at,
            category_id=tx.category_id,
            category_name=category_name,
            original_amount=tx.amount,
            original_currency=tx.currency,
        )
        for tx, category_name, converted in rows
    ]
