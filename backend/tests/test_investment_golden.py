"""Golden test con empresas reales (PHASE-44.7, ARCHITECTURE §7).

Recorre el pipeline COMPLETO —parser real de `edgartools` → anclaje → normalización
→ engine— sobre fixtures podadas de MCD, Realty Income y JNJ. Sin red (las
fixtures son la cache de la SEC podada a los conceptos mapeados) y sin BD (el
engine es puro).

Fija invariantes que un cambio silencioso de fórmula rompería:
- MCD publica resultado operativo → `ebit` SOURCED; no publica `Liabilities` →
  `total_liabilities` DERIVED; margen neto ~31,9%.
- Realty Income (REIT) y JNJ ya no publican resultado operativo → `ebit` DERIVED.
- Los márgenes netos cuadran con el cruzado (18,4% y 28,5%).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.modules.investment.analysis.engine import (
    base_ratios,
    dividend,
    evolution,
    forensic,
    stress,
    synthesis,
)
from app.modules.investment.analysis.engine.catalog import ALL_DEFAULT_THRESHOLDS
from app.modules.investment.analysis.engine.synthesis import SynthesisResult
from app.modules.investment.analysis.engine.types import SecuritySnapshot, StatementSeries
from app.modules.investment.enums import AccountingStd, SectorInternal
from app.modules.investment.fundamentals.adapters.annual import build_raw_filings
from app.modules.investment.fundamentals.adapters.base import SecurityIdentity
from app.modules.investment.fundamentals.adapters.edgar import EdgarAdapter
from app.modules.investment.fundamentals.canonical import CanonicalStatement, Provenance
from app.modules.investment.fundamentals.normalization import normalize

_FIXTURES = Path(__file__).parent / "fixtures" / "edgar"
_AS_OF = date(2026, 7, 1)


async def _statements(cik: str) -> list[CanonicalStatement]:
    adapter = EdgarAdapter(identity="", cache_dir=_FIXTURES)
    identity = SecurityIdentity(ticker="X", cik=cik, name="X")
    facts = await adapter.fetch_facts(identity)
    return [normalize(raw) for raw in build_raw_filings(facts, limit=8)]


def _run(
    statements: list[CanonicalStatement],
    *,
    sector: SectorInternal,
    is_reit: bool = False,
    is_financial: bool = False,
) -> SynthesisResult:
    snapshot = SecuritySnapshot(
        ticker="X",
        sector=sector,
        accounting_std=AccountingStd.GAAP,
        is_reit=is_reit,
        is_financial=is_financial,
    )
    series = StatementSeries(security=snapshot, statements=tuple(statements), as_of=_AS_OF)
    thresholds = ALL_DEFAULT_THRESHOLDS
    base = base_ratios.compute(series, thresholds)
    evo = evolution.compute(series, thresholds)
    forensic_result = forensic.compute(series, thresholds)
    last = series.years[-1]
    s2, s4 = base.get("S2", last), base.get("S4", last)
    bands = {"S2": s2.band if s2 else None, "S4": s4.band if s4 else None}
    div = dividend.compute(series, thresholds, forensic_bands=bands)
    st = stress.compute(series, None)
    return synthesis.compute(series, base, evo, forensic_result, div, st)


def _net_margin(statement: CanonicalStatement) -> Decimal:
    assert statement.revenue and statement.net_income is not None
    return statement.net_income / statement.revenue


async def test_golden_mcd() -> None:
    statements = await _statements("0000063908")
    assert len(statements) >= 3
    latest = statements[-1]
    assert Decimal("0.30") < _net_margin(latest) < Decimal("0.34")
    # MCD publica OperatingIncomeLoss → EBIT sourced; no publica Liabilities → derivado.
    assert latest.provenance_of("ebit") is Provenance.SOURCED
    assert latest.provenance_of("total_liabilities") is Provenance.DERIVED

    result = _run(statements, sector=SectorInternal.CONSUMER_DISCRETIONARY)
    assert {q.key for q in result.questions} == {"accounting", "cash", "dividend", "resilience"}
    assert result.confidence.value > 0


async def test_golden_realty_income_reit() -> None:
    statements = await _statements("0000726728")
    latest = statements[-1]
    assert Decimal("0.15") < _net_margin(latest) < Decimal("0.22")
    # Realty Income ya no publica resultado operativo → EBIT derivado del pretax.
    assert latest.provenance_of("ebit") is Provenance.DERIVED

    result = _run(statements, sector=SectorInternal.REAL_ESTATE, is_reit=True)
    assert result.confidence.value > 0


async def test_golden_jnj() -> None:
    statements = await _statements("0000200406")
    latest = statements[-1]
    assert Decimal("0.26") < _net_margin(latest) < Decimal("0.30")
    # JNJ dejó de publicar resultado operativo en 2015 → EBIT derivado.
    assert latest.provenance_of("ebit") is Provenance.DERIVED

    result = _run(statements, sector=SectorInternal.HEALTHCARE)
    assert result.confidence.value > 0


@pytest.mark.parametrize("cik", ["0000063908", "0000726728", "0000200406"])
async def test_pipeline_no_lanza_con_datos_reales(cik: str) -> None:
    """Contrato con edgartools: la forma real de `companyfacts` sigue encajando
    en el pipeline entero sin excepciones."""
    result = _run(await _statements(cik), sector=SectorInternal.UNKNOWN)
    assert result.dividend_verdict in {"healthy", "caution", "stressed", "not_applicable"}
