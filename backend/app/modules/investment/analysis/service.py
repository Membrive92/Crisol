"""Servicio de análisis (PHASE-44.7, ARCHITECTURE §4.2).

Cablea el engine PURO a la persistencia: lee los `FinancialStatement` de un
valor, reconstruye la serie canónica que el engine consume, encadena las 6 capas
y persiste el `AnalysisRun`. El engine no toca BD ni reloj; toda la impureza vive
aquí.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.modules.investment.analysis.engine.stress import StressParams
from app.modules.investment.analysis.engine.types import (
    MetricResult,
    SecuritySnapshot,
    StatementSeries,
)
from app.modules.investment.analysis.engine.version import ENGINE_VERSION
from app.modules.investment.analysis.models import AnalysisRun
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
from app.modules.investment.thresholds.service import load_thresholds, thresholds_hash


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

    thresholds = await load_thresholds(db, security.sector, security.accounting_std)
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
