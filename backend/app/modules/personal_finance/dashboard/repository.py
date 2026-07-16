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

from sqlalchemy import ColumnElement, Select, case, extract, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.categories.models import Category, CategoryKind
from app.modules.personal_finance.dashboard.conversion import (
    amount_is_convertible_expr,
    converted_amount_expr,
)
from app.modules.personal_finance.transactions.models import Transaction, TransactionFlow


# PHASE-34 (ADR-0004): la clasificación gasto/ingreso/transferencia la manda
# `transactions.flow`. Durante la transición, las filas sin flow (heredadas /
# write path aún sin migrar) caen a `category.kind`/`is_transfer` como antes.
# Los tres helpers son NULL-safe: un row sin flow ni categoría no rompe el
# WHERE. Se elimina el fallback (y el join a Category de la clasificación) en
# 34.6. Equivalente por construcción al backfill de 34.1.
def _is_income() -> ColumnElement[bool]:
    return case(
        (Transaction.flow.is_not(None), Transaction.flow == TransactionFlow.IN),
        else_=(Category.kind == CategoryKind.INCOME),
    )


def _is_expense() -> ColumnElement[bool]:
    return case(
        (Transaction.flow.is_not(None), Transaction.flow == TransactionFlow.OUT),
        else_=(Category.kind == CategoryKind.EXPENSE),
    )


def _is_internal_transfer() -> ColumnElement[bool]:
    """True sólo si la fila es una transferencia interna (excluir del cashflow).

    NULL-safe: cuando `flow` es NULL cae a `coalesce(is_transfer, false)`, así
    que una tx normal sin flow NO se descarta por error.
    """
    return case(
        (
            Transaction.flow.is_not(None),
            Transaction.flow.in_([TransactionFlow.TRANSFER_IN, TransactionFlow.TRANSFER_OUT]),
        ),
        else_=func.coalesce(Category.is_transfer, literal(False)),
    )


async def list_user_currencies(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[str]:
    """Devuelve las monedas distintas en las transacciones del usuario.

    Excluye soft-deleted (PHASE-10.1) y movimientos marcados como
    transferencia interna (PHASE-19.3 pares + PHASE-23.1 is_transfer)
    — una moneda que sólo aparece en transferencias no representa
    cashflow real y no debe inundar el selector.
    """
    query = (
        select(Transaction.currency)
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        # ADR-0005: la exclusión la gobierna `flow` (`_is_internal_transfer`,
        # NULL-safe). El filtro por `transfer_pair_id` era un cinturón extra del
        # caso legacy `flow NULL` — redundante una vez `flow` está poblado
        # (verificado: 0 filas `flow NULL AND transfer_pair_id NOT NULL`).
        .where(_is_internal_transfer().is_(False))
        .distinct()
        .order_by(Transaction.currency)
    )
    result = await db.execute(query)
    return [row[0] for row in result.all()]


async def get_transaction_month_bounds(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> tuple[str | None, str | None]:
    """PHASE-34 — Mes mínimo y máximo (`YYYY-MM`) con transacciones activas
    del usuario, INDEPENDIENTE de cualquier filtro de período.

    Lo usa el navegador de período del Análisis para acotar las flechas ◀▶ a
    los meses con datos (mismo papel que `available_from/to` en deuda).
    Devuelve `(None, None)` si el usuario aún no tiene transacciones.
    """
    result = await db.execute(
        select(
            # AUDIT-2026-07 (LOW): truncar en UTC (`func.timezone`) para que el
            # mes no dependa de la TZ de la sesión de PostgreSQL, igual que
            # debt_history/debt_health. Sin esto, min/max cerca de frontera de
            # mes podían caer en el mes contiguo según la TZ del servidor.
            func.to_char(
                func.min(func.timezone("UTC", Transaction.occurred_at)), "YYYY-MM"
            ),
            func.to_char(
                func.max(func.timezone("UTC", Transaction.occurred_at)), "YYYY-MM"
            ),
        )
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
    )
    row = result.one()
    return row[0], row[1]


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

    PHASE-19.3: excluye las txs con `transfer_pair_id IS NOT NULL`
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


def _exclude_transfer_kind(query: Any, *, outer_join: bool) -> Any:
    """Excluye transferencias internas del cashflow agregado.

    PHASE-34: la exclusión la manda `flow` (TRANSFER_*), con fallback a
    `category.is_transfer` para filas sin flow vía `_is_internal_transfer()`
    (NULL-safe, así que `outer_join` ya no altera la lógica — se conserva por
    compatibilidad de firma y se retira en 34.6). La exclusión por
    `transfer_pair_id` (pares emparejados, señal ortogonal) sigue viva en
    `_apply_scope`.
    """
    return query.where(_is_internal_transfer().is_(False))


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
    """Suma `amount` clasificando income/expense por `flow` (PHASE-34).

    Devuelve siempre ambas claves (0 si no hay). En modo `target_currency`,
    las transacciones sin tasa disponible quedan fuera.
    """
    amount = _amount_expr(target_currency)
    income_amount = case((_is_income(), amount), else_=Decimal("0"))
    expense_amount = case((_is_expense(), amount), else_=Decimal("0"))
    query = (
        select(
            func.coalesce(func.sum(income_amount), Decimal("0")),
            func.coalesce(func.sum(expense_amount), Decimal("0")),
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
    query = _exclude_transfer_kind(query, outer_join=True)

    row = (await db.execute(query)).one()
    return {CategoryKind.INCOME: Decimal(row[0]), CategoryKind.EXPENSE: Decimal(row[1])}


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
    income_amount = case((_is_income(), amount), else_=Decimal("0"))
    expense_amount = case((_is_expense(), amount), else_=Decimal("0"))

    if target_currency is not None:
        unconv_subq = (
            select(func.count())
            .select_from(Transaction)
            .outerjoin(Category, Category.id == Transaction.category_id)
            .where(~amount_is_convertible_expr(target_currency))
        )
        unconv_subq = _apply_scope(
            unconv_subq,
            user_id=user_id,
            currency=None,
            date_from=date_from,
            date_to=date_to,
        )
        unconv_subq = _exclude_transfer_kind(unconv_subq, outer_join=True)
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
    query = _exclude_transfer_kind(query, outer_join=True)

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
    query = _exclude_transfer_kind(query, outer_join=True)
    # AUDIT-2026-06 — La cara income/expense del donut se decide por `flow`
    # (igual que el KPI "Gastos" y la barra roja), NO por `Category.kind`.
    # Antes filtraba `Category.kind == kind`, así que cuando flow y la
    # categoría discrepaban (lo que PHASE-34/ADR-0004 permite a propósito)
    # el donut sumaba distinto que el resto de la pantalla: un OUT aparcado
    # en categoría de ingreso se le escapaba, y un TRANSFER_OUT en categoría
    # de gasto lo inflaba. Con `_is_expense()/_is_income()` el donut
    # reconcilia con summary + barras. Bonus: los OUT sin categoría caen al
    # bucket `category_id=None` en vez de desaparecer.
    if kind == CategoryKind.EXPENSE:
        query = query.where(_is_expense())
    elif kind == CategoryKind.INCOME:
        query = query.where(_is_income())

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
    """Totales income/expense por mes para el año pedido (PHASE-34: por flow)."""
    # AUDIT-2026-07 (LOW): extraer mes/año en UTC para no depender de la TZ de
    # la sesión de PostgreSQL (consistente con debt_history/debt_health).
    _occurred_utc = func.timezone("UTC", Transaction.occurred_at)
    month_col = extract("month", _occurred_utc)
    year_col = extract("year", _occurred_utc)
    amount = _amount_expr(target_currency)
    # Etiqueta income/expense por flow (fallback kind). Transferencias y
    # movimientos sin clasificar quedan en NULL y se descartan.
    kind_label = case(
        (_is_income(), literal(CategoryKind.INCOME.value)),
        (_is_expense(), literal(CategoryKind.EXPENSE.value)),
    )

    query = (
        select(month_col, kind_label.label("kind"), func.coalesce(func.sum(amount), 0))
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        # ADR-0005: la exclusión del cashflow la gobierna `flow`
        # (`_is_internal_transfer`, NULL-safe). El filtro por `transfer_pair_id`
        # era redundante (belt-and-suspenders del caso legacy `flow NULL`); las
        # txs siguen impactando al saldo individual de su cuenta vía `flow`.
        .where(_is_internal_transfer().is_(False))
        .where(year_col == year)
        .where(kind_label.is_not(None))
        .group_by(month_col, kind_label)
    )
    if currency is not None:
        query = query.where(Transaction.currency == currency)

    result = await db.execute(query)
    return [(int(month), CategoryKind(kind), Decimal(total)) for month, kind, total in result.all()]


async def get_totals_by_month_in_range(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    date_from: datetime,
    date_to: datetime,
    currency: str | None = None,
    target_currency: str | None = None,
) -> list[tuple[int, int, CategoryKind, Decimal]]:
    """PHASE-41 — Totales income/expense por (año, mes) dentro de
    `[date_from, date_to]`, con los meses de borde PARCIALES (sólo las tx del
    rango). Para el período `custom`: así las barras del chart mensual cuadran
    con los KPIs de flujo del mismo rango. Misma semántica `flow` que
    `get_totals_by_month`."""
    _occurred_utc = func.timezone("UTC", Transaction.occurred_at)
    month_col = extract("month", _occurred_utc)
    year_col = extract("year", _occurred_utc)
    amount = _amount_expr(target_currency)
    kind_label = case(
        (_is_income(), literal(CategoryKind.INCOME.value)),
        (_is_expense(), literal(CategoryKind.EXPENSE.value)),
    )
    query = (
        select(year_col, month_col, kind_label.label("kind"), func.coalesce(func.sum(amount), 0))
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(_is_internal_transfer().is_(False))
        .where(Transaction.occurred_at >= date_from)
        .where(Transaction.occurred_at <= date_to)
        .where(kind_label.is_not(None))
        .group_by(year_col, month_col, kind_label)
    )
    if currency is not None:
        query = query.where(Transaction.currency == currency)

    result = await db.execute(query)
    return [
        (int(y), int(m), CategoryKind(kind), Decimal(total)) for y, m, kind, total in result.all()
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
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(_is_expense())
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


# ─────────────────────────────────────────────────────────────────────
# PHASE-25 — Drill-down de categoría (KPIs + evolución + top tx)
# ─────────────────────────────────────────────────────────────────────


async def get_category_kpis(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    category_id: uuid.UUID,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[Decimal, int]:
    """Total + count para UNA categoría en el rango pedido. Mantiene
    las exclusiones estándar (papelera, transferencias)."""
    amount = _amount_expr(target_currency)
    query = (
        select(
            func.coalesce(func.sum(amount), Decimal("0")),
            func.count(Transaction.id),
        )
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.category_id == category_id)
    )
    query = _apply_scope(
        query,
        user_id=user_id,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
    )
    query = _exclude_transfer_kind(query, outer_join=True)
    row = (await db.execute(query)).one()
    return Decimal(row[0]), int(row[1])


async def get_category_monthly_evolution(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    category_id: uuid.UUID,
    currency: str | None = None,
    target_currency: str | None = None,
    months_back: int = 12,
) -> list[tuple[str, Decimal]]:
    """Evolución mensual de UNA categoría: últimos `months_back` meses
    cerrados + el mes en curso (inclusivo). Devuelve `(YYYY-MM, total)`
    ordenado cronológicamente. Meses sin actividad se omiten — el
    frontend rellena gaps si lo necesita."""
    # AUDIT-2026-07 (LOW): bucket de mes en UTC (consistente con el resto).
    month_col = func.to_char(
        func.timezone("UTC", Transaction.occurred_at), "YYYY-MM"
    ).label("month")
    amount = _amount_expr(target_currency)
    query = (
        select(month_col, func.coalesce(func.sum(amount), Decimal("0")))
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.category_id == category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_(None))
        .where(_is_internal_transfer().is_(False))
        .group_by(month_col)
        .order_by(month_col)
    )
    if currency is not None:
        query = query.where(Transaction.currency == currency)
    rows = (await db.execute(query)).all()
    # Recortamos a los últimos `months_back` meses para evitar series
    # gigantes en cuentas con histórico largo.
    return [(month, Decimal(total)) for month, total in rows[-months_back:]]


async def get_category_top_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    category_id: uuid.UUID,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 10,
) -> list[tuple[Transaction, str | None, Decimal | None]]:
    """Top N tx de la categoría en el rango, ordenadas por importe."""
    amount = _amount_expr(target_currency)
    query = (
        select(Transaction, Category.name, amount.label("converted_amount"))
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.category_id == category_id)
    )
    query = _apply_scope(
        query,
        user_id=user_id,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
    )
    query = _exclude_transfer_kind(query, outer_join=True)
    query = query.order_by(amount.desc().nulls_last()).limit(limit)
    result = await db.execute(query)
    return [
        (tx, name, Decimal(converted) if converted is not None else None)
        for tx, name, converted in result.all()
    ]
