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

from app.modules.personal_finance.accounts.debt_health import DEFAULT_REFERENCE_CURRENCY
from app.modules.personal_finance.accounts.debt_history import (
    _add_month,
    _end_of_month,
    _format_month,
    _start_of_month,
    _today_utc,
    compute_debt_history,
)
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
from app.modules.personal_finance.transactions.models import Transaction


def _pct(delta: Decimal, base: Decimal) -> float | None:
    """Δ% respecto a `base`; None si la base es 0 (sin referencia)."""
    if base == 0:
        return None
    return float(delta / abs(base) * Decimal("100"))


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
    included_ids = [a.id for a in included]

    asset_opening = sum(
        (a.opening_balance for a in included if a.nature == AccountNature.ASSET),
        Decimal("0"),
    )
    liab_opening = sum(
        (a.opening_balance for a in included if a.nature == AccountNature.LIABILITY),
        Decimal("0"),
    )

    if months_back <= 0:
        history: list[PositionPoint] = []
    else:
        history = await _historical_points(
            db,
            user_id,
            included_ids=included_ids,
            reference_currency=reference_currency,
            months_back=months_back,
            asset_opening=asset_opening,
            liab_opening=liab_opening,
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
    included_ids = [a.id for a in included]
    asset_opening = sum(
        (a.opening_balance for a in included if a.nature == AccountNature.ASSET), Decimal("0")
    )
    liab_opening = sum(
        (a.opening_balance for a in included if a.nature == AccountNature.LIABILITY), Decimal("0")
    )

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
            .where(Transaction.account_id.in_(included_ids))
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

    asof_rows = (await db.execute(_base().where(Transaction.occurred_at <= date_to))).all()
    range_rows = (
        await db.execute(
            _base()
            .where(Transaction.occurred_at >= date_from)
            .where(Transaction.occurred_at <= date_to)
        )
    ).all()
    asof_a, asof_l = _split(asof_rows)
    rng_a, rng_l = _split(range_rows)

    total_assets = (asset_opening + asof_a).quantize(Decimal("0.01"))
    total_liabilities = (liab_opening + asof_l).quantize(Decimal("0.01"))
    return PositionAsOfResponse(
        reference_currency=reference_currency,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        net_worth=(total_assets - total_liabilities).quantize(Decimal("0.01")),
        delta_assets=rng_a.quantize(Decimal("0.01")),
        delta_net_worth=(rng_a - rng_l).quantize(Decimal("0.01")),
    )


async def _historical_points(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    included_ids: list[uuid.UUID],
    reference_currency: str,
    months_back: int,
    asset_opening: Decimal,
    liab_opening: Decimal,
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

    paired_tx = aliased(Transaction)
    paired_account = aliased(Account)
    # Σ firmado por (naturaleza, mes) sobre TODO el histórico ≤ último cierre.
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
        .where(Transaction.account_id.in_(included_ids))
        .where(Transaction.currency == reference_currency)
        .where(Transaction.occurred_at <= last_month_end)
        .group_by(Account.nature, month_bucket)
    )
    rows = (await db.execute(query)).all()
    asset_by_month: dict[str, Decimal] = {}
    liab_by_month: dict[str, Decimal] = {}
    for nature, bucket, total in rows:
        key = _fmt(bucket)
        if nature == AccountNature.ASSET:
            asset_by_month[key] = Decimal(total)
        else:
            liab_by_month[key] = Decimal(total)

    def _cumulative(series: dict[str, Decimal]) -> dict[str, Decimal]:
        running = Decimal("0")
        out: dict[str, Decimal] = {}
        for k in sorted(series):
            running += series[k]
            out[k] = running
        return out

    asset_cum = _cumulative(asset_by_month)
    liab_cum = _cumulative(liab_by_month)

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
        liabilities = liab_opening + _at(liab_cum, key)
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
