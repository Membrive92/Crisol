"""Router de análisis (PHASE-44.7, ARCHITECTURE §5).

`analysis_runs` es scoped por usuario. El run es síncrono (<1s con datos ya
ingeridos); si no hay estados, 409 con instrucción de ingerir.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.investment.analysis.engine.catalog import ALL_METRIC_DEFINITIONS
from app.modules.investment.analysis.engine.flag_catalog import FLAG_HELP, FLAG_LABELS
from app.modules.investment.analysis.engine.score_help import SCORE_HELP
from app.modules.investment.analysis.engine.stress import StressParams
from app.modules.investment.analysis.engine.version import ENGINE_VERSION
from app.modules.investment.analysis.models import AnalysisRun
from app.modules.investment.analysis.schemas import (
    AnalysisRunListResponse,
    AnalysisRunResponse,
    AnalysisRunSummary,
    FlagHelpResponse,
    HelpCatalogResponse,
    MetricCatalogResponse,
    MetricDefinitionResponse,
    ReportLayerResponse,
    RunDiffResponse,
    RunRequest,
    ScoreComponentHelpResponse,
    ScoreHelpResponse,
    StressParamsRequest,
    ValuationMetricResponse,
    ValuationResponse,
)
from app.modules.investment.analysis.service import (
    build_report_layer,
    compare_runs,
    compute_security_valuation,
    get_latest_run,
    get_run,
    list_runs,
    run_analysis,
)
from app.modules.investment.pricing.adapters.base import PriceAdapter
from app.modules.investment.pricing.adapters.factory import get_price_adapter

router = APIRouter(prefix="/analysis", tags=["investment:analysis"])


def _to_stress_params(request: StressParamsRequest | None) -> StressParams | None:
    """Overrides del request → `StressParams`. Sin overrides → `None` (defaults
    del engine)."""
    if request is None:
        return None
    kwargs: dict[str, object] = {}
    if request.revenue_drops is not None:
        kwargs["revenue_drops"] = tuple(request.revenue_drops)
    if request.rate_shocks_bps is not None:
        kwargs["rate_shocks_bps"] = tuple(request.rate_shocks_bps)
    if request.pct_variable_debt is not None:
        kwargs["pct_variable_debt"] = request.pct_variable_debt
    return StressParams(**kwargs) if kwargs else None  # type: ignore[arg-type]


@router.get("/metrics", response_model=MetricCatalogResponse)
async def metric_catalog_endpoint(user: CurrentUser) -> MetricCatalogResponse:
    """El catálogo completo de métricas del engine: etiqueta, familia, unidad y
    cortes por defecto.

    Estático (no toca BD): es la definición del engine, no datos del usuario. Se
    sirve para que el cliente NO tenga que escribir las etiquetas a mano —
    hacerlo produjo tres rótulos que mentían sobre su propio número (PHASE-44.9).

    Ojo: los cortes que devuelve son los **por defecto** del engine. Los que se
    aplicaron a un análisis concreto viajan en `AnalysisRun.thresholds_used`,
    porque un `(sector × norma)` puede sobrescribirlos.
    """
    return MetricCatalogResponse(
        items=[MetricDefinitionResponse.model_validate(d) for d in ALL_METRIC_DEFINITIONS],
        engine_version=ENGINE_VERSION,
    )


@router.get("/help", response_model=HelpCatalogResponse)
async def help_catalog_endpoint(user: CurrentUser) -> HelpCatalogResponse:
    """Los textos de ayuda que el catálogo de métricas no puede llevar.

    La ficha de cada score forense con el nombre de cada una de sus variables, y
    la de cada bandera con dónde comprobarla en las cuentas.
    Sin esto la tarjeta de desglose imprimía la clave del motor y el usuario leía
    `DSRI` y `P4_cfo_supera_beneficio` en pantalla (PHASE-44.24.A).

    Estático, como `/metrics`: es la definición del engine, no datos del usuario.
    Va ANTES de `/{security_id}/runs` por el mismo motivo de orden que el resto
    del router — `help` no debe parsearse como un UUID de security.
    """
    return HelpCatalogResponse(
        scores=[
            ScoreHelpResponse(
                key=key,
                what=entry.what,
                why=entry.why,
                reading=entry.reading,
                components=[
                    ScoreComponentHelpResponse(
                        key=component_key, label=component.label, what=component.what
                    )
                    for component_key, component in entry.components.items()
                ],
            )
            for key, entry in SCORE_HELP.items()
        ],
        flags=[
            FlagHelpResponse(
                key=key,
                label=FLAG_LABELS[key],
                what=entry.what,
                why=entry.why,
                reading=entry.reading,
                how_to_verify=entry.how_to_verify,
            )
            for key, entry in FLAG_HELP.items()
        ],
        engine_version=ENGINE_VERSION,
    )


# `/runs/{run_id}` antes de `/{security_id}/runs` (mismo motivo de orden que en
# los otros routers: "runs" no debe parsearse como un UUID de security).
async def _with_report(db: AsyncSession, run: AnalysisRun) -> AnalysisRunResponse:
    """El run serializado MÁS su capa de lectura (PHASE-44.24.C).

    Vive aquí y no en el servicio porque es donde ocurre la serialización: el
    servicio devuelve el objeto ORM y `model_validate` lo convierte. Las tres
    rutas que sirven un run entero pasan por esta función, así que no puede
    haber una que devuelva el run sin su capa.
    """
    response = AnalysisRunResponse.model_validate(run)
    response.report = ReportLayerResponse.model_validate(
        await build_report_layer(db, run), from_attributes=True
    )
    return response


@router.get("/runs/{run_id}", response_model=AnalysisRunResponse)
async def get_run_endpoint(
    run_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AnalysisRunResponse:
    """Un análisis por id (con todo el desglose)."""
    return await _with_report(db, await get_run(db, run_id, user.id))


@router.post("/{security_id}/run", response_model=AnalysisRunResponse)
async def run_endpoint(
    security_id: uuid.UUID,
    body: RunRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AnalysisRunResponse:
    """Ejecuta el engine sobre los estados ingeridos y persiste el análisis.

    404 si el valor no está en el catálogo; 409 si no hay estados financieros
    ingeridos (hay que lanzar la ingesta primero).
    """
    run = await run_analysis(
        db,
        security_id=security_id,
        user_id=user.id,
        stress_params=_to_stress_params(body.stress_params),
    )
    await db.commit()
    return await _with_report(db, run)


# Antes de `/{security_id}/runs`: si no, no habría ambigüedad de path (tienen
# distinto número de segmentos), pero se declara junto para que se lean seguidos.
@router.get("/{security_id}/runs/latest", response_model=AnalysisRunResponse)
async def get_latest_run_endpoint(
    security_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AnalysisRunResponse:
    """El último análisis de un valor, con todo el desglose. 404 si no hay ninguno.

    Es lo que abre la pantalla de informe: sin él, el informe sólo existía
    mientras durase la respuesta de `POST /run` y desaparecía al recargar.
    """
    return await _with_report(db, await get_latest_run(db, security_id, user.id))


@router.get("/{security_id}/runs/compare", response_model=RunDiffResponse)
async def compare_runs_endpoint(
    security_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    base: uuid.UUID | None = None,
    target: uuid.UUID | None = None,
) -> RunDiffResponse:
    """Qué ha cambiado entre dos análisis del mismo valor (PHASE-44.24.F).

    Sin `base` ni `target`, compara los dos últimos. 404 si no hay dos, o si
    alguno de los ids no pertenece a este valor.

    Si el motor o la calibración difieren, `comparable` es `false` y las listas
    de cambios de la EMPRESA vienen vacías: presentar un cambio de banda como
    una degradación del negocio cuando lo que se movió fue el corte lleva a la
    conclusión contraria.
    """
    diff = await compare_runs(db, security_id, user.id, base, target)
    return RunDiffResponse.model_validate(diff, from_attributes=True)


@router.get("/{security_id}/runs", response_model=AnalysisRunListResponse)
async def list_runs_endpoint(
    security_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AnalysisRunListResponse:
    """Histórico de análisis de un valor (del más reciente al más antiguo)."""
    runs = await list_runs(db, security_id, user.id)
    return AnalysisRunListResponse(items=[AnalysisRunSummary.model_validate(r) for r in runs])


@router.get("/{security_id}/valuation", response_model=ValuationResponse)
async def valuation_endpoint(
    security_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    adapter: Annotated[PriceAdapter, Depends(get_price_adapter)],
    price: Annotated[
        Decimal | None,
        Query(gt=0, description="Precio a simular. Sin él se usa la cotización del proveedor."),
    ] = None,
) -> ValuationResponse:
    """Múltiplos de valoración contra la cotización viva (PHASE-44.12).

    **No sale del `AnalysisRun` y no se persiste.** Un múltiplo se mueve con el
    precio, así que guardarlo dentro del run haría que reejecutar un análisis
    antiguo diera otro número — y la reproducibilidad es lo que justifica que el
    motor forense sea book-based.

    Nunca devuelve error por falta de cotización: responde 200 con
    `available=false` y el motivo, que es lo que la pantalla enseña.
    """
    outcome = await compute_security_valuation(db, adapter, security_id, price_override=price)
    await db.commit()  # el refresco de cotización y tipos puede haber escrito

    if outcome.result is None:
        return ValuationResponse(
            available=False,
            reason=outcome.reason,
            price_is_override=outcome.price_is_override,
            provider_status=outcome.provider_status,
        )

    result = outcome.result
    return ValuationResponse(
        available=True,
        reason=None,
        price_is_override=outcome.price_is_override,
        metrics=[
            ValuationMetricResponse(key=m.key, value=m.value, status=m.status, reason=m.reason)
            for m in result.metrics
        ],
        fiscal_year=result.fiscal_year,
        fiscal_year_end=result.fiscal_year_end,
        statement_currency=result.statement_currency,
        market_cap=result.market_cap,
        enterprise_value=result.enterprise_value,
        quote_as_of=result.quote_as_of,
        quote_stale=result.quote_stale,
        provider_status=result.provider_status,
        fx_rate=result.fx_rate,
        fx_as_of=result.fx_as_of,
        days_since_fiscal_year_end=result.days_since_fiscal_year_end,
        staleness=result.staleness,
        notes=list(result.notes),
    )
