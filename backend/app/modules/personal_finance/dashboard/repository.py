"""Queries de agregación del módulo dashboard.

Todas las queries filtran por `user_id` (aislamiento multi-tenant) y por
`currency` (el dashboard devuelve totales en una única moneda). Se importan
los modelos `Transaction` y `Category` porque dashboard es una *vista*
read-only sobre esas tablas; no llama al service de otros módulos.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.categories.models import Category, CategoryKind
from app.modules.personal_finance.transactions.models import Transaction


async def list_user_currencies(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[str]:
    """Devuelve las monedas distintas en las transacciones del usuario.

    Útil para que el dashboard arranque con la moneda real del usuario
    en lugar de un default hardcodeado.
    """
    query = (
        select(Transaction.currency)
        .where(Transaction.user_id == user_id)
        .distinct()
        .order_by(Transaction.currency)
    )
    result = await db.execute(query)
    return [row[0] for row in result.all()]


def _apply_scope[Q: Select[Any]](
    query: Q,
    *,
    user_id: uuid.UUID,
    currency: str,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Q:
    """Aplica los filtros comunes (user_id, moneda, rango de fechas)."""
    query = query.where(Transaction.user_id == user_id)
    query = query.where(Transaction.currency == currency)
    if date_from is not None:
        query = query.where(Transaction.occurred_at >= date_from)
    if date_to is not None:
        query = query.where(Transaction.occurred_at <= date_to)
    return query


async def get_totals_by_kind(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[CategoryKind, Decimal]:
    """Suma `amount` agrupando por `category.kind` (income/expense).

    Las transacciones sin categoría quedan fuera (no tienen `kind`).
    """
    query = (
        select(Category.kind, func.coalesce(func.sum(Transaction.amount), 0))
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


async def count_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> int:
    """Cuenta todas las transacciones (incluyendo las sin categoría)."""
    query = select(func.count()).select_from(Transaction)
    query = _apply_scope(
        query,
        user_id=user_id,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
    )
    result = await db.execute(query)
    return int(result.scalar_one())


async def get_breakdown_by_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    kind: CategoryKind | None = None,
) -> list[tuple[uuid.UUID | None, str | None, CategoryKind | None, Decimal, int]]:
    """Totales por categoría. Incluye bucket con `category_id=None`.

    Si `kind` se especifica, el bucket "Sin categoría" se omite (no tiene kind).
    """
    query = (
        select(
            Category.id,
            Category.name,
            Category.kind,
            func.coalesce(func.sum(Transaction.amount), 0),
            func.count(Transaction.id),
        )
        .outerjoin(Category, Category.id == Transaction.category_id)
        .group_by(Category.id, Category.name, Category.kind)
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
        (cat_id, cat_name, cat_kind, Decimal(total), int(count))
        for cat_id, cat_name, cat_kind, total, count in result.all()
    ]


async def get_totals_by_month(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    year: int,
) -> list[tuple[int, CategoryKind, Decimal]]:
    """Totales agrupados por mes y por `category.kind` para el año pedido.

    Devuelve filas `(month_number, kind, total)`. El caller rellena los meses
    vacíos y calcula el balance.
    """
    month_col = extract("month", Transaction.occurred_at)
    year_col = extract("year", Transaction.occurred_at)

    query = (
        select(month_col, Category.kind, func.coalesce(func.sum(Transaction.amount), 0))
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.currency == currency)
        .where(year_col == year)
        .group_by(month_col, Category.kind)
    )

    result = await db.execute(query)
    return [(int(month), kind, Decimal(total)) for month, kind, total in result.all()]


async def get_top_expenses(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 10,
) -> list[tuple[Transaction, str | None]]:
    """Top N gastos (transacciones cuya categoría es `expense`), ordenados por importe desc.

    Las transacciones sin categoría se excluyen: no se puede confirmar que sean gasto.
    """
    query = (
        select(Transaction, Category.name)
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
    query = query.order_by(Transaction.amount.desc()).limit(limit)

    result = await db.execute(query)
    return [(tx, name) for tx, name in result.all()]
