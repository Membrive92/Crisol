"""Tests de las capas 1.5 (evolutiva) y 2 (forense) — PHASE-44.3.

Igual que en 44.2: engine puro, sin BD, y valores esperados calculados a mano.

La empresa sintética base crece un 20% exacto cada año con márgenes constantes,
lo que hace que la mayoría de ratios t/t−1 valgan justo 1,0 y que el M-Score y
el Z'' salgan de una aritmética verificable a mano. Los casos que deben disparar
banderas usan fixtures propios y deliberadamente rotos.
"""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import pytest

from app.modules.investment.analysis.engine import catalog, evolution, forensic
from app.modules.investment.analysis.engine.forensic import (
    NOT_APPLICABLE_TO_FINANCIALS,
    ZMIJEWSKI_P_CUTOFFS,
)
from app.modules.investment.analysis.engine.types import SecuritySnapshot, StatementSeries
from app.modules.investment.enums import AccountingStd, SectorInternal
from app.modules.investment.fundamentals.canonical import CanonicalStatement


def dec(value: str | int) -> Decimal:
    return Decimal(value)


def approx_dec(value: Decimal | None, expected: str, places: int = 6) -> None:
    assert value is not None, "se esperaba un valor calculado, no un hueco"
    quantum = Decimal(10) ** -places
    assert value.quantize(quantum) == Decimal(expected).quantize(
        quantum
    ), f"esperado {expected}, obtenido {value}"


# ── Empresa sintética: crecimiento del 20% con márgenes constantes ────


def _year(
    fiscal_year: int,
    *,
    revenue: int,
    cogs: int,
    sga: int,
    ebit: int,
    dna: int,
    interest: int,
    taxes: int,
    net_income: int,
    cash: int,
    receivables: int,
    inventory: int,
    current_assets: int,
    ppe: int,
    total_assets: int,
    short_term_debt: int,
    payables: int,
    current_liabilities: int,
    long_term_debt: int,
    total_liabilities: int,
    equity: int,
    retained: int,
    cfo: int,
    capex: int,
    dividends: int,
    taxes_paid: int,
    goodwill: int = 100,
    shares: int = 100,
    buybacks: int = 0,
    share_issuance: int = 0,
    debt_change: int = 0,
    acquisitions: int = 0,
) -> CanonicalStatement:
    return CanonicalStatement(
        fiscal_year=fiscal_year,
        fiscal_year_end=date(fiscal_year, 12, 31),
        accounting_std=AccountingStd.GAAP,
        cash=dec(cash),
        current_financial_assets=dec(0),
        receivables=dec(receivables),
        inventory=dec(inventory),
        current_assets=dec(current_assets),
        ppe_net=dec(ppe),
        goodwill=dec(goodwill),
        total_assets=dec(total_assets),
        short_term_debt=dec(short_term_debt),
        ltd_current_portion=dec(0),
        accounts_payable=dec(payables),
        current_liabilities=dec(current_liabilities),
        long_term_debt=dec(long_term_debt),
        total_liabilities=dec(total_liabilities),
        retained_earnings=dec(retained),
        equity=dec(equity),
        revenue=dec(revenue),
        cogs=dec(cogs),
        sga_expense=dec(sga),
        depreciation_amortization=dec(dna),
        impairments=dec(0),
        gains_on_sale_of_business=dec(0),
        ebit=dec(ebit),
        interest_expense=dec(interest),
        taxes=dec(taxes),
        net_income=dec(net_income),
        shares_basic=dec(shares),
        cfo=dec(cfo),
        capex=dec(capex),
        acquisitions=dec(acquisitions),
        dividends_paid=dec(dividends),
        buybacks=dec(buybacks),
        share_issuance=dec(share_issuance),
        debt_change=dec(debt_change),
        taxes_paid=dec(taxes_paid),
    )


def _security(*, is_financial: bool = False, is_reit: bool = False) -> SecuritySnapshot:
    return SecuritySnapshot(
        ticker="SYNT",
        sector=SectorInternal.INDUSTRIALS,
        accounting_std=AccountingStd.GAAP,
        is_financial=is_financial,
        is_reit=is_reit,
    )


def _statements() -> tuple[CanonicalStatement, ...]:
    return (
        _year(
            2022,
            revenue=1000,
            cogs=600,
            sga=150,
            ebit=200,
            dna=50,
            interest=25,
            taxes=35,
            net_income=140,
            cash=100,
            receivables=100,
            inventory=100,
            current_assets=400,
            ppe=400,
            total_assets=1000,
            short_term_debt=50,
            payables=100,
            current_liabilities=200,
            long_term_debt=300,
            total_liabilities=500,
            equity=500,
            retained=200,
            cfo=200,
            capex=60,
            dividends=50,
            taxes_paid=35,
        ),
        _year(
            2023,
            revenue=1200,
            cogs=720,
            sga=180,
            ebit=240,
            dna=60,
            interest=25,
            taxes=43,
            net_income=172,
            cash=120,
            receivables=120,
            inventory=120,
            current_assets=480,
            ppe=480,
            total_assets=1200,
            short_term_debt=50,
            payables=120,
            current_liabilities=240,
            long_term_debt=360,
            total_liabilities=600,
            equity=600,
            retained=300,
            cfo=240,
            capex=72,
            dividends=60,
            taxes_paid=43,
        ),
        _year(
            2024,
            revenue=1440,
            cogs=864,
            sga=216,
            ebit=288,
            dna=72,
            interest=28,
            taxes=52,
            net_income=208,
            cash=144,
            receivables=144,
            inventory=144,
            current_assets=576,
            ppe=576,
            total_assets=1440,
            short_term_debt=60,
            payables=144,
            current_liabilities=288,
            long_term_debt=432,
            total_liabilities=720,
            equity=720,
            retained=400,
            cfo=288,
            capex=88,
            dividends=72,
            taxes_paid=52,
        ),
    )


@pytest.fixture
def series() -> StatementSeries:
    return StatementSeries(security=_security(), statements=_statements(), as_of=date(2025, 3, 31))


def _series_of(*statements: CanonicalStatement, **security: bool) -> StatementSeries:
    return StatementSeries(
        security=_security(**security),
        statements=tuple(statements),
        as_of=date(2025, 3, 31),
    )


# ══ CAPA 1.5 — EVOLUTIVA ═════════════════════════════════════════════


def test_e1_variacion_interanual_y_base_100(series: StatementSeries) -> None:
    """Ventas 1.000 → 1.200 → 1.440: +20% cada año, base 100 → 120 → 144."""
    revenue = evolution.compute(series).series_for("revenue")
    assert revenue is not None
    assert [p.fiscal_year for p in revenue.points] == [2022, 2023, 2024]
    assert revenue.points[0].yoy is None, "el primer año no tiene con qué compararse"
    approx_dec(revenue.points[1].yoy, "0.2")
    approx_dec(revenue.points[2].yoy, "0.2")
    approx_dec(revenue.points[0].index_100, "100")
    approx_dec(revenue.points[1].index_100, "120")
    approx_dec(revenue.points[2].index_100, "144")


def test_e1_cagr(series: StatementSeries) -> None:
    """(1.440 / 1.000)^(1/2) − 1 = 0,2 exacto."""
    revenue = evolution.compute(series).series_for("revenue")
    assert revenue is not None
    approx_dec(revenue.cagr, "0.2")
    assert revenue.cagr_reason is None


def test_e1_cubre_las_diez_magnitudes(series: StatementSeries) -> None:
    """Las tres últimas entraron en PHASE-44.10: eran derivaciones que el motor
    calculaba y no consumía nadie, y el cuaderno del usuario las pide."""
    keys = {h.key for h in evolution.compute(series).horizontal}
    assert keys == {
        "revenue",
        "ebit_clean",
        "net_income",
        "cfo",
        "fcf_cfo",
        "fcf_maintenance",
        "dividends_paid",
        "shares_basic",
        "wc_operating",
        "wc_total",
    }


def test_el_cagr_no_existe_si_la_serie_cambia_de_signo() -> None:
    """De pérdidas a beneficios no hay tasa compuesta: devolver un número ahí
    sería inventarlo."""
    perdidas = _year(
        2022,
        revenue=1000,
        cogs=600,
        sga=150,
        ebit=-100,
        dna=50,
        interest=25,
        taxes=0,
        net_income=-125,
        cash=100,
        receivables=100,
        inventory=100,
        current_assets=400,
        ppe=400,
        total_assets=1000,
        short_term_debt=50,
        payables=100,
        current_liabilities=200,
        long_term_debt=300,
        total_liabilities=500,
        equity=500,
        retained=200,
        cfo=200,
        capex=60,
        dividends=0,
        taxes_paid=0,
    )
    serie = _series_of(perdidas, _statements()[1])
    net_income = evolution.compute(serie).series_for("net_income")
    assert net_income is not None
    assert net_income.cagr is None
    assert net_income.cagr_reason is not None
    assert "signo" in net_income.cagr_reason


def test_e2_common_size(series: StatementSeries) -> None:
    """2024: caja 144 / activo 1.440 = 10%; coste de ventas 864 / 1.440 = 60%."""
    result = evolution.compute(series)
    approx_dec(result.weight_of("cash", 2024), "0.1")
    approx_dec(result.weight_of("cogs", 2024), "0.6")


def test_e2_no_hace_common_size_de_las_acciones(series: StatementSeries) -> None:
    """ "Acciones sobre ventas" no significa nada."""
    items = {p.item for p in evolution.compute(series).vertical}
    assert "shares_basic" not in items


def test_e3_margen_constante_da_dispersion_cero(series: StatementSeries) -> None:
    """Margen EBIT 20% los tres años → σ = 0 pp → verde."""
    metric = evolution.compute(series).get("E3", 2024)
    assert metric is not None
    approx_dec(metric.value, "0")
    assert metric.band == "healthy"


def test_e3_margen_erratico_dispara_la_banda() -> None:
    """Márgenes 10%, 20% y 30% → σ poblacional = 8,16497 pp → rojo (>5)."""
    statements = tuple(
        _year(
            year,
            revenue=1000,
            cogs=600,
            sga=150,
            ebit=ebit,
            dna=0,
            interest=25,
            taxes=35,
            net_income=140,
            cash=100,
            receivables=100,
            inventory=100,
            current_assets=400,
            ppe=400,
            total_assets=1000,
            short_term_debt=50,
            payables=100,
            current_liabilities=200,
            long_term_debt=300,
            total_liabilities=500,
            equity=500,
            retained=200,
            cfo=200,
            capex=60,
            dividends=50,
            taxes_paid=35,
        )
        for year, ebit in ((2022, 100), (2023, 200), (2024, 300))
    )
    metric = evolution.compute(_series_of(*statements)).get("E3", 2024)
    assert metric is not None
    approx_dec(metric.value, "8.164966", places=5)
    assert metric.band == "stressed"


def test_e3_exige_tres_ejercicios() -> None:
    """σ con dos puntos es media distancia, no dispersión."""
    metric = evolution.compute(_series_of(*_statements()[:2])).get("E3", 2023)
    assert metric is not None
    assert metric.value is None
    assert metric.reason is not None
    assert "al menos 3" in metric.reason


def test_e4_crecimiento_sostenible(series: StatementSeries) -> None:
    """g = ROE × (1 − payout) = (208 − 72) / 660 = 0,206061.

    Patrimonio medio 2024 = (720 + 600) / 2 = 660.
    """
    metric = evolution.compute(series).get("E4", 2024)
    assert metric is not None
    approx_dec(metric.value, "0.206061")


def test_una_empresa_sana_no_levanta_banderas_de_coherencia(series: StatementSeries) -> None:
    """El fixture base crece de forma proporcional y se autofinancia: si algún
    cruce salta aquí, es que el cruce tiene un falso positivo."""
    assert evolution.compute(series).flags == ()


# ── Reglas de coherencia ──────────────────────────────────────────────


def _flat_company(year: int, **overrides: int) -> CanonicalStatement:
    base = dict(
        revenue=1000,
        cogs=600,
        sga=150,
        ebit=200,
        dna=50,
        interest=25,
        taxes=35,
        net_income=140,
        cash=100,
        receivables=100,
        inventory=100,
        current_assets=400,
        ppe=400,
        total_assets=1000,
        short_term_debt=50,
        payables=100,
        current_liabilities=200,
        long_term_debt=300,
        total_liabilities=500,
        equity=500,
        retained=200,
        cfo=200,
        capex=60,
        dividends=50,
        taxes_paid=35,
    )
    base.update(overrides)
    return _year(year, **base)  # type: ignore[arg-type]


def _keys(series: StatementSeries) -> set[str]:
    return {flag.key for flag in evolution.compute(series).flags}


def test_c1_cobros_que_crecen_mas_que_las_ventas() -> None:
    """Ventas planas y cobros +20% dos años seguidos → ámbar."""
    serie = _series_of(
        _flat_company(2022, receivables=100),
        _flat_company(2023, receivables=120),
        _flat_company(2024, receivables=145),
    )
    flags = evolution.compute(serie).flags
    c1 = [f for f in flags if f.key == "C1_receivables_vs_revenue"]
    assert len(c1) == 1
    assert c1[0].severity == "amber"
    assert c1[0].evidence["years"] == [2023, 2024]


def test_c1_no_salta_con_un_solo_año_malo() -> None:
    """Un año suelto lo explica la estacionalidad del circulante."""
    serie = _series_of(
        _flat_company(2022, receivables=100),
        _flat_company(2023, receivables=120),
        _flat_company(2024, receivables=121),
    )
    assert "C1_receivables_vs_revenue" not in _keys(serie)


def test_c2_beneficio_que_sube_sin_caja() -> None:
    serie = _series_of(
        _flat_company(2022, net_income=100, cfo=200),
        _flat_company(2023, net_income=140, cfo=190),
        _flat_company(2024, net_income=180, cfo=180),
    )
    assert "C2_income_without_cash" in _keys(serie)


def test_c3_inventario_hinchado() -> None:
    """Coste de ventas plano e inventario +25% → ámbar en ese año."""
    serie = _series_of(
        _flat_company(2022, inventory=100),
        _flat_company(2023, inventory=125),
    )
    assert "C3_inventory_vs_cogs" in _keys(serie)


def test_c4_descapitalizacion_exige_tres_años() -> None:
    """capex/amortización < 0,8 tres años seguidos → informativo."""
    serie = _series_of(
        _flat_company(2022, capex=30, dna=50),
        _flat_company(2023, capex=30, dna=50),
        _flat_company(2024, capex=30, dna=50),
    )
    flags = [f for f in evolution.compute(serie).flags if f.key == "C4_underinvestment"]
    assert len(flags) == 1
    assert flags[0].severity == "info"

    dos_años = _series_of(
        _flat_company(2023, capex=30, dna=50), _flat_company(2024, capex=30, dna=50)
    )
    assert "C4_underinvestment" not in _keys(dos_años)


def test_c5_fondo_de_comercio_sin_compras() -> None:
    serie = _series_of(
        _flat_company(2022, goodwill=100, acquisitions=0),
        _flat_company(2023, goodwill=200, acquisitions=0),
    )
    assert "C5_goodwill_without_acquisitions" in _keys(serie)


def test_c5_no_salta_si_hubo_compras() -> None:
    serie = _series_of(
        _flat_company(2022, goodwill=100, acquisitions=0),
        _flat_company(2023, goodwill=200, acquisitions=150),
    )
    assert "C5_goodwill_without_acquisitions" not in _keys(serie)


def test_c6_dilucion_leve_es_informativa() -> None:
    """+3% de acciones al año sin recompras → info."""
    serie = _series_of(
        _flat_company(2022, shares=100),
        _flat_company(2023, shares=103),
        _flat_company(2024, shares=107),
    )
    flags = [f for f in evolution.compute(serie).flags if f.key == "C6_dilution"]
    assert len(flags) == 1
    assert flags[0].severity == "info"


def test_c6_dilucion_fuerte_escala_a_ambar() -> None:
    """Por encima del 5% anual la dilución deja de ser un detalle."""
    serie = _series_of(
        _flat_company(2022, shares=100),
        _flat_company(2023, shares=110),
        _flat_company(2024, shares=125),
    )
    flags = [f for f in evolution.compute(serie).flags if f.key == "C6_dilution"]
    assert len(flags) == 1
    assert flags[0].severity == "amber"


def test_c7_dividendo_pagado_con_deuda_dos_años_es_rojo() -> None:
    """Se devuelve más de lo que se genera Y sube la deuda: patrón terminal."""
    serie = _series_of(
        _flat_company(2022, cfo=100, capex=50, dividends=200, debt_change=100),
        _flat_company(2023, cfo=100, capex=50, dividends=200, debt_change=100),
        _flat_company(2024, cfo=100, capex=50, dividends=200, debt_change=100),
    )
    flags = [
        f for f in evolution.compute(serie).flags if f.key == "C7_shareholder_return_funded_by_debt"
    ]
    assert len(flags) == 1
    assert flags[0].severity == "red"


def test_c7_un_solo_año_es_ambar() -> None:
    serie = _series_of(
        _flat_company(2022, cfo=200, capex=50, dividends=50, debt_change=0),
        _flat_company(2023, cfo=100, capex=50, dividends=200, debt_change=100),
    )
    flags = [
        f for f in evolution.compute(serie).flags if f.key == "C7_shareholder_return_funded_by_debt"
    ]
    assert len(flags) == 1
    assert flags[0].severity == "amber"


def test_c8_crecimiento_comprado() -> None:
    """Ventas +200 en el periodo con 150 gastados en comprar empresas."""
    serie = _series_of(
        _flat_company(2022, revenue=1000, acquisitions=150),
        _flat_company(2023, revenue=1200, acquisitions=0),
    )
    assert "C8_acquired_growth" in _keys(serie)


def test_c8_no_salta_con_crecimiento_organico() -> None:
    serie = _series_of(
        _flat_company(2022, revenue=1000, acquisitions=0),
        _flat_company(2023, revenue=1200, acquisitions=0),
    )
    assert "C8_acquired_growth" not in _keys(serie)


# ══ CAPA 2 — FORENSE ═════════════════════════════════════════════════


def test_m_score_de_beneish(series: StatementSeries) -> None:
    """Con crecimiento proporcional, 7 de las 8 variables valen 1,0 y solo SGI
    (1,2) y TATA (−80/1.440) se mueven:

        M = −4,84 + 0,920 + 0,528 + 0,404 + 0,892×1,2 + 0,115 − 0,172
            + 4,679×(−0,055556) − 0,327 = −2,561544
    """
    metric = forensic.compute(series).get("m_score", 2024)
    assert metric is not None
    approx_dec(metric.value, "-2.561544")
    assert metric.band == "healthy"


def test_el_desglose_del_m_score_trae_las_ocho_variables(series: StatementSeries) -> None:
    """El agregado es lo menos informativo: importa QUÉ variable dispara."""
    breakdown = forensic.compute(series).breakdown_for("m_score", 2024)
    assert breakdown is not None
    assert set(breakdown.components) == {
        "DSRI",
        "GMI",
        "AQI",
        "SGI",
        "DEPI",
        "SGAI",
        "LVGI",
        "TATA",
    }
    approx_dec(breakdown.components["DSRI"], "1")
    approx_dec(breakdown.components["SGI"], "1.2")
    approx_dec(breakdown.components["TATA"], "-0.055556")


def test_z_score_de_altman(series: StatementSeries) -> None:
    """Z'' = 6,56×0,2 + 3,26×0,277778 + 6,72×0,2 + 1,05×1,0 = 4,611556."""
    metric = forensic.compute(series).get("z_score", 2024)
    assert metric is not None
    approx_dec(metric.value, "4.611556")
    assert metric.band == "healthy"


def test_el_z_score_usa_el_ebit_reportado() -> None:
    """El modelo se calibró sobre EBIT contable: sustituirlo por `ebit_clean`
    movería la escala de los cortes originales."""
    con_deterioro = _flat_company(2022, ebit=200)
    limpio = CanonicalStatement(
        **{
            **{
                f.name: getattr(con_deterioro, f.name)
                for f in con_deterioro.__dataclass_fields__.values()
            },
            "impairments": dec(500),
        }
    )
    _, variables = forensic.compute_z_score(limpio)
    # X3 = ebit / activo = 200 / 1.000 = 0,2 pese a los 500 de deterioro.
    approx_dec(variables["X3"], "0.2")


def test_f_score_de_piotroski(series: StatementSeries) -> None:
    """Pasan P1-P4 y P7 (5 puntos); P5, P6, P8 y P9 exigen MEJORA y la empresa
    se mantiene idéntica en ratios, así que no suman."""
    metric = forensic.compute(series).get("f_score", 2024)
    assert metric is not None
    assert metric.value == dec(5)
    assert metric.band == "caution"

    breakdown = forensic.compute(series).breakdown_for("f_score", 2024)
    assert breakdown is not None
    assert breakdown.checks["P1_roa_positivo"] is True
    assert breakdown.checks["P5_menos_apalancamiento"] is False


def test_accruals_de_sloan(series: StatementSeries) -> None:
    """|208 − 288| / activo medio 1.320 = 0,060606 → ámbar (>5%)."""
    metric = forensic.compute(series).get("accruals", 2024)
    assert metric is not None
    approx_dec(metric.value, "0.060606")
    assert metric.band == "caution"


def test_f5_riesgo_de_fondo_de_comercio(series: StatementSeries) -> None:
    """100 / 1.440 = 0,069444 → verde."""
    metric = forensic.compute(series).get("F5", 2024)
    assert metric is not None
    approx_dec(metric.value, "0.069444")
    assert metric.band == "healthy"


def test_f6_circulante_que_acompaña_a_las_ventas(series: StatementSeries) -> None:
    """Circulante operativo +20% y ventas +20% → anomalía 0 → verde."""
    metric = forensic.compute(series).get("F6", 2024)
    assert metric is not None
    approx_dec(metric.value, "0")
    assert metric.band == "healthy"


def test_fz_x_score_de_zmijewski(series: StatementSeries) -> None:
    """X = −4,336 − 4,513×0,144444 + 5,679×0,5 + 0,004×2 = −2,140378."""
    metric = forensic.compute(series).get("FZ", 2024)
    assert metric is not None
    approx_dec(metric.value, "-2.140378")
    assert metric.band == "healthy"


def test_los_cortes_de_fz_equivalen_a_bandear_la_probabilidad() -> None:
    """Los umbrales de FZ son Φ⁻¹(15%) y Φ⁻¹(40%). Como Φ es monótona, bandear
    X da lo mismo que bandear P — y el engine se queda en Decimal exacto."""
    for probability, x_cutoff in ZMIJEWSKI_P_CUTOFFS:
        phi = (1 + math.erf(float(x_cutoff) / math.sqrt(2))) / 2
        assert abs(phi - float(probability)) < 1e-6


def test_f7_c_score_de_montier(series: StatementSeries) -> None:
    """Solo dispara el check 6 (activo +20% > 10%): C-Score = 1 → verde."""
    metric = forensic.compute(series).get("F7", 2024)
    assert metric is not None
    assert metric.value == dec(1)
    assert metric.band == "healthy"

    breakdown = forensic.compute(series).breakdown_for("F7", 2024)
    assert breakdown is not None
    assert breakdown.checks["C6_activo_crece_mas_del_10"] is True
    assert breakdown.checks["C1_beneficio_por_delante_de_caja"] is False


# ── Exclusiones y huecos ──────────────────────────────────────────────


def test_las_financieras_no_puntuan_pero_conservan_todas_las_claves() -> None:
    """Regla dura de ARCHITECTURE §4.2: `not_computable` con razón, JAMÁS
    omitido — el informe debe poder explicar por qué falta."""
    serie = _series_of(*_statements(), is_financial=True)
    result = forensic.compute(serie)
    claves = {m.key for m in result.metrics if m.fiscal_year == 2024}
    assert claves == set(forensic.METRIC_KEYS)
    for metric in result.metrics:
        assert metric.value is None
        assert metric.reason == NOT_APPLICABLE_TO_FINANCIALS
        assert metric.band is None


def test_las_socimis_avisan_de_que_el_z_score_no_esta_calibrado() -> None:
    serie = _series_of(*_statements(), is_reit=True)
    result = forensic.compute(serie)
    flags = [f for f in result.flags if f.key == "z_score_uncalibrated_for_reit"]
    assert len(flags) == 1
    assert flags[0].severity == "amber"
    assert flags[0].evidence["model_variant"] == "uncalibrated"
    # Pero el score SÍ se calcula: la nota avisa, no suprime.
    z = result.get("z_score", 2024)
    assert z is not None and z.value is not None


def test_el_primer_año_no_tiene_scores_interanuales(series: StatementSeries) -> None:
    """M, F, F6 y F7 comparan t con t−1; sin t−1 no hay nada que comparar."""
    result = forensic.compute(series)
    for key in ("m_score", "f_score", "F6", "F7"):
        metric = result.get(key, 2022)
        assert metric is not None, f"{key} debe existir aunque no se pueda calcular"
        assert metric.value is None
        assert metric.reason is not None
        assert "2021" in metric.reason


def test_los_scores_de_un_solo_ejercicio_si_salen_el_primer_año(
    series: StatementSeries,
) -> None:
    result = forensic.compute(series)
    for key in ("z_score", "F5", "FZ"):
        metric = result.get(key, 2022)
        assert metric is not None and metric.value is not None


def test_un_hueco_deja_el_score_sin_calcular_y_nombra_la_variable() -> None:
    """Sin `sga_expense` no hay SGAI, y sin SGAI no hay M-Score."""
    sin_sga = CanonicalStatement(
        fiscal_year=2024,
        fiscal_year_end=date(2024, 12, 31),
        accounting_std=AccountingStd.GAAP,
        revenue=dec(1000),
        receivables=dec(100),
    )
    amount, variables = forensic.compute_m_score(sin_sga, sin_sga)
    assert amount.value is None
    assert variables == {}
    assert amount.reason is not None
    assert "SGAI" in amount.reason


# ══ Catálogo agregado ════════════════════════════════════════════════


def test_el_catalogo_agregado_contiene_estas_capas() -> None:
    """Base (27) + evolutiva (2) + forense (8) están todas en el agregado.

    No se fija el TOTAL: crece con cada capa nueva. El recuento exacto lo
    verifica el test de la última capa añadida.
    """
    from app.modules.investment.analysis.engine import base_ratios

    agregadas = set(catalog.ALL_METRIC_KEYS)
    for familia in (base_ratios.METRIC_CATALOG, evolution.METRIC_CATALOG, forensic.METRIC_CATALOG):
        assert {d.key for d in familia} <= agregadas
    assert len(catalog.ALL_METRIC_KEYS) == len(set(catalog.ALL_METRIC_KEYS)), "claves únicas"


def test_no_hay_claves_repetidas_entre_capas() -> None:
    """Una clave duplicada haría que dos métricas compartieran umbral en BD."""
    from app.modules.investment.analysis.engine import base_ratios

    familias = (
        base_ratios.METRIC_CATALOG,
        evolution.METRIC_CATALOG,
        forensic.METRIC_CATALOG,
    )
    todas = [d.key for familia in familias for d in familia]
    assert len(todas) == len(set(todas))


def test_las_bandas_agregadas_incluyen_las_de_cada_capa() -> None:
    assert "L1" in catalog.ALL_DEFAULT_THRESHOLDS
    assert "E3" in catalog.ALL_DEFAULT_THRESHOLDS
    assert "m_score" in catalog.ALL_DEFAULT_THRESHOLDS


def test_definition_for_localiza_por_clave() -> None:
    definition = catalog.definition_for("m_score")
    assert definition is not None
    assert definition.family == "forense"
    assert catalog.definition_for("no_existe") is None


def test_las_capas_aceptan_el_mapa_de_umbrales_completo(series: StatementSeries) -> None:
    """Cada capa coge los suyos e ignora el resto: así el servicio carga UNA vez
    los umbrales de BD y se los pasa a las tres."""
    todos = catalog.ALL_DEFAULT_THRESHOLDS
    assert evolution.compute(series, todos).get("E3", 2024) is not None
    assert forensic.compute(series, todos).get("m_score", 2024) is not None
