"""Goldens de la calibración sectorial (PHASE-44.21).

Uno por perfil crítico. Cada uno comprueba una DECISIÓN del documento de
calibración sobre una empresa sintética que la ejercita — no que el código haga
lo que el código hace.

El engine sigue siendo puro: sin BD, sin red, sin reloj.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.modules.investment.analysis.engine import base_ratios, synthesis
from app.modules.investment.analysis.engine import dividend as dividend_layer
from app.modules.investment.analysis.engine import evolution as evolution_layer
from app.modules.investment.analysis.engine import forensic as forensic_layer
from app.modules.investment.analysis.engine import stress as stress_layer
from app.modules.investment.analysis.engine.catalog import ALL_DEFAULT_THRESHOLDS
from app.modules.investment.analysis.engine.sector_profiles import (
    _with_cuts,
    higher,
    resolve_thresholds,
)
from app.modules.investment.analysis.engine.types import SecuritySnapshot, StatementSeries
from app.modules.investment.enums import AccountingStd, SectorInternal
from app.modules.investment.fundamentals.canonical import CanonicalStatement


def dec(value: str | int) -> Decimal:
    return Decimal(value)


def _year(fiscal_year: int, *, revenue: int, dividends: int) -> CanonicalStatement:
    """Un ejercicio internamente coherente: EBIT = 30% de ventas − D&A y
    CFO = beneficio + D&A, para que ni los accruals ni Q3 salten por un
    descuadre del propio fixture."""
    da = 60
    ebit = revenue * 30 // 100 - da
    interest = 15
    ebt = ebit - interest
    taxes = ebt // 4
    net_income = ebt - taxes
    return CanonicalStatement(
        fiscal_year=fiscal_year,
        fiscal_year_end=date(fiscal_year, 12, 31),
        accounting_std=AccountingStd.GAAP,
        cash=dec(300),
        current_financial_assets=dec(100),
        receivables=dec(150),
        inventory=dec(150),
        current_assets=dec(700),
        ppe_net=dec(500),
        goodwill=dec(50),
        total_assets=dec(revenue * 12 // 10),
        short_term_debt=dec(50),
        ltd_current_portion=dec(50),
        accounts_payable=dec(120),
        current_liabilities=dec(300),
        long_term_debt=dec(200),
        total_liabilities=dec(revenue * 4 // 10),
        retained_earnings=dec(400),
        equity=dec(revenue * 8 // 10),
        revenue=dec(revenue),
        cogs=dec(revenue * 55 // 100),
        sga_expense=dec(revenue * 15 // 100),
        depreciation_amortization=dec(da),
        impairments=dec(0),
        gains_on_sale_of_business=dec(0),
        ebit=dec(ebit),
        interest_expense=dec(interest),
        taxes=dec(taxes),
        taxes_paid=dec(taxes),
        net_income=dec(net_income),
        shares_basic=dec(100),
        share_issuance=dec(0),
        cfo=dec(net_income + da),
        capex=dec(80),
        dividends_paid=dec(dividends),
    )


def _statements() -> tuple[CanonicalStatement, ...]:
    return (
        _year(2021, revenue=1000, dividends=60),
        _year(2022, revenue=1100, dividends=66),
        _year(2023, revenue=1200, dividends=72),
        _year(2024, revenue=1300, dividends=78),
    )


def _series(
    sector: SectorInternal,
    *,
    is_financial: bool = False,
    is_reit: bool = False,
    statements: tuple[CanonicalStatement, ...] | None = None,
) -> StatementSeries:
    return StatementSeries(
        security=SecuritySnapshot(
            ticker="TEST",
            sector=sector,
            accounting_std=AccountingStd.GAAP,
            is_financial=is_financial,
            is_reit=is_reit,
        ),
        statements=statements or _statements(),
        as_of=date(2025, 3, 31),
    )


def _synthesize(series: StatementSeries) -> synthesis.SynthesisResult:
    """Encadena las capas con los umbrales DEL SECTOR, como hace el servicio.

    Llamarlas con los defaults sería probar el motor genérico: la calibración
    sectorial sólo existe cuando alguien la resuelve.
    """
    specs = resolve_thresholds(
        series.security.sector,
        series.security.accounting_std,
        is_financial=series.security.is_financial,
    )
    return synthesis.compute(
        series,
        base_ratios.compute(series, specs),
        evolution_layer.compute(series, specs),
        forensic_layer.compute(series, specs),
        dividend_layer.compute(series, specs),
        stress_layer.compute(series),
    )


# ── Bandas por sector ─────────────────────────────────────────────────


def test_la_utility_apalancada_sale_ambar_y_no_roja() -> None:
    """4,8× de deuda neta sobre EBITDA es normal en una regulada (la mediana de
    grado de inversión del sector está en 5,1×) y catastrófico en el genérico."""
    utility = resolve_thresholds(SectorInternal.UTILITIES, AccountingStd.GAAP)
    assert utility["S4"].band_for(dec("4.8")) == "caution"
    assert ALL_DEFAULT_THRESHOLDS["S4"].band_for(dec("4.8")) == "stressed"


def test_la_tecnologica_apalancada_no_se_libra() -> None:
    """El perfil no es «relajar»: en asset-light, 2,5× ya es rojo."""
    tech = resolve_thresholds(SectorInternal.TECHNOLOGY, AccountingStd.GAAP)
    assert tech["S4"].band_for(dec("2.5")) == "stressed"
    assert ALL_DEFAULT_THRESHOLDS["S4"].band_for(dec("2.5")) == "caution"


def test_un_delta_con_la_geometria_equivocada_revienta_al_escribirlo() -> None:
    """En `higher_better` los cortes son el suelo y en `lower_better` el techo:
    los mismos dos números invierten el semáforo, y eso no puede pasar en
    silencio."""
    with pytest.raises(ValueError, match="significan lo contrario"):
        _with_cuts(ALL_DEFAULT_THRESHOLDS["S4"], higher("1", "2"))


# ── Reglas cruzadas ───────────────────────────────────────────────────


def test_golden_utility_enlaza_quien_financia_el_payout() -> None:
    """RC-2: en una regulada un payout alto es su modelo. Lo que decide es quién
    financia el exceso, y eso lo miran C7 y B4 — que no se relajan por sector."""
    caros = tuple(replace(s, dividends_paid=dec(200)) for s in _statements())
    resultado = _synthesize(_series(SectorInternal.UTILITIES, statements=caros))
    rc2 = [f for f in resultado.flags if f.key == "RC2_utility_payout_needs_funding_check"]
    assert rc2, "un payout en zona alta debería enlazar la pregunta de la financiación"
    assert "quién paga el exceso" in rc2[0].message
    assert rc2[0].severity == "info", "es un enlace de lectura, no una alarma nueva"


def test_golden_retail_con_circulante_negativo_no_sale_en_rojo_de_liquidez() -> None:
    """RC-1: cobrar antes de pagar es el modelo de la distribución.

    Con un ratio corriente por debajo de 1 y un ciclo de conversión negativo, el
    rojo permanente que salía es el ejemplo de manual de una alarma que se
    aprende a ignorar — y entonces tampoco se mira la que sí importa.
    """
    retail = tuple(
        replace(
            s,
            receivables=dec(0),
            inventory=dec(50),
            accounts_payable=dec(700),
            current_assets=dec(400),
            current_liabilities=dec(800),
        )
        for s in _statements()
    )
    series = _series(SectorInternal.CONSUMER_STAPLES, statements=retail)
    resultado = base_ratios.compute(
        series, resolve_thresholds(SectorInternal.CONSUMER_STAPLES, AccountingStd.GAAP)
    )

    ccc = resultado.get("A5", 2024)
    assert ccc is not None and ccc.value is not None and ccc.value < 0, "el fixture no es un retail"
    l1 = resultado.get("L1", 2024)
    assert l1 is not None and l1.value is not None and l1.value < 1
    assert l1.band != "stressed", "un modelo de circulante negativo no es riesgo de liquidez"
    assert l1.reason is not None and "cobra a sus clientes antes" in l1.reason
    assert [f for f in resultado.flags if f.key == "RC1_negative_working_capital"]


# ── Perfiles completos ────────────────────────────────────────────────


def test_golden_banco_apaga_lo_que_no_significa_nada_y_lo_explica() -> None:
    """La whitelist financiera: se apaga lo que no describe a un banco y cada
    apagón dice por qué. Un «N/A» mudo es indistinguible de un fallo."""
    resultado = _synthesize(_series(SectorInternal.FINANCIALS, is_financial=True))
    señales = {s.key: s for q in resultado.questions for s in q.signals}

    for key in ("S4", "Q2", "Q3"):
        señal = señales.get(key)
        assert señal is not None and señal.band is None, f"{key} no debería llevar semáforo"
        assert señal.reason, f"{key} se apaga sin decir por qué"

    resiliencia = resultado.question("resilience")
    assert resiliencia is not None
    assert resiliencia.audited is False
    assert any("capital regulatorio" in r for r in resiliencia.unaudited_reasons)

    contabilidad = resultado.question("accounting")
    assert contabilidad is not None
    assert any("cobertura forense limitada" in n for n in contabilidad.notes)


def test_golden_banco_conserva_el_nucleo_de_su_juicio() -> None:
    """Si se apagara todo, el informe de un banco dejaría de tener veredicto y
    nadie se enteraría: todas sus métricas saldrían grises con una explicación
    razonable."""
    bank = resolve_thresholds(SectorInternal.FINANCIALS, AccountingStd.GAAP, is_financial=True)
    for key in ("R5", "R6", "S3", "D1", "Q1", "Q5", "S8"):
        assert bank[key].applies, f"{key} debería seguir aplicando en un banco"
    assert bank["S3"].model_variant == "bank_capital_proxy"


def test_golden_reit_apaga_los_accruals_y_juzga_por_ffo() -> None:
    """En una socimi la amortización del inmueble domina los devengos: el modelo
    de Sloan mediría contabilidad inmobiliaria, no manipulación."""
    reit = resolve_thresholds(SectorInternal.REAL_ESTATE, AccountingStd.GAAP)
    assert reit["accruals"].applies is False
    assert "FFO" in (reit["accruals"].not_applicable_reason or "")
    assert reit["D6"].high_ok == dec("0.80")


def test_golden_la_resolucion_cae_al_generico_sin_perfil() -> None:
    """Un sector sin delta hereda el corte genérico: los perfiles son deltas, no
    doce copias que mantener sincronizadas."""
    for sector in (SectorInternal.INDUSTRIALS, SectorInternal.UNKNOWN):
        resolved = resolve_thresholds(sector, AccountingStd.GAAP)
        assert resolved["S4"].high_ok == ALL_DEFAULT_THRESHOLDS["S4"].high_ok


# ── Portantes ─────────────────────────────────────────────────────────


def test_golden_una_pregunta_sin_portante_no_se_da_por_auditada() -> None:
    """El cuarto estado. Sin flujo de explotación no hay Q1, y Q1 es portante de
    «¿genera caja de verdad?»: la pregunta sale gris, no verde."""
    sin_cfo = tuple(replace(s, cfo=None) for s in _statements())
    caja = _synthesize(_series(SectorInternal.INDUSTRIALS, statements=sin_cfo)).question("cash")
    assert caja is not None
    assert caja.audited is False
    assert caja.unaudited_reasons, "una pregunta no auditada dice QUÉ le falta"
    assert "Q1" in caja.load_bearing


def test_golden_con_los_portantes_evaluados_la_pregunta_si_se_audita() -> None:
    """La otra mitad: sin esto el gris sería universal, y tan poco informativo
    como el verde que sustituye."""
    caja = _synthesize(_series(SectorInternal.INDUSTRIALS)).question("cash")
    assert caja is not None
    assert caja.audited is True
    assert caja.unaudited_reasons == ()


# ── F7 con denominador variable ───────────────────────────────────────


def test_golden_el_c_score_de_un_sector_sin_inventario_no_cuenta_el_check_de_inventario() -> None:
    """El denominador variable de F7.

    A una eléctrica no le suben los días de inventario porque no tiene
    inventario: la ingesta le imputa cero (§4.5) y el check pasa SIEMPRE. Un
    aprobado automático no es una comprobación — infla el denominador del score
    con algo que no puede fallar. Fuera del cómputo.
    """
    utility = forensic_layer.compute(
        _series(SectorInternal.UTILITIES),
        resolve_thresholds(SectorInternal.UTILITIES, AccountingStd.GAAP),
    ).breakdown_for("F7", 2024)
    industrial = forensic_layer.compute(_series(SectorInternal.INDUSTRIALS)).breakdown_for(
        "F7", 2024
    )

    assert utility is not None and industrial is not None
    assert forensic_layer.C_SCORE_INVENTORY_CHECK not in utility.checks
    assert forensic_layer.C_SCORE_INVENTORY_CHECK in industrial.checks
    assert len(utility.checks) == len(industrial.checks) - 1


def test_golden_por_debajo_del_minimo_de_checks_el_c_score_no_se_publica() -> None:
    """Un 2 sobre 3 y un 2 sobre 6 son cosas distintas, y la banda de F7 está
    escrita para el segundo. Antes que un número descontextualizado, un
    `not_computable` que explica cuántos checks aplicaban."""
    amount, checks = forensic_layer.compute_c_score(
        _statements()[-1],
        _statements()[-2],
        inapplicable_checks=frozenset(
            {
                "C1_beneficio_por_delante_de_caja",
                "C2_dias_de_cobro_suben",
                forensic_layer.C_SCORE_INVENTORY_CHECK,
            }
        ),
    )
    assert amount.value is None and checks == {}
    assert amount.reason is not None and "aplican a este sector" in amount.reason


def test_golden_la_regla_de_inventario_no_se_comprueba_donde_no_hay_inventario() -> None:
    """Y se dice como lo que es: «no se plantea aquí», no «no se pudo comprobar».
    Lo segundo invita a ingerir más datos, y aquí no hay nada que ingerir."""
    resultado = _synthesize(_series(SectorInternal.UTILITIES))
    c3 = next(s for q in resultado.questions for s in q.signals if s.key == "C3_inventory_vs_cogs")
    assert c3.outcome == "informational"
    assert c3.reason is not None and "sin inventario material" in c3.reason
