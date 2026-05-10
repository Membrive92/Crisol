"""Queries de agregación del módulo dashboard.

Todas las queries filtran por `user_id` (aislamiento multi-tenant). El
modo de moneda es explícito vía dos parámetros mutuamente excluyentes:

- `currency` (legacy): filtra por esa moneda y agrega importes crudos.
  Equivalente al comportamiento pre-PHASE-8.3.
- `target_currency` (PHASE-8.3): no filtra por moneda. Convierte cada
  transacción a `target_currency` con la tasa **del día de su
  `occurred_at`** (vía `conversion.converted_amount_expr`) antes de
  agregar. Las transacciones sin tasa disponible quedan excluidas
  (NULL → SUM ignora). El service expone `missing_count` para que el
  caller sepa cuántas se quedaron fuera.

El service decide cuál usar según los parámetros que recibe el router.
Aquí ofrecemos ambos modos vía las flags `currency`/`target_currency`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, case, extract, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.categories.models import Category, CategoryKind
from app.modules.personal_finance.dashboard.conversion import (
    amount_is_convertible_expr,
    converted_amount_expr,
)
from app.modules.personal_finance.transactions.models import Transaction


async def list_user_currencies(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[str]:
    """Devuelve las monedas distintas en las transacciones del usuario.

    Excluye soft-deleted (PHASE-10.1) — una moneda que sólo existe en
    transacciones trasheadas no debe aparecer en el selector global.
    """
    query = (
        select(Transaction.currency)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .distinct()
        .order_by(Transaction.currency)
    )
    result = await db.execute(query)
    return [row[0] for row in result.all()]


def _apply_scope[Q: Select[Any]](
    query: Q,
    *,
    user_id: uuid.UUID,
    currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Q:
    """Filtros comunes (user_id, opcional currency legacy, rango de fechas).

    Siempre excluye soft-deleted (PHASE-10.1) — todas las agregaciones
    del dashboard ignoran transacciones en papelera. Cuando `currency`
    es None la query NO filtra por moneda — el caller está usando
    modo `target_currency` y agrega cross-currency.

    PHASE-19.3: además excluye las txs con `transfer_pair_id IS NOT NULL`
    — son movimientos internos entre cuentas del usuario y no afectan
    al flujo neto (sí al saldo individual de cada cuenta).
    """
    query = query.where(Transaction.user_id == user_id)
    query = query.where(Transaction.deleted_at.is_(None))
    query = query.where(Transaction.transfer_pair_id.is_(None))
    if currency is not None:
        query = query.where(Transaction.currency == currency)
    if date_from is not None:
        query = query.where(Transaction.occurred_at >= date_from)
    if date_to is not None:
        query = query.where(Transaction.occurred_at <= date_to)
    return query


def _amount_expr(target_currency: str | None) -> Any:
    """Devuelve la columna a sumar — convertida si target, cruda si no."""
    if target_currency is None:
        return Transaction.amount
    return converted_amount_expr(target_currency)


async def get_totals_by_kind(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[CategoryKind, Decimal]:
    """Suma `amount` agrupando por `category.kind` (income/expense).

    Las transacciones sin categoría quedan fuera. En modo
    `target_currency`, las que no tienen tasa disponible también.
    """
    amount = _amount_expr(target_currency)
    query = (
        select(Category.kind, func.coalesce(func.sum(amount), 0))
        .join(Category, Category.id == Transaction.category_id)
        .group_by(Category.kind)
    )
    query = _apply_scope(
        query,
        user_id=user_id,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
    )

    result = await db.execute(query)
    return {kind: Decimal(total) for kind, total in result.all()}


async def get_summary_aggregates(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[Decimal, Decimal, int, int]:
    """Una sola query con income, expense, total_count y unconvertible.

    Reemplaza las 3 queries serial pre-PHASE-8.4 (totals_by_kind +
    count_transactions + count_unconvertible). Las sumas income/expense
    se computan con `CASE` por categoría sobre el outerjoin (las
    transacciones sin categoría no contribuyen pero sí se cuentan).
    El `unconvertible_count` viene como **subquery escalar** dentro
    del mismo SELECT — sólo consulta cuando hay `target_currency`,
    en modo legacy es literal `0`.
    """
    amount = _amount_expr(target_currency)
    income_amount = case(
        (Category.kind == CategoryKind.INCOME, amount), else_=Decimal("0")
    )
    expense_amount = case(
        (Category.kind == CategoryKind.EXPENSE, amount), else_=Decimal("0")
    )

    if target_currency is not None:
        unconv_subq = select(func.count()).select_from(Transaction).where(
            ~amount_is_convertible_expr(target_currency)
        )
        unconv_subq = _apply_scope(
            unconv_subq,
            user_id=user_id,
            currency=None,
            date_from=date_from,
            date_to=date_to,
        )
        unconv_col = unconv_subq.scalar_subquery().label("unconvertible_count")
    else:
        unconv_col = literal(0).label("unconvertible_count")

    query = (
        select(
            func.coalesce(func.sum(income_amount), Decimal("0")).label("income"),
            func.coalesce(func.sum(expense_amount), Decimal("0")).label("expense"),
            func.count(Transaction.id).label("total_count"),
            unconv_col,
        )
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
    )
    query = _apply_scope(
        query,
        user_id=user_id,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
    )

    row = (await db.execute(query)).one()
    return (
        Decimal(row.income),
        Decimal(row.expense),
        int(row.total_count),
        int(row.unconvertible_count),
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
) -> list[
    tuple[
        uuid.UUID | None,
        str | None,
        CategoryKind | None,
        str | None,
        str | None,
        Decimal,
        int,
    ]
]:
    """Totales por categoría. Incluye bucket con `category_id=None`.

    Devuelve tuplas con `(id, name, kind, color, icon, total, count)` —
    color/icon llegan al frontend para que la UI (donut, chips,
    breakdowns) pinte cada categoría con su personalización.
    """
    amount = _amount_expr(target_currency)
    query = (
        select(
            Category.id,
            Category.name,
            Category.kind,
            Category.color,
            Category.icon,
            func.coalesce(func.sum(amount), 0),
            func.count(Transaction.id),
        )
        .outerjoin(Category, Category.id == Transaction.category_id)
        .group_by(
            Category.id,
            Category.name,
            Category.kind,
            Category.color,
            Category.icon,
        )
    )
    query = _apply_scope(
        query,
        user_id=user_id,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
    )
    if kind is not None:
        query = query.where(Category.kind == kind)

    result = await db.execute(query)
    return [
        (cat_id, cat_name, cat_kind, cat_color, cat_icon, Decimal(total), int(count))
        for cat_id, cat_name, cat_kind, cat_color, cat_icon, total, count in result.all()
    ]


async def get_totals_by_month(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    year: int,
    currency: str | None = None,
    target_currency: str | None = None,
) -> list[tuple[int, CategoryKind, Decimal]]:
    """Totales por mes y `category.kind` para el año pedido."""
    month_col = extract("month", Transaction.occurred_at)
    year_col = extract("year", Transaction.occurred_at)
    amount = _amount_expr(target_currency)

    query = (
        select(month_col, Category.kind, func.coalesce(func.sum(amount), 0))
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        # PHASE-19.3: las transferencias internas no son cashflow real.
        .where(Transaction.transfer_pair_id.is_(None))
        .where(year_col == year)
        .group_by(month_col, Category.kind)
    )
    if currency is not None:
        query = query.where(Transaction.currency == currency)

    result = await db.execute(query)
    return [(int(month), kind, Decimal(total)) for month, kind, total in result.all()]


async def get_top_expenses(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 10,
) -> list[tuple[Transaction, str | None, Decimal | None]]:
    """Top N gastos ordenados por importe convertido desc.

    Devuelve `(transaction, category_name, converted_amount)` — el
    importe convertido se devuelve para que el caller pueda exponerlo
    además del original. En modo legacy `converted_amount` es igual al
    `amount` de la transacción.
    """
    amount = _amount_expr(target_currency)
    query = (
        select(Transaction, Category.name, amount.label("converted_amount"))
        .join(Category, Category.id == Transaction.category_id)
        .where(Category.kind == CategoryKind.EXPENSE)
    )
    query = _apply_scope(
        query,
        user_id=user_id,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
    )
    # Ordenamos por el importe convertido — los gastos en moneda débil
    # no deben aparecer artificialmente arriba sólo por número grande.
    query = query.order_by(amount.desc().nulls_last()).limit(limit)

    result = await db.execute(query)
    return [
        (tx, name, Decimal(converted) if converted is not None else None)
        for tx, name, converted in result.all()
    ]
