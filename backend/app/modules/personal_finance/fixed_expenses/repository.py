"""Queries del módulo fixed_expenses (PHASE-13.1, renombrado en
PHASE-17.1)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.fixed_expenses.models import (
    FixedExpense,
    FixedExpenseStatus,
)


async def list_fixed_expenses(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: FixedExpenseStatus | None = None,
) -> list[FixedExpense]:
    """Lista los gastos fijos del usuario, opcionalmente filtrados
    por status. Orden: `next_due ASC` para que la próxima ejecución
    quede arriba.
    """
    query = (
        select(FixedExpense)
        .where(FixedExpense.user_id == user_id)
        .order_by(FixedExpense.next_due.asc())
    )
    if status is not None:
        query = query.where(FixedExpense.status == status)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_fixed_expense_by_id(
    db: AsyncSession, fixed_expense_id: uuid.UUID, user_id: uuid.UUID
) -> FixedExpense | None:
    """Obtiene un gasto fijo por ID, scoped al user."""
    query = select(FixedExpense).where(
        FixedExpense.user_id == user_id,
        FixedExpense.id == fixed_expense_id,
    )
    return (await db.execute(query)).scalar_one_or_none()


async def find_by_fingerprint(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    merchant: str,
    amount: Decimal,
    currency: str,
    cadence_days: int,
) -> FixedExpense | None:
    """Busca un gasto fijo existente por su huella
    (merchant + amount + currency + cadence). Usado por el detector
    para refrescar datos en lugar de duplicar.
    """
    query = select(FixedExpense).where(
        FixedExpense.user_id == user_id,
        FixedExpense.merchant == merchant,
        FixedExpense.amount == amount,
        FixedExpense.currency == currency,
        FixedExpense.cadence_days == cadence_days,
    )
    return (await db.execute(query)).scalar_one_or_none()


async def create_fixed_expense(
    db: AsyncSession, fixed_expense: FixedExpense
) -> FixedExpense:
    """Persiste un gasto fijo nuevo."""
    db.add(fixed_expense)
    await db.flush()
    await db.refresh(fixed_expense)
    return fixed_expense


async def delete_fixed_expense(db: AsyncSession, fixed_expense: FixedExpense) -> None:
    """DELETE real."""
    await db.delete(fixed_expense)
    await db.flush()
