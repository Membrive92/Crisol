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
from app.modules.personal_finance.accounts.installments_model import (
    LiabilityInstallment,
)
from app.modules.personal_finance.accounts.installments_repository import (
    installments_by_account,
)
from app.modules.personal_finance.accounts.models import (
    Account,
    AccountNature,
    AccountType,
)
from app.modules.personal_finance.accounts.repository import is_inflow, is_outflow
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


# ── M-02 (AUDIT-2026-07): saldo de deuda dirigido por CUADRO ────────────────
# Para un pasivo CON cuadro (loan/mortgage con apr+plazo+fecha), el saldo vivo
# lo manda el cuadro (Σ principal de cuotas no pagadas, PHASE-36), no los
# movimientos. Antes la serie temporal derivaba de movimientos y un préstamo
# sin pagos registrados salía PLANO en el histórico y arrancaba la proyección
# desde un saldo distinto al de /balances y /debt-health. Estos helpers derivan
# el saldo y la amortización de la CURVA del cuadro (remaining_balance por mes),
# de modo que histórico + proyección + KPI cuadren.


def _scheduled_remaining_at(insts: list[LiabilityInstallment], month: date) -> Decimal:
    """Saldo pendiente (NATIVO) al cierre de `month` según la curva del cuadro:
    el `remaining_balance` de la última cuota con vencimiento en o antes de
    `month`. Antes de la primera cuota = capital completo (Σ principal)."""
    ym = (month.year, month.month)
    remaining: Decimal | None = None
    principal_total = Decimal("0")
    for inst in insts:  # ordenadas por índice ascendente
        principal_total += inst.principal
        if (inst.due_date.year, inst.due_date.month) <= ym:
            remaining = inst.remaining_balance
    return remaining if remaining is not None else principal_total


def _scheduled_flow_in_month(
    insts: list[LiabilityInstallment], month: date
) -> tuple[Decimal, Decimal]:
    """(principal, interés) NATIVOS de la cuota que vence EN `month` (0,0 si
    ninguna) — alimenta las barras de amortización/interés del período."""
    for inst in insts:
        if inst.due_date.year == month.year and inst.due_date.month == month.month:
            return inst.principal, inst.interest
    return Decimal("0"), Decimal("0")


async def _compute_historical_points(
    db: AsyncSession,
    user_id: uuid.UUID,
    liabilities: list[Account],
    reference_currency: str,
    months_back: int,
    *,
    target_currency: str | None = None,
    insts_by_account: dict[uuid.UUID, list[LiabilityInstallment]],
    fx_factor: dict[uuid.UUID, Decimal],
) -> list[DebtHistoryPoint]:
    """Histórico mes a mes para los últimos `months_back` meses cerrados.

    No incluye el mes en curso (sería incompleto). Si el usuario no
    tiene liabilities, devuelve lista vacía.

    AUDIT-2026-07 (M-02) — FUENTE DEL SALDO, unificada con el cuadro:
    - Pasivos CON cuadro (loan/mortgage con cuotas persistidas): el saldo lo
      manda el CUADRO — la curva `remaining_balance` por mes (PHASE-36 "el
      cuadro manda"), igual que `/balances`, `/debt-health` y la proyección.
      Antes derivaba de movimientos, así que un préstamo sin pagos registrados
      salía PLANO y no cuadraba con el KPI.
    - Pasivos SIN cuadro (tarjetas sin plan): siguen derivando de MOVIMIENTOS
      (`opening + Σ signed_amount`).
    Las queries de movimientos se restringen a los pasivos SIN cuadro para no
    doble-contar. `fx_factor[id]` convierte a la divisa efectiva (1 en modo
    nativo); `insts_by_account` trae las cuotas por cuenta.
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

    # AUDIT-2026-07 (M-02): separa pasivos CON cuadro de los que NO. El saldo
    # de los primeros lo manda la curva del cuadro; el de los segundos, los
    # movimientos. Las queries de movimientos operan SÓLO sobre los sin cuadro.
    scheduled_liabs = [liab for liab in liabilities if insts_by_account.get(liab.id)]
    nonsched_liabs = [liab for liab in liabilities if not insts_by_account.get(liab.id)]
    # PHASE-37 — el interés histórico de un pasivo CON cuadro sale del cuadro
    # (la cuota que vence el mes), no de transacciones (el banco no lo
    # desglosa). Sus categorías vinculadas se excluyen del término
    # transaccional del interés para no contar dos veces (MUX por pasivo).
    scheduled_excluded_cats = {
        liab.category_id for liab in scheduled_liabs if liab.category_id is not None
    }
    liability_ids = [liab.id for liab in nonsched_liabs]
    # Opening (en divisa efectiva) sólo de los pasivos SIN cuadro.
    sum_opening = sum(
        (liab.opening_balance * fx_factor.get(liab.id, Decimal("1")) for liab in nonsched_liabs),
        Decimal("0"),
    )

    amount_expr = (
        converted_amount_expr(target_currency)
        if target_currency is not None
        else Transaction.amount
    )

    # Inversión de signo en SQL idéntica a la rama liability de
    # get_balances_for_user: una salida/cargo sube la deuda, una
    # entrada/pago la baja.
    # AUDIT-2026-06 (fix #8) — tx SIN categoría NO contribuye (`else_=0`,
    # PHASE-31.3). Antes era `else_=amount_expr`, lo que contradecía el
    # propio docstring del módulo ("misma inversión de signo que
    # get_balances_for_user") y metía cargos sin categoría en el saldo
    # histórico de deuda, divergiendo del saldo real de `/balances`.
    # AUDIT-2026-06 (alineación PHASE-34) — la dirección la manda `flow`
    # (`is_outflow`/`is_inflow`, los MISMOS predicados que
    # get_balances_for_user), no `Category.kind`. Antes, si flow y la
    # categoría discrepaban (lo que ADR-0004 permite), el último punto de
    # la línea no coincidía con el total de la DebtList. Por el backfill
    # 34.1 (flow ≡ derivación por categoría) es equivalente para los datos
    # heredados; sólo cambia las filas con flow puesto a mano.
    signed_amount = case(
        (is_outflow(), amount_expr),
        (is_inflow(), -amount_expr),
        else_=Decimal("0"),
    )

    # Lista de meses de la ventana (cronológica).
    window_months: list[date] = []
    cursor = first_month
    while cursor <= last_closed:
        window_months.append(cursor)
        cursor = _add_month(cursor, 1)

    last_month_end = _end_of_month(last_closed)
    first_month_start = datetime(first_month.year, first_month.month, 1, tzinfo=UTC)

    # AUDIT-2026-05: en vez de 3 queries por mes (3×N round-trips),
    # agrupamos por mes en SQL y hacemos el prefix-sum en Python (3
    # queries totales). El bucket se trunca en UTC para que la
    # pertenencia al mes coincida con las fronteras `_end_of_month`
    # (instantes UTC) usadas antes, sea cual sea la TZ de la sesión.
    month_bucket = func.date_trunc("month", func.timezone("UTC", Transaction.occurred_at))

    def _format_bucket(value: object) -> str:
        # `date_trunc` devuelve un timestamp naive a inicio de mes UTC.
        assert isinstance(value, datetime)
        return f"{value.year:04d}-{value.month:02d}"

    # Query A — saldo firmado por mes sobre TODO el histórico ≤ último
    # mes cerrado. El prefix-sum incluye el carry de meses previos a la
    # ventana, replicando el `occurred_at <= month_end` acumulado.
    cumulative_q = (
        select(month_bucket.label("bucket"), func.coalesce(func.sum(signed_amount), 0))
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.account_id.in_(liability_ids))
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.occurred_at <= last_month_end)
        .group_by(month_bucket)
    )
    if target_currency is None:
        cumulative_q = cumulative_q.where(Transaction.currency == reference_currency)
    signed_by_month: dict[str, Decimal] = {
        _format_bucket(bucket): Decimal(total)
        for bucket, total in (await db.execute(cumulative_q)).all()
    }

    # Query B — principal amortizado por mes (income transfer pair a
    # liabilities), dentro de la ventana.
    # AUDIT-2026-06 (fix #1) — "principal amortizado" es SÓLO la pata que
    # REDUCE la deuda: por la convención de signo (rama liability de
    # get_balances_for_user) eso es la entrada (`is_inflow`). Antes esta
    # query sumaba TODA tx con `transfer_pair_id` en una cuenta-pasivo,
    # incluyendo la pata de gasto que SUBE la deuda (p.ej. la contraparte
    # de una operación financiada o un cargo pareado), inflando el
    # "principal amortizado" del histórico.
    # AUDIT-2026-06 (alineación PHASE-34) — la dirección la manda `flow`
    # (`is_inflow`), no `Category.kind == INCOME`. El join a Category sigue
    # siendo interno porque el fallback de `is_inflow` (filas sin flow) lee
    # `Category.kind`; una pata amortizadora siempre tiene categoría.
    principal_q = (
        select(month_bucket.label("bucket"), func.coalesce(func.sum(amount_expr), 0))
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.account_id.in_(liability_ids))
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_not(None))
        .where(is_inflow())
        .where(Transaction.occurred_at >= first_month_start)
        .where(Transaction.occurred_at <= last_month_end)
        .group_by(month_bucket)
    )
    if target_currency is None:
        principal_q = principal_q.where(Transaction.currency == reference_currency)
    principal_by_month: dict[str, Decimal] = {
        _format_bucket(bucket): Decimal(total)
        for bucket, total in (await db.execute(principal_q)).all()
    }

    # Query C — intereses pagados por mes, dentro de la ventana.
    interest_q = (
        select(month_bucket.label("bucket"), func.coalesce(func.sum(amount_expr), 0))
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Category.kind == CategoryKind.EXPENSE)
        .where(Category.role == CategoryRole.DEBT_INTEREST)
        .where(Transaction.occurred_at >= first_month_start)
        .where(Transaction.occurred_at <= last_month_end)
        .group_by(month_bucket)
    )
    if scheduled_excluded_cats:
        interest_q = interest_q.where(Category.id.notin_(scheduled_excluded_cats))
    if target_currency is None:
        interest_q = interest_q.where(Transaction.currency == reference_currency)
    interest_by_month: dict[str, Decimal] = {
        _format_bucket(bucket): Decimal(total)
        for bucket, total in (await db.execute(interest_q)).all()
    }

    # Prefix-sum: saldo acumulado al cierre de cada mes con actividad
    # (las claves 'YYYY-MM' ordenan cronológicamente).
    running = Decimal("0")
    cumulative_at: dict[str, Decimal] = {}
    for month_key in sorted(signed_by_month):
        running += signed_by_month[month_key]
        cumulative_at[month_key] = running
    sorted_keys = sorted(cumulative_at)

    points: list[DebtHistoryPoint] = []
    for month in window_months:
        month_key = _format_month(month)
        # Acumulado ≤ month = prefix del último mes con actividad ≤ month.
        cumulative = Decimal("0")
        for key in sorted_keys:
            if key <= month_key:
                cumulative = cumulative_at[key]
            else:
                break
        # Movimientos (pasivos SIN cuadro).
        movement_debt = sum_opening + cumulative
        # Curva del cuadro (pasivos CON cuadro): saldo pendiente + amortización
        # del mes, en divisa efectiva.
        scheduled_debt = Decimal("0")
        scheduled_principal = Decimal("0")
        scheduled_interest = Decimal("0")
        for liab in scheduled_liabs:
            insts = insts_by_account[liab.id]
            factor = fx_factor.get(liab.id, Decimal("1"))
            scheduled_debt += _scheduled_remaining_at(insts, month) * factor
            sched_principal, sched_interest = _scheduled_flow_in_month(insts, month)
            scheduled_principal += sched_principal * factor
            scheduled_interest += sched_interest * factor
        total_debt = movement_debt + scheduled_debt
        principal_paid = principal_by_month.get(month_key, Decimal("0")) + scheduled_principal
        # PHASE-37 — interés histórico = transacciones (pasivos sin cuadro) +
        # interés del cuadro (pasivos con cuadro). Antes se descartaba el del
        # cuadro y el histórico salía plano a 0 frente a la proyección.
        interest_paid = interest_by_month.get(month_key, Decimal("0")) + scheduled_interest
        points.append(
            DebtHistoryPoint(
                month=month_key,
                total_debt=max(total_debt, Decimal("0")).quantize(Decimal("0.01")),
                principal_paid=principal_paid.quantize(Decimal("0.01")),
                interest_paid=interest_paid.quantize(Decimal("0.01")),
                kind="historical",
            )
        )

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
            if a.nature == AccountNature.LIABILITY
            and a.currency == native_currency
            and a.counts_as_debt
        ]
    else:
        liabilities = [
            a for a in accounts if a.nature == AccountNature.LIABILITY and a.counts_as_debt
        ]

    if not liabilities:
        return DebtHistoryResponse(
            items=[],
            reference_currency=effective_currency,
            months_historical=0,
            months_projected=0,
        )

    # 2. Cuotas por cuenta (saldo dirigido por cuadro, M-02) + saldos actuales
    #    + factores de conversión a la divisa efectiva.
    from app.modules.personal_finance.accounts.repository import get_balances_for_user

    insts_by_account = await installments_by_account(db, user_id, [liab.id for liab in liabilities])
    movements = await get_balances_for_user(db, user_id)

    # fx_factor: 1 en modo nativo o misma divisa; tasa de HOY si convertimos;
    # 0 si no hay tasa (la liability queda fuera del agregado, igual que antes).
    fx_factor: dict[uuid.UUID, Decimal] = {}
    for liab in liabilities:
        if target_currency is None or liab.currency.upper() == effective_currency:
            fx_factor[liab.id] = Decimal("1")
            continue
        one = await _convert_at_today(
            db, Decimal("1"), from_currency=liab.currency, target_currency=effective_currency
        )
        fx_factor[liab.id] = one if one is not None else Decimal("0")

    # Saldo actual por cuenta (divisa efectiva), arranque de la proyección:
    # CON cuadro lo manda la CURVA del cuadro al mes en curso
    # (`_scheduled_remaining_at`), de modo que histórico → arranque → proyección
    # sean CONTINUOS y precisos (misma base due-date que la proyección, que ya
    # usa build_schedule). Coincide con schedule_outstanding —y por tanto con
    # /balances y /debt-health— una vez la deuda está reconciliada (cuotas
    # vencidas marcadas pagadas). SIN cuadro: opening + movimientos.
    current_month = _start_of_month(_today_utc())
    current_balances: dict[uuid.UUID, Decimal] = {}
    for liab in liabilities:
        factor = fx_factor.get(liab.id, Decimal("1"))
        if factor == 0:
            continue  # sin tasa → fuera del agregado proyectado
        insts = insts_by_account.get(liab.id)
        if insts:
            native_balance = _scheduled_remaining_at(insts, current_month)
        else:
            native_balance = liab.opening_balance + movements.get(liab.id, Decimal("0"))
        current_balances[liab.id] = (native_balance * factor).quantize(Decimal("0.01"))

    # 3. Histórico + proyección.
    historical = await _compute_historical_points(
        db,
        user_id,
        liabilities,
        native_currency,
        months_back,
        target_currency=target_currency,
        insts_by_account=insts_by_account,
        fx_factor=fx_factor,
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
