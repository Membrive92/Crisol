"""Router del módulo dashboard.

Todos los endpoints son GET (read-only). El `user_id` viene del JWT vía
`CurrentUser`.

Modo de moneda: dos parámetros mutuamente excluyentes (gana
`target_currency` si llegan ambos).

- `?currency=EUR` (legacy) — filtra por esa moneda y agrega importes
  crudos. Comportamiento pre-PHASE-8.3.
- `?target_currency=EUR` (PHASE-8.3) — no filtra; convierte cada
  transacción al destino con la tasa **del día de su `occurred_at`** y
  agrega después. Las transacciones sin tasa se cuentan en
  `unconvertible_count` (sólo `summary` lo expone).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.categories.models import CategoryKind
from app.modules.personal_finance.dashboard.schemas import (
    CategoryAvailablePeriodsResponse,
    CategoryBreakdownItem,
    CategoryDetailResponse,
    ModuleDashboardSummary,
    MonthlyBucket,
    SummaryResponse,
    TopExpenseItem,
)
from app.modules.personal_finance.dashboard.service import (
    get_breakdown_by_category,
    get_category_available_periods,
    get_category_detail,
    get_module_summary,
    get_monthly_breakdown,
    get_summary,
    get_top_expenses,
    list_user_currencies,
    resolve_cycle_start_day,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# C4 — «el histórico entero en ciclos». `cycle=true` cambia la PREGUNTA que
# responde el endpoint: en vez de «¿qué pasó en agosto?», «¿qué pasó de nómina a
# nómina?». Las dos siguen existiendo a propósito — sin el flag, el mes natural
# queda intacto aunque el usuario tenga su ciclo configurado.
#
# El día NUNCA viaja en la query: sale de `user.cycle_start_day`, que
# `CurrentUser` ya trae. Sin ajuste, `cycle=true` es 422 (ver
# `resolve_cycle_start_day`).
# El default va en cada firma (`= False`) y no aquí: FastAPI rechaza un `Query`
# con default dentro de `Annotated`.
_CYCLE_QUERY = Query(
    description=(
        "Agrupa por el ciclo del usuario (users.cycle_start_day) en vez de por "
        "mes natural. El día sale del perfil; sin ajuste configurado, 422."
    ),
)

_DEFAULT_CURRENCY = "USD"


def _resolve_currency_params(
    currency: str | None, target_currency: str | None
) -> tuple[str | None, str | None]:
    """Si no llega ninguno, default a `currency=USD` (legacy)."""
    if target_currency is None and currency is None:
        return _DEFAULT_CURRENCY, None
    return currency, target_currency


@router.get("/currencies", response_model=list[str])
async def currencies_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[str]:
    """Monedas distintas presentes en las transacciones del usuario."""
    return await list_user_currencies(db, user.id)


@router.get("/summary", response_model=SummaryResponse)
async def summary_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    cycle: Annotated[bool, _CYCLE_QUERY] = False,
) -> SummaryResponse:
    """Balance, ingresos, gastos y total de movimientos.

    Con `cycle=true`, el Δ «vs período anterior» compara con el ciclo anterior
    EXACTO y `available_from/to` son anclas de ciclo. Los totales del período no
    cambian: los fija `[date_from, date_to]`.
    """
    cur, target = _resolve_currency_params(currency, target_currency)
    return await get_summary(
        db,
        user.id,
        currency=cur,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        cycle_start_day=resolve_cycle_start_day(user.cycle_start_day, cycle),
    )


@router.get("/module-summary", response_model=ModuleDashboardSummary)
async def module_summary_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> ModuleDashboardSummary:
    """PHASE-43.4 — tarjeta del módulo Finanzas Domésticas para el dashboard
    (flujo del período + ahorro + veredicto). ADR-0006. Sin rango: último mes
    con datos."""
    cur, target = _resolve_currency_params(currency, target_currency)
    return await get_module_summary(
        db,
        user.id,
        currency=cur,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        # PHASE-47 — sin rango, la tarjeta cae al último período CON DATOS, y
        # ese período es el del usuario.
        cycle_start_day=user.cycle_start_day,
    )


@router.get("/by-category", response_model=list[CategoryBreakdownItem])
async def by_category_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    kind: CategoryKind | None = None,
) -> list[CategoryBreakdownItem]:
    """Totales por categoría."""
    cur, target = _resolve_currency_params(currency, target_currency)
    return await get_breakdown_by_category(
        db,
        user.id,
        currency=cur,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        kind=kind,
    )


@router.get("/by-month", response_model=list[MonthlyBucket])
async def by_month_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    year: int = Query(default_factory=lambda: datetime.now().year, ge=1970, le=2999),
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
    cycle: Annotated[bool, _CYCLE_QUERY] = False,
) -> list[MonthlyBucket]:
    """12 buckets mensuales para el año, o —con `date_from`+`date_to` (período
    custom)— un bucket por mes del rango, con bordes parciales.

    Con `cycle=true` cada bucket es un CICLO del usuario y su clave `YYYY-MM` es
    el mes que lo ABRE: en la vista de año, los 12 ciclos que abren en él."""
    cur, target = _resolve_currency_params(currency, target_currency)
    return await get_monthly_breakdown(
        db,
        user.id,
        year=year,
        currency=cur,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        cycle_start_day=resolve_cycle_start_day(user.cycle_start_day, cycle),
    )


@router.get(
    "/category/{category_id}/available-periods",
    response_model=CategoryAvailablePeriodsResponse,
)
async def category_available_periods_endpoint(
    category_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    cycle: Annotated[bool, _CYCLE_QUERY] = False,
) -> CategoryAvailablePeriodsResponse:
    """Años + meses con transacciones activas para la categoría dada.

    Alimenta el selector temporal del drill-down de categoría — sólo
    mostramos chips para periodos que tienen datos reales. Excluye
    papelera. Importante: ruta más específica antes que
    `/category/{category_id}` para que FastAPI no la confunda.

    Con `cycle=true` los `(año, mes)` son anclas de ciclo, para que los chips
    ofrezcan exactamente los períodos que luego pintan datos.
    """
    return await get_category_available_periods(
        db,
        user.id,
        category_id,
        cycle_start_day=resolve_cycle_start_day(user.cycle_start_day, cycle),
    )


@router.get("/category/{category_id}", response_model=CategoryDetailResponse)
async def category_detail_endpoint(
    category_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    months_back: Annotated[int, Query(ge=1, le=36)] = 12,
    cycle: Annotated[bool, _CYCLE_QUERY] = False,
) -> CategoryDetailResponse:
    """PHASE-25 — Drill-down de una categoría: KPIs en el rango +
    evolución mensual + top 10 transacciones. Para la pantalla que se
    abre al pulsar un item del 'Desglose de gastos' del dashboard.

    Con `cycle=true`, `by_month` es una serie de CICLOS (`months_back` recorta
    los últimos N) y cada clave `YYYY-MM` es el mes que abre el ciclo."""
    cur, target = _resolve_currency_params(currency, target_currency)
    return await get_category_detail(
        db,
        user.id,
        category_id=category_id,
        currency=cur,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        months_back=months_back,
        cycle_start_day=resolve_cycle_start_day(user.cycle_start_day, cycle),
    )


@router.get("/top-expenses", response_model=list[TopExpenseItem])
async def top_expenses_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=10, ge=1, le=50),
) -> list[TopExpenseItem]:
    """Top N gastos por importe (convertido si target_currency)."""
    cur, target = _resolve_currency_params(currency, target_currency)
    return await get_top_expenses(
        db,
        user.id,
        currency=cur,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
