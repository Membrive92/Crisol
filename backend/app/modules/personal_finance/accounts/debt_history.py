"""Serie temporal de evolución de deuda (PHASE-22.1).

Genera dos tramos contiguos:

- **Histórico**: para cada mes cerrado de la ventana solicitada,
  el saldo agregado de liabilities al cierre + el principal y los
  intereses pagados durante ese mes.
- **Proyección**: desde el mes en curso hacia adelante, estima la
  caída de la deuda usando los cuadros de amortización (loans /
  mortgages) y la cuota teórica de tarjetas. No asume nuevos cargos.

Convenciones:

- Sólo cuentas no archivadas en la `reference_currency` cuentan.
  Las cuentas en otra moneda se ignoran (mismo criterio que
  `/balances` y `/debt-health`).
- `principal_paid` mensual = suma de transacciones tipo income
  enlazadas como `transfer_pair` que llegan a cuentas liability ese
  mes. Es el dinero que el usuario movió desde una cuenta corriente
  para amortizar.
- `interest_paid` mensual = suma de expenses en categorías con
  `role=DEBT_INTEREST` ese mes.
- El saldo histórico al cierre de un mes se computa como
  `opening_balance + Σ(signed_amount hasta el mes)` con la misma
  inversión de signo que `get_balances_for_user`.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.amortization import (
    AmortizationRow,
    build_schedule,
    compute_monthly_payment,
)
from app.modules.personal_finance.accounts.debt_health import (
    DEFAULT_REFERENCE_CURRENCY,
)
from app.modules.personal_finance.accounts.models import (
    Account,
    AccountNature,
    AccountType,
)
from app.modules.personal_finance.accounts.schemas import (
    DebtHistoryPoint,
    DebtHistoryResponse,
)
from app.modules.personal_finance.categories.models import (
    Category,
    CategoryKind,
    CategoryRole,
)
from app.modules.personal_finance.dashboard.conversion import (
    converted_amount_expr,
)
from app.modules.personal_finance.transactions.models import Transaction


def _today_utc() -> date:
    return datetime.now(UTC).date()


def _start_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def _end_of_month(d: date) -> datetime:
    last_day = calendar.monthrange(d.year, d.month)[1]
    return datetime(d.year, d.month, last_day, 23, 59, 59, tzinfo=UTC)


def _add_month(d: date, months: int) -> date:
    total = d.month - 1 + months
    new_year = d.year + total // 12
    new_month = total % 12 + 1
    return date(new_year, new_month, 1)


def _format_month(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


async def _compute_historical_points(
    db: AsyncSession,
    user_id: uuid.UUID,
    liabilities: list[Account],
    reference_currency: str,
    months_back: int,
    *,
    target_currency: str | None = None,
    sum_opening_target: Decimal | None = None,
) -> list[DebtHistoryPoint]:
    """Histórico mes a mes para los últimos `months_back` meses cerrados.

    No incluye el mes en curso (sería incompleto). Si el usuario no
    tiene liabilities, devuelve lista vacía.

    PHASE-30.6 — Con `target_currency`, intereses y principal se
    convierten per-tx y el saldo agregado usa la opening_balance
    pre-convertida que pasa el caller (`sum_opening_target`).
    """
    if not liabilities or months_back <= 0:
        return []

    today = _today_utc()
    last_closed = _start_of_month(today) - timedelta(days=1)
    # Primer mes de la ventana: months_back meses atrás contando el
    # último cerrado como índice 1.
    first_month = _start_of_month(last_closed)
    for _ in range(months_back - 1):
        first_month = _start_of_month(first_month) - timedelta(days=1)
        first_month = _start_of_month(first_month)

    liability_ids = [liab.id for liab in liabilities]
    sum_opening = (
        sum_opening_target
        if sum_opening_target is not None
        else sum((liab.opening_balance for liab in liabilities), Decimal("0"))
    )

    amount_expr = (
        converted_amount_expr(target_currency)
        if target_currency is not None
        else Transaction.amount
    )

    # Inversión de signo en SQL idéntica a get_balances_for_user, pero
    # acumulada hasta `month_end`. Para llamadas múltiples, una sola
    # query agrupada por cierre de mes sería más eficiente; el patrón
    # mensual de iteración es lo bastante barato para 12-24 meses.
    signed_amount = case(
        (Category.kind == CategoryKind.EXPENSE, amount_expr),
        (Category.kind == CategoryKind.INCOME, -amount_expr),
        else_=amount_expr,
    )

    points: list[DebtHistoryPoint] = []
    cursor = first_month
    while cursor <= last_closed:
        month_end = _end_of_month(cursor)
        month_start = datetime(cursor.year, cursor.month, 1, tzinfo=UTC)

        # Saldo acumulado de liabilities al cierre del mes.
        cumulative_q = (
            select(func.coalesce(func.sum(signed_amount), 0))
            .select_from(Transaction)
            .outerjoin(Category, Category.id == Transaction.category_id)
            .where(Transaction.user_id == user_id)
            .where(Transaction.account_id.in_(liability_ids))
            .where(Transaction.deleted_at.is_(None))
            .where(Transaction.occurred_at <= month_end)
        )
        if target_currency is None:
            cumulative_q = cumulative_q.where(Transaction.currency == reference_currency)
        cumulative = Decimal((await db.execute(cumulative_q)).scalar_one())
        total_debt = sum_opening + cumulative

        # Principal amortizado durante el mes (ingresos transferencia
        # llegando a liabilities).
        principal_q = (
            select(func.coalesce(func.sum(amount_expr), 0))
            .where(Transaction.user_id == user_id)
            .where(Transaction.account_id.in_(liability_ids))
            .where(Transaction.deleted_at.is_(None))
            .where(Transaction.transfer_pair_id.is_not(None))
            .where(Transaction.occurred_at >= month_start)
            .where(Transaction.occurred_at <= month_end)
        )
        if target_currency is None:
            principal_q = principal_q.where(Transaction.currency == reference_currency)
        principal_paid = Decimal((await db.execute(principal_q)).scalar_one())

        # Intereses pagados durante el mes.
        interest_q = (
            select(func.coalesce(func.sum(amount_expr), 0))
            .select_from(Transaction)
            .join(Category, Category.id == Transaction.category_id)
            .where(Transaction.user_id == user_id)
            .where(Transaction.deleted_at.is_(None))
            .where(Category.kind == CategoryKind.EXPENSE)
            .where(Category.role == CategoryRole.DEBT_INTEREST)
            .where(Transaction.occurred_at >= month_start)
            .where(Transaction.occurred_at <= month_end)
        )
        if target_currency is None:
            interest_q = interest_q.where(Transaction.currency == reference_currency)
        interest_paid = Decimal((await db.execute(interest_q)).scalar_one())

        points.append(
            DebtHistoryPoint(
                month=_format_month(cursor),
                total_debt=max(total_debt, Decimal("0")).quantize(Decimal("0.01")),
                principal_paid=principal_paid.quantize(Decimal("0.01")),
                interest_paid=interest_paid.quantize(Decimal("0.01")),
                kind="historical",
            )
        )
        cursor = _add_month(cursor, 1)

    return points


async def _project_points(
    db: AsyncSession,
    liabilities: list[Account],
    current_balances: dict[uuid.UUID, Decimal],
    months_ahead: int,
    *,
    target_currency: str | None = None,
    effective_currency: str | None = None,
) -> list[DebtHistoryPoint]:
    """Proyecta la evolución de deuda hacia adelante.

    Mantiene saldo por cuenta independiente: a las loans/mortgages
    con cuadro francés les aplica la fila correspondiente al mes
    proyectado; a las tarjetas les amortiza la cuota teórica (cuota
    francesa a 12 meses con APR, o 3% del saldo si no tiene APR).
    Una cuenta deja de contribuir cuando su saldo llega a 0.

    PHASE-30.6 — Cuando `target_currency` está activo, los saldos
    y cuotas se devuelven ya convertidos. Las liabilities cuyo saldo
    inicial ya venía convertido en `current_balances` operan en la
    divisa target; sus cuadros teóricos (nativos) se convierten
    cuota a cuota con la tasa de hoy.
    """
    if not liabilities or months_ahead <= 0:
        return []

    today = _today_utc()
    current_month = _start_of_month(today)

    # Schedules pre-calculados para loans/mortgages (siempre en divisa
    # nativa de la liability).
    schedules: dict[uuid.UUID, list[AmortizationRow]] = {}
    for liab in liabilities:
        if liab.type in {AccountType.LOAN, AccountType.MORTGAGE} and (
            liab.apr is not None
            and liab.term_months is not None
            and liab.start_date is not None
            and liab.opening_balance > 0
        ):
            schedules[liab.id] = build_schedule(
                principal=liab.opening_balance,
                apr=liab.apr,
                term_months=liab.term_months,
                start_date=liab.start_date,
            )

    # FX rates cacheadas por liability (un único factor por cuenta,
    # con la tasa de hoy). Si una cuenta no tiene tasa o ya está en
    # la divisa target, el factor es Decimal("1").
    fx_factor: dict[uuid.UUID, Decimal] = {}
    if target_currency is not None and effective_currency is not None:
        for liab in liabilities:
            if liab.id not in current_balances:
                continue
            if liab.currency.upper() == effective_currency:
                fx_factor[liab.id] = Decimal("1")
                continue
            converted = await _convert_at_today(
                db,
                Decimal("1"),
                from_currency=liab.currency,
                target_currency=effective_currency,
            )
            fx_factor[liab.id] = converted if converted is not None else Decimal("0")

    # Estado mutable: saldo proyectado por cuenta (ya en effective_currency
    # cuando target está activo, gracias a `current_balances` preconvertido).
    balances: dict[uuid.UUID, Decimal] = {
        liab.id: current_balances.get(liab.id, Decimal("0")) for liab in liabilities
    }

    def _convert_native_to_eff(account_id: uuid.UUID, native: Decimal) -> Decimal:
        if target_currency is None:
            return native
        return (native * fx_factor.get(account_id, Decimal("0"))).quantize(Decimal("0.01"))

    points: list[DebtHistoryPoint] = []
    for offset in range(1, months_ahead + 1):
        proj_month = _add_month(current_month, offset)
        month_principal = Decimal("0")
        month_interest = Decimal("0")

        for liab in liabilities:
            if liab.id not in balances:
                continue
            balance = balances[liab.id]
            if balance <= 0:
                continue

            if liab.id in schedules:
                # Busca la fila del schedule que corresponde al mes
                # proyectado, comparando year-month.
                schedule_row = next(
                    (
                        r
                        for r in schedules[liab.id]
                        if r.due_date.year == proj_month.year
                        and r.due_date.month == proj_month.month
                    ),
                    None,
                )
                if schedule_row is not None:
                    pay_principal_eff = _convert_native_to_eff(liab.id, schedule_row.principal)
                    pay_principal_eff = min(pay_principal_eff, balance)
                    month_principal += pay_principal_eff
                    month_interest += _convert_native_to_eff(liab.id, schedule_row.interest)
                    balances[liab.id] = balance - pay_principal_eff
            elif liab.type == AccountType.CREDIT_CARD:
                if liab.apr is not None:
                    # Operamos sobre el saldo nativo equivalente para
                    # respetar el APR (porcentaje, independiente de divisa).
                    factor = (
                        fx_factor.get(liab.id, Decimal("1")) if target_currency else Decimal("1")
                    )
                    native_equiv = balance / factor if factor > 0 else Decimal("0")
                    cuota_native = compute_monthly_payment(native_equiv, liab.apr, 12)
                    interest_native = (native_equiv * liab.apr / Decimal(12)).quantize(
                        Decimal("0.01")
                    )
                    pay_principal_native = cuota_native - interest_native
                    if pay_principal_native < 0:
                        pay_principal_native = Decimal("0")
                    pay_principal_eff = _convert_native_to_eff(liab.id, pay_principal_native)
                    pay_principal_eff = min(pay_principal_eff, balance)
                    month_principal += pay_principal_eff
                    month_interest += _convert_native_to_eff(liab.id, interest_native)
                    balances[liab.id] = balance - pay_principal_eff
                else:
                    pay_principal_eff = min(
                        (balance * Decimal("0.03")).quantize(Decimal("0.01")),
                        balance,
                    )
                    month_principal += pay_principal_eff
                    balances[liab.id] = balance - pay_principal_eff

        total_debt = sum(balances.values(), Decimal("0"))
        points.append(
            DebtHistoryPoint(
                month=_format_month(proj_month),
                total_debt=max(total_debt, Decimal("0")).quantize(Decimal("0.01")),
                principal_paid=month_principal.quantize(Decimal("0.01")),
                interest_paid=month_interest.quantize(Decimal("0.01")),
                kind="projected",
            )
        )

    return points


async def _convert_at_today(
    db: AsyncSession,
    amount: Decimal,
    *,
    from_currency: str,
    target_currency: str,
) -> Decimal | None:
    """Convierte `amount` al target con la tasa de hoy o `None` si no
    hay tasa disponible."""
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


async def compute_debt_history(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    months_back: int = 12,
    months_ahead: int = 12,
    target_currency: str | None = None,
) -> DebtHistoryResponse:
    """Calcula la serie temporal completa: histórico + proyección.

    Sin `target_currency`: el flujo histórico filtra por la moneda
    nativa del usuario y la proyección usa los saldos nativos.

    Con `target_currency` (PHASE-30.6): se incluyen liabilities de
    cualquier divisa; el histórico convierte per-tx, y la proyección
    convierte cada cuota / saldo proyectado con la tasa de hoy. Los
    liabilities sin tasa quedan excluidos.
    """
    # 1. Listar cuentas activas → determinar reference_currency + filtrar
    #    liabilities relevantes.
    query = select(Account).where(Account.user_id == user_id).where(Account.is_archived.is_(False))
    accounts = list((await db.execute(query)).scalars().all())
    if not accounts:
        return DebtHistoryResponse(
            items=[],
            reference_currency=(target_currency or DEFAULT_REFERENCE_CURRENCY).upper(),
            months_historical=0,
            months_projected=0,
        )

    accounts_sorted = sorted(accounts, key=lambda a: (a.display_order, a.name))
    native_currency = accounts_sorted[0].currency
    effective_currency = (target_currency or native_currency).upper()

    if target_currency is None:
        liabilities = [
            a
            for a in accounts
            if a.nature == AccountNature.LIABILITY and a.currency == native_currency
        ]
    else:
        liabilities = [a for a in accounts if a.nature == AccountNature.LIABILITY]

    if not liabilities:
        return DebtHistoryResponse(
            items=[],
            reference_currency=effective_currency,
            months_historical=0,
            months_projected=0,
        )

    # 2. Saldos actuales por cuenta (nativos) + opening pre-convertida
    #    en modo target para que `_compute_historical_points` no tenga
    #    que tocar conversiones de saldo iniciales.
    from app.modules.personal_finance.accounts.repository import get_balances_for_user

    movements = await get_balances_for_user(db, user_id)
    current_balances: dict[uuid.UUID, Decimal] = {}
    sum_opening_target = Decimal("0") if target_currency else None
    for liab in liabilities:
        native_balance = liab.opening_balance + movements.get(liab.id, Decimal("0"))
        if target_currency is None or liab.currency.upper() == effective_currency:
            current_balances[liab.id] = native_balance
            if sum_opening_target is not None:
                sum_opening_target += liab.opening_balance
            continue
        # Convertir saldo actual y opening con la tasa de hoy.
        converted_balance = await _convert_at_today(
            db,
            native_balance,
            from_currency=liab.currency,
            target_currency=effective_currency,
        )
        converted_opening = await _convert_at_today(
            db,
            liab.opening_balance,
            from_currency=liab.currency,
            target_currency=effective_currency,
        )
        if converted_balance is None or converted_opening is None:
            # Sin tasa → liability excluida del agregado proyectado.
            continue
        current_balances[liab.id] = converted_balance
        if sum_opening_target is not None:
            sum_opening_target += converted_opening

    # 3. Histórico + proyección.
    historical = await _compute_historical_points(
        db,
        user_id,
        liabilities,
        native_currency,
        months_back,
        target_currency=target_currency,
        sum_opening_target=sum_opening_target,
    )

    # La proyección usa los cuadros teóricos. Para modo target, las
    # cuotas también necesitan conversión a la tasa de hoy.
    projected = await _project_points(
        db,
        liabilities,
        current_balances,
        months_ahead,
        target_currency=target_currency,
        effective_currency=effective_currency,
    )

    return DebtHistoryResponse(
        items=historical + projected,
        reference_currency=effective_currency,
        months_historical=len(historical),
        months_projected=len(projected),
    )
