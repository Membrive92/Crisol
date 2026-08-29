"""Servicio de análisis (PHASE-44.7, ARCHITECTURE §4.2).

Cablea el engine PURO a la persistencia: lee los `FinancialStatement` de un
valor, reconstruye la serie canónica que el engine consume, encadena las 6 capas
y persiste el `AnalysisRun`. El engine no toca BD ni reloj; toda la impureza vive
aquí.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.currency import service as currency_service
from app.modules.investment.analysis import repository as repo
from app.modules.investment.analysis.engine import (
    base_ratios,
    dividend,
    evolution,
    forensic,
    stress,
    synthesis,
)
from app.modules.investment.analysis.engine.catalog import definition_for
from app.modules.investment.analysis.engine.sector_profiles import resolve_thresholds
from app.modules.investment.analysis.engine.stress import StressParams
from app.modules.investment.analysis.engine.types import (
    MetricResult,
    SecuritySnapshot,
    StatementSeries,
)
from app.modules.investment.analysis.engine.valuation import (
    ValuationInputs,
    ValuationResult,
    compute_valuation,
)
from app.modules.investment.analysis.engine.version import ENGINE_VERSION
from app.modules.investment.analysis.models import AnalysisRun
from app.modules.investment.analysis.presentation import (
    ReportLayer,
    RunDiff,
    build_report,
    diff_runs,
    profile_of,
)
from app.modules.investment.analysis.serialization import to_json_safe
from app.modules.investment.catalog.capabilities import capabilities_for
from app.modules.investment.catalog.models import Security
from app.modules.investment.catalog.service import get_security
from app.modules.investment.fundamentals import repository as fundamentals_repo
from app.modules.investment.fundamentals.canonical import (
    CANONICAL_ITEMS,
    CanonicalStatement,
    Provenance,
)
from app.modules.investment.fundamentals.models import FinancialStatement
from app.modules.investment.pricing.adapters.base import PriceAdapter
from app.modules.investment.pricing.service import quote_security
from app.modules.investment.thresholds.service import load_thresholds, thresholds_hash


@dataclass(frozen=True)
class ValuationOutcome:
    """Múltiplos, o el motivo por el que no hay ninguno.

    `reason` no es un log: es la frase que lee el usuario en la pantalla, así
    que dice qué falta y qué puede hacer al respecto."""

    result: ValuationResult | None
    reason: str | None
    price_is_override: bool
    provider_status: str = "cached"
    """Estado del proveedor. Viaja también cuando NO hay múltiplos: es
    justamente cuando el usuario necesita saber si el servicio está caído o si
    es que este valor no se cotiza."""


def _statement_from_row(row: FinancialStatement) -> CanonicalStatement:
    """`FinancialStatement` (ORM) → `CanonicalStatement` (puro).

    Reconstruye `item_provenance` desde `raw_source_ref['mapping']`: el ORM no
    tiene columna de procedencia, pero el mapeo guarda la de cada partida. Sin
    esto, un `imputed_zero` contaría como SOURCED e inflaría la confianza (§4.5).
    """
    values = {item: getattr(row, item) for item in CANONICAL_ITEMS}
    mapping = row.raw_source_ref.get("mapping", {}) if isinstance(row.raw_source_ref, dict) else {}
    item_provenance: dict[str, Provenance] = {}
    for item in CANONICAL_ITEMS:
        trace = mapping.get(item)
        prov = trace.get("provenance") if isinstance(trace, dict) else None
        if not prov or prov == Provenance.SOURCED.value:
            continue
        try:
            item_provenance[item] = Provenance(prov)
        except ValueError:  # una procedencia desconocida no debe romper el análisis
            continue
    return CanonicalStatement(
        fiscal_year=row.fiscal_year,
        fiscal_year_end=row.fiscal_year_end,
        accounting_std=row.accounting_std,
        currency=row.currency,
        filing_accession=row.filing_accession,
        item_provenance=item_provenance,
        raw_source_ref=row.raw_source_ref if isinstance(row.raw_source_ref, dict) else {},
        **values,
    )


async def build_series(db: AsyncSession, security: Security, *, as_of: date) -> StatementSeries:
    """La serie canónica vigente de un valor (una vista por año, ascendente)."""
    rows = await fundamentals_repo.list_statements(db, security.id, latest_only=True)
    snapshot = SecuritySnapshot(
        ticker=security.ticker,
        sector=security.sector,
        accounting_std=security.accounting_std,
        is_financial=security.is_financial,
        is_reit=security.is_reit,
    )
    return StatementSeries(
        security=snapshot,
        statements=tuple(_statement_from_row(row) for row in rows),
        as_of=as_of,
    )


def _value(metric: MetricResult | None) -> object:
    return metric.value if metric is not None else None


def _int_value(metric: MetricResult | None) -> int | None:
    if metric is None or metric.value is None:
        return None
    return int(metric.value)


async def run_analysis(
    db: AsyncSession,
    *,
    security_id: uuid.UUID,
    user_id: uuid.UUID,
    as_of: date | None = None,
    stress_params: StressParams | None = None,
) -> AnalysisRun:
    """Ejecuta el engine sobre los estados ingeridos y persiste el run.

    404 si el valor no está en el catálogo; 409 si no hay estados ingeridos
    todavía (hay que lanzar la ingesta primero).
    """
    security = await get_security(db, security_id)
    run_at = datetime.now(UTC)
    reference = as_of or run_at.date()

    series = await build_series(db, security, as_of=reference)
    if not series.statements:
        # Antes esto era un 409 único que decía "lanza la ingesta primero" incluso
        # para un valor cuya ingesta NO puede funcionar nunca (sin CIK no hay
        # filing en EDGAR): el usuario la lanzaba, fallaba, y no había forma de
        # entender por qué. 422 = la petición no es procesable para ESTE valor,
        # con el motivo; 409 = falta un paso que sí existe (PHASE-44.8 E1).
        caps = capabilities_for(cik=security.cik, analysis_status=security.analysis_status)
        if not caps.analysis_available:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{security.ticker}: {caps.reason}",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No hay estados financieros ingeridos para {security.ticker}. "
                "Lanza la ingesta primero."
            ),
        )

    thresholds = await load_thresholds(
        db,
        security.sector,
        security.accounting_std,
        # El perfil financiero es del VALOR: un holding clasificado en otro
        # sector puede serlo, y entonces manda su perfil sobre el del sector.
        is_financial=security.is_financial,
    )
    thresholds_version = thresholds_hash(thresholds)

    base = base_ratios.compute(series, thresholds)
    evolution_result = evolution.compute(series, thresholds)
    forensic_result = forensic.compute(series, thresholds)

    last_year = series.years[-1]
    s2 = base.get("S2", last_year)
    s4 = base.get("S4", last_year)
    forensic_bands = {"S2": s2.band if s2 else None, "S4": s4.band if s4 else None}
    dividend_result = dividend.compute(series, thresholds, forensic_bands=forensic_bands)
    stress_result = stress.compute(series, stress_params)
    synthesis_result = synthesis.compute(
        series, base, evolution_result, forensic_result, dividend_result, stress_result
    )

    z_definition = definition_for("z_score")
    run = AnalysisRun(
        security_id=security_id,
        user_id=user_id,
        run_date=run_at,
        engine_version=ENGINE_VERSION,
        thresholds_version=thresholds_version,
        # El juego EFECTIVO, no una referencia a él: `scoring_thresholds` se
        # muta in situ al resembrar y el hash es irreversible, así que sin
        # guardar los cortes aquí el run no se puede explicar más tarde.
        thresholds_used=to_json_safe(thresholds),
        years_covered=list(series.years),
        m_score=_value(forensic_result.get("m_score", last_year)),
        z_score=_value(forensic_result.get("z_score", last_year)),
        z_variant=z_definition.model_variant if z_definition is not None else None,
        f_score=_int_value(forensic_result.get("f_score", last_year)),
        accruals_ratio=_value(forensic_result.get("accruals", last_year)),
        fcf_payout=_value(dividend_result.get("D2", last_year)),
        fcf_coverage=_value(dividend_result.get("D3", last_year)),
        dividend_verdict=synthesis_result.dividend_verdict,
        confidence=synthesis_result.confidence.value,
        scores_detail={
            "forensic": to_json_safe(forensic_result),
            "base_ratios": to_json_safe(base),
        },
        dividend_analysis=to_json_safe(dividend_result),
        evolution=to_json_safe(evolution_result),
        flags=[to_json_safe(flag) for flag in synthesis_result.flags],
        verdict={
            "questions": to_json_safe(synthesis_result.questions),
            "safety_profile": to_json_safe(synthesis_result.safety_profile),
            "dividend_verdict": synthesis_result.dividend_verdict,
            "stress": to_json_safe(stress_result),
        },
        data_completeness=to_json_safe(synthesis_result.confidence),
    )
    return await repo.add_run(db, run)


async def list_runs(
    db: AsyncSession, security_id: uuid.UUID, user_id: uuid.UUID
) -> list[AnalysisRun]:
    return await repo.list_runs(db, security_id, user_id)


async def get_run(db: AsyncSession, run_id: uuid.UUID, user_id: uuid.UUID) -> AnalysisRun:
    run = await repo.get_run(db, run_id, user_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Análisis no encontrado.")
    return run


async def get_latest_run(
    db: AsyncSession, security_id: uuid.UUID, user_id: uuid.UUID
) -> AnalysisRun:
    """El último análisis de un valor. 404 si nunca se ha ejecutado ninguno."""
    run = await repo.get_latest_run(db, security_id, user_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Este valor no tiene ningún análisis todavía.",
        )
    return run


# ── Valoración por múltiplos (PHASE-44.12) ────────────────────────────
#
# La capa impura de `engine/valuation.py`: resuelve el precio y el tipo de
# cambio y se los da ya masticados al módulo puro. Todo el IO vive aquí porque
# el gate `test_el_engine_no_importa_io` prohíbe `pricing` y `currency` dentro
# del engine — y esa frontera es la que permite probar los múltiplos con un
# estado sintético y un Decimal.
#
# NO se persiste nada. Un múltiplo se mueve con la cotización, así que meterlo
# en el `AnalysisRun` haría que reejecutar un run antiguo diera otro número y se
# perdería la reproducibilidad que justifica todo el motor forense.


async def compute_security_valuation(
    db: AsyncSession,
    adapter: PriceAdapter,
    security_id: uuid.UUID,
    *,
    price_override: Decimal | None = None,
    as_of: date | None = None,
) -> ValuationOutcome:
    """Múltiplos de un valor contra su cotización viva.

    `price_override` permite simular ("¿y si entrara a 250 $?") y también cubre
    a los valores que el proveedor no cotiza. Se declara en la respuesta para
    que nadie confunda un precio inventado con uno de mercado.

    ⚠️ Puede COMMITEAR: `quote_security` asegura los tipos de cambio del día y
    ésos se confirman por dentro (ADR-0009). No la llames en mitad de una unidad
    de trabajo propia.
    """
    security = await get_security(db, security_id)
    today = as_of or datetime.now(UTC).date()
    series = await build_series(db, security, as_of=today)

    if series.latest is None:
        return ValuationOutcome(
            result=None,
            reason="Este valor no tiene ningún ejercicio ingerido todavía.",
            price_is_override=price_override is not None,
        )

    statement_currency = (series.latest.currency or "").upper()

    if price_override is not None:
        inputs = ValuationInputs(
            price=price_override,
            quote_as_of=today,
            quote_currency=statement_currency,
            # Con precio a mano no se ha consultado a nadie: decir "live" sería
            # afirmar que el proveedor responde sin haberlo comprobado.
            provider_status="cached",
        )
        return ValuationOutcome(
            result=compute_valuation(series, inputs),
            reason=None,
            price_is_override=True,
        )

    quoted = await quote_security(db, adapter, security)
    quote = quoted.quote
    if quote is None:
        return ValuationOutcome(
            result=None,
            reason=(
                "El proveedor de cotizaciones no ha respondido y no hay ningún precio "
                "guardado de antes. Puedes introducir uno a mano."
                if quoted.provider_status == "unreachable"
                else "No hay cotización de este valor, así que no se pueden calcular "
                "los múltiplos. Puedes introducir un precio a mano."
            ),
            price_is_override=False,
            provider_status=quoted.provider_status,
        )

    price = quote.price
    quote_currency = (quote.currency or "").upper()
    fx_rate: Decimal | None = None
    fx_as_of: date | None = None

    if quote_currency and statement_currency and quote_currency != statement_currency:
        # `convert` NO lanza cuando falta la tasa: devuelve el importe sin
        # convertir y `rate=1` (ADR-0009). Tomarlo por bueno mezclaría divisas
        # en un múltiplo sin que se notara, así que se comprueba el fallback.
        conversion = await currency_service.convert(
            db,
            amount=Decimal(1),
            from_currency=quote_currency,
            to_currency=statement_currency,
            at_date=quote.as_of.date(),
        )
        if conversion.fallback == "missing":
            return ValuationOutcome(
                result=None,
                reason=(
                    f"No hay tipo de cambio {quote_currency}→{statement_currency} para "
                    "convertir la cotización a la divisa de las cuentas."
                ),
                price_is_override=False,
                provider_status=quoted.provider_status,
            )
        fx_rate = conversion.rate
        fx_as_of = conversion.rate_date
        price = price * conversion.rate

    ttl = timedelta(hours=settings.price_ttl_hours)
    inputs = ValuationInputs(
        price=price,
        quote_as_of=quote.as_of.date(),
        quote_currency=quote_currency or statement_currency,
        quote_stale=(datetime.now(UTC) - quote.fetched_at) >= ttl,
        provider_status=quoted.provider_status,
        fx_rate=fx_rate,
        fx_as_of=fx_as_of,
    )
    return ValuationOutcome(
        result=compute_valuation(series, inputs),
        reason=None,
        price_is_override=False,
        provider_status=quoted.provider_status,
    )


# ── La capa de lectura, adjuntada al servir (PHASE-44.24.C) ───────────


async def build_report_layer(db: AsyncSession, run: AnalysisRun) -> ReportLayer:
    """La capa de lectura de un run: distancia, orden y procedencia.

    Vive AQUÍ y no en el router porque necesita cargar el `Security` y resolver
    los umbrales de hoy — dos cosas impuras que la capa de presentación no puede
    hacer por sí misma, y que por eso recibe por parámetro.

    La resolución de hoy sólo se usa para DERIVAR la procedencia de los runs que
    no la registran (motor < 1.7.0). Los posteriores la traen dentro y no se
    infiere nada.
    """
    security = await get_security(db, run.security_id)
    profile = profile_of(
        security.sector, is_financial=security.is_financial, is_reit=security.is_reit
    )
    return build_report(
        verdict=run.verdict or {},
        thresholds_used=run.thresholds_used,
        profile=profile,
        profile_thresholds=resolve_thresholds(
            security.sector, security.accounting_std, is_financial=security.is_financial
        ),
    )


async def compare_runs(
    db: AsyncSession,
    security_id: uuid.UUID,
    user_id: uuid.UUID,
    base_id: uuid.UUID | None,
    target_id: uuid.UUID | None,
) -> RunDiff:
    """Compara dos análisis del mismo valor.

    Sin ids, compara los dos ÚLTIMOS: es la pregunta por defecto («¿qué ha
    cambiado desde la última vez?»). 404 si no hay dos.

    Las reexpresiones se acotan a la ventana ENTRE las dos fechas: una
    reexpresión anterior al primer análisis ya está dentro de los dos y no
    explica nada de lo que se mueve.
    """
    runs = sorted(await repo.list_runs(db, security_id, user_id), key=lambda r: r.run_date)
    if len(runs) < 2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hacen falta dos análisis de este valor para poder compararlos.",
        )
    by_id = {r.id: r for r in runs}

    def _own(run_id: uuid.UUID) -> AnalysisRun:
        run = by_id.get(run_id)
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ese análisis no pertenece a este valor.",
            )
        return run

    # Las CUATRO combinaciones, explícitas. La versión anterior sólo distinguía
    # «los dos ids» de «ninguno», así que una selección parcial —que es lo que
    # manda móvil, y web mientras no se elija base— caía en «los dos últimos» y
    # devolvía la comparación de OTROS dos runs, con sus fechas en la cabecera.
    if target_id is not None and base_id is not None:
        base, target = _own(base_id), _own(target_id)
    elif target_id is not None:
        target = _own(target_id)
        anteriores = [r for r in runs if r.run_date < target.run_date]
        if not anteriores:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ese análisis es el más antiguo: no hay ninguno anterior con el que compararlo.",
            )
        base = anteriores[-1]
    elif base_id is not None:
        base = _own(base_id)
        target = runs[-1]
    else:
        base, target = runs[-2], runs[-1]

    # La guarda va DESPUÉS de resolver las cuatro ramas, no dentro de una.
    # Estaba sólo en la de `base` suelto, así que pedir el mismo id como base y
    # como target devolvía un diff vacío — y la pantalla lo anuncia como «nada
    # se ha movido», que es cierto y engañoso a la vez.
    if base.id == target.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se puede comparar un análisis consigo mismo.",
        )

    # Base es SIEMPRE el más antiguo, elija el usuario el orden que elija: un
    # diff al revés diría que un score «mejoró» cuando empeoró.
    if base.run_date > target.run_date:
        base, target = target, base

    restatements = await repo.list_restatements_between(
        db, security_id, base.run_date, target.run_date
    )
    return diff_runs(_run_payload(base), _run_payload(target), restatements)


def _run_payload(run: AnalysisRun) -> dict[str, Any]:
    """El run como diccionario plano, que es lo que la capa PURA sabe leer."""
    return {
        "id": run.id,
        "run_date": run.run_date,
        "engine_version": run.engine_version,
        "thresholds_version": run.thresholds_version,
        "years_covered": list(run.years_covered),
        "scores_detail": run.scores_detail,
        "evolution": run.evolution,
        "dividend_analysis": run.dividend_analysis,
        "flags": run.flags,
        "verdict": run.verdict,
    }
