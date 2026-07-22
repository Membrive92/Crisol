"""Tests del engine de análisis — Capa 1 (PHASE-44.2, ARCHITECTURE §7).

El engine es PURO: estos tests no tocan BD ni red y corren en milisegundos.

Los valores esperados están calculados a mano sobre una empresa sintética
cuadrada (activo = pasivo + patrimonio) con importes redondos. Nada de
aserciones "≥ 0": una comprobación de signo pasa igual con la fórmula
equivocada — es la lección de PHASE-41.
"""

from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.modules.investment.analysis.engine import base_ratios
from app.modules.investment.analysis.engine import derivations as dv
from app.modules.investment.analysis.engine.base_ratios import (
    DEFAULT_THRESHOLDS,
    METRIC_CATALOG,
    METRIC_KEYS,
    BaseRatiosResult,
)
from app.modules.investment.analysis.engine.conventions import avg_balance
from app.modules.investment.analysis.engine.types import (
    MetricResult,
    SecuritySnapshot,
    StatementSeries,
    ThresholdSpec,
)
from app.modules.investment.analysis.engine.version import ENGINE_VERSION
from app.modules.investment.enums import AccountingStd, SectorInternal, ThresholdDirection
from app.modules.investment.fundamentals.canonical import (
    CANONICAL_ITEMS,
    CanonicalStatement,
    Provenance,
    combine_provenance,
)


def dec(value: str | int) -> Decimal:
    return Decimal(value)


def approx_dec(value: Decimal | None, expected: str, places: int = 6) -> None:
    """Compara con precisión fija — para ratios con decimal periódico."""
    assert value is not None, "se esperaba un valor calculado, no un hueco"
    quantum = Decimal(10) ** -places
    assert value.quantize(quantum) == Decimal(expected).quantize(
        quantum
    ), f"esperado {expected}, obtenido {value}"


# ── Empresa sintética ─────────────────────────────────────────────────
#
# Balance cuadrado en los dos ejercicios:
#   2023: activo 2.000 = pasivo 1.200 + patrimonio 800
#   2024: activo 2.400 = pasivo 1.400 + patrimonio 1.000


def _statement_2023() -> CanonicalStatement:
    return CanonicalStatement(
        fiscal_year=2023,
        fiscal_year_end=date(2023, 12, 31),
        accounting_std=AccountingStd.GAAP,
        cash=dec(100),
        current_financial_assets=dec(50),
        receivables=dec(200),
        inventory=dec(300),
        current_assets=dec(800),
        total_assets=dec(2000),
        short_term_debt=dec(100),
        ltd_current_portion=dec(50),
        accounts_payable=dec(150),
        current_liabilities=dec(400),
        long_term_debt=dec(600),
        total_liabilities=dec(1200),
        equity=dec(800),
        revenue=dec(1600),
        cogs=dec(1000),
        depreciation_amortization=dec(80),
        impairments=dec(0),
        gains_on_sale_of_business=dec(0),
        ebit=dec(300),
        interest_expense=dec(50),
        taxes=dec(50),
        net_income=dec(200),
        shares_basic=dec(100),
        cfo=dec(400),
        capex=dec(150),
        dividends_paid=dec(80),
        taxes_paid=dec(50),
    )


def _statement_2024() -> CanonicalStatement:
    return CanonicalStatement(
        fiscal_year=2024,
        fiscal_year_end=date(2024, 12, 31),
        accounting_std=AccountingStd.GAAP,
        cash=dec(200),
        current_financial_assets=dec(100),
        receivables=dec(300),
        inventory=dec(400),
        current_assets=dec(1200),
        total_assets=dec(2400),
        short_term_debt=dec(100),
        ltd_current_portion=dec(100),
        accounts_payable=dec(250),
        current_liabilities=dec(600),
        long_term_debt=dec(600),
        total_liabilities=dec(1400),
        equity=dec(1000),
        revenue=dec(2000),
        cogs=dec(1200),
        depreciation_amortization=dec(100),
        impairments=dec(0),
        gains_on_sale_of_business=dec(0),
        ebit=dec(400),
        interest_expense=dec(50),
        taxes=dec(70),
        net_income=dec(280),
        shares_basic=dec(100),
        cfo=dec(500),
        capex=dec(200),
        dividends_paid=dec(100),
        taxes_paid=dec(70),
    )


def _security() -> SecuritySnapshot:
    return SecuritySnapshot(
        ticker="SYNT",
        sector=SectorInternal.INDUSTRIALS,
        accounting_std=AccountingStd.GAAP,
    )


@pytest.fixture
def series() -> StatementSeries:
    return StatementSeries(
        security=_security(),
        statements=(_statement_2023(), _statement_2024()),
        as_of=date(2025, 3, 31),
    )


@pytest.fixture
def result(series: StatementSeries) -> BaseRatiosResult:
    return base_ratios.compute(series)


def _metric(result: BaseRatiosResult, key: str, year: int = 2024) -> MetricResult:
    metric = result.get(key, year)
    assert metric is not None, f"la métrica {key} debe existir SIEMPRE (§4.5)"
    return metric


# ── Catálogo ──────────────────────────────────────────────────────────


def test_catalogo_tiene_27_metricas_con_claves_unicas() -> None:
    assert len(METRIC_CATALOG) == 27
    assert len(set(METRIC_KEYS)) == 27


def test_catalogo_cubre_las_cuatro_familias() -> None:
    familias = {definition.family for definition in METRIC_CATALOG}
    assert familias == {"liquidez", "actividad", "solvencia", "rentabilidad"}


def test_las_metricas_sin_banda_absoluta_no_tienen_umbral_por_defecto() -> None:
    """A1-A5, R1-R4 y R8 se juzgan por deriva (capa 1.5), no por banda."""
    sin_banda = {"A1", "A2", "A3", "A4", "A5", "R1", "R2", "R3", "R4", "R8"}
    assert set(METRIC_KEYS) - set(DEFAULT_THRESHOLDS) == sin_banda


def test_compute_devuelve_todas_las_metricas_para_todos_los_años(
    result: BaseRatiosResult,
) -> None:
    for year in (2023, 2024):
        claves = {m.key for m in result.by_year(year)}
        assert claves == set(METRIC_KEYS)


def test_engine_version_es_semver() -> None:
    partes = ENGINE_VERSION.split(".")
    assert len(partes) == 3 and all(p.isdigit() for p in partes)


# ── Liquidez ──────────────────────────────────────────────────────────


def test_l1_ratio_corriente(result: BaseRatiosResult) -> None:
    """1.200 / 600 = 2,0."""
    metric = _metric(result, "L1")
    assert metric.value == dec(2)
    assert metric.status == "ok"
    assert metric.band == "healthy"


def test_l2_prueba_acida(result: BaseRatiosResult) -> None:
    """(1.200 − 400) / 600 = 1,3333."""
    approx_dec(_metric(result, "L2").value, "1.333333")
    assert _metric(result, "L2").band == "healthy"


def test_l3_ratio_de_caja(result: BaseRatiosResult) -> None:
    """(200 + 100) / 600 = 0,5."""
    assert _metric(result, "L3").value == dec("0.5")
    assert _metric(result, "L3").band == "healthy"


def test_l4_muro_de_vencimientos(result: BaseRatiosResult) -> None:
    """(200 + 100 + FCF 300) / (100 + 100) = 3,0."""
    metric = _metric(result, "L4")
    assert metric.value == dec(3)
    assert metric.band == "healthy"


# ── Actividad ─────────────────────────────────────────────────────────


def test_a1_dias_de_cobro_usa_la_media_de_saldos(result: BaseRatiosResult) -> None:
    """media(300, 200) = 250 → 250 / 2.000 × 365 = 45,625 días."""
    metric = _metric(result, "A1")
    assert metric.value == dec("45.625")
    assert metric.status == "ok"
    assert metric.band is None, "el DSO no tiene banda absoluta, solo deriva"


def test_a2_dias_de_inventario(result: BaseRatiosResult) -> None:
    """media(400, 300) = 350 → 350 / 1.200 × 365 = 106,458333."""
    approx_dec(_metric(result, "A2").value, "106.458333")


def test_a3_dias_de_pago(result: BaseRatiosResult) -> None:
    """media(250, 150) = 200 → 200 / 1.200 × 365 = 60,833333."""
    approx_dec(_metric(result, "A3").value, "60.833333")


def test_a4_rotacion_de_activos(result: BaseRatiosResult) -> None:
    """2.000 / media(2.400, 2.000) = 2.000 / 2.200 = 0,909091."""
    approx_dec(_metric(result, "A4").value, "0.909091")


def test_a5_ciclo_de_conversion_de_caja(result: BaseRatiosResult) -> None:
    """45,625 + 106,458333 − 60,833333 = 91,25 días."""
    approx_dec(_metric(result, "A5").value, "91.25")


# ── Solvencia ─────────────────────────────────────────────────────────


def test_s1_apalancamiento(result: BaseRatiosResult) -> None:
    """1.400 / 2.400 = 0,583333 → verde (< 0,6)."""
    metric = _metric(result, "S1")
    approx_dec(metric.value, "0.583333")
    assert metric.band == "healthy"


def test_s2_cobertura_de_intereses(result: BaseRatiosResult) -> None:
    """EBIT limpio 400 / 50 = 8,0 → verde (> 6)."""
    metric = _metric(result, "S2")
    assert metric.value == dec(8)
    assert metric.band == "healthy"


def test_s3_autonomia_financiera(result: BaseRatiosResult) -> None:
    """1.000 / 2.400 = 0,416667 → verde (> 0,35)."""
    metric = _metric(result, "S3")
    approx_dec(metric.value, "0.416667")
    assert metric.band == "healthy"


def test_s4_deuda_neta_sobre_ebitda(result: BaseRatiosResult) -> None:
    """Deuda neta 500 / EBITDA 500 = 1,0 → verde (< 2)."""
    metric = _metric(result, "S4")
    assert metric.value == dec(1)
    assert metric.band == "healthy"


def test_s4b_deuda_neta_sobre_ebit(result: BaseRatiosResult) -> None:
    """500 / 400 = 1,25 → verde (< 3)."""
    assert _metric(result, "S4b").value == dec("1.25")


def test_s5_años_de_repago(result: BaseRatiosResult) -> None:
    """Deuda neta 500 / FCF 300 = 1,666667 años → verde (< 4)."""
    metric = _metric(result, "S5")
    approx_dec(metric.value, "1.666667")
    assert metric.band == "healthy"


def test_s6_cobertura_de_intereses_por_caja(result: BaseRatiosResult) -> None:
    """(CFO 500 + intereses 50 + impuestos pagados 70) / 50 = 12,4 → verde."""
    metric = _metric(result, "S6")
    assert metric.value == dec("12.4")
    assert metric.band == "healthy"


# ── Rentabilidad ──────────────────────────────────────────────────────


def test_r1_a_r4_margenes(result: BaseRatiosResult) -> None:
    assert _metric(result, "R1").value == dec("0.4")  # (2000−1200)/2000
    assert _metric(result, "R2").value == dec("0.25")  # EBITDA 500/2000
    assert _metric(result, "R3").value == dec("0.2")  # EBIT limpio 400/2000
    assert _metric(result, "R4").value == dec("0.14")  # 280/2000


def test_r5_roe_sobre_patrimonio_medio(result: BaseRatiosResult) -> None:
    """280 / media(1.000, 800) = 280 / 900 = 0,311111 → verde (> 12%)."""
    metric = _metric(result, "R5")
    approx_dec(metric.value, "0.311111")
    assert metric.band == "healthy"


def test_r6_roa_sobre_activo_medio(result: BaseRatiosResult) -> None:
    """280 / 2.200 = 0,127273."""
    approx_dec(_metric(result, "R6").value, "0.127273")


def test_r7_margen_fcf(result: BaseRatiosResult) -> None:
    """FCF 300 / 2.000 = 0,15 → verde (> 8%)."""
    metric = _metric(result, "R7")
    assert metric.value == dec("0.15")
    assert metric.band == "healthy"


def test_r8_fcf_por_accion(result: BaseRatiosResult) -> None:
    """300 / 100 acciones = 3,0. Sin banda: es serie."""
    metric = _metric(result, "R8")
    assert metric.value == dec(3)
    assert metric.band is None


def test_r9_roic(result: BaseRatiosResult) -> None:
    """NOPAT 320 / capital invertido medio 1.525 = 0,209836.

    NOPAT = EBIT limpio 400 × (1 − 70/350) = 400 × 0,8 = 320.
    Capital invertido: 2024 = 1.000 + 800 − 200 = 1.600;
                       2023 =   800 + 750 − 100 = 1.450 → media 1.525.
    """
    metric = _metric(result, "R9")
    approx_dec(metric.value, "0.209836")
    assert metric.band == "healthy"


def test_r9b_croic(result: BaseRatiosResult) -> None:
    """FCF 300 / 1.525 = 0,196721."""
    approx_dec(_metric(result, "R9b").value, "0.196721")


def test_r10_rentabilidad_bruta_sobre_activos(result: BaseRatiosResult) -> None:
    """Margen bruto 800 / activo medio 2.200 = 0,363636 → verde (> 0,33)."""
    metric = _metric(result, "R10")
    approx_dec(metric.value, "0.363636")
    assert metric.band == "healthy"


def test_dupont_reconstruye_el_roe(result: BaseRatiosResult) -> None:
    """ROE = margen neto × rotación × multiplicador de patrimonio.

    Si la identidad no cuadra, alguna de las tres piezas usa un denominador
    distinto del que debería (medio vs final) — que es el error clásico.
    """
    dupont = next(d for d in result.dupont if d.fiscal_year == 2024)
    assert dupont.net_margin.value is not None
    assert dupont.asset_turnover.value is not None
    assert dupont.equity_multiplier.value is not None
    approx_dec(dupont.equity_multiplier.value, "2.444444")

    reconstruido = (
        dupont.net_margin.value * dupont.asset_turnover.value * dupont.equity_multiplier.value
    )
    roe = _metric(result, "R5").value
    assert roe is not None
    approx_dec(reconstruido, str(roe.quantize(Decimal("0.000001"))))


# ── Derivaciones (§4.4) ───────────────────────────────────────────────


def test_derivaciones_con_importes_conocidos() -> None:
    statement = _statement_2024()
    assert dv.total_debt(statement).value == dec(800)  # 100 + 100 + 600
    assert dv.net_debt(statement).value == dec(500)  # 800 − 200 − 100
    assert dv.ebitda(statement).value == dec(500)  # 400 + 100
    assert dv.ebit_clean(statement).value == dec(400)  # 400 + 0 − 0
    assert dv.ebt(statement).value == dec(350)  # 280 + 70
    assert dv.effective_tax_rate(statement).value == dec("0.2")  # 70 / 350
    assert dv.nopat(statement).value == dec(320)  # 400 × 0,8
    assert dv.invested_capital(statement).value == dec(1600)  # 1000 + 800 − 200
    assert dv.wc_total(statement).value == dec(600)  # 1200 − 600
    assert dv.wc_operating(statement).value == dec(450)  # (300 + 400) − 250
    assert dv.fcf_cfo(statement).value == dec(300)  # 500 − 200
    assert dv.dividend_per_share(statement).value == dec(1)  # 100 / 100


def test_total_debt_sin_leases_y_variante_con_leases() -> None:
    """Los leases quedan fuera del total por defecto: incluirlos rompería la
    comparación con series anteriores a IFRS16/ASC842."""
    statement = CanonicalStatement(
        fiscal_year=2024,
        fiscal_year_end=date(2024, 12, 31),
        accounting_std=AccountingStd.GAAP,
        short_term_debt=dec(100),
        ltd_current_portion=dec(100),
        long_term_debt=dec(600),
        lease_liabilities_current=dec(30),
        lease_liabilities_noncurrent=dec(170),
    )
    assert dv.total_debt(statement).value == dec(800)
    assert dv.total_debt_incl_leases(statement).value == dec(1000)


def test_fcf_ebitda_contrasta_la_caja_desde_el_devengo(series: StatementSeries) -> None:
    """EBITDA 500 − capex 200 − Δcirculante 100 − impuestos pagados 70 = 130.

    Δcirculante operativo = 450 (2024) − 350 (2023) = 100.
    """
    assert dv.fcf_ebitda(series, 2024).value == dec(130)


def test_fcf_ebitda_sin_ejercicio_previo_no_es_computable(series: StatementSeries) -> None:
    """Sin t−1 no hay variación de circulante; suponerla cero inventaría caja."""
    amount = dv.fcf_ebitda(series, 2023)
    assert amount.value is None
    assert amount.reason is not None
    assert "2022" in amount.reason


def test_maintenance_capex_es_siempre_una_estimacion() -> None:
    """min(capex 200, D&A 100) = 100, y SIEMPRE marcado `estimated` [Dec.4]."""
    amount = dv.maintenance_capex(_statement_2024())
    assert amount.value == dec(100)
    assert amount.provenance is Provenance.ESTIMATED


def test_ffo_para_reits() -> None:
    """280 + 100 + 0 − 0 = 380."""
    assert dv.ffo(_statement_2024()).value == dec(380)


# ── Banderas ──────────────────────────────────────────────────────────


def test_sin_bandera_de_ebt_cuando_cuadra(result: BaseRatiosResult) -> None:
    """EBT 350 == EBIT 400 − intereses 50 → no hay divergencia."""
    assert not [f for f in result.flags if f.key == "ebt_divergence"]


def test_bandera_de_ebt_cuando_hay_partidas_no_modeladas() -> None:
    """EBT 350 vs EBIT − intereses 250 → 28,6% de divergencia."""
    statement = CanonicalStatement(
        fiscal_year=2024,
        fiscal_year_end=date(2024, 12, 31),
        accounting_std=AccountingStd.GAAP,
        ebit=dec(300),
        interest_expense=dec(50),
        taxes=dec(70),
        net_income=dec(280),
    )
    flag = dv.ebt_divergence_flag(statement)
    assert flag is not None
    assert flag.key == "ebt_divergence"
    assert flag.severity == "info"


# ── `pretax_income`, la partida 49 (PHASE-44.6) ───────────────────────


def _pretax_statement(**overrides: object) -> CanonicalStatement:
    base: dict[str, object] = {
        "fiscal_year": 2024,
        "fiscal_year_end": date(2024, 12, 31),
        "accounting_std": AccountingStd.GAAP,
        "ebit": dec(400),
        "interest_expense": dec(50),
        "taxes": dec(70),
        "net_income": dec(280),
    }
    base.update(overrides)
    return CanonicalStatement(**base)  # type: ignore[arg-type]


def test_el_ebt_prefiere_el_pretax_reportado_a_la_reconstruccion() -> None:
    """Publicado 360 ≠ reconstruido 350 (280+70): manda el publicado. La
    diferencia son los minoritarios, que `net_income` deja fuera."""
    assert dv.ebt(_pretax_statement(pretax_income=dec(360))).value == dec(360)


def test_sin_pretax_reportado_el_ebt_cae_a_la_reconstruccion() -> None:
    """Retrocompatible: los estados ya ingeridos no tienen la partida 49."""
    assert dv.ebt(_pretax_statement()).value == dec(350)


def test_la_bandera_de_ebt_no_se_evalua_si_el_ebit_es_derivado() -> None:
    """Si la ingesta derivó el EBIT como `ebt + intereses`, comparar
    `ebit − intereses` con el EBT es tautológico: la bandera no puede disparar
    NUNCA, y una comprobación que siempre pasa engaña más que no tenerla."""
    statement = _pretax_statement(
        ebit=dec(410),  # = pretax 360 + intereses 50, como haría el adapter
        pretax_income=dec(360),
        item_provenance={"ebit": Provenance.DERIVED},
    )
    assert dv.ebt_divergence_flag(statement) is None


def test_la_bandera_de_ebt_sigue_viva_si_el_ebit_es_sourced() -> None:
    """Con el EBIT publicado las dos fuentes son independientes: 300 − 50 = 250
    frente a un pretax de 360 son 30,6% de divergencia."""
    statement = _pretax_statement(ebit=dec(300), pretax_income=dec(360))
    flag = dv.ebt_divergence_flag(statement)
    assert flag is not None
    assert flag.key == "ebt_divergence"


def test_bandera_cuando_el_pretax_publicado_no_cuadra_con_neto_mas_impuestos() -> None:
    """Publicado 500 vs reconstruido 350: 30% — hay minoritarios o actividades
    discontinuadas que el canónico no modela."""
    flag = dv.ebt_reconstruction_flag(_pretax_statement(pretax_income=dec(500)))
    assert flag is not None
    assert flag.key == "ebt_reconstruction_divergence"
    assert flag.severity == "info"


def test_sin_bandera_de_reconstruccion_cuando_la_diferencia_es_tolerable() -> None:
    """355 vs 350 es un 1,4%, por debajo del 2%: ruido de redondeo, no señal."""
    assert dv.ebt_reconstruction_flag(_pretax_statement(pretax_income=dec(355))) is None


def test_sin_pretax_reportado_no_hay_bandera_de_reconstruccion() -> None:
    """Sin las dos fuentes no hay nada que comparar: no se inventa una señal."""
    assert dv.ebt_reconstruction_flag(_pretax_statement()) is None


def test_divergencia_de_fcf_exige_dos_años_seguidos(series: StatementSeries) -> None:
    """Un solo año divergente no levanta bandera: lo explica la estacionalidad."""
    flags = dv.fcf_divergence_flags(series)
    assert flags == ()


def test_divergencia_de_fcf_sostenida_levanta_bandera_ambar() -> None:
    """Tres años con el circulante disparándose: 2024 y 2025 divergen seguidos."""
    base = dict(
        accounting_std=AccountingStd.GAAP,
        cash=dec(100),
        current_financial_assets=dec(0),
        accounts_payable=dec(100),
        current_assets=dec(1000),
        current_liabilities=dec(400),
        total_assets=dec(2000),
        total_liabilities=dec(1000),
        equity=dec(1000),
        short_term_debt=dec(100),
        ltd_current_portion=dec(0),
        long_term_debt=dec(500),
        revenue=dec(2000),
        cogs=dec(1200),
        depreciation_amortization=dec(100),
        impairments=dec(0),
        gains_on_sale_of_business=dec(0),
        ebit=dec(400),
        interest_expense=dec(50),
        taxes=dec(70),
        net_income=dec(280),
        shares_basic=dec(100),
        cfo=dec(500),
        capex=dec(200),
        taxes_paid=dec(70),
    )
    statements = tuple(
        CanonicalStatement(
            fiscal_year=year,
            fiscal_year_end=date(year, 12, 31),
            receivables=dec(200) + dec(300) * (year - 2023),
            inventory=dec(200) + dec(300) * (year - 2023),
            **base,  # type: ignore[arg-type]
        )
        for year in (2023, 2024, 2025)
    )
    serie = StatementSeries(security=_security(), statements=statements, as_of=date(2026, 1, 1))
    flags = dv.fcf_divergence_flags(serie)
    assert [f.key for f in flags] == ["fcf_divergence"]
    assert flags[0].severity == "amber"
    assert flags[0].evidence["years"] == [2024, 2025]


# ── Huecos, aproximaciones y guardas ──────────────────────────────────


def test_un_hueco_da_not_computable_con_la_partida_que_falta() -> None:
    """Un hueco NO es cero [Dec.4]: la métrica sale sin valor y con razón."""
    incompleto = CanonicalStatement(
        fiscal_year=2024,
        fiscal_year_end=date(2024, 12, 31),
        accounting_std=AccountingStd.GAAP,
        current_assets=dec(1200),
        # current_liabilities ausente a propósito
    )
    serie = StatementSeries(security=_security(), statements=(incompleto,), as_of=date(2025, 1, 1))
    metric = base_ratios.compute(serie).get("L1", 2024)
    assert metric is not None
    assert metric.value is None
    assert metric.status == "not_computable"
    assert metric.reason is not None
    assert "current_liabilities" in metric.reason
    assert metric.band is None


def test_el_primer_año_sale_como_aproximacion(result: BaseRatiosResult) -> None:
    """Sin t−1 la media de balance cae al saldo final [Dec.3] — y se dice."""
    metric = _metric(result, "A1", year=2023)
    assert metric.status == "approximation"
    assert metric.reason is not None
    assert "2022" in metric.reason
    # 200 / 1.600 × 365 = 45,625 (saldo final, no media)
    assert metric.value == dec("45.625")


def test_el_segundo_año_ya_no_es_aproximacion(result: BaseRatiosResult) -> None:
    assert _metric(result, "A1", year=2024).status == "ok"


def test_guard_de_patrimonio_negativo_en_el_roe() -> None:
    """Con patrimonio negativo el ROE sale positivo cuando la empresa pierde
    dinero: es un número engañoso, así que no se muestra."""
    quebrada = CanonicalStatement(
        fiscal_year=2024,
        fiscal_year_end=date(2024, 12, 31),
        accounting_std=AccountingStd.GAAP,
        equity=dec(-500),
        net_income=dec(-200),
        total_assets=dec(1000),
        revenue=dec(1000),
    )
    serie = StatementSeries(security=_security(), statements=(quebrada,), as_of=date(2025, 1, 1))
    metric = base_ratios.compute(serie).get("R5", 2024)
    assert metric is not None
    assert metric.value is None
    assert metric.reason is not None
    assert "no positivo" in metric.reason


def test_denominador_cero_no_revienta() -> None:
    sin_pasivo_corriente = CanonicalStatement(
        fiscal_year=2024,
        fiscal_year_end=date(2024, 12, 31),
        accounting_std=AccountingStd.GAAP,
        current_assets=dec(1000),
        current_liabilities=dec(0),
    )
    serie = StatementSeries(
        security=_security(), statements=(sin_pasivo_corriente,), as_of=date(2025, 1, 1)
    )
    metric = base_ratios.compute(serie).get("L1", 2024)
    assert metric is not None
    assert metric.value is None
    assert metric.reason is not None
    assert "cero" in metric.reason


def test_s5_con_caja_neta_es_verde() -> None:
    """Liquidez > deuda: no hay años de repago que contar."""
    con_caja = CanonicalStatement(
        fiscal_year=2024,
        fiscal_year_end=date(2024, 12, 31),
        accounting_std=AccountingStd.GAAP,
        cash=dec(1000),
        current_financial_assets=dec(500),
        short_term_debt=dec(100),
        ltd_current_portion=dec(0),
        long_term_debt=dec(200),
        cfo=dec(400),
        capex=dec(100),
    )
    serie = StatementSeries(security=_security(), statements=(con_caja,), as_of=date(2025, 1, 1))
    metric = base_ratios.compute(serie).get("S5", 2024)
    assert metric is not None
    assert metric.value == dec(0)
    assert metric.band == "healthy"


def test_s5_sin_caja_libre_no_es_computable_y_explica_por_que() -> None:
    ahogada = CanonicalStatement(
        fiscal_year=2024,
        fiscal_year_end=date(2024, 12, 31),
        accounting_std=AccountingStd.GAAP,
        cash=dec(50),
        current_financial_assets=dec(0),
        short_term_debt=dec(300),
        ltd_current_portion=dec(100),
        long_term_debt=dec(600),
        cfo=dec(100),
        capex=dec(200),
    )
    serie = StatementSeries(security=_security(), statements=(ahogada,), as_of=date(2025, 1, 1))
    metric = base_ratios.compute(serie).get("S5", 2024)
    assert metric is not None
    assert metric.value is None
    assert metric.reason is not None
    assert "caja libre" in metric.reason


# ── Procedencia ───────────────────────────────────────────────────────


def test_la_procedencia_se_degrada_al_combinar() -> None:
    assert combine_provenance() is Provenance.SOURCED
    assert combine_provenance(Provenance.SOURCED, Provenance.DERIVED) is Provenance.DERIVED
    assert combine_provenance(Provenance.DERIVED, Provenance.ESTIMATED) is Provenance.ESTIMATED


def test_el_orden_de_degradacion_de_la_procedencia() -> None:
    """SOURCED < DERIVED < IMPUTED_ZERO < ESTIMATED (§4.5).

    `derived` aplica una identidad exacta; `imputed_zero` supone un dato que no
    está; `estimated` es un proxy con fórmula propia.
    """
    assert (
        combine_provenance(Provenance.DERIVED, Provenance.IMPUTED_ZERO) is Provenance.IMPUTED_ZERO
    )
    assert combine_provenance(Provenance.IMPUTED_ZERO, Provenance.ESTIMATED) is Provenance.ESTIMATED
    assert (
        combine_provenance(Provenance.SOURCED, Provenance.IMPUTED_ZERO) is Provenance.IMPUTED_ZERO
    )


def test_una_metrica_derivada_no_se_marca_sourced(result: BaseRatiosResult) -> None:
    assert _metric(result, "S4").provenance is Provenance.DERIVED


def test_un_cero_imputado_contamina_la_metrica_que_lo_usa() -> None:
    """Sin deuda a corto, la empresa NO etiqueta el concepto en XBRL. La ingesta
    lo imputa a 0 para que `total_debt` se pueda calcular (§4.5), pero la
    métrica resultante debe declarar que se apoya en un supuesto — si saliera
    `derived` a secas, un dato inventado se presentaría como calculado.
    """
    con_imputacion = CanonicalStatement(
        fiscal_year=2024,
        fiscal_year_end=date(2024, 12, 31),
        accounting_std=AccountingStd.GAAP,
        cash=dec(200),
        current_financial_assets=dec(100),
        short_term_debt=dec(0),
        ltd_current_portion=dec(0),
        long_term_debt=dec(600),
        ebit=dec(400),
        depreciation_amortization=dec(100),
        item_provenance={
            "short_term_debt": Provenance.IMPUTED_ZERO,
            "ltd_current_portion": Provenance.IMPUTED_ZERO,
        },
    )
    serie = StatementSeries(
        security=_security(), statements=(con_imputacion,), as_of=date(2025, 1, 1)
    )
    # Deuda total 600 − caja 300 = 300 de deuda neta / EBITDA 500 = 0,6
    metric = base_ratios.compute(serie).get("S4", 2024)
    assert metric is not None
    assert metric.value == dec("0.6")
    assert metric.provenance is Provenance.IMPUTED_ZERO


def test_una_partida_imputada_no_se_declara_sourced() -> None:
    """La completitud del informe no debe contar una imputación como dato."""
    statement = CanonicalStatement(
        fiscal_year=2024,
        fiscal_year_end=date(2024, 12, 31),
        accounting_std=AccountingStd.GAAP,
        inventory=dec(0),
        item_provenance={"inventory": Provenance.IMPUTED_ZERO},
    )
    assert statement.provenance_of("inventory") is Provenance.IMPUTED_ZERO
    assert statement.provenance_of("cash") is Provenance.SOURCED


# ── Umbrales ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0.9", "stressed"), ("1.0", "caution"), ("1.4", "caution"), ("1.5", "healthy")],
)
def test_bandas_higher_better_en_los_bordes(value: str, expected: str) -> None:
    spec = DEFAULT_THRESHOLDS["L1"]
    assert spec.direction is ThresholdDirection.HIGHER_BETTER
    assert spec.band_for(Decimal(value)) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0.5", "healthy"), ("0.6", "healthy"), ("0.7", "caution"), ("0.8", "stressed")],
)
def test_bandas_lower_better_en_los_bordes(value: str, expected: str) -> None:
    spec = DEFAULT_THRESHOLDS["S1"]
    assert spec.direction is ThresholdDirection.LOWER_BETTER
    assert spec.band_for(Decimal(value)) == expected


def test_un_umbral_que_no_aplica_no_pinta_banda() -> None:
    """`applies=False` (p. ej. Beneish en financieras) → sin banda, no basura."""
    spec = ThresholdSpec(
        metric_key="L1",
        direction=ThresholdDirection.HIGHER_BETTER,
        low_alarm=Decimal(1),
        low_ok=Decimal(2),
        applies=False,
    )
    assert spec.band_for(Decimal(3)) is None


def test_los_umbrales_pasados_sustituyen_a_los_por_defecto(series: StatementSeries) -> None:
    """El servicio inyecta los umbrales calibrados de BD [Dec.8]."""
    exigente = {
        "L1": ThresholdSpec(
            metric_key="L1",
            direction=ThresholdDirection.HIGHER_BETTER,
            low_alarm=Decimal(3),
            low_ok=Decimal(5),
        )
    }
    metric = base_ratios.compute(series, exigente).get("L1", 2024)
    assert metric is not None
    assert metric.value == dec(2)
    assert metric.band == "stressed"


# ── Invariantes de los tipos ──────────────────────────────────────────


def test_metric_result_prohibe_valor_ausente_con_status_ok() -> None:
    with pytest.raises(ValueError, match="incoherente"):
        MetricResult(
            key="L1",
            fiscal_year=2024,
            value=None,
            status="ok",
            provenance=Provenance.SOURCED,
        )


def test_metric_result_exige_razon_si_no_es_computable() -> None:
    with pytest.raises(ValueError, match="razón"):
        MetricResult(
            key="L1",
            fiscal_year=2024,
            value=None,
            status="not_computable",
            provenance=Provenance.SOURCED,
        )


def test_la_serie_rechaza_años_duplicados() -> None:
    with pytest.raises(ValueError, match="duplicados"):
        StatementSeries(
            security=_security(),
            statements=(_statement_2024(), _statement_2024()),
            as_of=date(2025, 1, 1),
        )


def test_la_serie_rechaza_orden_descendente() -> None:
    with pytest.raises(ValueError, match="ascendente"):
        StatementSeries(
            security=_security(),
            statements=(_statement_2024(), _statement_2023()),
            as_of=date(2025, 1, 1),
        )


def test_prior_no_salta_huecos_en_la_serie() -> None:
    """Con 2020 y 2024, el "anterior" de 2024 NO es 2020: una media (t, t−4)
    no es una media."""
    viejo = CanonicalStatement(
        fiscal_year=2020,
        fiscal_year_end=date(2020, 12, 31),
        accounting_std=AccountingStd.GAAP,
        receivables=dec(100),
    )
    serie = StatementSeries(
        security=_security(),
        statements=(viejo, _statement_2024()),
        as_of=date(2025, 1, 1),
    )
    assert serie.prior(2024) is None
    assert avg_balance(serie, "receivables", 2024).status == "approximation"


def test_una_partida_inexistente_es_un_error_no_un_hueco_silencioso() -> None:
    """Un typo devolvería `None` y la métrica saldría `not_computable` sin que
    nadie se entere: mejor que reviente."""
    with pytest.raises(KeyError):
        _statement_2024().get("recievables")


def test_el_canonico_tiene_las_49_partidas() -> None:
    """48 del DESIGN §4 + `pretax_income`, que añadió el cruzado EDGAR de
    PHASE-44.6 al ver que el EBIT hay que derivarlo del pretax."""
    assert len(CANONICAL_ITEMS) == 49
    assert len(set(CANONICAL_ITEMS)) == 49
    assert "pretax_income" in CANONICAL_ITEMS


def test_avg_balance_solo_acepta_partidas_de_balance(series: StatementSeries) -> None:
    """Promediar un flujo (ventas) sería un error conceptual."""
    with pytest.raises(KeyError):
        avg_balance(series, "revenue", 2024)


# ── Pureza del engine (ARCHITECTURE §0.1) ─────────────────────────────


def test_el_engine_no_importa_io() -> None:
    """El engine no toca BD, red ni reloj. Si alguien mete un `import
    sqlalchemy` aquí, la promesa de "testeable con sintéticos" se cae y este
    test lo caza en el acto."""
    prohibidos = {"sqlalchemy", "httpx", "requests", "asyncpg", "app.core.database"}
    engine_dir = Path(__file__).resolve().parents[1] / "app/modules/investment/analysis/engine"
    modulos = sorted(engine_dir.glob("*.py"))
    assert modulos, "no se encontraron módulos del engine"

    for modulo in modulos:
        arbol = ast.parse(modulo.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                nombres = [alias.name for alias in nodo.names]
            elif isinstance(nodo, ast.ImportFrom):
                nombres = [nodo.module or ""]
            else:
                continue
            for nombre in nombres:
                raiz = nombre.split(".")[0]
                assert (
                    raiz not in prohibidos and nombre not in prohibidos
                ), f"{modulo.name} importa '{nombre}': el engine debe ser puro"
