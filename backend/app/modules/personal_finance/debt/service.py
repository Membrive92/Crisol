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
        db, user_id, currency, start=start_dt, end=end_dt
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


async def _load_debt_fixed_expenses(
    db: AsyncSession, user_id: uuid.UUID, currency: str
) -> list[tuple[FixedExpense, Category]]:
    """Lista `(fixed_expense, category)` para gastos fijos confirmados,
    en la moneda de referencia y con cadencia mensual, cuya categoría
    tiene `role IN (DEBT_PAYMENT, DEBT_INTEREST)`."""
    query = (
        select(FixedExpense, Category)
        .join(Category, Category.id == FixedExpense.category_id)
        .where(FixedExpense.user_id == user_id)
        .where(FixedExpense.status == FixedExpenseStatus.CONFIRMED)
        .where(FixedExpense.currency == currency)
        .where(Category.role.in_({CategoryRole.DEBT_PAYMENT, CategoryRole.DEBT_INTEREST}))
    )
    rows = (await db.execute(query)).all()
    return [(fe, cat) for fe, cat in rows]


async def _load_non_debt_fixed_expense_monthly_total(
    db: AsyncSession, user_id: uuid.UUID, currency: str
) -> Decimal:
    """Σ cuotas mensuales de gastos fijos NO categorizados como deuda
    (cualquier otra categoría, o sin categoría). Sólo cuenta los
    `confirmed` con cadencia mensual; los semestrales/anuales no
    contribuyen al "esfuerzo mensual"."""
    query = (
        select(FixedExpense)
        .outerjoin(Category, Category.id == FixedExpense.category_id)
        .where(FixedExpense.user_id == user_id)
        .where(FixedExpense.status == FixedExpenseStatus.CONFIRMED)
        .where(FixedExpense.currency == currency)
    )
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
        total += fe.amount
    return total.quantize(Decimal("0.01"))


# ─────────────────────────────────────────────────────────────────────
# Orquestador principal
# ─────────────────────────────────────────────────────────────────────


async def compute_category_summary(
    db: AsyncSession, user_id: uuid.UUID, range_: DebtTimeRange = "ytd"
) -> DebtCategorySummary:
    """Calcula el snapshot completo de Capa 1 para `range_`."""
    today = _today_utc()
    range_start, range_end, monthly_buckets = _resolve_range(range_, today)
    currency = await _resolve_reference_currency(db, user_id)

    start_dt = _month_start_utc(range_start)
    end_dt = _range_end_utc(range_end)

    # ── 1. Pagos por role en el rango ────────────────────────────────
    totals = await aggregate_debt_payments_by_role(
        db, user_id, currency, start=start_dt, end=end_dt
    )
    interests_and_fees = totals[CategoryRole.DEBT_INTEREST]
    capital_amortized = totals[CategoryRole.DEBT_PAYMENT]
    total_payments = interests_and_fees + capital_amortized

    # ── 2. Composición por tipo ──────────────────────────────────────
    rows = await aggregate_debt_payments_by_category(
        db, user_id, currency, start=start_dt, end=end_dt
    )
    by_type = _build_by_type(rows, total_payments)

    # ── 3. Serie mensual ─────────────────────────────────────────────
    series_rows = await monthly_debt_series(
        db, user_id, currency, months=monthly_buckets
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
    monthly_income = await monthly_income_avg(db, user_id, currency)
    avg_monthly_debt_payment = await _avg_monthly_debt_payment_last_n_months(
        db, user_id, currency, months=6
    )

    if monthly_income > 0 and avg_monthly_debt_payment > 0:
        strict = float(avg_monthly_debt_payment / monthly_income)
    else:
        strict = None
    strict_status = classify_effort(strict)

    non_debt_fixed = await _load_non_debt_fixed_expense_monthly_total(
        db, user_id, currency
    )
    extended_numerator = avg_monthly_debt_payment + non_debt_fixed
    if monthly_income > 0 and extended_numerator > 0:
        extended = float(extended_numerator / monthly_income)
    else:
        extended = None
    extended_status = classify_effort(extended)

    # ── 5. Recurring quotas (cross-link a fixed_expenses) ────────────
    debt_fixed = await _load_debt_fixed_expenses(db, user_id, currency)
    recurring_quotas = [
        RecurringQuotaRef(
            fixed_expense_id=fe.id,
            merchant=fe.merchant,
            amount=fe.amount,
            currency=fe.currency,
            category_id=cat.id,
            category_name=cat.name,
        )
        for fe, cat in debt_fixed
    ]

    return DebtCategorySummary(
        reference_currency=currency,
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
