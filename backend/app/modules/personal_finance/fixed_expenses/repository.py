"""Queries del módulo fixed_expenses (PHASE-13.1, renombrado en
PHASE-17.1)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import case, select
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


# Orden de preferencia cuando una huella tiene VARIAS filas (anomalía de
# datos, ver abajo): refrescamos la que el usuario gestiona de forma activa.
_STATUS_PREFERENCE = case(
    (FixedExpense.status == FixedExpenseStatus.CONFIRMED, 0),
    (FixedExpense.status == FixedExpenseStatus.PENDING, 1),
    (FixedExpense.status == FixedExpenseStatus.PAUSED, 2),
    (FixedExpense.status == FixedExpenseStatus.CANCELLED, 3),
    (FixedExpense.status == FixedExpenseStatus.DISMISSED, 4),
    else_=5,
)


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

    La huella se DISEÑÓ única por usuario, pero no lo garantiza ninguna
    restricción y hay formas históricas de duplicarla (deriva de la huella
    entre scans: un `amount`/`merchant` que cambió y volvió, la fusión por
    prefijo de PHASE-14.7…). Cuando hay varias filas —p. ej. una CONFIRMED y
    una DISMISSED de lo mismo— un `scalar_one_or_none()` reventaba TODO el
    scan del cron (`MultipleResultsFound`), no sólo esa huella.

    Devolvemos UNA fila de forma determinista, prefiriendo la que el usuario
    gestiona activamente (CONFIRMED > PENDING > … > DISMISSED) y, a igualdad,
    la vista más recientemente. Esto NO resucita un patrón descartado: el
    `scan` sólo crea fila nueva si aquí devolvemos `None`; devolver cualquier
    fila existente refresca sin duplicar, así que la supresión de lo dismissed
    se mantiene sea cual sea la fila elegida.
    """
    query = (
        select(FixedExpense)
        .where(
            FixedExpense.user_id == user_id,
            FixedExpense.merchant == merchant,
            FixedExpense.amount == amount,
            FixedExpense.currency == currency,
            FixedExpense.cadence_days == cadence_days,
        )
        .order_by(_STATUS_PREFERENCE, FixedExpense.last_seen_at.desc(), FixedExpense.id)
        .limit(1)
    )
    return (await db.execute(query)).scalars().first()


async def create_fixed_expense(db: AsyncSession, fixed_expense: FixedExpense) -> FixedExpense:
    """Persiste un gasto fijo nuevo."""
    db.add(fixed_expense)
    await db.flush()
    await db.refresh(fixed_expense)
    return fixed_expense


async def delete_fixed_expense(db: AsyncSession, fixed_expense: FixedExpense) -> None:
    """DELETE real."""
    await db.delete(fixed_expense)
    await db.flush()


async def list_due_for_autopost(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    today: date,
) -> list[FixedExpense]:
    """Gastos fijos con `auto_post=True`, status `confirmed` y
    `next_due <= today` (PHASE-17.2).

    `paused` y `cancelled` quedan fuera — el flag `auto_post` puede
    seguir on en BD pero el lifecycle gana: una hipoteca pausada no
    se postea hasta que el usuario la reanude. `pending` también
    queda fuera — primero hay que confirmar.
    """
    query = (
        select(FixedExpense)
        .where(FixedExpense.user_id == user_id)
        .where(FixedExpense.auto_post.is_(True))
        .where(FixedExpense.status == FixedExpenseStatus.CONFIRMED)
        .where(FixedExpense.next_due <= today)
        .order_by(FixedExpense.next_due.asc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())
