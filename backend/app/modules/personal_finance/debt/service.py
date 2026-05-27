"""Servicio de Capa 1 del módulo deuda (PHASE-30.2)."""

from __future__ import annotations

import calendar
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.debt_health import (
    DEFAULT_REFERENCE_CURRENCY,
    EFFORT_BAND_CAUTION,
    EFFORT_BAND_HEALTHY,
    monthly_income_avg,
    classify_effort,
)
from app.modules.personal_finance.accounts.models import Account
from app.modules.personal_finance.categories.models import Category, CategoryRole
from app.modules.personal_finance.debt.repository import (
    aggregate_debt_payments_by_category,
    aggregate_debt_payments_by_role,
    monthly_debt_series,
)
from app.modules.personal_finance.debt.schemas import (
    DebtCategorySummary,
    DebtTimeRange,
    DebtTypeBreakdown,
    DebtTypeBucket,
    MonthlyDebtPoint,
    RecurringQuotaRef,
)
from app.modules.personal_finance.fixed_expenses.models import (
    FixedExpense,
    FixedExpenseStatus,
)


# ─────────────────────────────────────────────────────────────────────
# Helpers de rango temporal
# ─────────────────────────────────────────────────────────────────────


def _today_utc() -> date:
    return datetime.now(UTC).date()


def _start_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def _add_month(d: date, months: int) -> date:
    total = d.month - 1 + months
    new_year = d.year + total // 12
    new_month = total % 12 + 1
    return date(new_year, new_month, 1)


def _resolve_range(
    range_: DebtTimeRange, today: date | None = None
) -> tuple[date, date, list[date]]:
    """Devuelve `(range_start, range_end, monthly_buckets)`.

    `monthly_buckets` es la lista del primer día de cada mes del rango,
    incluyendo huecos sin actividad — necesaria para producir series
    de longitud determinista (ej. 12 puntos para `12m`).
    """
    today = today or _today_utc()
    if range_ == "month":
        start = _start_of_month(today)
        end = today
        return start, end, [start]
    if range_ == "ytd":
        start = date(today.year, 1, 1)
        end = today
        buckets = [
            _add_month(start, m) for m in range(today.month)
        ]
        return start, end, buckets
    # 12m: últimos 12 meses incluyendo el actual.
    start_month = _add_month(_start_of_month(today), -11)
    buckets = [_add_month(start_month, m) for m in range(12)]
    end = today
    return start_month, end, buckets


def _month_start_utc(d: date) -> datetime:
    return datetime(d.year, d.month, 1, tzinfo=UTC)


def _range_end_utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=UTC)


def _format_month(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


# ─────────────────────────────────────────────────────────────────────
# Resolución de moneda de referencia
# ─────────────────────────────────────────────────────────────────────


async def _avg_monthly_debt_payment_last_n_months(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    months: int = 6,
    target_currency: str | None = None,
) -> Decimal:
    """Media mensual de pagos a deuda en los últimos `months` meses
    cerrados (excluye el mes en curso). Misma ventana que
    `monthly_income_avg` — esencial para que el cociente del effort
    ratio compare valores comparables.
    """
    today = _today_utc()
    last_full_end = _start_of_month(today) - timedelta(days=1)
    window_start = _add_month(_start_of_month(last_full_end), -(months - 1))
    start_dt = datetime(window_start.year, window_start.month, 1, tzinfo=UTC)
    end_dt = datetime(
        last_full_end.year,
        last_full_end.month,
        last_full_end.day,
        23,
        59,
        59,
        tzinfo=UTC,
    )
    totals = await aggregate_debt_payments_by_role(
        db,
        user_id,
        currency,
        start=start_dt,
        end=end_dt,
        target_currency=target_currency,
    )
    total = totals[CategoryRole.DEBT_PAYMENT] + totals[CategoryRole.DEBT_INTEREST]
    if total <= 0:
        return Decimal("0")
    return (total / Decimal(months)).quantize(Decimal("0.01"))


async def _resolve_reference_currency(
    db: AsyncSession, user_id: uuid.UUID
) -> str:
    """Misma estrategia que `accounts.debt_health` — primera cuenta
    activa por display_order. Si no hay cuentas, EUR (default global)."""
    query = (
        select(Account)
        .where(Account.user_id == user_id)
        .where(Account.is_archived.is_(False))
    )
    accounts = list((await db.execute(query)).scalars().all())
    if not accounts:
        return DEFAULT_REFERENCE_CURRENCY
    accounts.sort(key=lambda a: (a.display_order, a.name))
    return accounts[0].currency


# ─────────────────────────────────────────────────────────────────────
# Composición por tipo (donut)
# ─────────────────────────────────────────────────────────────────────


_NAME_HINTS_MORTGAGE = ("hipoteca",)
_NAME_HINTS_CARD = ("tarjeta",)
_NAME_HINTS_LOAN = ("préstamo", "prestamo", "crédito personal", "credito personal")


def _classify_by_name(name: str) -> DebtTypeBucket:
    lower = name.lower()
    if any(h in lower for h in _NAME_HINTS_MORTGAGE):
        return "mortgage"
    if any(h in lower for h in _NAME_HINTS_CARD):
        return "credit_card"
    if any(h in lower for h in _NAME_HINTS_LOAN):
        return "loan"
    return "other"


def _build_by_type(
    rows: list[tuple[str, CategoryRole, Decimal]], total: Decimal
) -> list[DebtTypeBreakdown]:
    aggregates: dict[DebtTypeBucket, Decimal] = {
        "mortgage": Decimal("0"),
        "credit_card": Decimal("0"),
        "loan": Decimal("0"),
        "other": Decimal("0"),
    }
    for name, _role, amount in rows:
        aggregates[_classify_by_name(name)] += amount
    result: list[DebtTypeBreakdown] = []
    for bucket, amount in aggregates.items():
        if amount == 0:
            continue
        pct = float(amount / total) if total > 0 else 0.0
        result.append(
            DebtTypeBreakdown(
                type=bucket,
                amount=amount.quantize(Decimal("0.01")),
                percent=pct,
            )
        )
    # Orden estable: por importe descendiente (donut lo agradece).
    result.sort(key=lambda b: b.amount, reverse=True)
    return result


# ─────────────────────────────────────────────────────────────────────
# Fixed expenses → cuotas recurrentes vinculadas a deuda
# ─────────────────────────────────────────────────────────────────────


_MONTHLY_CADENCE_RANGE = range(28, 32)  # 28-31 días


async def _convert_at_today(
    db: AsyncSession,
    amount: Decimal,
    *,
    from_currency: str,
    target_currency: str,
) -> Decimal | None:
    """Convierte `amount` de `from_currency` a `target_currency` con la
    tasa de hoy. Devuelve `None` cuando no hay tasa disponible — el
    caller decide si excluir o contar como "no convertible"."""
    from app.modules.currency.service import convert as currency_convert

    result = await currency_convert(
        db,
        amount=amount,
        from_currency=from_currency,
        to_currency=target_currency,
        at_date=_today_utc(),
    )
    if result.fallback == "missing":
        return None
    return result.amount


async def _load_debt_fixed_expenses(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    target_currency: str | None = None,
) -> list[tuple[FixedExpense, Category, Decimal]]:
    """Lista `(fixed_expense, category, display_amount)` para gastos
    fijos confirmados cuya categoría tiene rol de deuda.

    Native mode: filtra por `FixedExpense.currency == currency` y
    `display_amount = fe.amount`.

    Converted mode: trae todos los confirmados con rol de deuda; cada
    `display_amount` viene convertido a `target_currency` con la tasa
    de hoy. Gastos en moneda sin tasa quedan excluidos."""
    query = (
        select(FixedExpense, Category)
        .join(Category, Category.id == FixedExpense.category_id)
        .where(FixedExpense.user_id == user_id)
        .where(FixedExpense.status == FixedExpenseStatus.CONFIRMED)
        .where(Category.role.in_({CategoryRole.DEBT_PAYMENT, CategoryRole.DEBT_INTEREST}))
    )
    if target_currency is None:
        query = query.where(FixedExpense.currency == currency)
    rows = (await db.execute(query)).all()

    result: list[tuple[FixedExpense, Category, Decimal]] = []
    for fe, cat in rows:
        if target_currency is None:
            result.append((fe, cat, fe.amount))
            continue
        converted = await _convert_at_today(
            db,
            fe.amount,
            from_currency=fe.currency,
            target_currency=target_currency,
        )
        if converted is None:
            continue
        result.append((fe, cat, converted))
    return result


async def _load_non_debt_fixed_expense_monthly_total(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    target_currency: str | None = None,
) -> Decimal:
    """Σ cuotas mensuales de gastos fijos NO categorizados como deuda
    (cualquier otra categoría, o sin categoría). Sólo cuenta los
    `confirmed` con cadencia mensual; los semestrales/anuales no
    contribuyen al "esfuerzo mensual".

    PHASE-30.6 — Native filtra por moneda; Converted suma todos
    convertidos a `target_currency` (excluye los sin tasa)."""
    query = (
        select(FixedExpense)
        .outerjoin(Category, Category.id == FixedExpense.category_id)
        .where(FixedExpense.user_id == user_id)
        .where(FixedExpense.status == FixedExpenseStatus.CONFIRMED)
    )
    if target_currency is None:
        query = query.where(FixedExpense.currency == currency)
    items = list((await db.execute(query)).scalars().all())
    debt_query = (
        select(Category.id)
        .where(Category.user_id == user_id)
        .where(Category.role.in_({CategoryRole.DEBT_PAYMENT, CategoryRole.DEBT_INTEREST}))
    )
    debt_category_ids = {
        row[0] for row in (await db.execute(debt_query)).all()
    }
    total = Decimal("0")
    for fe in items:
        if fe.category_id in debt_category_ids:
            continue
        if fe.cadence_days not in _MONTHLY_CADENCE_RANGE:
            continue
        if target_currency is None:
            total += fe.amount
            continue
        converted = await _convert_at_today(
            db,
            fe.amount,
            from_currency=fe.currency,
            target_currency=target_currency,
        )
        if converted is None:
            continue
        total += converted
    return total.quantize(Decimal("0.01"))


# ─────────────────────────────────────────────────────────────────────
# Orquestador principal
# ─────────────────────────────────────────────────────────────────────


async def compute_category_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    range_: DebtTimeRange = "ytd",
    *,
    target_currency: str | None = None,
) -> DebtCategorySummary:
    """Calcula el snapshot completo de Capa 1 para `range_`.

    PHASE-30.6 — Cuando se pasa `target_currency`, todos los importes
    devueltos se expresan en esa moneda con conversión per-tx vía
    `converted_amount_expr` (idéntico patrón al dashboard PHASE-8.3).
    El `reference_currency` de la respuesta se sobreescribe con
    `target_currency`. Cuando no se pasa, devuelve la moneda nativa
    del usuario (primera cuenta no archivada por display_order).
    """
    today = _today_utc()
    range_start, range_end, monthly_buckets = _resolve_range(range_, today)
    native_currency = await _resolve_reference_currency(db, user_id)
    effective_currency = (target_currency or native_currency).upper()

    start_dt = _month_start_utc(range_start)
    end_dt = _range_end_utc(range_end)

    # ── 1. Pagos por role en el rango ────────────────────────────────
    totals = await aggregate_debt_payments_by_role(
        db,
        user_id,
        native_currency,
        start=start_dt,
        end=end_dt,
        target_currency=target_currency,
    )
    interests_and_fees = totals[CategoryRole.DEBT_INTEREST]
    capital_amortized = totals[CategoryRole.DEBT_PAYMENT]
    total_payments = interests_and_fees + capital_amortized

    # ── 2. Composición por tipo ──────────────────────────────────────
    rows = await aggregate_debt_payments_by_category(
        db,
        user_id,
        native_currency,
        start=start_dt,
        end=end_dt,
        target_currency=target_currency,
    )
    by_type = _build_by_type(rows, total_payments)

    # ── 3. Serie mensual ─────────────────────────────────────────────
    series_rows = await monthly_debt_series(
        db,
        user_id,
        native_currency,
        months=monthly_buckets,
        target_currency=target_currency,
    )
    monthly_series = [
        MonthlyDebtPoint(
            month=_format_month(month_start),
            payments=payments.quantize(Decimal("0.01")),
            interests=interests.quantize(Decimal("0.01")),
            capital=(payments - interests).quantize(Decimal("0.01")),
        )
        for month_start, payments, interests in series_rows
    ]

    # ── 4. Tasa de esfuerzo ──────────────────────────────────────────
    #
    # Income y pagos se promedian sobre la MISMA ventana (últimos 6
    # meses cerrados). Si calculásemos pagos sobre el rango visualizado
    # (12m / ytd / month), los ratios se descompensarían porque
    # diluiríamos pagos reales recientes en huecos sin actividad
    # (usuario que empezó hace 6m con range=12m → ratio aparente la
    # mitad de la real).
    monthly_income = await monthly_income_avg(
        db, user_id, native_currency, target_currency=target_currency
    )
    avg_monthly_debt_payment = await _avg_monthly_debt_payment_last_n_months(
        db, user_id, native_currency, months=6, target_currency=target_currency
    )

    if monthly_income > 0 and avg_monthly_debt_payment > 0:
        strict = float(avg_monthly_debt_payment / monthly_income)
    else:
        strict = None
    strict_status = classify_effort(strict)

    non_debt_fixed = await _load_non_debt_fixed_expense_monthly_total(
        db, user_id, native_currency, target_currency=target_currency
    )
    extended_numerator = avg_monthly_debt_payment + non_debt_fixed
    if monthly_income > 0 and extended_numerator > 0:
        extended = float(extended_numerator / monthly_income)
    else:
        extended = None
    extended_status = classify_effort(extended)

    # ── 5. Recurring quotas (cross-link a fixed_expenses) ────────────
    debt_fixed = await _load_debt_fixed_expenses(
        db, user_id, native_currency, target_currency=target_currency
    )
    recurring_quotas = [
        RecurringQuotaRef(
            fixed_expense_id=fe.id,
            merchant=fe.merchant,
            amount=display_amount.quantize(Decimal("0.01")),
            currency=effective_currency if target_currency else fe.currency,
            category_id=cat.id,
            category_name=cat.name,
        )
        for fe, cat, display_amount in debt_fixed
    ]

    return DebtCategorySummary(
        reference_currency=effective_currency,
        range=range_,
        range_start=range_start,
        range_end=range_end,
        total_payments=total_payments.quantize(Decimal("0.01")),
        interests_and_fees=interests_and_fees.quantize(Decimal("0.01")),
        capital_amortized=capital_amortized.quantize(Decimal("0.01")),
        by_type=by_type,
        monthly_series=monthly_series,
        monthly_income_avg=monthly_income,
        effort_ratio_strict=strict,
        effort_ratio_strict_status=strict_status,  # type: ignore[arg-type]
        effort_ratio_extended=extended,
        effort_ratio_extended_status=extended_status,  # type: ignore[arg-type]
        recurring_quotas=recurring_quotas,
    )
