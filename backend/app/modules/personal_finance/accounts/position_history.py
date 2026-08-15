"""PHASE-37.1 — Serie temporal de patrimonio (activos / pasivos / neto).

Generaliza `debt_history` al patrimonio completo: dos series (activos y
pasivos) agregadas por mes desde los MOVIMIENTOS + `opening_balance`, con la
MISMA expresión de signo que `get_balances_for_user` (`signed_amount_expr`).

Invariante crítico (test cruzado `test_position_history`): el último punto
histórico == los saldos agregados actuales derivados de `get_balances_for_user`
para las mismas cuentas.

Alcance / limitaciones (ver PHASE-37 doc):
- MONO-DIVISA: solo cuentas en la divisa de referencia (misma limitación que
  `/accounts/balances`). Multi-divisa histórica requeriría tasas por fecha.
- Excluye cuentas archivadas y tipos NO valorados (brokerage/crypto), coherente
  con el agregado de patrimonio del servicio de balances.
- Archivar una cuenta la excluye de TODA la serie (para que sea reconstruible),
  no solo desde la fecha de archivo.
- Proyección (`months_forward > 0`): solo el lado PASIVO se proyecta (cuadro
  teórico, vía `debt_history`); los activos se mantienen planos — proyectar
  ingresos/gastos futuros sin modelo sería inventar datos.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Row, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.personal_finance.accounts.models import (
    UNVALUED_ACCOUNT_TYPES,
    Account,
    AccountNature,
)
from app.modules.personal_finance.accounts.repository import signed_amount_expr
from app.modules.personal_finance.accounts.schemas import (
    PositionAsOfResponse,
    PositionHistoryResponse,
    PositionPoint,
)
from app.modules.personal_finance.categories.models import Category
from app.modules.personal_finance.debt.health import DEFAULT_REFERENCE_CURRENCY
from app.modules.personal_finance.debt.history import (
    _add_month,
    _end_of_month,
    _format_month,
    _scheduled_remaining_at,
    _start_of_month,
    _today_utc,
    compute_debt_history,
)
from app.modules.personal_finance.debt.installments_model import LiabilityInstallment
from app.modules.personal_finance.debt.installments_repository import (
    installments_by_account,
)
from app.modules.personal_finance.transactions.models import Transaction


def _pct(delta: Decimal, base: Decimal) -> float | None:
    """Δ% respecto a `base`; None si la base es 0 (sin referencia)."""
    if base == 0:
        return None
    return float(delta / abs(base) * Decimal("100"))


def _scheduled_outstanding_as_of(
    insts: list[LiabilityInstallment], as_of: date, today: date
) -> Decimal:
    """PHASE-43.x — Deuda viva NATIVA de un pasivo CON cuadro a fecha `as_of`,
    dirigida por el cuadro (paid_at-based). Σ del `principal` de las cuotas NO
    pagadas a esa fecha. Idéntica lógica que `debt/service._outstanding_at`, para
    que el patrimonio y el módulo de deuda coincidan período a período:
    - `as_of >= hoy` (período en curso): sólo cuotas con `paid_at IS NULL` — una
      cuota del mes en curso con `paid_at` futuro (reconciliada a su vencimiento)
      ya está pagada. Coincide con `schedule_outstanding` de get_balances/debt-health.
    - `as_of` pasado: cuenta también las pagadas DESPUÉS de esa fecha (a fin de
      mayo aún debías la cuota que pagas en junio).
    """
    past = as_of < today
    return sum(
        (i.principal for i in insts if i.paid_at is None or (past and i.paid_at.date() > as_of)),
        Decimal("0"),
    )


async def compute_position_history(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    months_back: int = 12,
    months_forward: int = 0,
) -> PositionHistoryResponse:
    """Serie mensual de patrimonio + Δ del periodo pedido."""
    accounts = list(
        (
            await db.execute(
                select(Account)
                .where(Account.user_id == user_id)
                .where(Account.is_archived.is_(False))
            )
        )
        .scalars()
        .all()
    )
    if not accounts:
        return PositionHistoryResponse(
            reference_currency=DEFAULT_REFERENCE_CURRENCY,
            points=[],
            delta_period=None,
            delta_period_pct=None,
        )

    accounts_sorted = sorted(accounts, key=lambda a: (a.display_order, a.name))
    reference_currency = accounts_sorted[0].currency

    # Cuentas incluidas en el patrimonio: divisa de referencia + valoradas.
    included = [
        a
        for a in accounts
        if a.currency == reference_currency and a.type not in UNVALUED_ACCOUNT_TYPES
    ]
    if not included:
        return PositionHistoryResponse(
            reference_currency=reference_currency,
            points=[],
            delta_period=None,
            delta_period_pct=None,
        )

    # PHASE-43.x — pasivos CON cuadro dirigidos por la CURVA del cuadro (igual
    # que el chart de deuda y que get_balances/debt-health); activos y pasivos
    # SIN cuadro, por movimientos. Sin esto la línea de patrimonio no amortizaba
    # la deuda y no cuadraba con el KPI ni con el módulo de Deuda.
    liab_accounts = [a for a in included if a.nature == AccountNature.LIABILITY]
    insts_by_acc = await installments_by_account(db, user_id, [a.id for a in liab_accounts])
    sched_liabs = [a for a in liab_accounts if insts_by_acc.get(a.id)]
    nonsched_liab_ids = {a.id for a in liab_accounts if not insts_by_acc.get(a.id)}
    tx_ids = [
        a.id for a in included if a.nature == AccountNature.ASSET or a.id in nonsched_liab_ids
    ]

    asset_opening = sum(
        (a.opening_balance for a in included if a.nature == AccountNature.ASSET),
        Decimal("0"),
    )
    nonsched_liab_opening = sum(
        (a.opening_balance for a in included if a.id in nonsched_liab_ids),
        Decimal("0"),
    )

    if months_back <= 0:
        history: list[PositionPoint] = []
    else:
        history = await _historical_points(
            db,
            user_id,
            tx_ids=tx_ids,
            reference_currency=reference_currency,
            months_back=months_back,
            asset_opening=asset_opening,
            nonsched_liab_opening=nonsched_liab_opening,
            sched_liabs=sched_liabs,
            insts_by_acc=insts_by_acc,
        )

    projection = (
        await _projected_points(db, user_id, history, months_forward=months_forward)
        if months_forward > 0
        else []
    )
    points = history + projection

    # Δ del periodo pedido: neto actual (último histórico) − neto al inicio del
    # rango. None si no hay al menos dos puntos históricos.
    delta_period: Decimal | None = None
    delta_period_pct: float | None = None
    if len(history) >= 2:
        delta_period = history[-1].net_worth - history[0].net_worth
        delta_period_pct = _pct(delta_period, history[0].net_worth)

    return PositionHistoryResponse(
        reference_currency=reference_currency,
        points=points,
        delta_period=delta_period,
        delta_period_pct=delta_period_pct,
    )


async def compute_position_as_of(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    date_from: datetime,
    date_to: datetime,
) -> PositionAsOfResponse:
    """PHASE-41 — Patrimonio (activos/pasivos/neto) A FECHA `date_to` + Δ del
    patrimonio DURANTE `[date_from, date_to]`.

    Reutiliza `signed_amount_expr` (misma verdad de saldo que
    `get_balances_for_user` / `compute_position_history`): patrimonio a fecha =
    `opening + Σ(movimientos firmados ≤ date_to)`; Δ = `Σ(movimientos firmados
    en el rango)`. Mono-divisa (referencia), misma limitación que la serie.
    """
    accounts = list(
        (
            await db.execute(
                select(Account)
                .where(Account.user_id == user_id)
                .where(Account.is_archived.is_(False))
            )
        )
        .scalars()
        .all()
    )
    zero = PositionAsOfResponse(
        reference_currency=DEFAULT_REFERENCE_CURRENCY,
        total_assets=Decimal("0"),
        total_liabilities=Decimal("0"),
        net_worth=Decimal("0"),
        delta_assets=Decimal("0"),
        delta_net_worth=Decimal("0"),
    )
    if not accounts:
        return zero
    accounts_sorted = sorted(accounts, key=lambda a: (a.display_order, a.name))
    reference_currency = accounts_sorted[0].currency
    included = [
        a
        for a in accounts
        if a.currency == reference_currency and a.type not in UNVALUED_ACCOUNT_TYPES
    ]
    if not included:
        return zero.model_copy(update={"reference_currency": reference_currency})
    today = _today_utc()
    # PHASE-43.x — "el cuadro manda" también en el patrimonio: los pasivos CON
    # cuadro derivan su deuda viva de las cuotas (paid_at), no de los
    # movimientos —igual que get_balances/debt-health—. Sin esto un préstamo se
    # quedaba clavado en su apertura (nunca amortizaba en el patrimonio) y el
    # neto no cuadraba con el módulo de Deuda. Sólo activos + pasivos SIN cuadro
    # pasan por la suma de movimientos; los CON cuadro se agregan aparte.
    liab_accounts = [a for a in included if a.nature == AccountNature.LIABILITY]
    insts_by_acc = await installments_by_account(db, user_id, [a.id for a in liab_accounts])
    sched_liabs = [a for a in liab_accounts if insts_by_acc.get(a.id)]
    nonsched_liab_ids = {a.id for a in liab_accounts if not insts_by_acc.get(a.id)}
    asset_opening = sum(
        (a.opening_balance for a in included if a.nature == AccountNature.ASSET), Decimal("0")
    )
    nonsched_liab_opening = sum(
        (a.opening_balance for a in included if a.id in nonsched_liab_ids), Decimal("0")
    )
    # IDs que pasan por la suma de movimientos: activos + pasivos sin cuadro.
    tx_ids = [
        a.id for a in included if a.nature == AccountNature.ASSET or a.id in nonsched_liab_ids
    ]

    paired_tx = aliased(Transaction)
    paired_account = aliased(Account)

    def _base() -> Select[tuple[AccountNature, Decimal]]:
        return (
            select(
                Account.nature,
                func.coalesce(func.sum(signed_amount_expr(Account, paired_account)), 0),
            )
            .select_from(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            # `signed_amount_expr` cae a `Category.kind` cuando `flow` es NULL:
            # el join es obligatorio o SA mete `categories` como producto
            # cartesiano e infla la suma (misma unión que la serie histórica).
            .outerjoin(Category, Category.id == Transaction.category_id)
            .outerjoin(paired_tx, paired_tx.id == Transaction.transfer_pair_id)
            .outerjoin(paired_account, paired_account.id == paired_tx.account_id)
            .where(Transaction.user_id == user_id)
            .where(Transaction.deleted_at.is_(None))
            .where(Transaction.account_id.in_(tx_ids))
            .where(Transaction.currency == reference_currency)
            .group_by(Account.nature)
        )

    def _split(rows: Sequence[Row[tuple[AccountNature, Decimal]]]) -> tuple[Decimal, Decimal]:
        a = Decimal("0")
        li = Decimal("0")
        for nature, total in rows:
            if nature == AccountNature.ASSET:
                a = Decimal(total)
            else:
                li = Decimal(total)
        return a, li

    if tx_ids:
        asof_rows = (await db.execute(_base().where(Transaction.occurred_at <= date_to))).all()
        range_rows = (
            await db.execute(
                _base()
                .where(Transaction.occurred_at >= date_from)
                .where(Transaction.occurred_at <= date_to)
            )
        ).all()
    else:
        asof_rows = []
        range_rows = []
    asof_a, asof_nonsched_l = _split(asof_rows)
    rng_a, rng_nonsched_l = _split(range_rows)

    # Deuda viva de los pasivos CON cuadro a fin de rango y justo antes del
    # inicio (para el Δ). Los helpers del cuadro comparan por día.
    end_day = date_to.date()
    start_day = date_from.date() - timedelta(days=1)
    sched_end = sum(
        (_scheduled_outstanding_as_of(insts_by_acc[a.id], end_day, today) for a in sched_liabs),
        Decimal("0"),
    )
    sched_start = sum(
        (_scheduled_outstanding_as_of(insts_by_acc[a.id], start_day, today) for a in sched_liabs),
        Decimal("0"),
    )

    total_assets = (asset_opening + asof_a).quantize(Decimal("0.01"))
    total_liabilities = (nonsched_liab_opening + asof_nonsched_l + sched_end).quantize(
        Decimal("0.01")
    )
    delta_assets = rng_a
    # Δ pasivos = movimientos de los sin-cuadro en el rango + variación del cuadro.
    delta_liabilities = rng_nonsched_l + (sched_end - sched_start)
    return PositionAsOfResponse(
        reference_currency=reference_currency,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        net_worth=(total_assets - total_liabilities).quantize(Decimal("0.01")),
        delta_assets=delta_assets.quantize(Decimal("0.01")),
        delta_net_worth=(delta_assets - delta_liabilities).quantize(Decimal("0.01")),
    )


async def _historical_points(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    tx_ids: list[uuid.UUID],
    reference_currency: str,
    months_back: int,
    asset_opening: Decimal,
    nonsched_liab_opening: Decimal,
    sched_liabs: list[Account],
    insts_by_acc: dict[uuid.UUID, list[LiabilityInstallment]],
) -> list[PositionPoint]:
    today = _today_utc()
    last_closed = _start_of_month(today) - timedelta(days=1)
    first_month = _start_of_month(last_closed)
    for _ in range(months_back - 1):
        first_month = _start_of_month(_start_of_month(first_month) - timedelta(days=1))

    window_months: list[date] = []
    cursor = first_month
    while cursor <= last_closed:
        window_months.append(cursor)
        cursor = _add_month(cursor, 1)

    last_month_end = _end_of_month(last_closed)
    month_bucket = func.date_trunc("month", func.timezone("UTC", Transaction.occurred_at))

    def _fmt(value: object) -> str:
        assert isinstance(value, datetime)
        return f"{value.year:04d}-{value.month:02d}"

    # Σ firmado por (naturaleza, mes) para activos + pasivos SIN cuadro. Los
    # pasivos CON cuadro se excluyen de `tx_ids` — su saldo lo manda la curva.
    asset_by_month: dict[str, Decimal] = {}
    nonsched_liab_by_month: dict[str, Decimal] = {}
    if tx_ids:
        paired_tx = aliased(Transaction)
        paired_account = aliased(Account)
        query = (
            select(
                Account.nature,
                month_bucket.label("bucket"),
                func.coalesce(func.sum(signed_amount_expr(Account, paired_account)), 0),
            )
            .select_from(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .outerjoin(Category, Category.id == Transaction.category_id)
            .outerjoin(paired_tx, paired_tx.id == Transaction.transfer_pair_id)
            .outerjoin(paired_account, paired_account.id == paired_tx.account_id)
            .where(Transaction.user_id == user_id)
            .where(Transaction.deleted_at.is_(None))
            .where(Transaction.account_id.in_(tx_ids))
            .where(Transaction.currency == reference_currency)
            .where(Transaction.occurred_at <= last_month_end)
            .group_by(Account.nature, month_bucket)
        )
        rows = (await db.execute(query)).all()
        for nature, bucket, total in rows:
            key = _fmt(bucket)
            if nature == AccountNature.ASSET:
                asset_by_month[key] = Decimal(total)
            else:
                nonsched_liab_by_month[key] = Decimal(total)

    def _cumulative(series: dict[str, Decimal]) -> dict[str, Decimal]:
        running = Decimal("0")
        out: dict[str, Decimal] = {}
        for k in sorted(series):
            running += series[k]
            out[k] = running
        return out

    asset_cum = _cumulative(asset_by_month)
    nonsched_liab_cum = _cumulative(nonsched_liab_by_month)

    def _at(cum: dict[str, Decimal], month_key: str) -> Decimal:
        value = Decimal("0")
        for k in sorted(cum):
            if k <= month_key:
                value = cum[k]
            else:
                break
        return value

    points: list[PositionPoint] = []
    for month in window_months:
        key = _format_month(month)
        assets = asset_opening + _at(asset_cum, key)
        # Pasivos: sin-cuadro por movimientos + con-cuadro por la curva del mes.
        liabilities = nonsched_liab_opening + _at(nonsched_liab_cum, key)
        liabilities += sum(
            (_scheduled_remaining_at(insts_by_acc[a.id], month) for a in sched_liabs),
            Decimal("0"),
        )
        points.append(
            PositionPoint(
                month=month,
                total_assets=assets.quantize(Decimal("0.01")),
                total_liabilities=liabilities.quantize(Decimal("0.01")),
                net_worth=(assets - liabilities).quantize(Decimal("0.01")),
                is_projection=False,
            )
        )
    return points


async def _projected_points(
    db: AsyncSession,
    user_id: uuid.UUID,
    history: list[PositionPoint],
    *,
    months_forward: int,
) -> list[PositionPoint]:
    """Proyección: activos PLANOS (no se proyectan) + pasivos por el cuadro
    teórico (se reutiliza `debt_history` para el saldo de deuda proyectado)."""
    if not history:
        return []
    flat_assets = history[-1].total_assets
    # `debt_history` con months_back=0 devuelve sólo la proyección de deuda.
    debt = await compute_debt_history(db, user_id, months_back=0, months_ahead=months_forward)
    points: list[PositionPoint] = []
    for dp in debt.items:
        liabilities = Decimal(dp.total_debt)
        year, month = (int(x) for x in dp.month.split("-"))
        points.append(
            PositionPoint(
                month=date(year, month, 1),
                total_assets=flat_assets,
                total_liabilities=liabilities,
                net_worth=(flat_assets - liabilities).quantize(Decimal("0.01")),
                is_projection=True,
            )
        )
    return points
