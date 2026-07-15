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
from app.modules.personal_finance.accounts.installments_model import (
    LiabilityInstallment,
)
from app.modules.personal_finance.accounts.installments_repository import (
    interest_paid_in_window,
    interest_total,
    schedule_outstanding,
)
from app.modules.personal_finance.accounts.models import (
    UNVALUED_ACCOUNT_TYPES,
    Account,
    AccountNature,
    AccountType,
)
from app.modules.personal_finance.accounts.repository import is_inflow
from app.modules.personal_finance.accounts.schemas import DebtHealthKpis, DebtTypeSlice
from app.modules.personal_finance.categories.models import Category, CategoryKind, CategoryRole
from app.modules.personal_finance.dashboard.conversion import (
    converted_amount_expr,
)
from app.modules.personal_finance.dashboard.repository import (
    _is_income,
    _is_internal_transfer,
)
from app.modules.personal_finance.transactions.models import Transaction

DEFAULT_REFERENCE_CURRENCY = "EUR"

# PHASE-30.2 — Bandas de "tasa de esfuerzo" (Banco de España).
# Sustituyen a 36% / 43% (DTI estadounidense sobre ingresos brutos)
# por 30% / 35% sobre ingresos netos, que es lo que el supervisor
# español y la literatura europea consideran sostenible.
EFFORT_BAND_HEALTHY = Decimal("0.30")
EFFORT_BAND_CAUTION = Decimal("0.35")

# AUDIT-2026-06 (fix #5) — Tope del payoff lineal. En tarjetas revolving
# el ritmo de amortización de los últimos meses puede ser ínfimo (sólo
# se paga el mínimo), y la extrapolación lineal `saldo / ritmo` dispara
# horizontes absurdos (cientos de años). Por encima de este tope tratamos
# la estimación como "no acotable" (None) en vez de devolver un número
# sin sentido. 600 meses = 50 años: cualquier deuda que tarde más que eso
# en saldarse al ritmo actual es, a efectos prácticos, perpetua.
LINEAR_PAYOFF_CAP_MONTHS = 600


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

    AUDIT-2026-06 (fix #6) — El divisor es el nº de meses CON ingreso
    dentro de la ventana (acotado a `[1, months]`), no un fijo `months`.
    Antes dividía siempre entre 6 meses cerrados: un usuario nuevo con
    ingreso en sólo 2 de esos meses veía su media artificialmente
    deprimida (÷6 en vez de ÷2), inflando la tasa de esfuerzo. Esto
    además acerca esta media (Capa 2) a la de Capa 1
    (`compute_category_summary`), que ya divide por los meses cerrados
    del período. Se mantiene el límite superior `months` para que un
    usuario con mucho histórico no diluya el "ingreso reciente"
    promediando ventanas distintas según su antigüedad."""
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
    # AUDIT-2026-06 (fix #6) — Agrupamos por mes (truncado en UTC, igual
    # criterio de bucket que debt_history) para poder dividir por el nº de
    # meses con ingreso, no por un fijo `months`.
    month_bucket = func.date_trunc("month", func.timezone("UTC", Transaction.occurred_at))
    query = (
        select(month_bucket.label("bucket"), func.coalesce(func.sum(amount_expr), 0))
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_(None))
        # AUDIT-2026-07 (H-03): el ingreso lo decide `flow` (con fallback a
        # categoría para filas heredadas) y se EXCLUYEN transferencias
        # internas — mismos helpers que el dashboard, para que el "ingreso
        # medio" de deuda/DTI no cuente un traspaso entre cuentas propias como
        # ingreso e infle el denominador del ratio de esfuerzo. Antes filtraba
        # sólo `Category.kind == INCOME`, que una transferencia is_transfer
        # INCOME (sin pareja) atravesaba.
        .where(_is_income())
        .where(_is_internal_transfer().is_(False))
        .where(Transaction.occurred_at >= window_start)
        .where(Transaction.occurred_at <= window_end)
        .group_by(month_bucket)
    )
    if target_currency is None:
        query = query.where(Transaction.currency == currency)
    rows = (await db.execute(query)).all()
    # Sólo cuentan los meses con ingreso NETO positivo. El divisor es el
    # nº de esos meses, acotado a `[1, months]`.
    monthly_totals = [Decimal(total) for _bucket, total in rows if Decimal(total) > 0]
    total = sum(monthly_totals, Decimal("0"))
    if total <= 0 or not monthly_totals:
        return Decimal("0")
    divisor = min(len(monthly_totals), months)
    return (total / Decimal(divisor)).quantize(Decimal("0.01"))


async def windowed_income_total(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    start: date,
    end: date,
    target_currency: str | None = None,
) -> Decimal:
    """Σ ingresos (categoría INCOME, sin papelera, sin transferencias
    internas) en la ventana `[start, end]` inclusive (PHASE-30.8).

    A diferencia de `monthly_income_avg` (ventana fija de 6 meses
    cerrados, anclada en hoy), aquí la ventana la fija el caller —la
    usa la tasa de esfuerzo *period-scoped* de Capa 1, que luego divide
    por el nº de meses del período. Mismo modo dual de moneda que
    `monthly_income_avg`. Devuelve `Decimal('0')` si no hay ingresos.
    """
    window_start = datetime(start.year, start.month, start.day, 0, 0, 0, tzinfo=UTC)
    window_end = datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=UTC)
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
        # AUDIT-2026-07 (H-03): ingreso por `flow` + exclusión de
        # transferencias internas, reconciliado con el dashboard (ver
        # `monthly_income_avg`).
        .where(_is_income())
        .where(_is_internal_transfer().is_(False))
        .where(Transaction.occurred_at >= window_start)
        .where(Transaction.occurred_at <= window_end)
    )
    if target_currency is None:
        query = query.where(Transaction.currency == currency)
    total = Decimal((await db.execute(query)).scalar_one())
    return total if total > 0 else Decimal("0")


async def _interest_paid_ytd(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    *,
    target_currency: str | None = None,
    exclude_account_ids: set[uuid.UUID] | None = None,
) -> Decimal:
    """Suma de expenses en categorías de intereses desde 1-enero hasta hoy.

    PHASE-30.6 — Mismo modo dual que `monthly_income_avg`.

    PHASE-37 (fix) — `exclude_account_ids` deja fuera las transacciones de
    las cuentas cuyo interés YA sale del cuadro de amortización (MUX por
    pasivo). Sin esta exclusión, un usuario que además registrase el
    interés como transacción lo contaría dos veces (el bug de "dos fuentes
    de verdad" que mató PHASE-34).

    AUDIT-2026-06 (fix #4) — Se acota `occurred_at <= fin del día de hoy
    (UTC)`. Sin la cota superior, las cuotas de interés autopostadas a
    fecha futura (gastos fijos confirmados que se proyectan adelante)
    entraban en el "interés pagado YTD", inflándolo con interés que el
    usuario aún no ha pagado. Mismo criterio de ventana que
    `monthly_income_avg`/`_principal_paid_last_n_months` (que cierran su
    ventana en `window_end`)."""
    today = _today_utc()
    year_start = datetime(today.year, 1, 1, tzinfo=UTC)
    today_end = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=UTC)
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
        .where(Transaction.occurred_at <= today_end)
    )
    if exclude_account_ids:
        query = query.where(Transaction.account_id.notin_(exclude_account_ids))
    if target_currency is None:
        query = query.where(Transaction.currency == currency)
    return Decimal((await db.execute(query)).scalar_one())


async def _load_installments_by_account(
    db: AsyncSession,
    user_id: uuid.UUID,
    liability_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[LiabilityInstallment]]:
    """Carga las cuotas persistidas de cada liability, ordenadas por
    índice, agrupadas por `account_id` (AUDIT-2026-06 fix #3).

    Una sola query para todas las liabilities — el caller las usa como
    fuente primaria del principal real y de los meses restantes, igual
    que el endpoint `/accounts/{id}/schedule`."""
    if not liability_ids:
        return {}
    rows = (
        (
            await db.execute(
                select(LiabilityInstallment)
                .where(LiabilityInstallment.user_id == user_id)
                .where(LiabilityInstallment.account_id.in_(liability_ids))
                .order_by(
                    LiabilityInstallment.account_id,
                    LiabilityInstallment.installment_index.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    by_account: dict[uuid.UUID, list[LiabilityInstallment]] = {}
    for inst in rows:
        by_account.setdefault(inst.account_id, []).append(inst)
    return by_account


async def _counterpart_principal(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
) -> Decimal | None:
    """Principal derivado de la tx contraparte pareada (flujo
    convert-to-debt, PHASE-24). Misma derivación que
    `regenerate_schedule` en accounts/service.py: la primera tx activa
    con `transfer_pair_id` en la cuenta es la operación financiada y su
    `amount` es el principal de la deuda. `None` si no hay contraparte.
    """
    counterpart = (
        await db.execute(
            select(Transaction.amount)
            .where(Transaction.account_id == account_id)
            .where(Transaction.user_id == user_id)
            .where(Transaction.deleted_at.is_(None))
            .where(Transaction.transfer_pair_id.is_not(None))
            .order_by(Transaction.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if counterpart is None or counterpart <= 0:
        return None
    return Decimal(counterpart)


async def _effective_principal(
    db: AsyncSession,
    user_id: uuid.UUID,
    liab: Account,
    installments: list[LiabilityInstallment],
) -> Decimal | None:
    """Principal REAL de una liability para la cuota francesa
    (AUDIT-2026-06 fix #3).

    Orden de preferencia (idéntico al endpoint de schedule):
    1. Cuotas persistidas: `principal_1 + remaining_balance_1` (el
       principal total del cuadro, robusto a overrides).
    2. `opening_balance` si es positivo.
    3. Tx contraparte pareada (convert-to-debt: `opening_balance=0`).

    Devuelve `None` si no se puede derivar ningún principal positivo —
    el caller cae al estimado lineal o excluye la cuota."""
    if installments:
        first = installments[0]
        principal_total = first.principal + first.remaining_balance
        if principal_total > 0:
            return Decimal(principal_total)
    if liab.opening_balance > 0:
        return Decimal(liab.opening_balance)
    return await _counterpart_principal(db, user_id, liab.id)


def _months_remaining_from_schedule(
    liab: Account,
    balance: Decimal,
    today: date,
    *,
    installments: list[LiabilityInstallment] | None = None,
    effective_principal: Decimal | None = None,
) -> int | None:
    """Cuenta cuántas cuotas quedan por pagar para una liability
    concreta (PHASE-30.2).

    AUDIT-2026-06 (fix #3) — Cuando hay cuotas PERSISTIDAS las usamos
    como fuente de verdad (coherente con `/accounts/{id}/schedule` y con
    el estado de pago real): una cuota se considera pendiente si NO está
    marcada `paid_at` y su `due_date >= primer día del mes actual`. Así
    las liabilities de convert-to-debt (`opening_balance=0`) entran en el
    cómputo en lugar de quedar fuera (antes `opening_balance <= 0`
    devolvía `None` y una deuda real no contaba para `time_to_payoff` ni
    para la cuota francesa, pudiendo dejar a un usuario sobreendeudado en
    estado 'healthy').

    Sin cuotas persistidas reconstruye el cuadro desde el
    `effective_principal` (opening_balance o tx contraparte). Devuelve
    `None` sólo cuando faltan los datos para estimar nada — el caller
    hace fallback a la proyección lineal.

    Una fila se considera pendiente si su `due_date >= primer día del
    mes actual` (el mes en curso aún cuenta como debido).
    """
    month_floor = _start_of_month(today)

    # Path PHASE-24.1: cuotas persistidas (con overrides + estado de pago).
    if installments:
        if balance <= 0:
            return 0
        return sum(
            1 for inst in installments if inst.paid_at is None and inst.due_date >= month_floor
        )

    if liab.apr is None or liab.term_months is None or liab.start_date is None:
        return None
    principal = effective_principal if effective_principal is not None else liab.opening_balance
    if principal is None or principal <= 0:
        return None
    schedule = build_schedule(
        principal=principal,
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
    installments_by_account: dict[uuid.UUID, list[LiabilityInstallment]],
    effective_principals: dict[uuid.UUID, Decimal | None],
    target_currency: str | None = None,
) -> int | None:
    """PHASE-30.2 — combina schedule + fallback lineal por liability.

    Para liabilities con cuadro (cuotas persistidas o cuadro francés
    reconstruible) usamos las cuotas restantes directamente (mucho más
    fiable en hipotecas tempranas); para las que no lo tienen (tarjetas o
    préstamos sin apr declarado) fallback a la proyección lineal.

    AUDIT-2026-06 (fix #3) — Prioriza las cuotas PERSISTIDAS y el
    principal real (`effective_principals`), de modo que las liabilities
    de convert-to-debt (`opening_balance=0`) también cuentan.
    AUDIT-2026-06 (fix #5) — El estimado lineal se descarta si supera
    `LINEAR_PAYOFF_CAP_MONTHS` (deuda revolving prácticamente perpetua):
    devolver un horizonte de cientos de años es ruido, no información.

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
        est = _months_remaining_from_schedule(
            liab,
            balance,
            today,
            installments=installments_by_account.get(liab.id),
            effective_principal=effective_principals.get(liab.id),
        )
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
            estimate = int((no_schedule_balance / monthly_principal).to_integral_value())
            # fix #5 — descartamos horizontes absurdos (revolving al mínimo).
            if estimate <= LINEAR_PAYOFF_CAP_MONTHS:
                linear_estimate = estimate

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
    (`transfer_pair_id IS NOT NULL`).

    AUDIT-2026-06 (fix #2) — Se filtra explícitamente
    `Category.kind == INCOME`: por la convención de signo (rama liability
    de get_balances_for_user) sólo la pata income REDUCE la deuda. Antes
    esta query sumaba TODA tx con `transfer_pair_id` en la cuenta-pasivo,
    incluyendo la pata de gasto que la SUBE; eso inflaba el ritmo de
    amortización y por tanto acortaba artificialmente el `time_to_payoff`
    lineal. El join a Category es interno: la pata amortizadora es INCOME
    y siempre tiene categoría.
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
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.account_id.in_(liability_ids))
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_not(None))
        # AUDIT-2026-07 (LOW): la pata que amortiza (reduce la deuda) es la
        # ENTRADA (`is_inflow`, flow-based), el MISMO predicado que
        # debt_history.principal_q y la rama liability de get_balances_for_user.
        # Antes usaba `Category.kind == INCOME`, que discrepaba cuando flow y
        # categoría no coinciden (lo que ADR-0004 permite).
        .where(is_inflow())
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
    query = select(Account).where(Account.user_id == user_id).where(Account.is_archived.is_(False))
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
    # PHASE-36 — "el cuadro manda": las liabilities CON cuadro derivan su
    # deuda viva de las cuotas no pagadas (igual que /balances), no de los
    # movimientos. Cargamos las cuotas UNA vez y reusamos abajo (cuota
    # francesa, time-to-payoff). Antes esto se cargaba más abajo (línea ~710).
    liability_ids_all = [a.id for a in accounts if a.nature == AccountNature.LIABILITY]
    installments_by_account = await _load_installments_by_account(db, user_id, liability_ids_all)
    total_assets = Decimal("0")
    total_liabilities = Decimal("0")
    # PHASE-40 — patrimonio neto usa TODOS los pasivos (incluida la tarjeta
    # revolving `counts_as_debt=False`, cuyo saldo compensa el efectivo aún no
    # adeudado); `total_liabilities` (deuda viva) usa solo los que cuentan como
    # deuda.
    net_worth_liabilities = Decimal("0")
    liabilities: list[Account] = []
    liability_balances: dict[uuid.UUID, Decimal] = {}
    for account in accounts:
        # AUDIT-2026-06 — brokerage/crypto NO entran en `total_assets`,
        # exactamente igual que `get_balances` (PHASE-31.4). Antes
        # debt-health los contaba aquí pero net-worth no, así que el KPI
        # "% en deuda" (debt_to_assets) y el patrimonio neto de la misma
        # card asumían conjuntos de activos distintos. Las liabilities
        # nunca son de estos tipos, así que sólo afecta a activos.
        if account.nature == AccountNature.ASSET and account.type in UNVALUED_ACCOUNT_TYPES:
            continue
        # Saldo nativo de la cuenta (siempre en su propia divisa, igual
        # que en /balances).
        native_balance = account.opening_balance + movements.get(account.id, Decimal("0"))
        if account.nature == AccountNature.LIABILITY:
            sched_outstanding = schedule_outstanding(installments_by_account.get(account.id, []))
            if sched_outstanding is not None:
                native_balance = sched_outstanding

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
            net_worth_liabilities += aggregable_balance
            # Tarjeta revolving (`counts_as_debt=False`) → cuenta en patrimonio
            # pero NO en deuda viva / DTI / composición.
            if account.counts_as_debt:
                total_liabilities += aggregable_balance
                liabilities.append(account)
                liability_balances[account.id] = aggregable_balance
        else:
            total_assets += aggregable_balance

    net_worth = total_assets - net_worth_liabilities
    debt_to_assets = float(total_liabilities / total_assets) if total_assets > 0 else None

    # AUDIT-2026-06 (fix #3) — Las cuotas persistidas son la fuente de verdad
    # para la cuota francesa y los meses restantes (igual que el endpoint
    # `/accounts/{id}/schedule`), e incluyen las liabilities de convert-to-debt
    # cuyo `opening_balance` es 0. PHASE-36: ya cargadas arriba
    # (`installments_by_account`), reusadas aquí.
    effective_principals: dict[uuid.UUID, Decimal | None] = {}
    for liab in liabilities:
        effective_principals[liab.id] = await _effective_principal(
            db, user_id, liab, installments_by_account.get(liab.id, [])
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
            installments = installments_by_account.get(liab.id, [])
            if installments:
                # fix #3 — cuota persistida (con overrides reales): fuente
                # de verdad alineada con el cuadro de `/schedule`.
                native_cuota = Decimal(installments[0].payment)
                if liab.apr is not None:
                    weighted_apr_num += liab.apr * balance
                    weighted_apr_den += balance
            elif liab.apr is not None and liab.term_months is not None:
                # Sin cuotas persistidas: cuota francesa sobre el principal
                # REAL (opening_balance o tx contraparte de convert-to-debt),
                # no el saldo actual — la cuota francesa es constante. Antes
                # se usaba `opening_balance` directo, que es 0 en
                # convert-to-debt y dejaba la cuota (y por tanto la tasa de
                # esfuerzo) fuera, pudiendo marcar 'healthy' a un usuario
                # sobreendeudado.
                principal = effective_principals.get(liab.id)
                if principal is not None and principal > 0:
                    native_cuota = compute_monthly_payment(principal, liab.apr, liab.term_months)
                    # weighted_apr opera sobre el balance ya en effective.
                    weighted_apr_num += liab.apr * balance
                    weighted_apr_den += balance
        elif liab.type == AccountType.CREDIT_CARD:
            installments = installments_by_account.get(liab.id, [])
            if installments:
                # PHASE-36 — Tarjeta con compra a plazos (cuadro persistido):
                # la cuota real es la del cuadro, no una estimación.
                native_cuota = Decimal(installments[0].payment)
                if liab.apr is not None:
                    weighted_apr_num += liab.apr * balance
                    weighted_apr_den += balance
            # Tarjeta sin cuadro: estimar la cuota mensual como `saldo / 12`
            # si tiene APR (financiación a un año típica), o el mínimo común
            # (3% del saldo). Si tiene APR declarado, contribuye al weighted_apr.
            elif liab.apr is not None:
                weighted_apr_num += liab.apr * balance
                weighted_apr_den += balance
                # Cuota teórica de 12 meses con apr — sobre el saldo
                # nativo, no el convertido, para que sea fiel a la
                # liability real.
                native_card_balance = liab.opening_balance + movements.get(liab.id, Decimal("0"))
                native_cuota = compute_monthly_payment(native_card_balance, liab.apr, 12)
            else:
                native_card_balance = liab.opening_balance + movements.get(liab.id, Decimal("0"))
                native_cuota = (native_card_balance * Decimal("0.03")).quantize(Decimal("0.01"))

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

    weighted_apr = float(weighted_apr_num / weighted_apr_den) if weighted_apr_den > 0 else None

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

    # 5. Intereses YTD + totales del cuadro (PHASE-37: MUX por pasivo).
    #    El interés no se registra como movimiento aparte (va dentro de la
    #    cuota), así que las liabilities CON cuadro derivan su interés del
    #    cuadro; las que no tienen cuadro, de sus transacciones DEBT_INTEREST.
    #    Se excluyen las cuentas con cuadro del término transaccional para no
    #    contar el mismo interés dos veces (XOR, no aditivo — lección PHASE-34).
    today = _today_utc()
    year_start = date(today.year, 1, 1)
    scheduled_liab_ids = {liab.id for liab in liabilities if installments_by_account.get(liab.id)}
    tx_interest = await _interest_paid_ytd(
        db,
        user_id,
        native_currency,
        target_currency=target_currency,
        exclude_account_ids=scheduled_liab_ids,
    )

    async def _to_effective(native_val: Decimal, liab_currency: str) -> Decimal:
        """Convierte un importe nativo del cuadro al effective_currency (tasa
        de hoy, igual que los saldos). Identidad en modo nativo / misma divisa."""
        if native_val == 0:
            return Decimal("0")
        if target_currency is None or liab_currency.upper() == effective_currency:
            return native_val
        converted = await _convert_at_today(
            db, native_val, from_currency=liab_currency, target_currency=effective_currency
        )
        return converted if converted is not None else Decimal("0")

    sched_interest_ytd = Decimal("0")
    sched_interest_total = Decimal("0")
    sched_interest_remaining = Decimal("0")
    for liab in liabilities:
        insts = installments_by_account.get(liab.id, [])
        if not insts:
            continue
        sched_interest_ytd += await _to_effective(
            interest_paid_in_window(insts, start=year_start, end=today), liab.currency
        )
        sched_interest_total += await _to_effective(
            interest_total(insts), liab.currency
        )
        sched_interest_remaining += await _to_effective(
            interest_total(insts, unpaid_only=True), liab.currency
        )

    interest_ytd = tx_interest + sched_interest_ytd

    # 5b. Composición de la deuda viva por tipo (PHASE-37) — reutiliza los
    #     saldos ya dirigidos por cuadro/convertidos. Fuente ÚNICA de la
    #     deuda viva (misma que total_liabilities), sin recomputar aparte.
    debt_by_type_map: dict[str, Decimal] = {}
    for liab in liabilities:
        bal = liability_balances.get(liab.id, Decimal("0"))
        if bal <= 0:
            continue
        debt_by_type_map[liab.type.value] = (
            debt_by_type_map.get(liab.type.value, Decimal("0")) + bal
        )
    debt_by_type = [
        DebtTypeSlice(type=t, amount=amt.quantize(Decimal("0.01")))
        for t, amt in sorted(debt_by_type_map.items(), key=lambda kv: kv[1], reverse=True)
    ]

    # 6. Time-to-payoff (PHASE-30.2): prefer schedule over linear projection.
    time_to_payoff = await _time_to_payoff_months(
        db,
        user_id,
        liabilities,
        liability_balances,
        native_currency,
        total_liabilities,
        installments_by_account=installments_by_account,
        effective_principals=effective_principals,
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
        debt_by_type=debt_by_type,
        interest_paid_ytd=interest_ytd.quantize(Decimal("0.01")),
        interest_scheduled_total=sched_interest_total.quantize(Decimal("0.01")),
        interest_remaining=sched_interest_remaining.quantize(Decimal("0.01")),
        weighted_apr=weighted_apr,
        time_to_payoff_months=time_to_payoff,
        reference_currency=effective_currency,
    )
