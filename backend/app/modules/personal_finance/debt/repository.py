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
from app.modules.personal_finance.accounts.repository import is_inflow, is_outflow
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
    exclude_category_ids: set[uuid.UUID] | None = None,
) -> dict[CategoryRole, Decimal]:
    """Σ amount agrupado por `Category.role` para categorías de deuda.

    Excluye papelera y txs de transferencia interna. Devuelve `Decimal('0')`
    en ambos roles cuando no hay datos para que el caller no tenga que
    distinguir entre "no hay key" y "hay key con 0".

    PHASE-37 — `exclude_category_ids` deja fuera las categorías VINCULADAS a
    un pasivo con cuadro (`accounts.category_id`): el interés/capital de esas
    deudas sale del cuadro, no de sus transacciones, así que sumarlos aquí
    los contaría dos veces (MUX por pasivo).
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
    if exclude_category_ids:
        query = query.where(Category.id.notin_(exclude_category_ids))
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
    exclude_category_ids: set[uuid.UUID] | None = None,
) -> list[tuple[date, Decimal, Decimal]]:
    """Para cada mes de `months` (primer día de cada uno) devuelve
    `(month, total_payments, interests)`.

    Hace una sola query agrupada por `(año, mes, role)` y rellena los
    huecos con 0 en el service — más barato que iterar mes a mes.

    PHASE-37 — `exclude_category_ids`: idéntico a `aggregate_debt_payments_by_role`
    (categorías vinculadas a pasivos con cuadro se excluyen; su interés/capital
    lo aporta el cuadro para no doblar).
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
    if exclude_category_ids:
        query = query.where(Category.id.notin_(exclude_category_ids))
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


async def daily_liability_flows(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    liability_ids: list[uuid.UUID],
    start: datetime,
    end: datetime,
    reference_currency: str,
    target_currency: str | None = None,
) -> dict[int, tuple[Decimal, Decimal]]:
    """Por día del mes, flujo sobre cuentas-pasivo (PHASE-30.9):
    `{día: (emitida, amortizado)}`.

    - `emitida` = Σ cargos que SUBEN la deuda (gasto categorizado).
    - `amortizado` = Σ entradas que la BAJAN (income, típicamente pagos).

    AUDIT-2026-06 (fix #7) — Mismo split de signo que
    `get_balances_for_user` (la fuente de verdad del saldo) y que
    `debt_history`: expense suma al saldo de un pasivo, income resta y
    **tx SIN categoría NO contribuye** (PHASE-31.3, `else_=0`). Antes
    `emitida` usaba `else_=amount`, contando como "deuda emitida" cargos
    sin categorizar — divergía de `get_balances_for_user`, que los ignora,
    y desplazaba la línea de saldo del chart diario respecto al saldo real
    de la cuenta. Bucket por día truncado en UTC para coincidir con las
    fronteras `_month_start_utc`/`_range_end_utc` sea cual sea la TZ de
    sesión.
    """
    if not liability_ids:
        return {}
    amount = _amount_expr(target_currency)
    day_expr = func.extract("day", func.timezone("UTC", Transaction.occurred_at))
    # AUDIT-2026-06 (alineación PHASE-34) — la dirección la manda `flow`
    # (`is_outflow`/`is_inflow`, MISMOS predicados que get_balances_for_user),
    # no `Category.kind`. Sólo la salida/cargo sube la deuda; la entrada/pago
    # amortiza; sin flujo ni categoría → 0. Equivalente al criterio por
    # categoría para datos backfilled (34.1); sólo cambia filas con flow a mano.
    emitida_expr = case((is_outflow(), amount), else_=Decimal("0"))
    amortizado_expr = case((is_inflow(), amount), else_=Decimal("0"))
    query = (
        select(
            day_expr.label("d"),
            func.coalesce(func.sum(emitida_expr), 0),
            func.coalesce(func.sum(amortizado_expr), 0),
        )
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.account_id.in_(liability_ids))
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.occurred_at >= start)
        .where(Transaction.occurred_at <= end)
        .group_by("d")
    )
    if target_currency is None:
        query = query.where(Transaction.currency == reference_currency)
    rows = (await db.execute(query)).all()
    return {int(d): (Decimal(em), Decimal(am)) for d, em, am in rows}


async def liability_signed_before(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    liability_ids: list[uuid.UUID],
    before: datetime,
    reference_currency: str,
    target_currency: str | None = None,
) -> Decimal:
    """Σ del saldo firmado de los pasivos ANTES de `before` (PHASE-30.9):
    el "carry" para anclar la línea de saldo del mes.

    AUDIT-2026-06 (fix #7) — Signo IDÉNTICO al de la rama liability de
    `get_balances_for_user`: la salida/cargo suma (sube la deuda), la
    entrada/pago resta (la amortiza) y **tx SIN categoría NO contribuye**
    (PHASE-31.3, `else_=0`). Antes usaba `else_=amount`, contando cargos sin
    categoría como deuda emitida → el carry divergía del saldo real del
    pasivo y desanclaba la línea de saldo respecto a `/balances`.

    AUDIT-2026-06 (alineación PHASE-34) — la dirección la manda `flow`
    (`is_outflow`/`is_inflow`), no `Category.kind`, para que el carry case
    con get_balances_for_user incluso cuando flow y categoría discrepan."""
    if not liability_ids:
        return Decimal("0")
    amount = _amount_expr(target_currency)
    signed = case(
        (is_outflow(), amount),
        (is_inflow(), -amount),
        else_=Decimal("0"),
    )
    query = (
        select(func.coalesce(func.sum(signed), 0))
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.account_id.in_(liability_ids))
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.occurred_at < before)
    )
    if target_currency is None:
        query = query.where(Transaction.currency == reference_currency)
    return Decimal((await db.execute(query)).scalar_one())


async def daily_category_flows(
    db: AsyncSession,
    user_id: uuid.UUID,
    reference_currency: str,
    *,
    start: datetime,
    end: datetime,
    target_currency: str | None = None,
    exclude_category_ids: set[uuid.UUID] | None = None,
) -> dict[int, tuple[Decimal, Decimal]]:
    """Por día del mes, flujo de categorías de deuda (Capa 1):
    `{día: (capital, interest)}` donde capital=Σ DEBT_PAYMENT e
    interest=Σ DEBT_INTEREST. Sirve para el interés (barra informativa)
    y como fallback de "amortizado" cuando no hay cuentas-pasivo.

    PHASE-37 — `exclude_category_ids`: mismo MUX (categorías vinculadas a
    pasivos con cuadro fuera; su interés lo aporta el cuadro)."""
    amount = _amount_expr(target_currency)
    day_expr = func.extract("day", func.timezone("UTC", Transaction.occurred_at))
    capital_expr = case((Category.role == CategoryRole.DEBT_PAYMENT, amount), else_=Decimal("0"))
    interest_expr = case((Category.role == CategoryRole.DEBT_INTEREST, amount), else_=Decimal("0"))
    query = (
        select(
            day_expr.label("d"),
            func.coalesce(func.sum(capital_expr), 0),
            func.coalesce(func.sum(interest_expr), 0),
        )
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_(None))
        .where(Category.role.in_(DEBT_ROLES))
        .where(Transaction.occurred_at >= start)
        .where(Transaction.occurred_at <= end)
        .group_by("d")
    )
    if exclude_category_ids:
        query = query.where(Category.id.notin_(exclude_category_ids))
    if target_currency is None:
        query = query.where(Transaction.currency == reference_currency)
    rows = (await db.execute(query)).all()
    return {int(d): (Decimal(cap), Decimal(intr)) for d, cap, intr in rows}


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
