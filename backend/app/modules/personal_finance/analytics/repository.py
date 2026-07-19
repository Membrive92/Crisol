"""Queries del módulo analytics (PHASE-37.3).

Read-only, todas filtran por `user_id`. Reutiliza las expresiones
CANÓNICAS de clasificación del dinero por `flow` del dashboard
(`_is_expense`, `_is_income`, `_is_internal_transfer`, `_amount_expr`,
`_apply_scope`) en vez de reimplementarlas: son la fuente única de la
semántica ADR-0004 (PHASE-34) y duplicarlas las haría divergir — el
mismo anti-patrón que lessons.md advierte en PHASE-34. Analytics es
parte del mismo módulo de dominio (`personal_finance`), así que el
import cruzado está permitido por la arquitectura.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ColumnElement, case, func, literal, not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.categories.models import (
    Category,
    CategoryRole,
    ExpenseNature,
)
from app.modules.personal_finance.dashboard.repository import (
    _amount_expr,
    _apply_scope,
    _is_expense,
    _is_internal_transfer,
)
from app.modules.personal_finance.fixed_expenses.models import FixedExpense, FixedExpenseStatus
from app.modules.personal_finance.transactions.models import Transaction

_DEBT_ROLES = (CategoryRole.DEBT_PAYMENT, CategoryRole.DEBT_INTEREST)


async def seed_structural_breakdown(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
    """Reglas 1 y 2 de la heurística, DESGLOSADAS `(fijos, deuda)`.

    Regla 1 (`fijos`): categorías apuntadas por un `fixed_expense` CONFIRMADO.
    Regla 2 (`deuda`): categorías con rol de deuda (`DEBT_PAYMENT`/`DEBT_INTEREST`).

    El endpoint `explain` necesita distinguirlas (razones `rule_1`/`rule_2`);
    `seed_structural_category_ids` las une. Fuente única para no divergir.
    """
    fixed_q = (
        select(FixedExpense.category_id)
        .where(FixedExpense.user_id == user_id)
        .where(FixedExpense.status == FixedExpenseStatus.CONFIRMED)
        .where(FixedExpense.category_id.is_not(None))
        .distinct()
    )
    debt_q = (
        select(Category.id).where(Category.user_id == user_id).where(Category.role.in_(_DEBT_ROLES))
    )
    fixed_rows = (await db.execute(fixed_q)).scalars().all()
    debt_rows = (await db.execute(debt_q)).scalars().all()
    fixed_ids = {cid for cid in fixed_rows if cid is not None}
    debt_ids = set(debt_rows)
    return fixed_ids, debt_ids


async def seed_structural_category_ids(db: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Categorías estructurales por reglas 1 y 2 (unión).

    La regla 3 (recurrencia por importe estable) se calcula aparte en
    `analytics.service` con `classify_recurring_categories` sobre
    `monthly_expense_by_category`.
    """
    fixed_ids, debt_ids = await seed_structural_breakdown(db, user_id)
    return fixed_ids | debt_ids


async def monthly_expense_by_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    window_start: datetime,
    window_end: datetime,
    currency: str | None = None,
    target_currency: str | None = None,
) -> dict[uuid.UUID, list[Decimal]]:
    """Total de GASTO por (categoría, mes) dentro de la ventana.

    Sólo categorías reales (`category_id IS NOT NULL`) — la regla 3 de
    recurrencia razona por categoría, y el bucket "sin categoría" no es
    una categoría recurrente. Devuelve, por categoría, la lista de sus
    totales mensuales (un elemento por mes con actividad), lista para
    `classify_recurring_categories`.
    """
    month_col = func.to_char(func.timezone("UTC", Transaction.occurred_at), "YYYY-MM").label(
        "month"
    )
    amount = _amount_expr(target_currency)
    query = (
        select(Transaction.category_id, month_col, func.coalesce(func.sum(amount), Decimal("0")))
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(_is_expense())
        .where(Transaction.category_id.is_not(None))
        .group_by(Transaction.category_id, month_col)
    )
    query = _apply_scope(
        query,
        user_id=user_id,
        currency=currency,
        date_from=window_start,
        date_to=window_end,
    )
    query = query.where(_is_internal_transfer().is_(False))
    rows = (await db.execute(query)).all()
    by_category: dict[uuid.UUID, list[Decimal]] = defaultdict(list)
    for cat_id, _month, total in rows:
        if cat_id is not None:
            by_category[cat_id].append(Decimal(total))
    return dict(by_category)


async def expense_categories_in_range(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[tuple[uuid.UUID, str, ExpenseNature]]:
    """Categorías reales con GASTO en el rango — `(id, name, expense_nature)`.

    El universo que el endpoint `explain` describe: las categorías que el
    usuario ve en su desglose del periodo. Excluye el bucket sin categoría
    (no es una categoría que se pueda clasificar ni sobre la que fijar un
    override). Orden estable por nombre.
    """
    query = (
        select(Category.id, Category.name, Category.expense_nature)
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(_is_expense())
        .group_by(Category.id, Category.name, Category.expense_nature)
        .order_by(Category.name)
    )
    query = _apply_scope(
        query, user_id=user_id, currency=currency, date_from=date_from, date_to=date_to
    )
    query = query.where(_is_internal_transfer().is_(False))
    rows = (await db.execute(query)).all()
    return [(cid, name, nature) for cid, name, nature in rows]


async def tx_override_counts_by_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[uuid.UUID, int]:
    """Nº de tx de GASTO por categoría con override propio (`is_exceptional`
    no nulo) en el rango. Alimenta `tx_overrides` del `explain`: cuántas
    transacciones de la categoría contradicen (o refuerzan) su clasificación."""
    query = (
        select(Transaction.category_id, func.count())
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(_is_expense())
        .where(Transaction.category_id.is_not(None))
        .where(Transaction.is_exceptional.is_not(None))
        .group_by(Transaction.category_id)
    )
    query = _apply_scope(
        query, user_id=user_id, currency=currency, date_from=date_from, date_to=date_to
    )
    query = query.where(_is_internal_transfer().is_(False))
    rows = (await db.execute(query)).all()
    return {cid: int(count) for cid, count in rows if cid is not None}


async def count_expense_months_in_window(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    window_start: datetime,
    window_end: datetime,
    currency: str | None = None,
    target_currency: str | None = None,
) -> int:
    """Nº de meses naturales DISTINTOS de la ventana con algún gasto.

    PHASE-43.1 — alimenta `recurrence_available`/`window_months_with_data`:
    la regla 3 (recurrencia) sólo es significativa si hay ≥
    `RECURRENCE_MIN_MONTHS` meses completos con datos. Mismo alcance de gasto
    (flow=OUT, transferencias excluidas) que el resto de queries del módulo.
    """
    month_col = func.to_char(func.timezone("UTC", Transaction.occurred_at), "YYYY-MM")
    query = (
        select(func.count(func.distinct(month_col)))
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(_is_expense())
    )
    query = _apply_scope(
        query,
        user_id=user_id,
        currency=currency,
        date_from=window_start,
        date_to=window_end,
    )
    query = query.where(_is_internal_transfer().is_(False))
    return int((await db.execute(query)).scalar_one() or 0)


def is_structural_expr(structural_category_ids: set[uuid.UUID]) -> ColumnElement[bool]:
    """Expresión SQL: ¿esta tx de gasto es estructural?

    Cascada de precedencia (ADR-0006 / PHASE-43.2), de mayor a menor:

      1. `transactions.is_exceptional` (override por transacción):
         TRUE  → puntual · FALSE → estructural.
      2. `categories.expense_nature` (override por categoría):
         EXCEPTIONAL → puntual · STRUCTURAL → estructural.
      3. heurística: pertenece al conjunto estructural (reglas 1 ∪ 2 ∪ 3).

    Con el conjunto vacío, la heurística es `False` (sólo cuentan los
    overrides) — evita un `IN ()` degenerado.

    **Requiere que la query una `Category`** (todos los consumidores hacen
    `outerjoin(Category, ...)`): la rama 2 lee `Category.expense_nature`. Con
    `category_id` NULL (`outerjoin` sin match) esa columna es NULL, las dos
    condiciones de la rama 2 dan NULL/False y cae a la heurística — correcto.
    """
    if structural_category_ids:
        heuristic: ColumnElement[bool] = Transaction.category_id.in_(list(structural_category_ids))
    else:
        heuristic = literal(False)
    return case(
        # 1. override por transacción
        (Transaction.is_exceptional.is_(True), literal(False)),
        (Transaction.is_exceptional.is_(False), literal(True)),
        # 2. override por categoría
        (Category.expense_nature == ExpenseNature.EXCEPTIONAL, literal(False)),
        (Category.expense_nature == ExpenseNature.STRUCTURAL, literal(True)),
        # 3. heurística (reglas 1 ∪ 2 ∪ 3)
        else_=heuristic,
    )


async def expense_split_totals(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    structural_category_ids: set[uuid.UUID],
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[Decimal, Decimal]:
    """(gasto_estructural, gasto_puntual) en el rango pedido.

    Sobre el mismo conjunto de GASTO (flow=OUT, transferencias excluidas)
    que el dashboard, partido por `is_structural_expr`. Su suma == gasto
    total del rango (invariante que los tests verifican).
    """
    amount = _amount_expr(target_currency)
    is_struct = is_structural_expr(structural_category_ids)
    structural_amount = case((is_struct, amount), else_=Decimal("0"))
    exceptional_amount = case((is_struct, Decimal("0")), else_=amount)
    query = (
        select(
            func.coalesce(func.sum(structural_amount), Decimal("0")),
            func.coalesce(func.sum(exceptional_amount), Decimal("0")),
        )
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(_is_expense())
    )
    query = _apply_scope(
        query, user_id=user_id, currency=currency, date_from=date_from, date_to=date_to
    )
    query = query.where(_is_internal_transfer().is_(False))
    row = (await db.execute(query)).one()
    return Decimal(row[0]), Decimal(row[1])


async def structural_monthly_avg(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    structural_category_ids: set[uuid.UUID],
    window_start: datetime,
    window_end: datetime,
    currency: str | None = None,
    target_currency: str | None = None,
) -> Decimal:
    """Media mensual del gasto estructural en la ventana (base del runway).

    Numerador: Σ gasto estructural de la ventana. Denominador: nº de
    meses de la ventana CON algún gasto (no todos los `M` meses — si el
    usuario tiene menos histórico, no diluimos con ceros de meses que no
    existían). Un mes con gasto pero 0 estructural cuenta como 0 y sí
    baja la media (comportamiento correcto). Sin ningún mes con gasto →
    0 (el caller lo trata como "sin base para runway").
    """
    month_col = func.to_char(func.timezone("UTC", Transaction.occurred_at), "YYYY-MM").label(
        "month"
    )
    amount = _amount_expr(target_currency)
    is_struct = is_structural_expr(structural_category_ids)
    structural_amount = case((is_struct, amount), else_=Decimal("0"))
    query = (
        select(month_col, func.coalesce(func.sum(structural_amount), Decimal("0")))
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(_is_expense())
        .group_by(month_col)
    )
    query = _apply_scope(
        query,
        user_id=user_id,
        currency=currency,
        date_from=window_start,
        date_to=window_end,
    )
    query = query.where(_is_internal_transfer().is_(False))
    rows = (await db.execute(query)).all()
    if not rows:
        return Decimal("0")
    total = sum((Decimal(total) for _month, total in rows), Decimal("0"))
    return total / Decimal(len(rows))


async def top_exceptional_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    structural_category_ids: set[uuid.UUID],
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 5,
) -> list[tuple[Transaction, str | None, Decimal | None]]:
    """Los `limit` mayores gastos PUNTUALES del rango, importe desc."""
    amount = _amount_expr(target_currency)
    is_struct = is_structural_expr(structural_category_ids)
    query = (
        select(Transaction, Category.name, amount.label("converted_amount"))
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(_is_expense())
        .where(not_(is_struct))
    )
    query = _apply_scope(
        query, user_id=user_id, currency=currency, date_from=date_from, date_to=date_to
    )
    query = query.where(_is_internal_transfer().is_(False))
    query = query.order_by(amount.desc().nulls_last()).limit(limit)
    result = await db.execute(query)
    return [
        (tx, name, Decimal(converted) if converted is not None else None)
        for tx, name, converted in result.all()
    ]


async def exceptional_by_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    structural_category_ids: set[uuid.UUID],
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[tuple[uuid.UUID | None, str | None, str | None, str | None, Decimal]]:
    """Gasto PUNTUAL agrupado por categoría, importe desc.

    Devuelve `(id, name, color, icon, total)` — incluye el bucket
    `category_id=None` (puntuales sin categoría).
    """
    amount = _amount_expr(target_currency)
    is_struct = is_structural_expr(structural_category_ids)
    total_col = func.coalesce(func.sum(amount), Decimal("0")).label("total")
    query = (
        select(Category.id, Category.name, Category.color, Category.icon, total_col)
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(_is_expense())
        .where(not_(is_struct))
        .group_by(Category.id, Category.name, Category.color, Category.icon)
    )
    query = _apply_scope(
        query, user_id=user_id, currency=currency, date_from=date_from, date_to=date_to
    )
    query = query.where(_is_internal_transfer().is_(False))
    query = query.order_by(total_col.desc())
    rows = (await db.execute(query)).all()
    return [(cid, name, color, icon, Decimal(total)) for cid, name, color, icon, total in rows]
