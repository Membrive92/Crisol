"""KPIs de salud financiera basados en deudas (PHASE-22.4).

Calcula los indicadores que la UI muestra en la card "Salud
financiera" del dashboard. Sólo lee — no escribe nada en BD.

Definiciones (alineadas con literatura estándar de personal finance):

- **DTI (debt-to-income)**: `Σ cuotas mensuales / ingreso mensual medio`.
- **debt_to_assets**: `Σ liabilities / Σ assets`.
- **interest_paid_ytd**: suma de expenses en las categorías "Intereses
  hipoteca / préstamo / tarjeta" desde 1 de enero hasta hoy.
- **weighted_apr**: APR medio ponderado por saldo entre liabilities
  que tienen `apr` declarado (las tarjetas con APR conocido cuentan).
- **time_to_payoff**: proyección lineal. Mira el principal pagado
  los últimos 3 meses → ratio mensual de amortización → divide
  saldo total liabilities entre ese ratio.

Convenciones:

- Sólo cuentas no archivadas entran en los cómputos.
- `monthly_income_avg`: media de las últimas 6 ventanas mensuales
  cerradas, excluyendo transferencias internas.
- Si no hay datos suficientes para algún KPI, devuelve `None` /
  `Decimal('0')` según contrato.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.amortization import compute_monthly_payment
from app.modules.personal_finance.accounts.models import Account, AccountNature, AccountType
from app.modules.personal_finance.accounts.schemas import DebtHealthKpis
from app.modules.personal_finance.categories.models import Category, CategoryKind
from app.modules.personal_finance.transactions.models import Transaction

DEFAULT_REFERENCE_CURRENCY = "EUR"

# Nombres exactos de las categorías que cuentan como intereses (creadas
# por el seed PHASE-22). Si el usuario renombra o borra una, no afecta
# al cómputo de las que sí mantengan el nombre original.
INTEREST_CATEGORY_NAMES: frozenset[str] = frozenset(
    {
        "Intereses hipoteca",
        "Intereses préstamo",
        "Intereses tarjeta",
    }
)


def _today_utc() -> date:
    return datetime.now(UTC).date()


def _start_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def _classify_dti(ratio: float | None) -> str:
    if ratio is None:
        return "unknown"
    if ratio < 0.36:
        return "healthy"
    if ratio <= 0.43:
        return "caution"
    return "stressed"


async def _monthly_income_avg(
    db: AsyncSession, user_id: uuid.UUID, currency: str, *, months: int = 6
) -> Decimal:
    """Media de ingresos mensuales en los últimos `months` meses
    completos. Excluye papelera y transferencias internas.
    """
    today = _today_utc()
    # Último día del mes pasado (no incluimos el mes en curso porque
    # estaría incompleto y bajaría la media).
    last_full_month_end = _start_of_month(today) - timedelta(days=1)
    window_end = datetime(
        last_full_month_end.year,
        last_full_month_end.month,
        last_full_month_end.day,
        23,
        59,
        59,
        tzinfo=UTC,
    )
    # Inicio: primer día del mes `months` atrás.
    window_start_month = last_full_month_end
    for _ in range(months - 1):
        window_start_month = _start_of_month(window_start_month) - timedelta(days=1)
    window_start = datetime(
        window_start_month.year,
        window_start_month.month,
        1,
        0,
        0,
        0,
        tzinfo=UTC,
    )

    query = (
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_(None))
        .where(Transaction.currency == currency)
        .where(Category.kind == CategoryKind.INCOME)
        .where(Transaction.occurred_at >= window_start)
        .where(Transaction.occurred_at <= window_end)
    )
    total = Decimal((await db.execute(query)).scalar_one())
    if total <= 0:
        return Decimal("0")
    return (total / Decimal(months)).quantize(Decimal("0.01"))


async def _interest_paid_ytd(
    db: AsyncSession, user_id: uuid.UUID, currency: str
) -> Decimal:
    """Suma de expenses en categorías de intereses desde 1-enero hasta hoy."""
    today = _today_utc()
    year_start = datetime(today.year, 1, 1, tzinfo=UTC)
    query = (
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.currency == currency)
        .where(Category.kind == CategoryKind.EXPENSE)
        .where(Category.name.in_(INTEREST_CATEGORY_NAMES))
        .where(Transaction.occurred_at >= year_start)
    )
    return Decimal((await db.execute(query)).scalar_one())


async def _principal_paid_last_n_months(
    db: AsyncSession,
    user_id: uuid.UUID,
    liability_ids: list[uuid.UUID],
    currency: str,
    months: int = 3,
) -> Decimal:
    """Suma del principal amortizado en los últimos `months` meses
    completos a las liabilities del usuario.

    "Principal amortizado" = txs entrantes (income) en cuentas
    liability, vía transferencias internas confirmadas
    (`transfer_pair_id IS NOT NULL`). La tx tiene `amount` positivo y
    `category.kind=income`, pero como es transfer no debería tener
    categoría asignada — usamos `transfer_pair_id` como filtro
    principal.
    """
    if not liability_ids:
        return Decimal("0")
    today = _today_utc()
    last_full_month_end = _start_of_month(today) - timedelta(days=1)
    window_start_month = last_full_month_end
    for _ in range(months - 1):
        window_start_month = _start_of_month(window_start_month) - timedelta(days=1)
    window_start = datetime(
        window_start_month.year,
        window_start_month.month,
        1,
        0,
        0,
        0,
        tzinfo=UTC,
    )
    window_end = datetime(
        last_full_month_end.year,
        last_full_month_end.month,
        last_full_month_end.day,
        23,
        59,
        59,
        tzinfo=UTC,
    )

    query = (
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.user_id == user_id)
        .where(Transaction.account_id.in_(liability_ids))
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_not(None))
        .where(Transaction.currency == currency)
        .where(Transaction.occurred_at >= window_start)
        .where(Transaction.occurred_at <= window_end)
    )
    return Decimal((await db.execute(query)).scalar_one())


async def compute_debt_health(
    db: AsyncSession, user_id: uuid.UUID
) -> DebtHealthKpis:
    """Computa todos los KPIs de salud financiera para el usuario."""
    # 1. Cuentas activas y agregados de saldo.
    query = (
        select(Account)
        .where(Account.user_id == user_id)
        .where(Account.is_archived.is_(False))
    )
    accounts = list((await db.execute(query)).scalars().all())

    if not accounts:
        return DebtHealthKpis(
            total_liabilities=Decimal("0"),
            total_assets=Decimal("0"),
            net_worth=Decimal("0"),
            debt_to_assets_ratio=None,
            dti_ratio=None,
            dti_status="unknown",
            monthly_debt_payment=Decimal("0"),
            monthly_income_avg=Decimal("0"),
            interest_paid_ytd=Decimal("0"),
            weighted_apr=None,
            time_to_payoff_months=None,
            reference_currency=DEFAULT_REFERENCE_CURRENCY,
        )

    # Reference currency = primera no archivada por display_order.
    accounts_sorted = sorted(accounts, key=lambda a: (a.display_order, a.name))
    reference_currency = accounts_sorted[0].currency

    # 2. Saldos por cuenta. Reusamos el repository sólo para movimientos.
    from app.modules.personal_finance.accounts.repository import get_balances_for_user

    movements = await get_balances_for_user(db, user_id)
    total_assets = Decimal("0")
    total_liabilities = Decimal("0")
    liabilities: list[Account] = []
    liability_balances: dict[uuid.UUID, Decimal] = {}
    for account in accounts:
        if account.currency != reference_currency:
            # Para PHASE-22.4 mínimo viable, ignoramos cuentas en otras
            # divisas. Mismo enfoque que `mixed_currencies` en /balances.
            continue
        current_balance = account.opening_balance + movements.get(
            account.id, Decimal("0")
        )
        if account.nature == AccountNature.LIABILITY:
            total_liabilities += current_balance
            liabilities.append(account)
            liability_balances[account.id] = current_balance
        else:
            total_assets += current_balance

    net_worth = total_assets - total_liabilities
    debt_to_assets = (
        float(total_liabilities / total_assets) if total_assets > 0 else None
    )

    # 3. Cuota mensual estimada — suma cuotas francesas de loans/mortgages
    #    + estimación de tarjetas.
    monthly_payment_total = Decimal("0")
    weighted_apr_num = Decimal("0")
    weighted_apr_den = Decimal("0")
    for liab in liabilities:
        balance = liability_balances.get(liab.id, Decimal("0"))
        if balance <= 0:
            continue
        if liab.type in {AccountType.LOAN, AccountType.MORTGAGE}:
            if liab.apr is not None and liab.term_months is not None:
                # Usar el principal inicial declarado para la cuota
                # (no el saldo actual; la cuota francesa es constante).
                monthly_payment_total += compute_monthly_payment(
                    liab.opening_balance, liab.apr, liab.term_months
                )
                weighted_apr_num += liab.apr * balance
                weighted_apr_den += balance
        elif liab.type == AccountType.CREDIT_CARD:
            # Tarjeta: estimar la cuota mensual como `saldo / 12` si
            # tiene APR (financiación a un año típica), o el mínimo
            # común (3% del saldo). Si tiene APR declarado, también
            # contribuye al weighted_apr.
            if liab.apr is not None:
                weighted_apr_num += liab.apr * balance
                weighted_apr_den += balance
                # Cuota teórica de 12 meses con apr.
                monthly_payment_total += compute_monthly_payment(
                    balance, liab.apr, 12
                )
            else:
                # Pago mínimo estimado: 3% del saldo.
                monthly_payment_total += (balance * Decimal("0.03")).quantize(
                    Decimal("0.01")
                )

    weighted_apr = (
        float(weighted_apr_num / weighted_apr_den)
        if weighted_apr_den > 0
        else None
    )

    # 4. Income medio + DTI.
    monthly_income = await _monthly_income_avg(
        db, user_id, reference_currency, months=6
    )
    dti_ratio = (
        float(monthly_payment_total / monthly_income)
        if monthly_income > 0 and monthly_payment_total > 0
        else None
    )
    dti_status = _classify_dti(dti_ratio)

    # 5. Intereses YTD.
    interest_ytd = await _interest_paid_ytd(db, user_id, reference_currency)

    # 6. Time-to-payoff: proyección lineal con principal pagado en los
    #    últimos 3 meses completos.
    time_to_payoff: int | None = None
    if liabilities and total_liabilities > 0:
        principal_3m = await _principal_paid_last_n_months(
            db,
            user_id,
            [liab.id for liab in liabilities],
            reference_currency,
            months=3,
        )
        if principal_3m > 0:
            monthly_principal = principal_3m / Decimal(3)
            months_left = int((total_liabilities / monthly_principal).to_integral_value())
            time_to_payoff = months_left

    return DebtHealthKpis(
        total_liabilities=total_liabilities,
        total_assets=total_assets,
        net_worth=net_worth,
        debt_to_assets_ratio=debt_to_assets,
        dti_ratio=dti_ratio,
        dti_status=dti_status,
        monthly_debt_payment=monthly_payment_total.quantize(Decimal("0.01")),
        monthly_income_avg=monthly_income,
        interest_paid_ytd=interest_ytd,
        weighted_apr=weighted_apr,
        time_to_payoff_months=time_to_payoff,
        reference_currency=reference_currency,
    )


