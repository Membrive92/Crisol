"""Queries de agregación de Capa 1 del módulo deuda (PHASE-30.2)."""

from __future__ import annotations

import calendar
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.categories.models import Category, CategoryRole
from app.modules.personal_finance.transactions.models import Transaction

DEBT_ROLES: frozenset[CategoryRole] = frozenset(
    {CategoryRole.DEBT_PAYMENT, CategoryRole.DEBT_INTEREST}
)


def _month_start_utc(d: date) -> datetime:
    return datetime(d.year, d.month, 1, tzinfo=UTC)


def _month_end_utc(d: date) -> datetime:
    last_day = calendar.monthrange(d.year, d.month)[1]
    return datetime(d.year, d.month, last_day, 23, 59, 59, tzinfo=UTC)


async def aggregate_debt_payments_by_role(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    start: datetime,
    end: datetime,
) -> dict[CategoryRole, Decimal]:
    """Σ amount agrupado por `Category.role` para categorías de deuda.

    Excluye papelera y txs de transferencia interna. Devuelve `Decimal('0')`
    en ambos roles cuando no hay datos para que el caller no tenga que
    distinguir entre "no hay key" y "hay key con 0".
    """
    query = (
        select(Category.role, func.coalesce(func.sum(Transaction.amount), 0))
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_(None))
        .where(Transaction.currency == currency)
        .where(Category.role.in_(DEBT_ROLES))
        .where(Transaction.occurred_at >= start)
        .where(Transaction.occurred_at <= end)
        .group_by(Category.role)
    )
    result = await db.execute(query)
    totals: dict[CategoryRole, Decimal] = {
        CategoryRole.DEBT_PAYMENT: Decimal("0"),
        CategoryRole.DEBT_INTEREST: Decimal("0"),
    }
    for role, amount in result.all():
        totals[role] = Decimal(amount)
    return totals


async def aggregate_debt_payments_by_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    start: datetime,
    end: datetime,
) -> list[tuple[str, CategoryRole, Decimal]]:
    """Devuelve `(category_name, role, total)` para construir el donut
    de composición por tipo. El service mapea name → bucket
    (mortgage/loan/credit_card/other)."""
    query = (
        select(
            Category.name,
            Category.role,
            func.coalesce(func.sum(Transaction.amount), 0),
        )
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_(None))
        .where(Transaction.currency == currency)
        .where(Category.role.in_(DEBT_ROLES))
        .where(Transaction.occurred_at >= start)
        .where(Transaction.occurred_at <= end)
        .group_by(Category.name, Category.role)
    )
    rows = (await db.execute(query)).all()
    return [(name, role, Decimal(amount)) for name, role, amount in rows]


async def monthly_debt_series(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    months: list[date],
) -> list[tuple[date, Decimal, Decimal]]:
    """Para cada mes de `months` (primer día de cada uno) devuelve
    `(month, total_payments, interests)`.

    Hace una sola query agrupada por `(año, mes, role)` y rellena los
    huecos con 0 en el service — más barato que iterar mes a mes.
    """
    if not months:
        return []
    start = _month_start_utc(months[0])
    end = _month_end_utc(months[-1])

    year_expr = func.extract("year", Transaction.occurred_at)
    month_expr = func.extract("month", Transaction.occurred_at)
    interest_amount = case(
        (Category.role == CategoryRole.DEBT_INTEREST, Transaction.amount),
        else_=Decimal("0"),
    )

    query = (
        select(
            year_expr.label("y"),
            month_expr.label("m"),
            func.coalesce(func.sum(Transaction.amount), 0).label("payments"),
            func.coalesce(func.sum(interest_amount), 0).label("interests"),
        )
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_(None))
        .where(Transaction.currency == currency)
        .where(Category.role.in_(DEBT_ROLES))
        .where(Transaction.occurred_at >= start)
        .where(Transaction.occurred_at <= end)
        .group_by("y", "m")
    )
    rows = (await db.execute(query)).all()
    by_month: dict[tuple[int, int], tuple[Decimal, Decimal]] = {
        (int(r.y), int(r.m)): (Decimal(r.payments), Decimal(r.interests))
        for r in rows
    }

    series: list[tuple[date, Decimal, Decimal]] = []
    for month_start in months:
        payments, interests = by_month.get(
            (month_start.year, month_start.month),
            (Decimal("0"), Decimal("0")),
        )
        series.append((month_start, payments, interests))
    return series
