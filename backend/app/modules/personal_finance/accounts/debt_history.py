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
- `interest_paid` mensual = suma de expenses en
  `INTEREST_CATEGORY_NAMES` ese mes.
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
    build_schedule,
    compute_monthly_payment,
)
from app.modules.personal_finance.accounts.debt_health import (
    DEFAULT_REFERENCE_CURRENCY,
    INTEREST_CATEGORY_NAMES,
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
from app.modules.personal_finance.categories.models import Category, CategoryKind
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
) -> list[DebtHistoryPoint]:
    """Histórico mes a mes para los últimos `months_back` meses cerrados.

    No incluye el mes en curso (sería incompleto). Si el usuario no
    tiene liabilities, devuelve lista vacía.
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
    sum_opening = sum((liab.opening_balance for liab in liabilities), Decimal("0"))

    # Inversión de signo en SQL idéntica a get_balances_for_user, pero
    # acumulada hasta `month_end`. Para llamadas múltiples, una sola
    # query agrupada por cierre de mes sería más eficiente; el patrón
    # mensual de iteración es lo bastante barato para 12-24 meses.
    signed_amount = case(
        (Category.kind == CategoryKind.EXPENSE, Transaction.amount),
        (Category.kind == CategoryKind.INCOME, -Transaction.amount),
        else_=Transaction.amount,
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
            .where(Transaction.currency == reference_currency)
            .where(Transaction.occurred_at <= month_end)
        )
        cumulative = Decimal((await db.execute(cumulative_q)).scalar_one())
        total_debt = sum_opening + cumulative

        # Principal amortizado durante el mes (ingresos transferencia
        # llegando a liabilities).
        principal_q = (
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.user_id == user_id)
            .where(Transaction.account_id.in_(liability_ids))
            .where(Transaction.deleted_at.is_(None))
            .where(Transaction.transfer_pair_id.is_not(None))
            .where(Transaction.currency == reference_currency)
            .where(Transaction.occurred_at >= month_start)
            .where(Transaction.occurred_at <= month_end)
        )
        principal_paid = Decimal((await db.execute(principal_q)).scalar_one())

        # Intereses pagados durante el mes.
        interest_q = (
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .select_from(Transaction)
            .join(Category, Category.id == Transaction.category_id)
            .where(Transaction.user_id == user_id)
            .where(Transaction.deleted_at.is_(None))
            .where(Transaction.currency == reference_currency)
            .where(Category.kind == CategoryKind.EXPENSE)
            .where(Category.name.in_(INTEREST_CATEGORY_NAMES))
            .where(Transaction.occurred_at >= month_start)
            .where(Transaction.occurred_at <= month_end)
        )
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


def _project_points(
    liabilities: list[Account],
    current_balances: dict[uuid.UUID, Decimal],
    months_ahead: int,
) -> list[DebtHistoryPoint]:
    """Proyecta la evolución de deuda hacia adelante.

    Mantiene saldo por cuenta independiente: a las loans/mortgages
    con cuadro francés les aplica la fila correspondiente al mes
    proyectado; a las tarjetas les amortiza la cuota teórica (cuota
    francesa a 12 meses con APR, o 3% del saldo si no tiene APR).
    Una cuenta deja de contribuir cuando su saldo llega a 0.
    """
    if not liabilities or months_ahead <= 0:
        return []

    today = _today_utc()
    current_month = _start_of_month(today)

    # Schedules pre-calculados para loans/mortgages.
    schedules: dict[uuid.UUID, list] = {}
    for liab in liabilities:
        if liab.type in {AccountType.LOAN, AccountType.MORTGAGE}:
            if liab.apr is not None and liab.term_months is not None and liab.start_date is not None and liab.opening_balance > 0:
                schedules[liab.id] = build_schedule(
                    principal=liab.opening_balance,
                    apr=liab.apr,
                    term_months=liab.term_months,
                    start_date=liab.start_date,
                )

    # Estado mutable: saldo proyectado por cuenta.
    balances: dict[uuid.UUID, Decimal] = {
        liab.id: current_balances.get(liab.id, Decimal("0"))
        for liab in liabilities
    }

    points: list[DebtHistoryPoint] = []
    for offset in range(1, months_ahead + 1):
        proj_month = _add_month(current_month, offset)
        month_principal = Decimal("0")
        month_interest = Decimal("0")

        for liab in liabilities:
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
                    pay_principal = min(schedule_row.principal, balance)
                    month_principal += pay_principal
                    month_interest += schedule_row.interest
                    balances[liab.id] = balance - pay_principal
            elif liab.type == AccountType.CREDIT_CARD:
                if liab.apr is not None:
                    cuota = compute_monthly_payment(balance, liab.apr, 12)
                    # Mes a mes la tarjeta: interés = saldo * apr/12.
                    interest_m = (balance * liab.apr / Decimal(12)).quantize(
                        Decimal("0.01")
                    )
                    pay_principal = min(cuota - interest_m, balance)
                    if pay_principal < 0:
                        pay_principal = Decimal("0")
                    month_principal += pay_principal
                    month_interest += interest_m
                    balances[liab.id] = balance - pay_principal
                else:
                    pay_principal = min(
                        (balance * Decimal("0.03")).quantize(Decimal("0.01")),
                        balance,
                    )
                    month_principal += pay_principal
                    balances[liab.id] = balance - pay_principal

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


async def compute_debt_history(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    months_back: int = 12,
    months_ahead: int = 12,
) -> DebtHistoryResponse:
    """Calcula la serie temporal completa: histórico + proyección.

    Si el usuario no tiene liabilities en la `reference_currency`,
    devuelve respuesta vacía con la divisa por defecto.
    """
    # 1. Listar cuentas activas → determinar reference_currency + filtrar
    #    liabilities en esa moneda.
    query = (
        select(Account)
        .where(Account.user_id == user_id)
        .where(Account.is_archived.is_(False))
    )
    accounts = list((await db.execute(query)).scalars().all())
    if not accounts:
        return DebtHistoryResponse(
            items=[],
            reference_currency=DEFAULT_REFERENCE_CURRENCY,
            months_historical=0,
            months_projected=0,
        )

    accounts_sorted = sorted(accounts, key=lambda a: (a.display_order, a.name))
    reference_currency = accounts_sorted[0].currency
    liabilities = [
        a
        for a in accounts
        if a.nature == AccountNature.LIABILITY and a.currency == reference_currency
    ]

    if not liabilities:
        return DebtHistoryResponse(
            items=[],
            reference_currency=reference_currency,
            months_historical=0,
            months_projected=0,
        )

    # 2. Saldos actuales por cuenta (reutiliza el repository).
    from app.modules.personal_finance.accounts.repository import get_balances_for_user

    movements = await get_balances_for_user(db, user_id)
    current_balances: dict[uuid.UUID, Decimal] = {}
    for liab in liabilities:
        current_balances[liab.id] = liab.opening_balance + movements.get(
            liab.id, Decimal("0")
        )

    # 3. Histórico + proyección.
    historical = await _compute_historical_points(
        db, user_id, liabilities, reference_currency, months_back
    )
    projected = _project_points(liabilities, current_balances, months_ahead)

    return DebtHistoryResponse(
        items=historical + projected,
        reference_currency=reference_currency,
        months_historical=len(historical),
        months_projected=len(projected),
    )
