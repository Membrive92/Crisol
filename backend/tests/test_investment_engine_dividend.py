"""Tests de la Capa 3 (dividendo) — PHASE-44.4.

Engine puro, valores calculados a mano. La empresa base reparte un dividendo
holgadamente cubierto por la caja; los casos de riesgo (dividendo pagado con
deuda, payout errático, anomalía fiscal) usan fixtures propios.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.investment.analysis.engine import catalog, dividend
from app.modules.investment.analysis.engine.dividend import DividendResult
from app.modules.investment.analysis.engine.types import (
    Band,
    SecuritySnapshot,
    StatementSeries,
)
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


# ── Empresa sintética con dividendo cubierto ──────────────────────────


def _year(
    fiscal_year: int,
    *,
    net_income: int,
    cfo: int,
    capex: int,
    dividends: int,
    revenue: int,
    ebit: int,
    dna: int,
    shares: int = 100,
    cash: int = 200,
    financial: int = 100,
    buybacks: int = 0,
    sbc: int = 0,
    debt_change: int = 0,
    share_issuance: int = 0,
    taxes: int = 0,
    taxes_paid: int = 0,
    gains: int = 0,
    impairments: int = 0,
    receivables: int = 0,
    inventory: int = 0,
    payables: int = 0,
) -> CanonicalStatement:
    # Circulante y taxes_paid a 0 por defecto para que fcf_ebitda (y por tanto
    # Q3) sea computable con circulante constante entre años → Δwc_operating = 0.
    return CanonicalStatement(
        fiscal_year=fiscal_year,
        fiscal_year_end=date(fiscal_year, 12, 31),
        accounting_std=AccountingStd.GAAP,
        cash=dec(cash),
        current_financial_assets=dec(financial),
        receivables=dec(receivables),
        inventory=dec(inventory),
        accounts_payable=dec(payables),
        revenue=dec(revenue),
        ebit=dec(ebit),
        depreciation_amortization=dec(dna),
        impairments=dec(impairments),
        gains_on_sale_of_business=dec(gains),
        taxes=dec(taxes),
        taxes_paid=dec(taxes_paid),
        net_income=dec(net_income),
        shares_basic=dec(shares),
        sbc_expense=dec(sbc),
        cfo=dec(cfo),
        capex=dec(capex),
        dividends_paid=dec(dividends),
        buybacks=dec(buybacks),
        share_issuance=dec(share_issuance),
        debt_change=dec(debt_change),
    )


def _security(*, is_reit: bool = False, is_financial: bool = False) -> SecuritySnapshot:
    return SecuritySnapshot(
        ticker="DIV",
        sector=SectorInternal.CONSUMER_STAPLES,
        accounting_std=AccountingStd.GAAP,
        is_reit=is_reit,
        is_financial=is_financial,
    )


def _series_of(
    *statements: CanonicalStatement, is_reit: bool = False, is_financial: bool = False
) -> StatementSeries:
    return StatementSeries(
        security=_security(is_reit=is_reit, is_financial=is_financial),
        statements=tuple(statements),
        as_of=date(2025, 3, 31),
    )


def _latest() -> CanonicalStatement:
    """2024: NI 200, CFO 300, capex 100 → FCF 200; dividendo 80; DPS 0,80."""
    return _year(
        2024,
        net_income=200,
        cfo=300,
        capex=100,
        dividends=80,
        revenue=1000,
        ebit=250,
        dna=50,
        taxes=50,
    )


@pytest.fixture
def series() -> StatementSeries:
    return _series_of(
        _year(
            2022,
            net_income=160,
            cfo=240,
            capex=80,
            dividends=60,
            revenue=800,
            ebit=200,
            dna=40,
            taxes=40,
        ),
        _year(
            2023,
            net_income=180,
            cfo=270,
            capex=90,
            dividends=70,
            revenue=900,
            ebit=225,
            dna=45,
            taxes=45,
        ),
        _latest(),
    )


@pytest.fixture
def result(series: StatementSeries) -> DividendResult:
    return dividend.compute(series)


def _m(result: DividendResult, key: str, year: int = 2024):  # type: ignore[no-untyped-def]
    metric = result.get(key, year)
    assert metric is not None, f"la métrica {key} debe existir SIEMPRE"
    return metric


# ── Cobertura (D) ─────────────────────────────────────────────────────


def test_d1_payout_sobre_beneficio(result: DividendResult) -> None:
    """80 / 200 = 0,4 → verde (<60%)."""
    metric = _m(result, "D1")
    approx_dec(metric.value, "0.4")
    assert metric.band == "healthy"


def test_d2_payout_sobre_fcf(result: DividendResult) -> None:
    """80 / FCF 200 = 0,4 → verde."""
    metric = _m(result, "D2")
    approx_dec(metric.value, "0.4")
    assert metric.band == "healthy"


def test_d3_cobertura_fcf(result: DividendResult) -> None:
    """FCF 200 / 80 = 2,5 → verde (>1,6)."""
    metric = _m(result, "D3")
    approx_dec(metric.value, "2.5")
    assert metric.band == "healthy"


def test_d4_payout_ajustado_por_sbc() -> None:
    """Con SBC 40: 80 / (200 − 40) = 0,5. Sin SBC coincide con D2."""
    serie = _series_of(
        _year(
            2024,
            net_income=200,
            cfo=300,
            capex=100,
            dividends=80,
            revenue=1000,
            ebit=250,
            dna=50,
            sbc=40,
        ),
    )
    metric = dividend.compute(serie).get("D4", 2024)
    assert metric is not None
    approx_dec(metric.value, "0.5")


def test_d5_retorno_total_sobre_fcf() -> None:
    """(dividendo 80 + recompras 40) / FCF 200 = 0,6 → verde (<90%)."""
    serie = _series_of(
        _year(
            2024,
            net_income=200,
            cfo=300,
            capex=100,
            dividends=80,
            revenue=1000,
            ebit=250,
            dna=50,
            buybacks=40,
        ),
    )
    metric = dividend.compute(serie).get("D5", 2024)
    assert metric is not None
    approx_dec(metric.value, "0.6")
    assert metric.band == "healthy"


def test_d6_no_aplica_a_empresas_no_reit(result: DividendResult) -> None:
    metric = _m(result, "D6")
    assert metric.value is None
    assert metric.reason is not None
    assert "socimi" in metric.reason


def test_d8_margen_de_seguridad(result: DividendResult) -> None:
    """(FCF 200 − dividendo 80) / ventas 1000 = 0,12 → verde (>5%)."""
    metric = _m(result, "D8")
    approx_dec(metric.value, "0.12")
    assert metric.band == "healthy"


# ── Ajuste REIT ───────────────────────────────────────────────────────


def test_las_socimis_miden_la_cobertura_sobre_ffo() -> None:
    """FFO = NI 200 + D&A 50 + deterioros 0 − plusvalías 0 = 250.

    D1 (REIT) = dividendo 80 / FFO 250 = 0,32; D2 (REIT) = 80 / 250 = 0,32
    (usa FFO, no FCF); D6 = 80 / 250 = 0,32 → verde.
    """
    serie = _series_of(_latest(), is_reit=True)
    result = dividend.compute(serie)
    approx_dec(_m(result, "D1").value, "0.32")
    approx_dec(_m(result, "D2").value, "0.32")
    d6 = _m(result, "D6")
    approx_dec(d6.value, "0.32")
    assert d6.band == "healthy"


def test_en_no_reit_d2_usa_la_caja_libre_no_ffo(result: DividendResult) -> None:
    """Confirma que la base cambia: no-REIT D2 = 0,4 (sobre FCF 200), no 0,32."""
    approx_dec(_m(result, "D2").value, "0.4")


# ── Calidad de la caja (Q) ────────────────────────────────────────────


def test_q1_conversion_cfo_sobre_beneficio(result: DividendResult) -> None:
    """CFO 300 / NI 200 = 1,5 → verde (>1,0)."""
    metric = _m(result, "Q1")
    approx_dec(metric.value, "1.5")
    assert metric.band == "healthy"


def test_q2_conversion_fcf_sobre_ebitda(result: DividendResult) -> None:
    """FCF 200 / EBITDA (250+50=300) = 0,666667 → verde (>50%)."""
    metric = _m(result, "Q2")
    approx_dec(metric.value, "0.666667")
    assert metric.band == "healthy"


def test_q3_divergencia_fcf_dual(result: DividendResult) -> None:
    """fcf_cfo 200 vs fcf_ebitda 2024.

    fcf_ebitda = EBITDA 300 − capex 100 − Δwc_operating − taxes_paid(0).
    Sin partidas de circulante, Δwc_operating = 0. → 200. Divergencia 0 → verde.
    """
    metric = _m(result, "Q3")
    approx_dec(metric.value, "0")
    assert metric.band == "healthy"


def test_q5_peso_de_extraordinarios() -> None:
    """|plusvalías 60 − deterioros 10| / |EBT 250| = 0,2 → borde ámbar."""
    serie = _series_of(
        _year(
            2024,
            net_income=200,
            cfo=300,
            capex=100,
            dividends=80,
            revenue=1000,
            ebit=250,
            dna=50,
            taxes=50,
            gains=60,
            impairments=10,
        ),
    )
    metric = dividend.compute(serie).get("Q5", 2024)
    assert metric is not None
    approx_dec(metric.value, "0.2")


# ── Soporte del balance (B) ───────────────────────────────────────────


def test_b3_años_de_dividendo_en_caja(result: DividendResult) -> None:
    """(caja 200 + financieros 100) / dividendo 80 = 3,75 → verde (>2)."""
    metric = _m(result, "B3")
    approx_dec(metric.value, "3.75")
    assert metric.band == "healthy"


def test_b4_dividendo_financiado_con_deuda() -> None:
    """Dividendo 250 > FCF 200 y entra deuda → rojo."""
    serie = _series_of(
        _year(
            2024,
            net_income=200,
            cfo=300,
            capex=100,
            dividends=250,
            revenue=1000,
            ebit=250,
            dna=50,
            debt_change=100,
        ),
    )
    flags = dividend.compute(serie).flags
    b4 = [f for f in flags if f.key == "B4_dividend_funded_externally"]
    assert len(b4) == 1
    assert b4[0].severity == "red"
    assert b4[0].evidence["debt_change"] == "100"


def test_b4_no_salta_si_el_dividendo_cabe_en_la_caja(result: DividendResult) -> None:
    assert not [f for f in result.flags if f.key == "B4_dividend_funded_externally"]


def test_b1_la_deuda_compite_con_el_dividendo() -> None:
    """S4 en rojo + D2 en ámbar → cruce B1 ámbar. Las bandas forenses se
    inyectan (vienen de la Capa 1)."""
    serie = _series_of(
        _year(
            2024, net_income=200, cfo=300, capex=100, dividends=150, revenue=1000, ebit=250, dna=50
        ),  # D2 = 150/200 = 0,75 → ámbar
    )
    bands: dict[str, Band | None] = {"S4": "stressed", "S2": "healthy"}
    flags = dividend.compute(serie, forensic_bands=bands).flags
    assert any(f.key == "B1_debt_competes_with_dividend" for f in flags)


def test_b2_los_intereses_cobran_antes() -> None:
    """S2 en rojo + payout >60% → B2 rojo compuesto."""
    serie = _series_of(
        _year(
            2024, net_income=200, cfo=300, capex=100, dividends=150, revenue=1000, ebit=250, dna=50
        ),
    )
    bands: dict[str, Band | None] = {"S2": "stressed", "S4": "healthy"}
    flags = dividend.compute(serie, forensic_bands=bands).flags
    b2 = [f for f in flags if f.key == "B2_interest_priority"]
    assert len(b2) == 1
    assert b2[0].severity == "red"


def test_los_cruces_de_balance_no_se_evaluan_sin_bandas(result: DividendResult) -> None:
    """Sin `forensic_bands`, B1/B2 no se evalúan (no hay dato de S2/S4)."""
    assert not [f for f in result.flags if f.key.startswith(("B1", "B2"))]


# ── Anomalía fiscal (Q4) ──────────────────────────────────────────────


def test_q4_caida_del_tipo_efectivo() -> None:
    """ETR 40%, 40%, 20%: el último cae 20 pp bajo la mediana (40%) → ámbar."""
    serie = _series_of(
        _year(
            2022,
            net_income=60,
            cfo=100,
            capex=20,
            dividends=20,
            revenue=500,
            ebit=120,
            dna=20,
            taxes=40,
        ),  # EBT 100, ETR 0,4
        _year(
            2023,
            net_income=60,
            cfo=100,
            capex=20,
            dividends=20,
            revenue=500,
            ebit=120,
            dna=20,
            taxes=40,
        ),  # ETR 0,4
        _year(
            2024,
            net_income=80,
            cfo=100,
            capex=20,
            dividends=20,
            revenue=500,
            ebit=120,
            dna=20,
            taxes=20,
        ),  # EBT 100, ETR 0,2
    )
    flags = dividend.compute(serie).flags
    q4 = [f for f in flags if f.key == "Q4_tax_anomaly"]
    assert len(q4) == 1
    assert q4[0].evidence["fiscal_year"] == 2024


# ── Trayectoria (T) ───────────────────────────────────────────────────


def test_d7_serie_de_dps(result: DividendResult) -> None:
    """DPS = dividendo / acciones: 0,60 → 0,70 → 0,80."""
    dps = result.dps_series
    assert [p.fiscal_year for p in dps] == [2022, 2023, 2024]
    approx_dec(dps[0].dps, "0.6")
    approx_dec(dps[2].dps, "0.8")


def test_t1_racha_sin_recorte(result: DividendResult) -> None:
    """DPS crece los tres años → 2 subidas consecutivas sin recorte."""
    assert result.trajectory.streak_no_cut == 2


def test_t1_un_recorte_rompe_la_racha() -> None:
    """DPS 0,60 → 0,70 → 0,50: el último año recorta → racha 0."""
    serie = _series_of(
        _year(2022, net_income=160, cfo=240, capex=80, dividends=60, revenue=800, ebit=200, dna=40),
        _year(2023, net_income=180, cfo=270, capex=90, dividends=70, revenue=900, ebit=225, dna=45),
        _year(
            2024, net_income=200, cfo=300, capex=100, dividends=50, revenue=1000, ebit=250, dna=50
        ),
    )
    assert dividend.compute(serie).trajectory.streak_no_cut == 0


def test_t2_cagr_del_dividendo(result: DividendResult) -> None:
    """DPS 0,60 → 0,80 en 2 años: (0,8/0,6)^(1/2) − 1 = 0,154701 → verde (>0)."""
    metric = _m(result, "T2")
    approx_dec(metric.value, "0.154701")
    assert metric.band == "healthy"


def test_t2_dividendo_decreciente_es_rojo() -> None:
    """DPS 0,80 → 0,60: CAGR negativo → rojo directo."""
    serie = _series_of(
        _year(
            2022, net_income=200, cfo=300, capex=100, dividends=80, revenue=1000, ebit=250, dna=50
        ),
        _year(
            2023, net_income=200, cfo=300, capex=100, dividends=70, revenue=1000, ebit=250, dna=50
        ),
        _year(
            2024, net_income=200, cfo=300, capex=100, dividends=60, revenue=1000, ebit=250, dna=50
        ),
    )
    metric = dividend.compute(serie).get("T2", 2024)
    assert metric is not None
    assert metric.value is not None and metric.value < 0
    assert metric.band == "stressed"


def test_t3_estabilidad_del_payout(result: DividendResult) -> None:
    """Payout sobre FCF: 60/160=0,375 · 70/180=0,388889 · 80/200=0,4.

    σ poblacional ≈ 0,0102272 → ×100 = 1,022719 pp → verde (<20).
    """
    metric = _m(result, "T3")
    approx_dec(metric.value, "1.022719", places=5)
    assert metric.band == "healthy"


def test_t3_exige_tres_ejercicios() -> None:
    serie = _series_of(
        _year(2023, net_income=180, cfo=270, capex=90, dividends=70, revenue=900, ebit=225, dna=45),
        _latest(),
    )
    metric = dividend.compute(serie).get("T3", 2024)
    assert metric is not None
    assert metric.value is None
    assert metric.reason is not None
    assert "al menos 3" in metric.reason


def test_t4_desaceleracion_del_dividendo() -> None:
    """DPS 0,50 → 0,80 → 0,82: el último salto (2,5%) es mucho menor que el CAGR
    de la serie → momentum a la baja."""
    serie = _series_of(
        _year(
            2022, net_income=200, cfo=300, capex=100, dividends=50, revenue=1000, ebit=250, dna=50
        ),
        _year(
            2023, net_income=200, cfo=300, capex=100, dividends=80, revenue=1000, ebit=250, dna=50
        ),
        _year(
            2024, net_income=200, cfo=300, capex=100, dividends=82, revenue=1000, ebit=250, dna=50
        ),
    )
    assert dividend.compute(serie).trajectory.momentum_slowdown is True


def test_t4_dividendo_que_acelera_no_marca_desaceleracion(result: DividendResult) -> None:
    assert result.trajectory.momentum_slowdown is False


# ── Empresa que no reparte dividendo ──────────────────────────────────


def test_una_empresa_sin_dividendo_calcula_lo_que_puede() -> None:
    """La Capa 3 no decide "no aplicable" (eso es la síntesis): calcula
    mecánicamente. Payout 0 → verde; cobertura → not_computable (÷0)."""
    serie = _series_of(
        _year(
            2024, net_income=200, cfo=300, capex=100, dividends=0, revenue=1000, ebit=250, dna=50
        ),
    )
    result = dividend.compute(serie)
    d2 = result.get("D2", 2024)
    assert d2 is not None
    assert d2.value == dec(0)  # payout 0%
    d3 = result.get("D3", 2024)
    assert d3 is not None
    assert d3.value is None  # FCF / 0 dividendos
    assert d3.reason is not None
    assert "cero" in d3.reason


# ── Huecos ────────────────────────────────────────────────────────────


def test_un_hueco_deja_la_metrica_sin_calcular() -> None:
    """Sin `cfo` no hay FCF, y sin FCF no hay cobertura D3."""
    serie = _series_of(
        CanonicalStatement(
            fiscal_year=2024,
            fiscal_year_end=date(2024, 12, 31),
            accounting_std=AccountingStd.GAAP,
            dividends_paid=dec(80),
            net_income=dec(200),
        ),
    )
    metric = dividend.compute(serie).get("D3", 2024)
    assert metric is not None
    assert metric.value is None
    assert metric.status == "not_computable"


# ── Catálogo agregado ─────────────────────────────────────────────────


def test_el_catalogo_agregado_incluye_la_capa_dividendo() -> None:
    """33 base + 2 evolutivas + 8 forenses + 14 dividendo + 7 valoración = 64.

    Las 7 de valoración (PHASE-44.12) están catalogadas para que la UI lea su
    etiqueta de una sola fuente, pero NO siembran umbral: su `direction` es
    `None`, así que `ALL_DEFAULT_THRESHOLDS` no crece con ellas.
    """
    assert len(catalog.ALL_METRIC_DEFINITIONS) == 64
    assert len(set(catalog.ALL_METRIC_KEYS)) == 64


def test_el_catalogo_dividendo_tiene_14_metricas() -> None:
    assert len(dividend.METRIC_CATALOG) == 14


def test_no_hay_claves_repetidas_con_otras_capas() -> None:
    assert len(catalog.ALL_METRIC_KEYS) == len(set(catalog.ALL_METRIC_KEYS))


def test_dividend_acepta_el_mapa_de_umbrales_completo(series: StatementSeries) -> None:
    result = dividend.compute(series, catalog.ALL_DEFAULT_THRESHOLDS)
    assert result.get("D2", 2024) is not None


def test_en_una_financiera_las_ratios_sobre_caja_libre_no_se_calculan() -> None:
    """PHASE-44.19 — la cobertura sobre caja libre no describe a un banco.

    Hasta ahora esto no hacía falta porque la pestaña entera se ocultaba para
    toda financiera. Al dejar de ocultarla —lo que recupera ocho métricas ya
    calculadas— estas cinco habrían salido con banda y color, que es peor que no
    enseñarlas: en un banco la caja libre del esquema CFO − capex no significa lo
    que significa en una industrial.

    Se marcan igual que D6 con las socimis: `not_computable` CON motivo, jamás
    omitidas (regla dura de ARCHITECTURE §4.2).
    """
    sobre_caja = {"D2", "D3", "D4", "D5", "D8"}
    banco = dividend.compute(_series_of(_latest(), is_financial=True), None)
    normal = dividend.compute(_series_of(_latest()), None)

    for key in sobre_caja:
        del_banco = [m for m in banco.metrics if m.key == key]
        assert del_banco, f"{key} no puede desaparecer: se lista con motivo"
        for metric in del_banco:
            assert metric.status == "not_computable", f"{key} no debería calcularse en un banco"
            assert metric.reason and "financiera" in metric.reason
            assert metric.band is None

    # D1 divide por BENEFICIO, no por caja: es contable y vale en un banco igual
    # que en una fábrica. Si se eximiera también, la pestaña quedaría vacía y no
    # habríamos arreglado nada.
    d1_banco = [m for m in banco.metrics if m.key == "D1"]
    assert any(m.value is not None for m in d1_banco), "D1 sí aplica a una financiera"

    # Y no se ha apagado de más: en una no financiera siguen calculándose.
    for key in sobre_caja:
        assert any(m.value is not None for m in normal.metrics if m.key == key), key
