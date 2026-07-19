"""Lógica de negocio del módulo dashboard.

Read-only: agregaciones sobre `transactions`. El service decide entre
los dos modos de moneda:

- **legacy** (`currency` filtra): mantiene el contrato anterior a
  PHASE-8.3 — totales por una sola moneda, sin conversión.
- **cross-currency** (`target_currency`): convierte cada transacción a
  la moneda destino con la tasa **del día de su `occurred_at`** (vía
  `conversion.converted_amount_expr`) y agrega después.

Si llegan ambos parámetros, gana `target_currency` — es el modo
preferido. Si no llega ninguno, se asume legacy con `_DEFAULT_CURRENCY`.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import Date as SQLDate
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.currency import service as currency_service
from app.modules.personal_finance.categories.models import CategoryKind
from app.modules.personal_finance.categories.repository import get_category_by_id
from app.modules.personal_finance.dashboard import repository
from app.modules.personal_finance.dashboard.schemas import (
    CategoryAvailablePeriodItem,
    CategoryAvailablePeriodsResponse,
    CategoryBreakdownItem,
    CategoryDetailResponse,
    CategoryMonthlyBucket,
    ModuleDashboardSummary,
    ModuleSummaryItem,
    ModuleVerdict,
    MonthlyBucket,
    SummaryResponse,
    TopExpenseItem,
)
from app.modules.personal_finance.transactions.models import Transaction

_UNCATEGORIZED_NAME = "Sin categoría"


async def ensure_rates_for_user_scope(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    target_currency: str,
    date_from: datetime | None,
    date_to: datetime | None,
) -> None:
    """Antes de agregar en cross-currency, asegura que las tasas para
    cada día con transacciones existan en BD.

    Sin esta llamada, transacciones históricas (más antiguas que el
    snapshot embebido + ventana de 14d) quedarían fuera del SUM con
    `unconvertible_count > 0`. Con ella, el primer request de cada
    fecha dispara fetch + persist + queda cacheado para siempre.

    Reusable desde otros módulos (transactions también lo llama antes
    de listar con `target_currency`).
    """
    target = target_currency.upper()
    query = (
        select(cast(Transaction.occurred_at, SQLDate))
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.currency != target)
        .distinct()
    )
    if date_from is not None:
        query = query.where(Transaction.occurred_at >= date_from)
    if date_to is not None:
        query = query.where(Transaction.occurred_at <= date_to)

    result = await db.execute(query)
    dates: list[date] = [row[0] for row in result.all()]
    if not dates:
        return
    await currency_service.ensure_rates_for_dates(db, dates)


def _resolve_mode(
    currency: str | None, target_currency: str | None
) -> tuple[str | None, str | None, str]:
    """Devuelve `(legacy_currency, target_currency, displayed_currency)`.

    - Si `target_currency` viene → modo cross-currency. `legacy=None`.
    - Si sólo `currency` → modo legacy. `target=None`.
    - Si ninguno → usar `currency` legacy con default upstream.
    """
    if target_currency is not None:
        target = target_currency.upper()
        return None, target, target
    if currency is not None:
        cur = currency.upper()
        return cur, None, cur
    return None, None, ""


async def list_user_currencies(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[str]:
    """Monedas distintas presentes en las transacciones del usuario."""
    return await repository.list_user_currencies(db, user_id)


def _previous_period(date_from: datetime, date_to: datetime) -> tuple[datetime, datetime]:
    """PHASE-41 — Período EQUIVALENTE anterior para el Δ "vs período anterior".

    - MES natural completo (1º 00:00 … último día 23:59:59) → el mes natural
      anterior exacto.
    - AÑO natural completo (1-ene 00:00 … 31-dic 23:59:59) → el año anterior.
    - Cualquier otro rango (custom, parcial) → ventana de igual longitud justo
      antes, con el límite superior EXCLUSIVO (−1 µs) para no solapar la
      frontera con el período actual (intervalo cerrado en el repositorio).

    Antes SIEMPRE se usaba la ventana de igual longitud, lo que para meses de
    distinta duración desplazaba el "anterior" ~1 día (p.ej. mayo → [31-mar…
    30-abr] en vez de abril natural).
    """
    tz = date_from.tzinfo
    same_year_month = date_from.year == date_to.year and date_from.month == date_to.month
    at_month_start = (
        date_from.day == 1
        and (date_from.hour, date_from.minute, date_from.second, date_from.microsecond) == (0, 0, 0, 0)
    )
    at_month_end = (
        date_to.day == calendar.monthrange(date_to.year, date_to.month)[1]
        and (date_to.hour, date_to.minute, date_to.second) == (23, 59, 59)
    )
    if same_year_month and at_month_start and at_month_end:
        y, m = (date_from.year, date_from.month - 1)
        if m == 0:
            y, m = y - 1, 12
        last = calendar.monthrange(y, m)[1]
        return (
            datetime(y, m, 1, 0, 0, 0, tzinfo=tz),
            datetime(y, m, last, 23, 59, 59, tzinfo=tz),
        )
    at_year_start = (
        date_from.month == 1
        and date_from.day == 1
        and (date_from.hour, date_from.minute, date_from.second, date_from.microsecond) == (0, 0, 0, 0)
    )
    at_year_end = (
        date_to.month == 12
        and date_to.day == 31
        and (date_to.hour, date_to.minute, date_to.second) == (23, 59, 59)
    )
    if date_from.year == date_to.year and at_year_start and at_year_end:
        y = date_from.year - 1
        return (
            datetime(y, 1, 1, 0, 0, 0, tzinfo=tz),
            datetime(y, 12, 31, 23, 59, 59, tzinfo=tz),
        )
    period_length = date_to - date_from
    return (date_from - period_length, date_from - timedelta(microseconds=1))


async def get_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> SummaryResponse:
    """Balance global. Soporta legacy (`currency`) y cross-currency (`target_currency`)."""
    legacy, target, displayed = _resolve_mode(currency, target_currency)

    if target is not None:
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target,
            date_from=date_from,
            date_to=date_to,
        )

    income, expenses, count, unconvertible = await repository.get_summary_aggregates(
        db,
        user_id,
        currency=legacy,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
    )

    prev_income: Decimal | None = None
    prev_expenses: Decimal | None = None
    prev_balance: Decimal | None = None
    if date_from is not None and date_to is not None:
        # PHASE-41 — período equivalente anterior: mes/año natural anterior para
        # un rango que ES un mes/año completo; ventana de igual longitud (límite
        # superior exclusivo, sin solape en la frontera cerrada del repositorio)
        # para custom/parcial. Antes usaba siempre la ventana, que en meses de
        # distinta duración desplazaba el "anterior" ~1 día.
        prev_from, prev_to = _previous_period(date_from, date_to)
        prev_totals = await repository.get_totals_by_kind(
            db,
            user_id,
            currency=legacy,
            target_currency=target,
            date_from=prev_from,
            date_to=prev_to,
        )
        prev_income = prev_totals.get(CategoryKind.INCOME, Decimal("0"))
        prev_expenses = prev_totals.get(CategoryKind.EXPENSE, Decimal("0"))
        prev_balance = prev_income - prev_expenses

    # PHASE-37.1 — Δ vs periodo anterior equivalente (regla común de toda la
    # app: mes vs mes anterior, custom vs rango precedente de igual longitud).
    balance = income - expenses
    cashflow_delta: Decimal | None = None
    savings_rate_delta_pp: float | None = None
    if prev_balance is not None:
        cashflow_delta = balance - prev_balance
    if (
        prev_income is not None
        and prev_income > 0
        and income > 0
        and prev_balance is not None
    ):
        rate_now = float(balance / income * 100)
        rate_prev = float(prev_balance / prev_income * 100)
        savings_rate_delta_pp = rate_now - rate_prev

    # PHASE-34 — límites globales (mes min/max con datos), independientes del
    # filtro de período, para acotar el navegador de período del Análisis.
    available_from, available_to = await repository.get_transaction_month_bounds(db, user_id)

    return SummaryResponse(
        income=income,
        expenses=expenses,
        balance=balance,
        transaction_count=count,
        currency=displayed,
        unconvertible_count=unconvertible,
        previous_period_income=prev_income,
        previous_period_expenses=prev_expenses,
        previous_period_balance=prev_balance,
        cashflow_delta=cashflow_delta,
        savings_rate_delta_pp=savings_rate_delta_pp,
        available_from=available_from,
        available_to=available_to,
    )


# Umbral del veredicto de finanzas domésticas (ADR-0006, decisión del usuario):
# el veredicto lo da el SIGNO del flujo de caja del período; una banda muerta de
# ±5% del ingreso alrededor de cero es "atención" (ni claramente ahorra ni
# claramente gasta de más).
_CASHFLOW_VERDICT_BAND = Decimal("0.05")


async def _latest_month_bounds(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[datetime, datetime]:
    """Rango `[inicio, fin]` del ÚLTIMO mes con transacciones del usuario, o del
    mes en curso si aún no tiene datos.

    PHASE-43.4 (fix) — la card no puede anclarse al mes NATURAL en curso: quien
    importa por meses tiene el mes actual vacío hasta que lo sube, así que la
    card salía siempre a 0. El último mes con datos es la foto más reciente
    representativa. Sólo se usa como fallback cuando el caller no pasa rango."""
    _, latest = await repository.get_transaction_month_bounds(db, user_id)
    now = datetime.now(UTC)
    year, month = (
        (int(latest[:4]), int(latest[5:7])) if latest else (now.year, now.month)
    )
    last_day = calendar.monthrange(year, month)[1]
    return (
        datetime(year, month, 1, tzinfo=UTC),
        datetime(year, month, last_day, 23, 59, 59, tzinfo=UTC),
    )


async def get_module_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> ModuleDashboardSummary:
    """PHASE-43.4 (ADR-0006) — tarjeta del módulo Finanzas Domésticas para el
    dashboard: flujo de caja del período + tasa de ahorro + veredicto.

    El período lo fija el navegador del dashboard (`date_from`/`date_to`); si no
    llega ninguno, se usa el ÚLTIMO mes con datos (no el mes natural en curso,
    que suele estar vacío para quien importa por meses).

    El veredicto lo da el signo del flujo de caja (decisión del usuario):
    positivo con margen → `healthy`; negativo con margen → `stressed`; dentro
    de ±5% del ingreso → `caution`; sin ingresos en el período → `neutral`.
    """
    if date_from is None or date_to is None:
        date_from, date_to = await _latest_month_bounds(db, user_id)

    summary = await get_summary(
        db,
        user_id,
        currency=currency,
        target_currency=target_currency,
        date_from=date_from,
        date_to=date_to,
    )

    income = summary.income
    balance = summary.balance
    savings_rate_pct = float(balance / income * 100) if income > 0 else None

    verdict: ModuleVerdict
    if income <= 0:
        verdict = "neutral"
    else:
        band = income * _CASHFLOW_VERDICT_BAND
        if balance > band:
            verdict = "healthy"
        elif balance < -band:
            verdict = "stressed"
        else:
            verdict = "caution"

    secondary: list[ModuleSummaryItem] = []
    if savings_rate_pct is not None:
        secondary.append(
            ModuleSummaryItem(label="Ahorro", value=f"{savings_rate_pct:.0f} %")
        )

    return ModuleDashboardSummary(
        verdict=verdict,
        headline_value=balance,
        headline_label="flujo neto",
        currency=summary.currency,
        secondary=secondary,
        link="/personal-finance/analysis",
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
) -> list[CategoryBreakdownItem]:
    """Desglose por categoría."""
    legacy, target, _ = _resolve_mode(currency, target_currency)
    if target is not None:
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target,
            date_from=date_from,
            date_to=date_to,
        )
    rows = await repository.get_breakdown_by_category(
        db,
        user_id,
        currency=legacy,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        kind=kind,
    )
    items = [
        CategoryBreakdownItem(
            category_id=cat_id,
            category_name=cat_name if cat_name is not None else _UNCATEGORIZED_NAME,
            category_kind=cat_kind.value if cat_kind is not None else None,
            category_color=cat_color,
            category_icon=cat_icon,
            total=total,
            count=count,
        )
        for cat_id, cat_name, cat_kind, cat_color, cat_icon, total, count in rows
    ]
    items.sort(key=lambda i: i.total, reverse=True)
    return items


async def get_monthly_breakdown(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    year: int,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[MonthlyBucket]:
    """12 buckets mensuales para el año, o —si se pasa `[date_from, date_to]`
    (PHASE-41, período custom)— un bucket por cada mes tocado por el rango, con
    los meses de borde PARCIALES para que las barras cuadren con los KPIs de
    flujo del mismo rango."""
    legacy, target, _ = _resolve_mode(currency, target_currency)
    if date_from is not None and date_to is not None:
        if target is not None:
            await ensure_rates_for_user_scope(
                db, user_id, target_currency=target, date_from=date_from, date_to=date_to
            )
        rows_range = await repository.get_totals_by_month_in_range(
            db, user_id, date_from=date_from, date_to=date_to, currency=legacy, target_currency=target
        )
        income_r: dict[tuple[int, int], Decimal] = {}
        expenses_r: dict[tuple[int, int], Decimal] = {}
        for y, m, kind, total in rows_range:
            if kind == CategoryKind.INCOME:
                income_r[(y, m)] = total
            elif kind == CategoryKind.EXPENSE:
                expenses_r[(y, m)] = total
        buckets: list[MonthlyBucket] = []
        cy, cm = date_from.year, date_from.month
        while (cy, cm) <= (date_to.year, date_to.month):
            inc = income_r.get((cy, cm), Decimal("0"))
            exp = expenses_r.get((cy, cm), Decimal("0"))
            buckets.append(
                MonthlyBucket(
                    month=f"{cy:04d}-{cm:02d}", income=inc, expenses=exp, balance=inc - exp
                )
            )
            cm += 1
            if cm > 12:
                cm = 1
                cy += 1
        return buckets
    if target is not None:
        # `by-month` cubre el año completo, así que el rango es ese.
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target,
            date_from=datetime(year, 1, 1),
            date_to=datetime(year, 12, 31, 23, 59, 59),
        )
    rows = await repository.get_totals_by_month(
        db, user_id, year=year, currency=legacy, target_currency=target
    )

    income_per_month: dict[int, Decimal] = {m: Decimal("0") for m in range(1, 13)}
    expenses_per_month: dict[int, Decimal] = {m: Decimal("0") for m in range(1, 13)}

    for month, kind, total in rows:
        if kind == CategoryKind.INCOME:
            income_per_month[month] = total
        elif kind == CategoryKind.EXPENSE:
            expenses_per_month[month] = total

    return [
        MonthlyBucket(
            month=f"{year:04d}-{m:02d}",
            income=income_per_month[m],
            expenses=expenses_per_month[m],
            balance=income_per_month[m] - expenses_per_month[m],
        )
        for m in range(1, 13)
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
) -> list[TopExpenseItem]:
    """Top N gastos por importe convertido desc."""
    legacy, target, _ = _resolve_mode(currency, target_currency)
    if target is not None:
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target,
            date_from=date_from,
            date_to=date_to,
        )
    rows = await repository.get_top_expenses(
        db,
        user_id,
        currency=legacy,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return [
        TopExpenseItem(
            transaction_id=tx.id,
            description=tx.description,
            # `converted` viene en moneda destino cuando hay target. En
            # modo legacy es el amount original.
            amount=converted if converted is not None else tx.amount,
            occurred_at=tx.occurred_at,
            category_id=tx.category_id,
            category_name=category_name,
            original_amount=tx.amount,
            original_currency=tx.currency,
        )
        for tx, category_name, converted in rows
    ]


async def get_category_available_periods(
    db: AsyncSession,
    user_id: uuid.UUID,
    category_id: uuid.UUID,
) -> CategoryAvailablePeriodsResponse:
    """Años + meses (1-12) con transacciones activas para una categoría.

    Excluye papelera. Años descendente, meses ascendente. 404 si la
    categoría no existe o no pertenece al usuario — fallback a 404
    en lugar de devolver una lista vacía para no enmascarar errores
    de routing en el cliente.
    """
    category = await get_category_by_id(db, category_id, user_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoría no encontrada.",
        )
    query = (
        select(
            func.extract("year", Transaction.occurred_at).label("year"),
            func.extract("month", Transaction.occurred_at).label("month"),
        )
        .where(Transaction.user_id == user_id)
        .where(Transaction.category_id == category_id)
        .where(Transaction.deleted_at.is_(None))
        .distinct()
    )
    rows = (await db.execute(query)).all()
    months_by_year: dict[int, set[int]] = {}
    for year, month in rows:
        if year is None or month is None:
            continue
        months_by_year.setdefault(int(year), set()).add(int(month))
    items = [
        CategoryAvailablePeriodItem(year=year, months=sorted(months_by_year[year]))
        for year in sorted(months_by_year, reverse=True)
    ]
    return CategoryAvailablePeriodsResponse(periods=items)


async def get_category_detail(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    category_id: uuid.UUID,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    months_back: int = 12,
) -> CategoryDetailResponse:
    """PHASE-25 — drill-down de una categoría: KPIs (total, count,
    ticket medio) + evolución mensual (últimos `months_back` meses)
    + top tx del rango.

    404 si la categoría no existe / no es del usuario.
    """
    category = await get_category_by_id(db, category_id, user_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoría no encontrada.",
        )
    legacy, target, resolved_currency = _resolve_mode(currency, target_currency)
    if target is not None:
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target,
            date_from=date_from,
            date_to=date_to,
        )
    total_raw, count = await repository.get_category_kpis(
        db,
        user_id,
        category_id=category_id,
        currency=legacy,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
    )
    # Quantize a céntimos para que la serialización de Pydantic produzca
    # siempre "0.00" en vez de "0" cuando no hay datos.
    total = total_raw.quantize(Decimal("0.01"))
    monthly = await repository.get_category_monthly_evolution(
        db,
        user_id,
        category_id=category_id,
        currency=legacy,
        target_currency=target,
        months_back=months_back,
    )
    top = await repository.get_category_top_transactions(
        db,
        user_id,
        category_id=category_id,
        currency=legacy,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        limit=10,
    )
    average = total / Decimal(count) if count > 0 else Decimal("0")
    return CategoryDetailResponse(
        category_id=category.id,
        category_name=category.name,
        category_kind=category.kind.value,
        category_color=category.color,
        category_icon=category.icon,
        currency=resolved_currency,
        total=total,
        count=count,
        average_amount=average.quantize(Decimal("0.01")),
        by_month=[CategoryMonthlyBucket(month=month, total=total_m) for month, total_m in monthly],
        top_transactions=[
            TopExpenseItem(
                transaction_id=tx.id,
                description=tx.description,
                amount=converted if converted is not None else tx.amount,
                occurred_at=tx.occurred_at,
                category_id=tx.category_id,
                category_name=cat_name,
                original_amount=tx.amount,
                original_currency=tx.currency,
            )
            for tx, cat_name, converted in top
        ],
    )
