"""KPIs de salud financiera basados en deudas (PHASE-22.4 + PHASE-30.2).

Calcula los indicadores que la UI muestra en la card "Salud
financiera" del dashboard. Sólo lee — no escribe nada en BD.

Definiciones (alineadas con literatura estándar de personal finance):

- **Tasa de esfuerzo** (PHASE-30.2): `Σ cuotas mensuales / ingreso
  mensual medio`. Banco de España recomienda < 30% (saludable), 30-35%
  precaución, > 35% sobreendeudamiento. El campo de respuesta sigue
  llamándose `dti_ratio` / `dti_status` por compatibilidad con el
  frontend; las **bandas** son las nuevas. PHASE-30.x renombra la
  etiqueta en UI a "Tasa de esfuerzo".
- **debt_to_assets**: `Σ liabilities / Σ assets`.
- **interest_paid_ytd**: suma de expenses en categorías con
  `role=DEBT_INTEREST` desde 1 de enero hasta hoy.
- **weighted_apr**: APR medio ponderado por saldo entre liabilities
  que tienen `apr` declarado (las tarjetas con APR conocido cuentan).
- **time_to_payoff** (PHASE-30.2): cuando la liability tiene cuadro de
  amortización (loan/mortgage con apr/term/start_date), usamos
  directamente las cuotas restantes del schedule en lugar de
  extrapolar el ritmo de los últimos meses. La extrapolación lineal
  estaba dando resultados disparatadamente cortos en hipotecas
  francesas tempranas (los primeros meses amortizan poco principal y
  el modelo lineal asumía que ese ritmo iba a crecer al mismo nivel).
  Fallback a la proyección lineal sólo cuando no hay schedule (caso
  tarjetas sin plan o liabilities sin apr declarado).

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

from app.modules.personal_finance.accounts.amortization import (
    build_schedule,
    compute_monthly_payment,
)
from app.modules.personal_finance.accounts.models import Account, AccountNature, AccountType
from app.modules.personal_finance.accounts.schemas import DebtHealthKpis
from app.modules.personal_finance.categories.models import Category, CategoryKind, CategoryRole
from app.modules.personal_finance.dashboard.conversion import (
    converted_amount_expr,
)
from app.modules.personal_finance.transactions.models import Transaction

DEFAULT_REFERENCE_CURRENCY = "EUR"

# PHASE-30.2 — Bandas de "tasa de esfuerzo" (Banco de España).
# Sustituyen a 36% / 43% (DTI estadounidense sobre ingresos brutos)
# por 30% / 35% sobre ingresos netos, que es lo que el supervisor
# español y la literatura europea consideran sostenible.
EFFORT_BAND_HEALTHY = Decimal("0.30")
EFFORT_BAND_CAUTION = Decimal("0.35")


def _today_utc() -> date:
    return datetime.now(UTC).date()


def _start_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def classify_effort(ratio: float | None) -> str:
    """Clasifica un ratio de tasa de esfuerzo en una banda BdE.

    - `healthy` cuando < 30% (recomendación del Banco de España).
    - `caution` cuando 30% ≤ ratio ≤ 35%.
    - `stressed` cuando > 35% (sobreendeudamiento según el supervisor).
    - `unknown` cuando el ratio no se puede calcular (sin ingresos
      declarados o sin liabilities).
    """
    if ratio is None:
        return "unknown"
    if ratio < float(EFFORT_BAND_HEALTHY):
        return "healthy"
    if ratio <= float(EFFORT_BAND_CAUTION):
        return "caution"
    return "stressed"


async def monthly_income_avg(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    months: int = 6,
    target_currency: str | None = None,
) -> Decimal:
    """Media de ingresos mensuales en los últimos `months` meses
    completos. Excluye papelera y transferencias internas.

    Compartido entre `compute_debt_health` (Capa 2) y
    `debt/service.compute_category_summary` (Capa 1) para que ambos
    expongan la misma definición de "ingreso medio".

    PHASE-30.6 — cuando `target_currency` se pasa, convierte cada tx
    a esa moneda con la tasa del día (`converted_amount_expr`) y NO
    filtra por `Transaction.currency`. Ingresos en monedas sin tasa
    quedan excluidos.
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

    amount_expr = (
        converted_amount_expr(target_currency)
        if target_currency is not None
        else Transaction.amount
    )
    query = (
        select(func.coalesce(func.sum(amount_expr), 0))
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_(None))
        .where(Category.kind == CategoryKind.INCOME)
        .where(Transaction.occurred_at >= window_start)
        .where(Transaction.occurred_at <= window_end)
    )
    if target_currency is None:
        query = query.where(Transaction.currency == currency)
    total = Decimal((await db.execute(query)).scalar_one())
    if total <= 0:
        return Decimal("0")
    return (total / Decimal(months)).quantize(Decimal("0.01"))


async def _interest_paid_ytd(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    target_currency: str | None = None,
) -> Decimal:
    """Suma de expenses en categorías de intereses desde 1-enero hasta hoy.

    PHASE-30.6 — Mismo modo dual que `monthly_income_avg`."""
    today = _today_utc()
    year_start = datetime(today.year, 1, 1, tzinfo=UTC)
    amount_expr = (
        converted_amount_expr(target_currency)
        if target_currency is not None
        else Transaction.amount
    )
    query = (
        select(func.coalesce(func.sum(amount_expr), 0))
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Category.kind == CategoryKind.EXPENSE)
        .where(Category.role == CategoryRole.DEBT_INTEREST)
        .where(Transaction.occurred_at >= year_start)
    )
    if target_currency is None:
        query = query.where(Transaction.currency == currency)
    return Decimal((await db.execute(query)).scalar_one())


def _months_remaining_from_schedule(
    liab: Account, balance: Decimal, today: date
) -> int | None:
    """Cuenta cuántas filas del cuadro francés quedan por pagar
    para una liability concreta (PHASE-30.2).

    Una fila se considera pendiente si su `due_date >= primer día del
    mes actual` (el mes en curso aún cuenta como debido). Devuelve
    `None` cuando la cuenta no tiene los datos para construir un
    schedule — el caller hace fallback a la proyección lineal.
    """
    if liab.apr is None or liab.term_months is None or liab.start_date is None:
        return None
    if liab.opening_balance <= 0:
        return None
    schedule = build_schedule(
        principal=liab.opening_balance,
        apr=liab.apr,
        term_months=liab.term_months,
        start_date=liab.start_date,
    )
    if not schedule:
        return None
    month_floor = _start_of_month(today)
    remaining = sum(1 for row in schedule if row.due_date >= month_floor)
    # Cuando el saldo actual es 0 (deuda saldada anticipadamente),
    # tratamos como 0 meses restantes aunque el schedule original
    # cubriera más.
    if balance <= 0:
        return 0
    return remaining


async def _time_to_payoff_months(
    db: AsyncSession,
    user_id: uuid.UUID,
    liabilities: list[Account],
    liability_balances: dict[uuid.UUID, Decimal],
    reference_currency: str,
    total_liabilities: Decimal,
    *,
    target_currency: str | None = None,
) -> int | None:
    """PHASE-30.2 — combina schedule + fallback lineal por liability.

    Para liabilities con cuadro francés disponible usamos las cuotas
    restantes directamente (mucho más fiable en hipotecas tempranas);
    para las que no lo tienen (tarjetas o préstamos sin apr declarado)
    fallback a la proyección lineal compartida.

    El tiempo total a payoff es el **máximo** de los individuales:
    el usuario sigue endeudado hasta que la última liability se salde,
    no hasta la media. Devuelve `None` si no se puede estimar nada.
    """
    if not liabilities or total_liabilities <= 0:
        return None

    today = _today_utc()
    schedule_estimates: list[int] = []
    no_schedule_ids: list[uuid.UUID] = []
    no_schedule_balance = Decimal("0")
    for liab in liabilities:
        balance = liability_balances.get(liab.id, Decimal("0"))
        if balance <= 0:
            continue
        est = _months_remaining_from_schedule(liab, balance, today)
        if est is not None:
            schedule_estimates.append(est)
        else:
            no_schedule_ids.append(liab.id)
            no_schedule_balance += balance

    linear_estimate: int | None = None
    if no_schedule_ids and no_schedule_balance > 0:
        principal_3m = await _principal_paid_last_n_months(
            db,
            user_id,
            no_schedule_ids,
            reference_currency,
            months=3,
            target_currency=target_currency,
        )
        if principal_3m > 0:
            monthly_principal = principal_3m / Decimal(3)
            linear_estimate = int(
                (no_schedule_balance / monthly_principal).to_integral_value()
            )

    candidates: list[int] = list(schedule_estimates)
    if linear_estimate is not None:
        candidates.append(linear_estimate)

    if not candidates:
        return None
    return max(candidates)


async def _principal_paid_last_n_months(
    db: AsyncSession,
    user_id: uuid.UUID,
    liability_ids: list[uuid.UUID],
    currency: str,
    months: int = 3,
    *,
    target_currency: str | None = None,
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

    amount_expr = (
        converted_amount_expr(target_currency)
        if target_currency is not None
        else Transaction.amount
    )
    query = (
        select(func.coalesce(func.sum(amount_expr), 0))
        .where(Transaction.user_id == user_id)
        .where(Transaction.account_id.in_(liability_ids))
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_not(None))
        .where(Transaction.occurred_at >= window_start)
        .where(Transaction.occurred_at <= window_end)
    )
    if target_currency is None:
        query = query.where(Transaction.currency == currency)
    return Decimal((await db.execute(query)).scalar_one())


async def _convert_at_today(
    db: AsyncSession,
    amount: Decimal,
    *,
    from_currency: str,
    target_currency: str,
) -> Decimal | None:
    """Helper local: convierte `amount` con la tasa de hoy o
    devuelve `None` si no hay tasa. Se replica aquí (y en
    `debt/service.py`) en lugar de importarlo para evitar
    dependencias circulares — la lógica vive en
    `currency.service.convert`."""
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


async def compute_debt_health(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    target_currency: str | None = None,
) -> DebtHealthKpis:
    """Computa todos los KPIs de salud financiera para el usuario.

    PHASE-30.6 — Cuando se pasa `target_currency`, todos los importes
    devueltos se expresan en esa moneda:

    - Saldos de cuentas: convertidos con la tasa **de hoy** (snapshot
      simple — el patrón "saldo en otra divisa" del producto).
    - Income, intereses y principal amortizado: convertidos per-tx
      vía `converted_amount_expr` (tasa del día de cada tx).
    - Cuotas teóricas de liabilities: convertidas con la tasa de hoy.

    Cuando falta tasa para convertir un saldo de cuenta, esa cuenta
    queda excluida del agregado (mismo principio que `mixed_currencies`
    en `/balances`).
    """
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
            reference_currency=(target_currency or DEFAULT_REFERENCE_CURRENCY).upper(),
        )

    # Reference currency = primera no archivada por display_order
    # (o target_currency si se ha pasado).
    accounts_sorted = sorted(accounts, key=lambda a: (a.display_order, a.name))
    native_currency = accounts_sorted[0].currency
    effective_currency = (target_currency or native_currency).upper()

    # 2. Saldos por cuenta. Reusamos el repository sólo para movimientos.
    from app.modules.personal_finance.accounts.repository import get_balances_for_user

    movements = await get_balances_for_user(db, user_id)
    total_assets = Decimal("0")
    total_liabilities = Decimal("0")
    liabilities: list[Account] = []
    liability_balances: dict[uuid.UUID, Decimal] = {}
    for account in accounts:
        # Saldo nativo de la cuenta (siempre en su propia divisa, igual
        # que en /balances).
        native_balance = account.opening_balance + movements.get(
            account.id, Decimal("0")
        )

        # Decidir el balance "agregable" según el modo:
        # - Sin target: como antes, sólo cuentas en reference_currency.
        # - Con target: convertir todas al target con la tasa de hoy.
        if target_currency is None:
            if account.currency != native_currency:
                continue
            aggregable_balance = native_balance
        else:
            if account.currency.upper() == effective_currency:
                aggregable_balance = native_balance
            else:
                converted = await _convert_at_today(
                    db,
                    native_balance,
                    from_currency=account.currency,
                    target_currency=effective_currency,
                )
                if converted is None:
                    # Sin tasa → no contamos la cuenta (mismo contrato
                    # que mixed_currencies).
                    continue
                aggregable_balance = converted

        if account.nature == AccountNature.LIABILITY:
            total_liabilities += aggregable_balance
            liabilities.append(account)
            liability_balances[account.id] = aggregable_balance
        else:
            total_assets += aggregable_balance

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
        # Cuota nativa (en la divisa de la liability). La convertimos al
        # target una vez calculada.
        native_cuota = Decimal("0")
        if liab.type in {AccountType.LOAN, AccountType.MORTGAGE}:
            if liab.apr is not None and liab.term_months is not None:
                # Usar el principal inicial declarado para la cuota
                # (no el saldo actual; la cuota francesa es constante).
                native_cuota = compute_monthly_payment(
                    liab.opening_balance, liab.apr, liab.term_months
                )
                # weighted_apr opera sobre el balance ya en effective.
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
                # Cuota teórica de 12 meses con apr — sobre el saldo
                # nativo, no el convertido, para que sea fiel a la
                # liability real.
                native_card_balance = liab.opening_balance + movements.get(
                    liab.id, Decimal("0")
                )
                native_cuota = compute_monthly_payment(
                    native_card_balance, liab.apr, 12
                )
            else:
                native_card_balance = liab.opening_balance + movements.get(
                    liab.id, Decimal("0")
                )
                native_cuota = (native_card_balance * Decimal("0.03")).quantize(
                    Decimal("0.01")
                )

        if native_cuota <= 0:
            continue
        if target_currency is None or liab.currency.upper() == effective_currency:
            monthly_payment_total += native_cuota
        else:
            converted_cuota = await _convert_at_today(
                db,
                native_cuota,
                from_currency=liab.currency,
                target_currency=effective_currency,
            )
            if converted_cuota is not None:
                monthly_payment_total += converted_cuota

    weighted_apr = (
        float(weighted_apr_num / weighted_apr_den)
        if weighted_apr_den > 0
        else None
    )

    # 4. Income medio + DTI.
    monthly_income = await monthly_income_avg(
        db,
        user_id,
        native_currency,
        months=6,
        target_currency=target_currency,
    )
    dti_ratio = (
        float(monthly_payment_total / monthly_income)
        if monthly_income > 0 and monthly_payment_total > 0
        else None
    )
    dti_status = classify_effort(dti_ratio)

    # 5. Intereses YTD.
    interest_ytd = await _interest_paid_ytd(
        db, user_id, native_currency, target_currency=target_currency
    )

    # 6. Time-to-payoff (PHASE-30.2): prefer schedule over linear projection.
    time_to_payoff = await _time_to_payoff_months(
        db,
        user_id,
        liabilities,
        liability_balances,
        native_currency,
        total_liabilities,
        target_currency=target_currency,
    )

    return DebtHealthKpis(
        total_liabilities=total_liabilities.quantize(Decimal("0.01")),
        total_assets=total_assets.quantize(Decimal("0.01")),
        net_worth=net_worth.quantize(Decimal("0.01")),
        debt_to_assets_ratio=debt_to_assets,
        dti_ratio=dti_ratio,
        dti_status=dti_status,
        monthly_debt_payment=monthly_payment_total.quantize(Decimal("0.01")),
        monthly_income_avg=monthly_income,
        interest_paid_ytd=interest_ytd,
        weighted_apr=weighted_apr,
        time_to_payoff_months=time_to_payoff,
        reference_currency=effective_currency,
    )


