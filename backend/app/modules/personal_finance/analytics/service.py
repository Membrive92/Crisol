"""Lógica de negocio del módulo analytics (PHASE-37.3).

Orquesta la heurística de recurrencia (`recurrence.py`) con las queries
(`repository.py`) para producir la respuesta de gasto estructural vs
puntual y la tasa de ahorro dual.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.currency.service import convert
from app.modules.personal_finance.accounts.models import AccountNature, AccountType
from app.modules.personal_finance.accounts.repository import (
    get_balances_for_user,
    list_accounts,
)
from app.modules.personal_finance.analytics import repository as repo
from app.modules.personal_finance.analytics.recurrence import (
    RECURRENCE_MIN_MONTHS,
    RECURRENCE_WINDOW_MONTHS,
    classify_recurring_categories,
    recurrence_detail,
)
from app.modules.personal_finance.analytics.schemas import (
    CategoryAmount,
    CategoryStructureExplain,
    CommittedItem,
    ExpenseStructureResponse,
    MonthOutlookResponse,
    StructureReason,
    TxRef,
)
from app.modules.personal_finance.categories.models import CategoryKind, ExpenseNature
from app.modules.personal_finance.dashboard.repository import get_totals_by_kind
from app.modules.personal_finance.dashboard.service import ensure_rates_for_user_scope
from app.modules.personal_finance.debt.installments_repository import installments_by_account
from app.modules.personal_finance.fixed_expenses.models import FixedExpenseStatus
from app.modules.personal_finance.fixed_expenses.repository import list_fixed_expenses
from app.modules.personal_finance.user_month import (
    user_month_bounds,
    user_months_back,
)

# Cuentas líquidas para el runway/colchón: efectivo y equivalentes, no
# inversiones (brokerage/crypto) ni deuda.
_LIQUID_TYPES = frozenset({AccountType.BANK, AccountType.SAVINGS, AccountType.CASH})


def _month_floor_shift(dt: datetime, months_back: int) -> datetime:
    """Primer día (UTC 00:00) del mes que está `months_back` meses antes
    del mes de `dt`. `months_back=0` → primer día del mes de `dt`."""
    total = (dt.year * 12 + (dt.month - 1)) - months_back
    year, month0 = divmod(total, 12)
    return datetime(year, month0 + 1, 1, tzinfo=UTC)


def _recurrence_window(
    date_to: datetime | None,
    *,
    now: datetime | None = None,
    cycle_start_day: int | None = None,
) -> tuple[datetime, datetime]:
    """PHASE-43.1 — ventana de `RECURRENCE_WINDOW_MONTHS` meses naturales
    COMPLETOS terminados en `min(date_to, hoy)`.

    Dos correcciones sobre el cálculo previo (`window_end = date_to`):

    1. **Clamp a hoy** (bug A): un rango que termina en el futuro (p. ej. el
       selector "Año en curso" emite 31/12) no puede anclar la ventana en
       meses sin datos. Sin esto, ver el año actual a mitad de julio dejaba
       la ventana en jul–dic con un solo mes (julio parcial) de datos, la
       regla 3 no clasificaba nada y la tasa estructural degradaba a las
       reglas 1+2 en silencio.

    2. **Sólo meses completos** (bug B): un mes cortado —el mes en curso, o
       el mes final de un rango que termina a mitad— vale ~50 % de un mes
       normal, cae fuera de la banda ±40 % y consume un hueco del conteo
       `in_band`. Se excluye el mes del ancla SALVO que el ancla caiga en su
       último día natural (entonces ese mes está completo y SÍ entra —
       imprescindible para clasificar bien un período pasado como "Año 2025",
       cuyo diciembre es un mes completo visto desde 2026).

    `now` es inyectable para tests deterministas (no dependen del reloj).

    Trade-off aceptado (ya documentado en PHASE-37.3): un gasto recurrente
    nuevo tarda un mes natural completo en poder clasificarse como estructural.
    """
    now = now if now is not None else datetime.now(UTC)
    anchor = min(date_to, now) if date_to is not None else now
    anchor_date = anchor.date()

    # PHASE-47 — «mes» es el del USUARIO. La ventana que decide qué gasto es
    # estructural gobierna la tasa de ahorro estructural y el denominador del
    # runway; dejarla en meses naturales mientras el resto de la pantalla corta
    # por el ciclo produce dos verdades sobre el mismo dinero, y la que manda
    # depende de qué tarjeta mires. Sin día declarado, `user_month_bounds`
    # devuelve el mes natural exacto y esto es idéntico a lo de siempre.
    _, current_end = user_month_bounds(anchor_date, cycle_start_day)
    # El período del ancla está completo sólo si el ancla es su último día.
    anchor_month_complete = anchor_date == current_end
    if anchor_month_complete:
        first_start, _ = user_month_bounds(anchor_date, cycle_start_day)
        earlier = user_months_back(anchor_date, cycle_start_day, RECURRENCE_WINDOW_MONTHS - 1)
        window_start_date = earlier[0][0] if earlier else first_start
        window_end_date = current_end
    else:
        completos = user_months_back(anchor_date, cycle_start_day, RECURRENCE_WINDOW_MONTHS)
        window_start_date = completos[0][0]
        window_end_date = completos[-1][1]

    window_start = datetime(
        window_start_date.year, window_start_date.month, window_start_date.day, tzinfo=UTC
    )
    # Último microsegundo del período, misma convención que antes.
    window_end = (
        datetime(window_end_date.year, window_end_date.month, window_end_date.day, tzinfo=UTC)
        + timedelta(days=1)
        - timedelta(microseconds=1)
    )
    return window_start, window_end


def _safe_rate(income: Decimal, expense: Decimal) -> float | None:
    """(income - expense) / income como float; None si income <= 0."""
    if income <= 0:
        return None
    return float((income - expense) / income)


async def get_expense_structure(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    cycle_start_day: int | None = None,
) -> ExpenseStructureResponse:
    """Calcula el desglose estructural/puntual del gasto del rango.

    La ventana de recurrencia (para clasificar categorías recurrentes y
    la media mensual estructural) son los meses naturales COMPLETOS hasta
    `min(date_to, hoy)` — ver `_recurrence_window`. Así ver un período
    pasado usa el histórico hasta ese punto, no el actual, y ningún mes
    parcial contamina la clasificación.
    """
    window_start, window_end = _recurrence_window(date_to, cycle_start_day=cycle_start_day)

    if target_currency is not None:
        # Cubrir toda la ventana (no sólo el rango) para que la conversión
        # del histórico de recurrencia no deje meses fuera por falta de tasa.
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target_currency,
            date_from=window_start,
            date_to=window_end,
        )

    # Reglas 1 y 2 (fixed_expense confirmado + rol de deuda) ∪ regla 3
    # (recurrencia por importe estable sobre la ventana).
    seed = await repo.seed_structural_category_ids(db, user_id)
    monthly = await repo.monthly_expense_by_category(
        db,
        user_id,
        window_start=window_start,
        window_end=window_end,
        currency=currency,
        target_currency=target_currency,
    )
    recurring = classify_recurring_categories(monthly)
    structural_ids = seed | recurring

    # Explicitar cuándo la regla 3 no puede clasificar por falta de histórico
    # (bug A): antes degradaba a reglas 1+2 sin avisar.
    months_with_data = await repo.count_expense_months_in_window(
        db,
        user_id,
        window_start=window_start,
        window_end=window_end,
        currency=currency,
        target_currency=target_currency,
    )
    recurrence_available = months_with_data >= RECURRENCE_MIN_MONTHS

    structural_total, exceptional_total = await repo.expense_split_totals(
        db,
        user_id,
        structural_category_ids=structural_ids,
        currency=currency,
        target_currency=target_currency,
        date_from=date_from,
        date_to=date_to,
    )
    monthly_avg = await repo.structural_monthly_avg(
        db,
        user_id,
        structural_category_ids=structural_ids,
        window_start=window_start,
        window_end=window_end,
        currency=currency,
        target_currency=target_currency,
    )

    totals = await get_totals_by_kind(
        db,
        user_id,
        currency=currency,
        target_currency=target_currency,
        date_from=date_from,
        date_to=date_to,
    )
    income_total = totals[CategoryKind.INCOME]
    # Gasto bruto = estructural + puntual (mismos filtros que el split);
    # equivale al gasto de `get_totals_by_kind` — incluida la exclusión de lo
    # aplazado (PHASE-47.E), sin la cual las dos mitades de la tasa de ahorro
    # se calcularían sobre universos distintos.
    gross_expense = structural_total + exceptional_total

    top_rows = await repo.top_exceptional_transactions(
        db,
        user_id,
        structural_category_ids=structural_ids,
        currency=currency,
        target_currency=target_currency,
        date_from=date_from,
        date_to=date_to,
        limit=5,
    )
    by_cat_rows = await repo.exceptional_by_category(
        db,
        user_id,
        structural_category_ids=structural_ids,
        currency=currency,
        target_currency=target_currency,
        date_from=date_from,
        date_to=date_to,
    )

    return ExpenseStructureResponse(
        reference_currency=(target_currency or currency or "EUR"),
        income_total=income_total,
        structural_total=structural_total,
        exceptional_total=exceptional_total,
        structural_monthly_avg=monthly_avg,
        savings_rate_gross=_safe_rate(income_total, gross_expense),
        savings_rate_structural=_safe_rate(income_total, structural_total),
        top_exceptional=[
            TxRef(
                id=tx.id,
                description=tx.description,
                amount=tx.amount,
                converted_amount=converted,
                flow=tx.flow,
                currency=tx.currency,
                occurred_at=tx.occurred_at,
                category_id=tx.category_id,
                category_name=name,
            )
            for tx, name, converted in top_rows
        ],
        exceptional_by_category=[
            CategoryAmount(
                category_id=cid,
                category_name=name,
                color=color,
                icon=icon,
                total=total,
                deferred_total=deferred,
            )
            for cid, name, color, icon, total, deferred in by_cat_rows
        ],
        window_start=window_start.date(),
        window_end=window_end.date(),
        window_months_with_data=months_with_data,
        recurrence_available=recurrence_available,
    )


async def explain_expense_structure(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    cycle_start_day: int | None = None,
) -> list[CategoryStructureExplain]:
    """PHASE-43.2 (bug D) — por qué cada categoría del desglose es Fija o
    Variable. Convierte el KPI de "número que ignoro" en "número que puedo
    auditar y corregir": sin esto, el override de categoría es a ciegas.

    Clasifica a nivel de CATEGORÍA con la MISMA cascada que la capa SQL
    (`is_structural_expr`) pero sin el nivel de transacción — ese se reporta
    aparte como `tx_overrides`. La ventana de recurrencia es la de PHASE-43.1.
    """
    window_start, window_end = _recurrence_window(date_to, cycle_start_day=cycle_start_day)

    if target_currency is not None:
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target_currency,
            date_from=window_start,
            date_to=window_end,
        )

    monthly = await repo.monthly_expense_by_category(
        db,
        user_id,
        window_start=window_start,
        window_end=window_end,
        currency=currency,
        target_currency=target_currency,
    )
    fixed_ids, debt_ids = await repo.seed_structural_breakdown(db, user_id)
    categories = await repo.expense_categories_in_range(
        db, user_id, currency=currency, date_from=date_from, date_to=date_to
    )
    tx_overrides = await repo.tx_override_counts_by_category(
        db, user_id, currency=currency, date_from=date_from, date_to=date_to
    )

    out: list[CategoryStructureExplain] = []
    for cid, name, nature in categories:
        detail = recurrence_detail(monthly.get(cid, []))
        is_structural, reason = _classify_category_reason(
            nature, cid, fixed_ids, debt_ids, detail.months_active, detail.months_in_band
        )
        out.append(
            CategoryStructureExplain(
                category_id=cid,
                category_name=name,
                is_structural=is_structural,
                reason=reason,
                months_active=detail.months_active,
                months_in_band=detail.months_in_band,
                median_monthly=detail.median,
                tx_overrides=tx_overrides.get(cid, 0),
            )
        )
    return out


def _classify_category_reason(
    nature: ExpenseNature,
    category_id: uuid.UUID,
    fixed_ids: set[uuid.UUID],
    debt_ids: set[uuid.UUID],
    months_active: int,
    months_in_band: int,
) -> tuple[bool, StructureReason]:
    """Veredicto + razón a nivel de categoría, en el MISMO orden de
    precedencia que `is_structural_expr` (override categoría > reglas 1/2 >
    regla 3). El override de transacción se reporta aparte (`tx_overrides`)."""
    if nature == ExpenseNature.EXCEPTIONAL:
        return False, "override_category"
    if nature == ExpenseNature.STRUCTURAL:
        return True, "override_category"
    if category_id in fixed_ids:
        return True, "rule_1_fixed_expense"
    if category_id in debt_ids:
        return True, "rule_2_debt_role"
    if months_active < RECURRENCE_MIN_MONTHS:
        return False, "insufficient_history"
    if months_in_band >= RECURRENCE_MIN_MONTHS:
        return True, "rule_3_recurrence"
    return False, "not_recurring"


async def _structural_monthly_avg(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None,
    target_currency: str | None,
    window_start: datetime,
    window_end: datetime,
) -> Decimal:
    """Media mensual del gasto estructural (base del runway) — misma
    definición que `get_expense_structure`, factorizada para reusar en el
    month-outlook. Recibe la ventana ya calculada (`_recurrence_window`)."""
    seed = await repo.seed_structural_category_ids(db, user_id)
    monthly = await repo.monthly_expense_by_category(
        db,
        user_id,
        window_start=window_start,
        window_end=window_end,
        currency=currency,
        target_currency=target_currency,
    )
    structural_ids = seed | classify_recurring_categories(monthly)
    return await repo.structural_monthly_avg(
        db,
        user_id,
        structural_category_ids=structural_ids,
        window_start=window_start,
        window_end=window_end,
        currency=currency,
        target_currency=target_currency,
    )


async def get_month_outlook(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    cycle_start_day: int | None = None,
) -> MonthOutlookResponse:
    """Proyección de fin de mes + runway (PHASE-37.4).

    `committed_remaining` = gastos fijos confirmados con `next_due` en lo que
    queda de mes + cuotas de deuda con `due_date` en el mes aún sin pagar
    (incluye atrasados). MUX: un gasto fijo apuntado a un pasivo CON cuadro se
    excluye porque su cuota ya lo cubre (no doblar). `runway_months` = colchón
    líquido / gasto estructural mensual medio (37.3)."""
    now = datetime.now(UTC)
    today = now.date()
    # PHASE-47 — «fin de mes» es el fin del mes DEL USUARIO. Es la tarjeta que
    # más chirriaba con el ajuste puesto: anunciaba «quedan 11 días» contando
    # hasta el 31 cuando al usuario le quedaban 24 hasta su próxima nómina, y
    # el runway se calculaba sobre un período que él no vive.
    month_start, month_end = user_month_bounds(today, cycle_start_day)
    days_remaining = (month_end - today).days

    # Ventana de recurrencia para el gasto estructural del runway: meses
    # completos hasta hoy (excluye el mes en curso parcial — PHASE-43.1).
    window_start, window_end = _recurrence_window(None, now=now, cycle_start_day=cycle_start_day)

    accounts = await list_accounts(db, user_id, include_archived=False)
    reference = (
        target_currency or currency or (accounts[0].currency if accounts else "EUR")
    ).upper()

    if target_currency is not None:
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target_currency,
            date_from=window_start,
            date_to=window_end,
        )

    async def _to_ref(amount: Decimal, from_cur: str) -> Decimal | None:
        """Importe en la divisa de referencia, o `None` si no se puede
        homogeneizar. En modo NATIVO (`target_currency=None`) no mezclamos
        divisas: una cuenta/cargo en otra divisa se excluye (`None`) para que
        el numerador (líquido) y el denominador (gasto estructural, que filtra
        por `currency`) del runway usen el MISMO alcance. En modo target,
        convertimos a la tasa de hoy; una tasa ausente devuelve `None`
        (se descarta, como el dashboard) en vez de sumar valor en otra divisa."""
        if from_cur.upper() == reference:
            return amount
        if amount == 0:
            return Decimal("0")
        if target_currency is None:
            return None
        res = await convert(
            db, amount=amount, from_currency=from_cur, to_currency=reference, at_date=today
        )
        return None if res.fallback == "missing" else res.amount

    # Saldo líquido (efectivo + equivalentes, no inversiones ni deuda).
    movements = await get_balances_for_user(db, user_id)
    liquid_balance = Decimal("0")
    for a in accounts:
        if a.type not in _LIQUID_TYPES:
            continue
        native_bal = a.opening_balance + movements.get(a.id, Decimal("0"))
        conv = await _to_ref(native_bal, a.currency)
        if conv is not None:
            liquid_balance += conv

    liab_accounts = [a for a in accounts if a.nature == AccountNature.LIABILITY]
    insts_by_acc = await installments_by_account(db, user_id, [a.id for a in liab_accounts])

    # Cargos comprometidos: gastos fijos confirmados + cuotas del mes sin
    # pagar. NO se de-duplican por cuenta (un gasto fijo puede ser un cargo
    # legítimo distinto de la cuota, p. ej. una suscripción en una tarjeta
    # financiada; y un pago de cuota modelado también como gasto fijo se cobra
    # desde el banco, no desde el pasivo, así que un MUX por `account_id` no lo
    # captura). Acotado a la VENTANA DEL MES en curso: no arrastra el backlog
    # de meses anteriores (impagos viejos) — un outlook mensual no lista 6
    # meses de atrasos.
    items: list[CommittedItem] = []
    fixed = await list_fixed_expenses(db, user_id, status=FixedExpenseStatus.CONFIRMED)
    for fe in fixed:
        if not (month_start <= fe.next_due <= month_end):
            continue
        amount = await _to_ref(fe.amount, fe.currency)
        if amount is None:
            continue
        items.append(
            CommittedItem(
                name=fe.merchant,
                amount=amount,
                expected_date=fe.next_due,
                overdue=fe.next_due < today,
                kind="fixed",
            )
        )
    for a in liab_accounts:
        for inst in insts_by_acc.get(a.id, []):
            if inst.paid_at is not None or not (month_start <= inst.due_date <= month_end):
                continue
            amount = await _to_ref(inst.payment, a.currency)
            if amount is None:
                continue
            items.append(
                CommittedItem(
                    name=a.name,
                    amount=amount,
                    expected_date=inst.due_date,
                    overdue=inst.due_date < today,
                    kind="installment",
                )
            )
    items.sort(key=lambda i: i.expected_date)
    committed_remaining = sum((i.amount for i in items), Decimal("0"))

    # Runway: numerador (líquido) y denominador (gasto estructural) en el mismo
    # alcance de divisa (ver `_to_ref`). None si no hay base estructural o si
    # no hay colchón (líquido ≤ 0, p. ej. saldo de apertura sin cuadrar).
    monthly_avg = await _structural_monthly_avg(
        db,
        user_id,
        currency=currency,
        target_currency=target_currency,
        window_start=window_start,
        window_end=window_end,
    )
    runway = float(liquid_balance / monthly_avg) if monthly_avg > 0 and liquid_balance > 0 else None

    return MonthOutlookResponse(
        reference_currency=reference,
        committed_remaining=committed_remaining.quantize(Decimal("0.01")),
        committed_items=items,
        days_remaining=days_remaining,
        liquid_balance=liquid_balance.quantize(Decimal("0.01")),
        runway_months=runway,
    )
