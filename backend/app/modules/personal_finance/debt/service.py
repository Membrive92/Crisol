"""Servicio de Capa 1 del módulo deuda (PHASE-30.2)."""

from __future__ import annotations

import calendar
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.debt_health import (
    DEFAULT_REFERENCE_CURRENCY,
    classify_effort,
    windowed_income_total,
)
from app.modules.personal_finance.accounts.models import Account
from app.modules.personal_finance.categories.models import Category, CategoryRole
from app.modules.personal_finance.debt.repository import (
    aggregate_debt_payments_by_category,
    aggregate_debt_payments_by_role,
    debt_movement_bounds,
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


def _period_bounds(range_: DebtTimeRange, anchor: date) -> tuple[date, date]:
    """`[start, period_end]` natural del período que CONTIENE `anchor`,
    sin recortar a hoy.

    - `month`   → 1º…último día del mes de `anchor`.
    - `quarter` → trimestre natural (Q1=Ene-Mar … Q4=Oct-Dic).
    - `year`    → 1-ene…31-dic del año de `anchor`.
    """
    if range_ == "month":
        start = date(anchor.year, anchor.month, 1)
        last_day = calendar.monthrange(anchor.year, anchor.month)[1]
        return start, date(anchor.year, anchor.month, last_day)
    if range_ == "quarter":
        q_index = (anchor.month - 1) // 3
        first_month = q_index * 3 + 1
        last_month = first_month + 2
        start = date(anchor.year, first_month, 1)
        last_day = calendar.monthrange(anchor.year, last_month)[1]
        return start, date(anchor.year, last_month, last_day)
    # year
    return date(anchor.year, 1, 1), date(anchor.year, 12, 31)


def resolve_period_end(
    range_: DebtTimeRange,
    anchor: date | None = None,
    today: date | None = None,
) -> date:
    """Fecha de corte ("as-of") del período: fin natural del período,
    salvo el período en curso que se recorta a hoy.

    PHASE-30.8 — Fuente ÚNICA de verdad del as-of, compartida entre
    Capa 1 (`compute_category_summary`) y Capa 2 (`compute_debt_health`
    / `compute_debt_history`) para que los tres endpoints coincidan en
    la fecha de corte de un mismo período.
    """
    today = today or _today_utc()
    anchor = anchor or today
    _, period_end = _period_bounds(range_, anchor)
    return min(period_end, today)


def _resolve_range(
    range_: DebtTimeRange,
    anchor: date | None = None,
    today: date | None = None,
) -> tuple[date, date, list[date]]:
    """Devuelve `(range_start, range_end, monthly_buckets)`.

    PHASE-30.8 — El período lo determina `anchor` (cualquier día dentro
    del período objetivo); ausente → hoy → período en curso. `range_end`
    se recorta a hoy (`min(period_end, today)`): los períodos pasados
    salen completos, el actual parcial.

    `monthly_buckets` (meses sin actividad incluidos, longitud
    determinista):
    - `month`/`quarter` → siempre los meses naturales **completos** del
      período (1 y 3) → eje estable al navegar entre períodos del mismo
      tipo; los meses futuros del trimestre en curso salen a 0.
    - `year` → YTD para el año en curso (no pintamos meses futuros, que
      serían barras vacías) y los 12 meses para años pasados.

    Con `anchor=None` esto es idéntico al comportamiento previo a
    PHASE-30.8.
    """
    today = today or _today_utc()
    anchor = anchor or today
    start, period_end = _period_bounds(range_, anchor)
    range_end = min(period_end, today)
    last_bucket = _start_of_month(range_end) if range_ == "year" else _start_of_month(period_end)
    buckets: list[date] = []
    month = start
    while month <= last_bucket:
        buckets.append(month)
        month = _add_month(month, 1)
    return start, range_end, buckets


def _month_start_utc(d: date) -> datetime:
    return datetime(d.year, d.month, 1, tzinfo=UTC)


def _range_end_utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=UTC)


def _format_month(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


# ─────────────────────────────────────────────────────────────────────
# Resolución de moneda de referencia
# ─────────────────────────────────────────────────────────────────────


async def _resolve_reference_currency(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Misma estrategia que `accounts.debt_health` — primera cuenta
    activa por display_order. Si no hay cuentas, EUR (default global)."""
    query = select(Account).where(Account.user_id == user_id).where(Account.is_archived.is_(False))
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


# Mapa account.type → bucket del donut. Sólo nos interesan tipos
# liability; assets nunca aparecen vinculados a categorías de deuda.
_ACCOUNT_TYPE_BUCKET: dict[str, DebtTypeBucket] = {
    "mortgage": "mortgage",
    "loan": "loan",
    "credit_card": "credit_card",
}


def _classify_by_name(name: str) -> DebtTypeBucket:
    """Fallback de clasificación cuando la categoría no está vinculada
    a una cuenta (PHASE-30.4) — heurística sobre el nombre.

    PHASE-30.7 — `loan` se chequea ANTES que `mortgage` porque la
    categoría seed "Préstamos e hipotecas" contiene ambos substrings
    y la convención del producto es interpretarla como préstamo
    genérico (la mayoría de usuarios sin hipoteca usan esta categoría
    para sus préstamos). Quien tenga una hipoteca real puede o bien
    crear una categoría "Hipoteca Banco X" (no contiene "préstamo" →
    cae en mortgage) o vincular la liability a una categoría
    explícita para que la clasificación sea por `account.type`.
    """
    lower = name.lower()
    if any(h in lower for h in _NAME_HINTS_LOAN):
        return "loan"
    if any(h in lower for h in _NAME_HINTS_MORTGAGE):
        return "mortgage"
    if any(h in lower for h in _NAME_HINTS_CARD):
        return "credit_card"
    return "other"


def _classify_row(name: str, linked_account_type: str | None) -> DebtTypeBucket:
    """Señal primaria: tipo de la cuenta vinculada a la categoría
    (PHASE-30.4). Fallback: matching por nombre."""
    if linked_account_type is not None:
        bucket = _ACCOUNT_TYPE_BUCKET.get(linked_account_type)
        if bucket is not None:
            return bucket
    return _classify_by_name(name)


def _build_by_type(
    rows: list[tuple[str, CategoryRole, Decimal, str | None]],
    total: Decimal,
) -> list[DebtTypeBreakdown]:
    aggregates: dict[DebtTypeBucket, Decimal] = {
        "mortgage": Decimal("0"),
        "credit_card": Decimal("0"),
        "loan": Decimal("0"),
        "other": Decimal("0"),
    }
    for name, _role, amount, linked_type in rows:
        aggregates[_classify_row(name, linked_type)] += amount
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
    debt_category_ids = {row[0] for row in (await db.execute(debt_query)).all()}
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
    range_: DebtTimeRange = "year",
    *,
    anchor: date | None = None,
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
    range_start, range_end, monthly_buckets = _resolve_range(range_, anchor, today)
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

    # ── 4. Tasa de esfuerzo (period-scoped, PHASE-30.8) ──────────────
    #
    # Se promedia sobre los meses CERRADOS del período —se excluye el
    # mes en curso, aún incompleto, igual que hacía la ventana fija
    # anterior—: así numerador y denominador son medias mensuales reales
    # y no quedan diluidas por un mes a medias (la distorsión de dividir
    # ingreso parcial por meses completos rompería la coherencia con el
    # término de gastos fijos del ratio ampliado). Numerador = Σ pagos
    # de esos meses (reutiliza la serie ya calculada); denominador =
    # ingreso de la misma ventana. Sin meses cerrados (p. ej. `month`
    # del mes en curso) → ratio `None`: a mitad de mes no se puede saber.
    current_month_start = _start_of_month(today)
    closed_idx = [i for i, b in enumerate(monthly_buckets) if b < current_month_start]
    if closed_idx:
        n_closed = len(closed_idx)
        debt_closed = sum((monthly_series[i].payments for i in closed_idx), Decimal("0"))
        avg_monthly_debt_payment = (debt_closed / Decimal(n_closed)).quantize(Decimal("0.01"))
        last_closed = monthly_buckets[closed_idx[-1]]
        income_end = date(
            last_closed.year,
            last_closed.month,
            calendar.monthrange(last_closed.year, last_closed.month)[1],
        )
        income_total = await windowed_income_total(
            db,
            user_id,
            native_currency,
            start=range_start,
            end=income_end,
            target_currency=target_currency,
        )
        monthly_income = (income_total / Decimal(n_closed)).quantize(Decimal("0.01"))
    else:
        avg_monthly_debt_payment = Decimal("0")
        monthly_income = Decimal("0")

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

    # ── 6. Límites de períodos con datos (navegador de período) ──────
    # Mismos predicados que los agregados → las flechas nunca caen en
    # un período con KPIs todos a cero.
    bound_from, bound_to = await debt_movement_bounds(
        db, user_id, native_currency, target_currency=target_currency
    )

    return DebtCategorySummary(
        reference_currency=effective_currency,
        range=range_,
        range_start=range_start,
        range_end=range_end,
        available_from=_format_month(bound_from) if bound_from else None,
        available_to=_format_month(bound_to) if bound_to else None,
        total_payments=total_payments.quantize(Decimal("0.01")),
        interests_and_fees=interests_and_fees.quantize(Decimal("0.01")),
        capital_amortized=capital_amortized.quantize(Decimal("0.01")),
        by_type=by_type,
        monthly_series=monthly_series,
        monthly_income_avg=monthly_income,
        monthly_debt_payment_avg=avg_monthly_debt_payment,
        effort_ratio_strict=strict,
        effort_ratio_strict_status=strict_status,  # type: ignore[arg-type]
        effort_ratio_extended=extended,
        effort_ratio_extended_status=extended_status,  # type: ignore[arg-type]
        recurring_quotas=recurring_quotas,
    )
