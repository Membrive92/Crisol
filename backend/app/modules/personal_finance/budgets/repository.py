"""Queries a DB del módulo budgets (PHASE-12.1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.budgets.models import Budget
from app.modules.personal_finance.categories.models import Category, CategoryKind
from app.modules.personal_finance.dashboard.conversion import (
    amount_is_convertible_expr,
    converted_amount_expr,
)
from app.modules.personal_finance.transactions.models import Transaction


async def list_active_budgets(
    db: AsyncSession, user_id: uuid.UUID, *, today: date
) -> list[Budget]:
    """Lista presupuestos activos: `effective_to IS NULL` o `>= today`."""
    query = (
        select(Budget)
        .where(Budget.user_id == user_id)
        .where(or_(Budget.effective_to.is_(None), Budget.effective_to >= today))
        .order_by(Budget.created_at.desc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_budget_by_id(
    db: AsyncSession, budget_id: uuid.UUID, user_id: uuid.UUID
) -> Budget | None:
    """Obtiene un presupuesto por ID, filtrando por user_id."""
    query = select(Budget).where(
        Budget.user_id == user_id, Budget.id == budget_id
    )
    return (await db.execute(query)).scalar_one_or_none()


async def get_active_budget_for_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    category_id: uuid.UUID | None,
    today: date,
) -> Budget | None:
    """Devuelve el presupuesto activo para una categoría dada (o global
    si `category_id IS NULL`). Usado por el service para evitar
    duplicados antes de crear uno nuevo.
    """
    query = (
        select(Budget)
        .where(Budget.user_id == user_id)
        .where(or_(Budget.effective_to.is_(None), Budget.effective_to >= today))
    )
    if category_id is None:
        query = query.where(Budget.category_id.is_(None))
    else:
        query = query.where(Budget.category_id == category_id)
    return (await db.execute(query)).scalar_one_or_none()


async def create_budget(db: AsyncSession, budget: Budget) -> Budget:
    """Persiste un nuevo presupuesto."""
    db.add(budget)
    await db.flush()
    await db.refresh(budget)
    return budget


async def delete_budget(db: AsyncSession, budget: Budget) -> None:
    """DELETE real (no soft). Por ahora la papelera de transacciones
    es el único módulo con soft-delete; presupuestos son baratos de
    recrear.
    """
    await db.delete(budget)
    await db.flush()


async def sum_expenses_in_period(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str,
    month_start: datetime,
    month_end: datetime,
    category_id: uuid.UUID | None,
    convert_other_currencies: bool = False,
) -> tuple[Decimal, int]:
    """Suma `amount` de transacciones activas de gasto en el rango.

    Comportamiento por flag (PHASE-16):

    - `convert_other_currencies=False` (default, pre-PHASE-16):
      filtra `Transaction.currency == currency`. Devuelve
      `(total, 0)` — sin convertibilidad en juego.
    - `convert_other_currencies=True`: NO filtra por currency. Suma
      todas las txs de gasto convirtiendo a `currency` con
      `converted_amount_expr` (tasa del día de cada tx, mismo
      helper que el dashboard PHASE-8.3). Las txs sin tasa
      disponible se excluyen del SUM (NULL → SUM ignora) y se
      cuentan como `unconvertible`.

    Filtro por categoría opcional — `None` = todas las de gasto.
    """
    if not convert_other_currencies:
        sum_query = (
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .select_from(Transaction)
            .join(Category, Category.id == Transaction.category_id)
            .where(Transaction.user_id == user_id)
            .where(Transaction.deleted_at.is_(None))
            # PHASE-19.3: una salida que es transferencia interna no
            # cuenta como gasto y no consume presupuesto.
            .where(Transaction.transfer_pair_id.is_(None))
            .where(Transaction.currency == currency)
            .where(Transaction.occurred_at >= month_start)
            .where(Transaction.occurred_at <= month_end)
            .where(Category.kind == CategoryKind.EXPENSE)
        )
        if category_id is not None:
            sum_query = sum_query.where(Transaction.category_id == category_id)
        total = (await db.execute(sum_query)).scalar_one()
        return Decimal(total), 0

    converted = converted_amount_expr(currency)
    convertible = amount_is_convertible_expr(currency)

    sum_query = (
        select(func.coalesce(func.sum(converted), 0))
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_(None))
        .where(Transaction.occurred_at >= month_start)
        .where(Transaction.occurred_at <= month_end)
        .where(Category.kind == CategoryKind.EXPENSE)
    )
    if category_id is not None:
        sum_query = sum_query.where(Transaction.category_id == category_id)

    unconv_query = (
        select(func.count())
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_(None))
        .where(Transaction.occurred_at >= month_start)
        .where(Transaction.occurred_at <= month_end)
        .where(Category.kind == CategoryKind.EXPENSE)
        .where(~convertible)
    )
    if category_id is not None:
        unconv_query = unconv_query.where(Transaction.category_id == category_id)

    total = (await db.execute(sum_query)).scalar_one()
    unconv = (await db.execute(unconv_query)).scalar_one()
    return Decimal(total), int(unconv)
