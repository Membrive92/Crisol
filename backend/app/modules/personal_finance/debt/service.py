"""Servicio de Capa 1 del módulo deuda (PHASE-30.2)."""

from __future__ import annotations

import calendar
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.debt_health import (
    DEFAULT_REFERENCE_CURRENCY,
    classify_effort,
    windowed_income_total,
)
from app.modules.personal_finance.accounts.debt_history import _scheduled_remaining_at
from app.modules.personal_finance.accounts.installments_repository import (
    installments_by_account,
    interest_paid_in_window,
    principal_paid_in_window,
)
from app.modules.personal_finance.accounts.models import Account, AccountNature
from app.modules.personal_finance.categories.models import Category, CategoryRole
from app.modules.personal_finance.debt.repository import (
    aggregate_debt_payments_by_category,
    aggregate_debt_payments_by_role,
    daily_category_flows,
    daily_liability_flows,
    debt_movement_bounds,
    liability_signed_before,
    monthly_debt_series,
)
from app.modules.personal_finance.debt.schemas import (
    DailyDebtPoint,
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
# Serie diaria (sólo range='month') — evolución del saldo de deuda
# ─────────────────────────────────────────────────────────────────────


async def _build_daily_series(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    native_currency: str,
    effective_currency: str,
    range_start: date,
    range_end: date,
    start_dt: datetime,
    end_dt: datetime,
    target_currency: str | None,
) -> list[DailyDebtPoint]:
    """Construye la serie diaria del mes (PHASE-30.9).

    Con cuentas-pasivo: línea de saldo (apertura + carry + Σ flujos
    diarios) + barras emitida/amortizado/interés. Sin cuentas-pasivo:
    cae a barras de pagos categorizados (capital DEBT_PAYMENT) + interés,
    sin línea de saldo (`balance=None`) — así el chart diario sigue
    siendo útil aunque el usuario no haya declarado contratos.

    AUDIT-2026-07 (M-02) — FUENTE DEL SALDO, unificada con el cuadro (igual
    que `debt_history`): los pasivos CON cuadro aportan su
    `schedule_outstanding` (PHASE-36 "el cuadro manda"); los SIN cuadro,
    apertura + carry + Σ flujos diarios. Así el NIVEL de la línea cuadra con
    /balances y /debt-health. La contribución del cuadro es constante en el mes
    (la amortización de un préstamo es mensual, no diaria); las barras
    emitida/amortizado siguen reflejando los movimientos de los pasivos sin
    cuadro.
    """
    q = Decimal("0.01")
    acc_q = select(Account).where(Account.user_id == user_id).where(Account.is_archived.is_(False))
    accounts = list((await db.execute(acc_q)).scalars().all())
    if target_currency is None:
        liabilities = [
            a
            for a in accounts
            if a.nature == AccountNature.LIABILITY
            and a.currency == native_currency
            and a.counts_as_debt
        ]
    else:
        liabilities = [
            a for a in accounts if a.nature == AccountNature.LIABILITY and a.counts_as_debt
        ]
    liability_ids = [a.id for a in liabilities]

    # PHASE-37 — cuadro cargado ya aquí: las categorías vinculadas a un pasivo
    # con cuadro se excluyen del flujo categorizado (MUX) y su interés lo
    # aporta el cuadro por día (más abajo).
    insts_by_account = await installments_by_account(db, user_id, liability_ids)
    scheduled = [a for a in liabilities if insts_by_account.get(a.id)]
    nonsched = [a for a in liabilities if not insts_by_account.get(a.id)]
    nonsched_ids = [a.id for a in nonsched]
    excluded_cat_ids = {a.category_id for a in scheduled if a.category_id is not None} or None

    # Interés diario (Capa 1) + capital categorizado (fallback sin pasivos).
    cat_flows = await daily_category_flows(
        db,
        user_id,
        native_currency,
        start=start_dt,
        end=end_dt,
        target_currency=target_currency,
        exclude_category_ids=excluded_cat_ids,
    )
    last_day = range_end.day
    points: list[DailyDebtPoint] = []

    if not liability_ids:
        for d in range(1, last_day + 1):
            capital, interest = cat_flows.get(d, (Decimal("0"), Decimal("0")))
            points.append(
                DailyDebtPoint(
                    day=d,
                    emitida=Decimal("0.00"),
                    amortizado=capital.quantize(q),
                    interest=interest.quantize(q),
                    balance=None,
                )
            )
        return points

    # AUDIT-2026-07 (M-02): el NIVEL de la línea de saldo de los pasivos CON
    # cuadro lo manda `schedule_outstanding` (PHASE-36), no su apertura +
    # movimientos. Restringimos flujos/carry/apertura a los pasivos SIN cuadro
    # y añadimos el saldo del cuadro como base (constante en el mes: la
    # amortización de un préstamo es mensual, no diaria). Así el nivel diario
    # cuadra con /balances y /debt-health.

    # Saldo del cuadro para el MES mostrado (misma base due-date que
    # debt_history, para que las dos vistas temporales cuadren entre sí).
    displayed_month = date(range_end.year, range_end.month, 1)
    scheduled_base = Decimal("0")
    for a in scheduled:
        native = _scheduled_remaining_at(insts_by_account[a.id], displayed_month)
        if target_currency is None or a.currency.upper() == effective_currency:
            scheduled_base += native
        else:
            converted = await _convert_at_today(
                db, native, from_currency=a.currency, target_currency=effective_currency
            )
            if converted is not None:
                scheduled_base += converted

    # PHASE-37 — interés del cuadro por día: la cuota pagada este mes aporta
    # su interés al día de su `paid_at`. Las cuotas son mensuales, así que a
    # lo sumo una por pasivo cae en el mes mostrado.
    sched_interest_by_day: dict[int, Decimal] = {}
    for a in scheduled:
        for inst in insts_by_account[a.id]:
            paid = inst.paid_at
            if (
                paid is None
                or paid.year != displayed_month.year
                or paid.month != displayed_month.month
            ):
                continue
            if target_currency is None or a.currency.upper() == effective_currency:
                val = inst.interest
            else:
                converted = await _convert_at_today(
                    db, inst.interest, from_currency=a.currency, target_currency=effective_currency
                )
                val = converted if converted is not None else Decimal("0")
            sched_interest_by_day[paid.day] = (
                sched_interest_by_day.get(paid.day, Decimal("0")) + val
            )

    if nonsched_ids:
        flows = await daily_liability_flows(
            db,
            user_id,
            liability_ids=nonsched_ids,
            start=start_dt,
            end=end_dt,
            reference_currency=native_currency,
            target_currency=target_currency,
        )
        carry = await liability_signed_before(
            db,
            user_id,
            liability_ids=nonsched_ids,
            before=start_dt,
            reference_currency=native_currency,
            target_currency=target_currency,
        )
    else:
        flows = {}
        carry = Decimal("0")
    # Apertura agregada de los pasivos SIN cuadro (convertida a hoy en target).
    opening = Decimal("0")
    for a in nonsched:
        if target_currency is None or a.currency.upper() == effective_currency:
            opening += a.opening_balance
            continue
        converted = await _convert_at_today(
            db, a.opening_balance, from_currency=a.currency, target_currency=effective_currency
        )
        if converted is not None:
            opening += converted

    balance = opening + carry + scheduled_base
    for d in range(1, last_day + 1):
        emitida, amortizado = flows.get(d, (Decimal("0"), Decimal("0")))
        _capital, cat_interest = cat_flows.get(d, (Decimal("0"), Decimal("0")))
        interest = cat_interest + sched_interest_by_day.get(d, Decimal("0"))
        balance = balance + emitida - amortizado
        points.append(
            DailyDebtPoint(
                day=d,
                emitida=emitida.quantize(q),
                amortizado=amortizado.quantize(q),
                interest=interest.quantize(q),
                balance=max(balance, Decimal("0")).quantize(q),
            )
        )
    return points


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

    # ── 0. Pasivos con cuadro (PHASE-37) ─────────────────────────────
    # El interés/capital de una deuda CON cuadro lo aporta el cuadro de
    # amortización, no sus transacciones (el banco no desglosa el interés,
    # va dentro de la cuota). MUX por pasivo: se excluyen del flujo
    # categorizado las categorías VINCULADAS a un pasivo con cuadro para
    # no contar dos veces, y se suma el interés/capital del cuadro.
    acc_q = select(Account).where(Account.user_id == user_id).where(Account.is_archived.is_(False))
    all_accounts = list((await db.execute(acc_q)).scalars().all())
    if target_currency is None:
        liabs = [
            a
            for a in all_accounts
            if a.nature == AccountNature.LIABILITY and a.currency == native_currency
        ]
    else:
        liabs = [a for a in all_accounts if a.nature == AccountNature.LIABILITY]
    insts_by_acc = await installments_by_account(db, user_id, [a.id for a in liabs])
    scheduled = [a for a in liabs if insts_by_acc.get(a.id)]
    excluded_cat_ids = {a.category_id for a in scheduled if a.category_id is not None} or None

    async def _sched_paid(fn: Callable[..., Decimal], *, start: date, end: date) -> Decimal:
        """Σ (interés|principal) pagado en `[start, end]` sobre los pasivos
        con cuadro, convertido al effective (tasa de hoy, como los saldos)."""
        total = Decimal("0")
        for a in scheduled:
            native = fn(insts_by_acc[a.id], start=start, end=end)
            if native == 0:
                continue
            if target_currency is None or a.currency.upper() == effective_currency:
                total += native
            else:
                converted = await _convert_at_today(
                    db, native, from_currency=a.currency, target_currency=effective_currency
                )
                if converted is not None:
                    total += converted
        return total

    # ── 1. Pagos por role en el rango (categoría MUX + cuadro) ───────
    totals = await aggregate_debt_payments_by_role(
        db,
        user_id,
        native_currency,
        start=start_dt,
        end=end_dt,
        target_currency=target_currency,
        exclude_category_ids=excluded_cat_ids,
    )
    sched_interest_range = await _sched_paid(
        interest_paid_in_window, start=range_start, end=range_end
    )
    sched_principal_range = await _sched_paid(
        principal_paid_in_window, start=range_start, end=range_end
    )
    interests_and_fees = totals[CategoryRole.DEBT_INTEREST] + sched_interest_range
    capital_amortized = totals[CategoryRole.DEBT_PAYMENT] + sched_principal_range
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
        exclude_category_ids=excluded_cat_ids,
    )
    monthly_series: list[MonthlyDebtPoint] = []
    for month_start, payments, interests in series_rows:
        month_end = date(
            month_start.year,
            month_start.month,
            calendar.monthrange(month_start.year, month_start.month)[1],
        )
        m_sched_i = await _sched_paid(interest_paid_in_window, start=month_start, end=month_end)
        m_sched_p = await _sched_paid(principal_paid_in_window, start=month_start, end=month_end)
        m_interest = interests + m_sched_i
        m_payments = payments + m_sched_i + m_sched_p
        monthly_series.append(
            MonthlyDebtPoint(
                month=_format_month(month_start),
                payments=m_payments.quantize(Decimal("0.01")),
                interests=m_interest.quantize(Decimal("0.01")),
                capital=(m_payments - m_interest).quantize(Decimal("0.01")),
            )
        )

    # ── 3b. Serie diaria (sólo range='month'): evolución del saldo ───
    daily_series = (
        await _build_daily_series(
            db,
            user_id,
            native_currency=native_currency,
            effective_currency=effective_currency,
            range_start=range_start,
            range_end=range_end,
            start_dt=start_dt,
            end_dt=end_dt,
            target_currency=target_currency,
        )
        if range_ == "month"
        else None
    )

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
        daily_series=daily_series,
        monthly_income_avg=monthly_income,
        monthly_debt_payment_avg=avg_monthly_debt_payment,
        effort_ratio_strict=strict,
        effort_ratio_strict_status=strict_status,
        effort_ratio_extended=extended,
        effort_ratio_extended_status=extended_status,
        recurring_quotas=recurring_quotas,
    )
