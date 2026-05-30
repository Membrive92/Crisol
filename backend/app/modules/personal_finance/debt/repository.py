"""Queries de agregación de Capa 1 del módulo deuda (PHASE-30.2).

PHASE-30.6 — Soporte cross-currency. Las tres queries aceptan dos
modos mutuamente excluyentes:

- **Native** (`currency=str, target_currency=None`): filtra
  `Transaction.currency == currency` y agrega importes crudos.
  Comportamiento previo, lo que devuelve el endpoint por defecto.
- **Converted** (`target_currency=str, currency` se ignora): no
  filtra por moneda; cada `Transaction.amount` se convierte a
  `target_currency` con la tasa **del día de su `occurred_at`**
  (vía `converted_amount_expr` del módulo dashboard). Txs sin tasa
  disponible quedan excluidas del SUM (NULL → SUM ignora), mismo
  contrato que el dashboard.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.modules.personal_finance.accounts.models import Account
from app.modules.personal_finance.categories.models import Category, CategoryRole
from app.modules.personal_finance.dashboard.conversion import (
    converted_amount_expr,
)
from app.modules.personal_finance.transactions.models import Transaction

DEBT_ROLES: frozenset[CategoryRole] = frozenset(
    {CategoryRole.DEBT_PAYMENT, CategoryRole.DEBT_INTEREST}
)


def _month_start_utc(d: date) -> datetime:
    return datetime(d.year, d.month, 1, tzinfo=UTC)


def _month_end_utc(d: date) -> datetime:
    last_day = calendar.monthrange(d.year, d.month)[1]
    return datetime(d.year, d.month, last_day, 23, 59, 59, tzinfo=UTC)


def _amount_expr(target_currency: str | None) -> ColumnElement[Any]:
    """Devuelve la expresión de importe a sumar. Convertida si hay
    `target_currency`, cruda si no."""
    if target_currency is not None:
        return converted_amount_expr(target_currency)
    # InstrumentedAttribute[Decimal] is a column expr at runtime; the
    # SQLAlchemy stubs don't expose it as ColumnElement, so cast.
    return cast("ColumnElement[Any]", Transaction.amount)


async def aggregate_debt_payments_by_role(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    start: datetime,
    end: datetime,
    target_currency: str | None = None,
) -> dict[CategoryRole, Decimal]:
    """Σ amount agrupado por `Category.role` para categorías de deuda.

    Excluye papelera y txs de transferencia interna. Devuelve `Decimal('0')`
    en ambos roles cuando no hay datos para que el caller no tenga que
    distinguir entre "no hay key" y "hay key con 0".
    """
    amount = _amount_expr(target_currency)
    query = (
        select(Category.role, func.coalesce(func.sum(amount), 0))
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_(None))
        .where(Category.role.in_(DEBT_ROLES))
        .where(Transaction.occurred_at >= start)
        .where(Transaction.occurred_at <= end)
        .group_by(Category.role)
    )
    if target_currency is None:
        query = query.where(Transaction.currency == currency)
    result = await db.execute(query)
    totals: dict[CategoryRole, Decimal] = {
        CategoryRole.DEBT_PAYMENT: Decimal("0"),
        CategoryRole.DEBT_INTEREST: Decimal("0"),
    }
    for role, total in result.all():
        totals[role] = Decimal(total)
    return totals


async def aggregate_debt_payments_by_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    start: datetime,
    end: datetime,
    target_currency: str | None = None,
) -> list[tuple[str, CategoryRole, Decimal, str | None]]:
    """Devuelve `(category_name, role, total, linked_account_type)`
    para construir el donut de composición por tipo.

    PHASE-30.7 — `linked_account_type` proviene de
    `accounts.category_id` (PHASE-30.4): cuando un usuario vincula una
    liability a una categoría de pagos, sabemos con certeza si esos
    pagos van a una hipoteca / préstamo / tarjeta. El service usa
    esa info como señal primaria, con fallback al matching por nombre.
    Si hay varias cuentas vinculadas a la misma categoría, devolvemos
    la primera (por display_order) — el caso real es 1-a-1.
    """
    amount = _amount_expr(target_currency)
    # Subquery escalar: type de la PRIMERA liability vinculada a la
    # categoría (orden por display_order, name). NULL si no hay
    # ninguna cuenta vinculada.
    linked_type_subq = (
        select(Account.type)
        .where(Account.user_id == user_id)
        .where(Account.category_id == Category.id)
        .where(Account.is_archived.is_(False))
        .order_by(Account.display_order, Account.name)
        .limit(1)
        .correlate(Category)
        .scalar_subquery()
    )
    query = (
        select(
            Category.name,
            Category.role,
            func.coalesce(func.sum(amount), 0),
            linked_type_subq.label("linked_type"),
        )
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_(None))
        .where(Category.role.in_(DEBT_ROLES))
        .where(Transaction.occurred_at >= start)
        .where(Transaction.occurred_at <= end)
        .group_by(Category.name, Category.role, Category.id)
    )
    if target_currency is None:
        query = query.where(Transaction.currency == currency)
    rows = (await db.execute(query)).all()
    return [(name, role, Decimal(total), linked_type) for name, role, total, linked_type in rows]


async def monthly_debt_series(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    months: list[date],
    target_currency: str | None = None,
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
    amount = _amount_expr(target_currency)
    interest_amount = case(
        (Category.role == CategoryRole.DEBT_INTEREST, amount),
        else_=Decimal("0"),
    )

    query = (
        select(
            year_expr.label("y"),
            month_expr.label("m"),
            func.coalesce(func.sum(amount), 0).label("payments"),
            func.coalesce(func.sum(interest_amount), 0).label("interests"),
        )
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_(None))
        .where(Category.role.in_(DEBT_ROLES))
        .where(Transaction.occurred_at >= start)
        .where(Transaction.occurred_at <= end)
        .group_by("y", "m")
    )
    if target_currency is None:
        query = query.where(Transaction.currency == currency)
    rows = (await db.execute(query)).all()
    by_month: dict[tuple[int, int], tuple[Decimal, Decimal]] = {
        (int(r.y), int(r.m)): (Decimal(r.payments), Decimal(r.interests)) for r in rows
    }

    series: list[tuple[date, Decimal, Decimal]] = []
    for month_start in months:
        payments, interests = by_month.get(
            (month_start.year, month_start.month),
            (Decimal("0"), Decimal("0")),
        )
        series.append((month_start, payments, interests))
    return series


async def debt_movement_bounds(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    target_currency: str | None = None,
) -> tuple[date | None, date | None]:
    """Primer y último `occurred_at` (como fecha) con movimientos de
    deuda (PHASE-30.8).

    Usa el **mismo set de predicados** que los agregados (papelera,
    transferencias internas, roles de deuda y, en modo nativo, moneda)
    para que el navegador de período nunca aterrice en un período cuyos
    KPIs de Capa 1 sean todos cero. `(None, None)` si no hay datos.
    """
    query = (
        select(
            func.min(Transaction.occurred_at),
            func.max(Transaction.occurred_at),
        )
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_(None))
        .where(Category.role.in_(DEBT_ROLES))
    )
    if target_currency is None:
        query = query.where(Transaction.currency == currency)
    min_dt, max_dt = (await db.execute(query)).one()
    return (
        min_dt.date() if min_dt is not None else None,
        max_dt.date() if max_dt is not None else None,
    )
