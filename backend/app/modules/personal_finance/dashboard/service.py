"""Lógica de negocio del módulo dashboard.

Read-only: agregaciones sobre `transactions`. El service decide entre
los dos modos de moneda:

- **legacy** (`currency` filtra): mantiene el contrato anterior a
  PHASE-8.3 — totales por una sola moneda, sin conversión.
- **cross-currency** (`target_currency`): convierte cada transacción a
  la moneda destino con la tasa **del día de su `occurred_at`** (vía
  `conversion.converted_amount_expr`) y agrega después.

Si llegan ambos parámetros, gana `target_currency` — es el modo
preferido. Si no llega ninguno, se asume legacy con `_DEFAULT_CURRENCY`.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import Date as SQLDate
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.currency import service as currency_service
from app.modules.personal_finance.categories.models import CategoryKind
from app.modules.personal_finance.categories.repository import get_category_by_id
from app.modules.personal_finance.dashboard import repository
from app.modules.personal_finance.dashboard.schemas import (
    CategoryAvailablePeriodItem,
    CategoryAvailablePeriodsResponse,
    CategoryBreakdownItem,
    CategoryDetailResponse,
    CategoryMonthlyBucket,
    ModuleDashboardSummary,
    ModuleSummaryItem,
    ModuleVerdict,
    MonthlyBucket,
    SummaryResponse,
    TopExpenseItem,
)
from app.modules.personal_finance.transactions.models import Transaction
from app.modules.personal_finance.user_month import user_month_bounds

_UNCATEGORIZED_NAME = "Sin categoría"


async def ensure_rates_for_user_scope(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    target_currency: str,
    date_from: datetime | None,
    date_to: datetime | None,
) -> None:
    """Antes de agregar en cross-currency, asegura que las tasas para
    cada día con transacciones existan en BD.

    Sin esta llamada, transacciones históricas (más antiguas que el
    snapshot embebido + ventana de 14d) quedarían fuera del SUM con
    `unconvertible_count > 0`. Con ella, el primer request de cada
    fecha dispara fetch + persist + queda cacheado para siempre.

    Reusable desde otros módulos (transactions también lo llama antes
    de listar con `target_currency`).
    """
    target = target_currency.upper()
    query = (
        select(cast(Transaction.occurred_at, SQLDate))
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.currency != target)
        .distinct()
    )
    if date_from is not None:
        query = query.where(Transaction.occurred_at >= date_from)
    if date_to is not None:
        query = query.where(Transaction.occurred_at <= date_to)

    result = await db.execute(query)
    dates: list[date] = [row[0] for row in result.all()]
    if not dates:
        return
    await currency_service.ensure_rates_for_dates(db, dates)


def _resolve_mode(
    currency: str | None, target_currency: str | None
) -> tuple[str | None, str | None, str]:
    """Devuelve `(legacy_currency, target_currency, displayed_currency)`.

    - Si `target_currency` viene → modo cross-currency. `legacy=None`.
    - Si sólo `currency` → modo legacy. `target=None`.
    - Si ninguno → usar `currency` legacy con default upstream.
    """
    if target_currency is not None:
        target = target_currency.upper()
        return None, target, target
    if currency is not None:
        cur = currency.upper()
        return cur, None, cur
    return None, None, ""


async def list_user_currencies(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[str]:
    """Monedas distintas presentes en las transacciones del usuario."""
    return await repository.list_user_currencies(db, user_id)


def resolve_cycle_start_day(profile_cycle_start_day: int | None, cycle: bool) -> int | None:
    """C4 — El día `D` con el que cortar, o `None` para mes natural.

    El día **nunca viaja del cliente**: se lee del perfil (`users.cycle_start_day`,
    que `CurrentUser` ya trae en cada request). El query param `cycle` sólo dice
    *qué pregunta* se está haciendo — «nómina a nómina» en vez de «el calendario»
    —, no con qué número responderla; si el cliente pudiera mandar el día, dos
    pantallas podrían pintar cortes distintos del mismo dato.

    `cycle=true` sin ajuste configurado es un 422 y no un silencioso mes natural:
    el llamante pidió algo que el perfil no puede responder, y devolverle otra
    cosa con un 200 le haría creer que está viendo sus ciclos.

    Recibe el día ya extraído del perfil (no el objeto `User`) para no arrastrar
    el modelo de `users` hasta el service del dashboard.
    """
    if not cycle:
        return None
    if profile_cycle_start_day is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "No has definido el día en que empieza tu mes. "
                "Configúralo en Ajustes antes de pedir los períodos por ciclo."
            ),
        )
    return profile_cycle_start_day


def _cycle_anchor_of(moment: datetime, cycle_start_day: int) -> tuple[int, int]:
    """`(año, mes)` del ciclo que CONTIENE `moment` — el gemelo Python de
    `repository.cycle_shifted_occurred_at`.

    Misma aritmética: restar `D − 1` días y quedarse con el mes. Existe porque
    rellenar los huecos de la serie es cosa de Python — la query sólo devuelve
    los ciclos CON datos y el chart necesita también los vacíos.

    Lee los campos del `datetime` tal cual, sin normalizar huso, igual que hace
    la detección de mes/año natural de `_previous_period`. Los bordes de período
    llegan siempre en UTC (`toISOString()` desde el navegador), que es también
    como bucketiza el SQL, así que las dos mitades coinciden. Con `D = 1`
    devuelve `(moment.year, moment.month)` exacto: el mes natural no cambia ni un
    bit por pasar por aquí.
    """
    shifted = moment - timedelta(days=cycle_start_day - 1)
    return shifted.year, shifted.month


def _cycle_bounds(cycle_start_day: int, year: int, month: int) -> tuple[datetime, datetime]:
    """Bounds `[día D de M 00:00:00, día D−1 de M+1 23:59:59]` en UTC.

    El `−1` no es un adorno: el intervalo del repositorio es CERRADO en ambos
    extremos (`>= date_from AND <= date_to`), así que emitir `date_to = D de M+1`
    contaría el primer día del ciclo siguiente DOS veces. Misma convención que
    `boundsForCustomRange` en el frontend.

    Con `D = 1` el ciclo degenera EXACTAMENTE en el mes natural (`[1 de M,
    último día de M]`), que es la propiedad que verifica que la aritmética está
    bien.
    """
    start = datetime(year, month, cycle_start_day, 0, 0, 0, tzinfo=UTC)
    if cycle_start_day == 1:
        last = calendar.monthrange(year, month)[1]
        return start, datetime(year, month, last, 23, 59, 59, tzinfo=UTC)
    ny, nm = (year, month + 1) if month < 12 else (year + 1, 1)
    return start, datetime(ny, nm, cycle_start_day - 1, 23, 59, 59, tzinfo=UTC)


def _previous_period(
    date_from: datetime,
    date_to: datetime,
    *,
    cycle_start_day: int | None = None,
) -> tuple[datetime, datetime]:
    """PHASE-41 — Período EQUIVALENTE anterior para el Δ "vs período anterior".

    - CICLO completo del usuario (C4, sólo con `cycle_start_day`) → el ciclo
      anterior EXACTO (ancla − 1), no una ventana de igual longitud. Importa
      porque los ciclos no miden lo mismo: el del 14-jul dura 31 días y el del
      14-feb, 28. Con la ventana, «vs período anterior» comparaba el ciclo con
      un tramo desplazado que se comía tres días del anterior y perdía tres del
      suyo.
    - MES natural completo (1º 00:00 … último día 23:59:59) → el mes natural
      anterior exacto.
    - AÑO natural completo (1-ene 00:00 … 31-dic 23:59:59) → el año anterior.
    - Cualquier otro rango (custom, parcial) → ventana de igual longitud justo
      antes, con el límite superior EXCLUSIVO (−1 µs) para no solapar la
      frontera con el período actual (intervalo cerrado en el repositorio).

    Antes SIEMPRE se usaba la ventana de igual longitud, lo que para meses de
    distinta duración desplazaba el "anterior" ~1 día (p.ej. mayo → [31-mar…
    30-abr] en vez de abril natural).

    La rama del ciclo exige que el rango recibido SEA un ciclo entero, no sólo
    que el ajuste exista: con el preset activo el usuario puede pedir un rango
    libre, y ahí el comparable honesto sigue siendo la ventana de igual longitud.
    La comprobación es por INSTANTE (`==` entre datetimes aware), así que un
    cliente que exprese los mismos bordes en otro huso también entra.
    """
    if cycle_start_day is not None:
        year, month = _cycle_anchor_of(date_from, cycle_start_day)
        if (date_from, date_to) == _cycle_bounds(cycle_start_day, year, month):
            py, pm = (year, month - 1) if month > 1 else (year - 1, 12)
            return _cycle_bounds(cycle_start_day, py, pm)
    tz = date_from.tzinfo
    same_year_month = date_from.year == date_to.year and date_from.month == date_to.month
    at_month_start = date_from.day == 1 and (
        date_from.hour,
        date_from.minute,
        date_from.second,
        date_from.microsecond,
    ) == (0, 0, 0, 0)
    at_month_end = date_to.day == calendar.monthrange(date_to.year, date_to.month)[1] and (
        date_to.hour,
        date_to.minute,
        date_to.second,
    ) == (23, 59, 59)
    if same_year_month and at_month_start and at_month_end:
        y, m = (date_from.year, date_from.month - 1)
        if m == 0:
            y, m = y - 1, 12
        last = calendar.monthrange(y, m)[1]
        return (
            datetime(y, m, 1, 0, 0, 0, tzinfo=tz),
            datetime(y, m, last, 23, 59, 59, tzinfo=tz),
        )
    at_year_start = (
        date_from.month == 1
        and date_from.day == 1
        and (date_from.hour, date_from.minute, date_from.second, date_from.microsecond)
        == (0, 0, 0, 0)
    )
    at_year_end = (
        date_to.month == 12
        and date_to.day == 31
        and (date_to.hour, date_to.minute, date_to.second) == (23, 59, 59)
    )
    if date_from.year == date_to.year and at_year_start and at_year_end:
        y = date_from.year - 1
        return (
            datetime(y, 1, 1, 0, 0, 0, tzinfo=tz),
            datetime(y, 12, 31, 23, 59, 59, tzinfo=tz),
        )
    period_length = date_to - date_from
    return (date_from - period_length, date_from - timedelta(microseconds=1))


async def get_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    cycle_start_day: int | None = None,
) -> SummaryResponse:
    """Balance global. Soporta legacy (`currency`) y cross-currency (`target_currency`).

    C4 — `cycle_start_day` NO cambia qué transacciones entran (eso lo fija
    `[date_from, date_to]`, que ya llega recortado al ciclo desde el navegador).
    Cambia dos cosas de presentación: el comparable «vs período anterior» pasa a
    ser el ciclo anterior EXACTO, y `available_from/to` pasan a ser anclas de
    ciclo para que las flechas aterricen donde hay datos.
    """
    legacy, target, displayed = _resolve_mode(currency, target_currency)

    if target is not None:
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target,
            date_from=date_from,
            date_to=date_to,
        )

    income, expenses, count, unconvertible = await repository.get_summary_aggregates(
        db,
        user_id,
        currency=legacy,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
    )

    prev_income: Decimal | None = None
    prev_expenses: Decimal | None = None
    prev_balance: Decimal | None = None
    if date_from is not None and date_to is not None:
        # PHASE-41 — período equivalente anterior: mes/año natural anterior para
        # un rango que ES un mes/año completo; ventana de igual longitud (límite
        # superior exclusivo, sin solape en la frontera cerrada del repositorio)
        # para custom/parcial. Antes usaba siempre la ventana, que en meses de
        # distinta duración desplazaba el "anterior" ~1 día.
        prev_from, prev_to = _previous_period(date_from, date_to, cycle_start_day=cycle_start_day)
        prev_totals = await repository.get_totals_by_kind(
            db,
            user_id,
            currency=legacy,
            target_currency=target,
            date_from=prev_from,
            date_to=prev_to,
        )
        prev_income = prev_totals.get(CategoryKind.INCOME, Decimal("0"))
        prev_expenses = prev_totals.get(CategoryKind.EXPENSE, Decimal("0"))
        prev_balance = prev_income - prev_expenses

    # PHASE-37.1 — Δ vs periodo anterior equivalente (regla común de toda la
    # app: mes vs mes anterior, custom vs rango precedente de igual longitud).
    balance = income - expenses
    cashflow_delta: Decimal | None = None
    savings_rate_delta_pp: float | None = None
    if prev_balance is not None:
        cashflow_delta = balance - prev_balance
    if prev_income is not None and prev_income > 0 and income > 0 and prev_balance is not None:
        rate_now = float(balance / income * 100)
        rate_prev = float(prev_balance / prev_income * 100)
        savings_rate_delta_pp = rate_now - rate_prev

    # PHASE-47.E2 — cuánto del gasto del periodo está aplazado. No entra en
    # `expenses` (que mide caja); viaja aparte para que el desglose pueda
    # explicar por qué no cuadra con él.
    deferred = await repository.get_deferred_expense_total(
        db,
        user_id,
        currency=legacy,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
    )

    # PHASE-34 — límites globales (mes min/max con datos), independientes del
    # filtro de período, para acotar el navegador de período del Análisis.
    available_from, available_to = await repository.get_transaction_month_bounds(
        db, user_id, cycle_start_day=cycle_start_day
    )

    return SummaryResponse(
        income=income,
        expenses=expenses,
        balance=balance,
        transaction_count=count,
        currency=displayed,
        unconvertible_count=unconvertible,
        deferred_expenses=deferred,
        previous_period_income=prev_income,
        previous_period_expenses=prev_expenses,
        previous_period_balance=prev_balance,
        cashflow_delta=cashflow_delta,
        savings_rate_delta_pp=savings_rate_delta_pp,
        available_from=available_from,
        available_to=available_to,
    )


# Umbral del veredicto de finanzas domésticas (ADR-0006, decisión del usuario):
# el veredicto lo da el SIGNO del flujo de caja del período; una banda muerta de
# ±5% del ingreso alrededor de cero es "atención" (ni claramente ahorra ni
# claramente gasta de más).
_CASHFLOW_VERDICT_BAND = Decimal("0.05")


async def _latest_month_bounds(
    db: AsyncSession, user_id: uuid.UUID, *, cycle_start_day: int | None = None
) -> tuple[datetime, datetime]:
    """Rango `[inicio, fin]` del ÚLTIMO mes con transacciones del usuario, o del
    mes en curso si aún no tiene datos.

    PHASE-43.4 (fix) — la card no puede anclarse al mes NATURAL en curso: quien
    importa por meses tiene el mes actual vacío hasta que lo sube, así que la
    card salía siempre a 0. El último mes con datos es la foto más reciente
    representativa. Sólo se usa como fallback cuando el caller no pasa rango."""
    # PHASE-47 — los bounds vienen ya en la unidad del usuario: pedirlos con su
    # día hace que `latest` sea el ancla de SU último período, no la del mes
    # natural. Sin día declarado es exactamente lo de siempre.
    _, latest = await repository.get_transaction_month_bounds(
        db, user_id, cycle_start_day=cycle_start_day
    )
    now = datetime.now(UTC)
    year, month = (int(latest[:4]), int(latest[5:7])) if latest else (now.year, now.month)
    # El ancla identifica el período que ABRE en ese mes; sus extremos los da la
    # declaración única, que degenera en el mes natural sin día.
    anchor_day = cycle_start_day if cycle_start_day else 1
    start, end = user_month_bounds(date(year, month, anchor_day), cycle_start_day)
    return (
        datetime(start.year, start.month, start.day, tzinfo=UTC),
        datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=UTC),
    )


async def get_module_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    cycle_start_day: int | None = None,
) -> ModuleDashboardSummary:
    """PHASE-43.4 (ADR-0006) — tarjeta del módulo Finanzas Domésticas para el
    dashboard: flujo de caja del período + tasa de ahorro + veredicto.

    El período lo fija el navegador del dashboard (`date_from`/`date_to`); si no
    llega ninguno, se usa el ÚLTIMO mes con datos (no el mes natural en curso,
    que suele estar vacío para quien importa por meses).

    El veredicto lo da el signo del flujo de caja (decisión del usuario):
    positivo con margen → `healthy`; negativo con margen → `stressed`; dentro
    de ±5% del ingreso → `caution`; sin ingresos en el período → `neutral`.
    """
    if date_from is None or date_to is None:
        date_from, date_to = await _latest_month_bounds(
            db, user_id, cycle_start_day=cycle_start_day
        )

    summary = await get_summary(
        db,
        user_id,
        currency=currency,
        target_currency=target_currency,
        date_from=date_from,
        date_to=date_to,
    )

    income = summary.income
    balance = summary.balance
    savings_rate_pct = float(balance / income * 100) if income > 0 else None

    verdict: ModuleVerdict
    if income <= 0:
        verdict = "neutral"
    else:
        band = income * _CASHFLOW_VERDICT_BAND
        if balance > band:
            verdict = "healthy"
        elif balance < -band:
            verdict = "stressed"
        else:
            verdict = "caution"

    secondary: list[ModuleSummaryItem] = []
    if savings_rate_pct is not None:
        secondary.append(ModuleSummaryItem(label="Ahorro", value=f"{savings_rate_pct:.0f} %"))

    return ModuleDashboardSummary(
        verdict=verdict,
        headline_value=balance,
        headline_label="flujo neto",
        currency=summary.currency,
        secondary=secondary,
        link="/personal-finance/analysis",
    )


async def get_breakdown_by_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    kind: CategoryKind | None = None,
) -> list[CategoryBreakdownItem]:
    """Desglose por categoría."""
    legacy, target, _ = _resolve_mode(currency, target_currency)
    if target is not None:
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target,
            date_from=date_from,
            date_to=date_to,
        )
    rows = await repository.get_breakdown_by_category(
        db,
        user_id,
        currency=legacy,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        kind=kind,
    )
    items = [
        CategoryBreakdownItem(
            category_id=cat_id,
            category_name=cat_name if cat_name is not None else _UNCATEGORIZED_NAME,
            category_kind=cat_kind.value if cat_kind is not None else None,
            category_color=cat_color,
            category_icon=cat_icon,
            total=total,
            count=count,
            deferred_total=deferred,
        )
        for cat_id, cat_name, cat_kind, cat_color, cat_icon, total, count, deferred in rows
    ]
    items.sort(key=lambda i: i.total, reverse=True)
    return items


async def get_monthly_breakdown(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    year: int,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    cycle_start_day: int | None = None,
) -> list[MonthlyBucket]:
    """12 buckets mensuales para el año, o —si se pasa `[date_from, date_to]`
    (PHASE-41, período custom)— un bucket por cada mes tocado por el rango, con
    los meses de borde PARCIALES para que las barras cuadren con los KPIs de
    flujo del mismo rango.

    C4 — con `cycle_start_day`, cada bucket es un CICLO del usuario y su clave
    `YYYY-MM` es el ancla (el mes que lo abre). En la rama de rango, el relleno
    de huecos itera **anclas de ciclo**: iterar meses naturales sobre datos ya
    agrupados por ciclo produciría barras vacías al principio y al final del
    rango (el ciclo del 14-ago cubre trozos de agosto y de septiembre, pero es
    UNA barra, no dos)."""
    legacy, target, _ = _resolve_mode(currency, target_currency)
    if date_from is not None and date_to is not None:
        if target is not None:
            await ensure_rates_for_user_scope(
                db, user_id, target_currency=target, date_from=date_from, date_to=date_to
            )
        rows_range = await repository.get_totals_by_month_in_range(
            db,
            user_id,
            date_from=date_from,
            date_to=date_to,
            currency=legacy,
            target_currency=target,
            cycle_start_day=cycle_start_day,
        )
        income_r: dict[tuple[int, int], Decimal] = {}
        expenses_r: dict[tuple[int, int], Decimal] = {}
        for y, m, kind, total in rows_range:
            if kind == CategoryKind.INCOME:
                income_r[(y, m)] = total
            elif kind == CategoryKind.EXPENSE:
                expenses_r[(y, m)] = total
        buckets: list[MonthlyBucket] = []
        # `D = 1` degenera en el mes natural, así que la misma aritmética cubre
        # los dos modos sin una segunda rama que pueda divergir.
        step_day = cycle_start_day if cycle_start_day is not None else 1
        cy, cm = _cycle_anchor_of(date_from, step_day)
        last_y, last_m = _cycle_anchor_of(date_to, step_day)
        while (cy, cm) <= (last_y, last_m):
            inc = income_r.get((cy, cm), Decimal("0"))
            exp = expenses_r.get((cy, cm), Decimal("0"))
            buckets.append(
                MonthlyBucket(
                    month=f"{cy:04d}-{cm:02d}", income=inc, expenses=exp, balance=inc - exp
                )
            )
            cm += 1
            if cm > 12:
                cm = 1
                cy += 1
        return buckets
    if target is not None:
        # `by-month` cubre el año completo, así que el rango es ese. Con ciclo,
        # los 12 buckets se estiran hasta `D − 1` días dentro de enero del año
        # siguiente: el backfill de tasas cubre ese borde o el último ciclo
        # perdería sus últimos días por falta de tasa.
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target,
            date_from=datetime(year, 1, 1),
            date_to=datetime(year, 12, 31, 23, 59, 59) + timedelta(days=(cycle_start_day or 1) - 1),
        )
    rows = await repository.get_totals_by_month(
        db,
        user_id,
        year=year,
        currency=legacy,
        target_currency=target,
        cycle_start_day=cycle_start_day,
    )

    # C4 — con el ciclo activo la serie arranca en el ciclo que abrió el día D de
    # DICIEMBRE del año anterior, porque es el que contiene los días 1..D−1 de
    # enero. Sin él esos movimientos no caían en ninguna barra y el histórico en
    # ciclos no sumaba lo mismo que el natural, que es justo lo que la fase
    # promete: el ciclo cambia cómo se reparte el dinero, no cuánto hay.
    # PHASE-47 — DOCE buckets: los doce períodos que ABREN en el año pedido.
    #
    # Aquí hubo trece durante unas horas. El razonamiento era que los días 1..D−1
    # de enero pertenecen al período que abrió en diciembre del año anterior, así
    # que sin ese bucket extra ese dinero no salía en ninguna barra. Cierto — pero
    # la conclusión estaba mal: lo que faltaba no era una barra, era desplazar
    # también el AÑO. El usuario lo dijo al verlo: «si estoy viendo gastos de
    # 2026, no debería salir ese diciembre de 2025».
    #
    # Con el año del usuario (12-ene → 11-ene, `userYearBounds` en el frontend)
    # los doce períodos lo cubren entero, sin huecos ni bucket huérfano. Los días
    # 1..D−1 de enero caen en SU año anterior, que es la misma consecuencia que
    # ya acepta a nivel de mes.
    serie: list[tuple[int, int]] = [(year, m) for m in range(1, 13)]

    income_per_bucket: dict[tuple[int, int], Decimal] = {b: Decimal("0") for b in serie}
    expenses_per_bucket: dict[tuple[int, int], Decimal] = dict.fromkeys(serie, Decimal("0"))

    for row_year, month, kind, total in rows:
        clave = (row_year, month)
        if clave not in income_per_bucket:
            continue
        if kind == CategoryKind.INCOME:
            income_per_bucket[clave] = total
        elif kind == CategoryKind.EXPENSE:
            expenses_per_bucket[clave] = total

    return [
        MonthlyBucket(
            month=f"{y:04d}-{m:02d}",
            income=income_per_bucket[(y, m)],
            expenses=expenses_per_bucket[(y, m)],
            balance=income_per_bucket[(y, m)] - expenses_per_bucket[(y, m)],
        )
        for (y, m) in serie
    ]


async def get_top_expenses(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 10,
) -> list[TopExpenseItem]:
    """Top N gastos por importe convertido desc."""
    legacy, target, _ = _resolve_mode(currency, target_currency)
    if target is not None:
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target,
            date_from=date_from,
            date_to=date_to,
        )
    rows = await repository.get_top_expenses(
        db,
        user_id,
        currency=legacy,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return [
        TopExpenseItem(
            transaction_id=tx.id,
            description=tx.description,
            # `converted` viene en moneda destino cuando hay target. En
            # modo legacy es el amount original.
            amount=converted if converted is not None else tx.amount,
            flow=tx.flow,
            occurred_at=tx.occurred_at,
            category_id=tx.category_id,
            category_name=category_name,
            original_amount=tx.amount,
            original_currency=tx.currency,
        )
        for tx, category_name, converted in rows
    ]


async def get_category_available_periods(
    db: AsyncSession,
    user_id: uuid.UUID,
    category_id: uuid.UUID,
    *,
    cycle_start_day: int | None = None,
) -> CategoryAvailablePeriodsResponse:
    """Años + meses (1-12) con transacciones activas para una categoría.

    Excluye papelera. Años descendente, meses ascendente. 404 si la
    categoría no existe o no pertenece al usuario — fallback a 404
    en lugar de devolver una lista vacía para no enmascarar errores
    de routing en el cliente.

    C4 — con `cycle_start_day`, los `(año, mes)` son **anclas de ciclo**: los
    chips tienen que ofrecer los mismos períodos que luego pintan datos. Si los
    chips fueran meses naturales y las series ciclos, pulsar «febrero» podría
    aterrizar en un ciclo vacío.

    Sin ajuste, el helper devuelve `timezone('UTC', occurred_at)` — la misma
    expresión que ya usaban `by-month` y los bounds desde AUDIT-2026-07. Esta
    query leía `occurred_at` en crudo, así que dependía de la TZ de la sesión de
    PostgreSQL; ahora hay UNA sola forma de preguntar «¿de qué mes es esto?».
    """
    category = await get_category_by_id(db, category_id, user_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoría no encontrada.",
        )
    occurred = repository.cycle_shifted_occurred_at(cycle_start_day)
    query = (
        select(
            func.extract("year", occurred).label("year"),
            func.extract("month", occurred).label("month"),
        )
        .where(Transaction.user_id == user_id)
        .where(Transaction.category_id == category_id)
        .where(Transaction.deleted_at.is_(None))
        .distinct()
    )
    rows = (await db.execute(query)).all()
    months_by_year: dict[int, set[int]] = {}
    for year, month in rows:
        if year is None or month is None:
            continue
        months_by_year.setdefault(int(year), set()).add(int(month))
    items = [
        CategoryAvailablePeriodItem(year=year, months=sorted(months_by_year[year]))
        for year in sorted(months_by_year, reverse=True)
    ]
    return CategoryAvailablePeriodsResponse(periods=items)


async def get_category_detail(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    category_id: uuid.UUID,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    months_back: int = 12,
    cycle_start_day: int | None = None,
) -> CategoryDetailResponse:
    """PHASE-25 — drill-down de una categoría: KPIs (total, count,
    ticket medio) + evolución mensual (últimos `months_back` meses)
    + top tx del rango.

    404 si la categoría no existe / no es del usuario.

    C4 — `cycle_start_day` sólo afecta a la SERIE (`by_month`), que pasa a ser de
    ciclos. Los KPIs y el top ya se calculan sobre `[date_from, date_to]`, que
    llega recortado al ciclo desde el navegador.
    """
    category = await get_category_by_id(db, category_id, user_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoría no encontrada.",
        )
    legacy, target, resolved_currency = _resolve_mode(currency, target_currency)
    if target is not None:
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target,
            date_from=date_from,
            date_to=date_to,
        )
    total_raw, count = await repository.get_category_kpis(
        db,
        user_id,
        category_id=category_id,
        currency=legacy,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
    )
    # Quantize a céntimos para que la serialización de Pydantic produzca
    # siempre "0.00" en vez de "0" cuando no hay datos.
    total = total_raw.quantize(Decimal("0.01"))
    monthly = await repository.get_category_monthly_evolution(
        db,
        user_id,
        category_id=category_id,
        currency=legacy,
        target_currency=target,
        months_back=months_back,
        cycle_start_day=cycle_start_day,
    )
    top = await repository.get_category_top_transactions(
        db,
        user_id,
        category_id=category_id,
        currency=legacy,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        limit=10,
    )
    average = total / Decimal(count) if count > 0 else Decimal("0")
    return CategoryDetailResponse(
        category_id=category.id,
        category_name=category.name,
        category_kind=category.kind.value,
        category_color=category.color,
        category_icon=category.icon,
        currency=resolved_currency,
        total=total,
        count=count,
        average_amount=average.quantize(Decimal("0.01")),
        by_month=[CategoryMonthlyBucket(month=month, total=total_m) for month, total_m in monthly],
        top_transactions=[
            TopExpenseItem(
                transaction_id=tx.id,
                description=tx.description,
                amount=converted if converted is not None else tx.amount,
                flow=tx.flow,
                occurred_at=tx.occurred_at,
                category_id=tx.category_id,
                category_name=cat_name,
                original_amount=tx.amount,
                original_currency=tx.currency,
            )
            for tx, cat_name, converted in top
        ],
    )
