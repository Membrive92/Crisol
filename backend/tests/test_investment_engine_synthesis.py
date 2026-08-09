"""Tests de las capas 3.5 (stress) y 4 (síntesis) — PHASE-44.5.

Engine puro, valores calculados a mano. La síntesis se prueba encadenando las
capas reales sobre empresas sintéticas (sana, dudosa, en quiebra) y verificando
que el veredicto y el perfil salen de las reglas explícitas del DESIGN §5.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.modules.investment.analysis.engine import (
    base_ratios,
    flag_rules,
    synthesis,
)
from app.modules.investment.analysis.engine import (
    dividend as dividend_layer,
)
from app.modules.investment.analysis.engine import (
    evolution as evolution_layer,
)
from app.modules.investment.analysis.engine import (
    forensic as forensic_layer,
)
from app.modules.investment.analysis.engine import (
    stress as stress_layer,
)
from app.modules.investment.analysis.engine.stress import StressParams
from app.modules.investment.analysis.engine.types import (
    FlagEvaluation,
    SecuritySnapshot,
    StatementSeries,
)
from app.modules.investment.enums import AccountingStd, SectorInternal
from app.modules.investment.fundamentals.canonical import CanonicalStatement, Provenance


def dec(value: str | int) -> Decimal:
    return Decimal(value)


def approx_dec(value: Decimal | None, expected: str, places: int = 6) -> None:
    assert value is not None
    quantum = Decimal(10) ** -places
    assert value.quantize(quantum) == Decimal(expected).quantize(
        quantum
    ), f"esperado {expected}, obtenido {value}"


# ── Empresa sana con dividendo cubierto ───────────────────────────────


def _healthy_year(fiscal_year: int, *, revenue: int, dividends: int) -> CanonicalStatement:
    """Un ejercicio con la cuenta de resultados y el flujo de caja INTERNAMENTE
    coherentes: EBIT = 30% de ventas − D&A; CFO = beneficio neto + D&A (sin
    variación de circulante). Así fcf_cfo y fcf_ebitda casan salvo por los
    intereses, y ni los accruals ni Q3 saltan por un descuadre del fixture."""
    da = 60
    ebit = revenue * 30 // 100 - da
    interest = 15
    ebt = ebit - interest
    taxes = ebt // 4
    net_income = ebt - taxes
    cfo = net_income + da
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
        cfo=dec(cfo),
        capex=dec(80),
        dividends_paid=dec(dividends),
    )


def _healthy_series() -> StatementSeries:
    return StatementSeries(
        security=SecuritySnapshot(
            ticker="SANA",
            sector=SectorInternal.CONSUMER_STAPLES,
            accounting_std=AccountingStd.GAAP,
        ),
        statements=(
            _healthy_year(2021, revenue=1000, dividends=60),
            _healthy_year(2022, revenue=1100, dividends=66),
            _healthy_year(2023, revenue=1200, dividends=72),
            _healthy_year(2024, revenue=1300, dividends=78),
        ),
        as_of=date(2025, 3, 31),
    )


def _stress_year(fiscal_year: int) -> CanonicalStatement:
    """Ejercicio de números redondos para verificar el stress a mano: FCF 200,
    dividendo 80, deuda total 300, tipo efectivo 20%."""
    return CanonicalStatement(
        fiscal_year=fiscal_year,
        fiscal_year_end=date(fiscal_year, 12, 31),
        accounting_std=AccountingStd.GAAP,
        cash=dec(300),
        current_financial_assets=dec(100),
        current_assets=dec(700),
        total_assets=dec(1400),
        short_term_debt=dec(50),
        ltd_current_portion=dec(50),
        current_liabilities=dec(300),
        long_term_debt=dec(200),
        total_liabilities=dec(560),
        equity=dec(840),
        revenue=dec(1000 + (fiscal_year - 2022) * 100),
        cogs=dec(550),
        depreciation_amortization=dec(50),
        impairments=dec(0),
        gains_on_sale_of_business=dec(0),
        ebit=dec(200 + (fiscal_year - 2022) * 25),  # Δebit/Δrevenue = 0,25
        interest_expense=dec(20),
        taxes=dec(50),
        taxes_paid=dec(50),
        net_income=dec(200),
        shares_basic=dec(100),
        cfo=dec(300),
        capex=dec(100),
        dividends_paid=dec(80),
    )


def _stress_series() -> StatementSeries:
    return StatementSeries(
        security=SecuritySnapshot(
            ticker="STR", sector=SectorInternal.INDUSTRIALS, accounting_std=AccountingStd.GAAP
        ),
        statements=(_stress_year(2022), _stress_year(2023), _stress_year(2024)),
        as_of=date(2025, 3, 31),
    )


def _synthesize(
    series: StatementSeries, params: StressParams | None = None
) -> synthesis.SynthesisResult:
    base = base_ratios.compute(series)
    evolution = evolution_layer.compute(series)
    forensic = forensic_layer.compute(series)
    dividend = dividend_layer.compute(series)
    stress = stress_layer.compute(series, params)
    return synthesis.compute(series, base, evolution, forensic, dividend, stress)


# ══ CAPA 3.5 — STRESS ════════════════════════════════════════════════


def test_margen_de_contribucion_es_la_mediana_de_la_serie() -> None:
    """Δebit/Δrevenue = 25/100 = 0,25 en cada tramo → mediana 0,25."""
    margin = stress_layer.estimate_contribution_margin(_stress_series())
    approx_dec(margin, "0.25")


def test_st1_shock_de_ingresos() -> None:
    """Ventas −20% sobre 1.200: Δebit = 0,25 × (−240) = −60.

    FCF base = CFO 300 − capex 100 = 200. tax shield = 1 − 50/250 = 0,8.
    ΔFCF = −60 × 0,8 = −48 → FCF' = 152. Cobertura 200/80=2,5 → 152/80=1,9.
    """
    result = stress_layer.compute(_stress_series())
    st1 = result.get("ST1_revenue_-20")
    assert st1 is not None
    approx_dec(st1.coverage_before, "2.5")
    approx_dec(st1.coverage_after, "1.9")
    assert st1.label == "escenario hipotético"


def test_st2_shock_de_tipos() -> None:
    """Deuda total = 50+50+200 = 300. Variable 30% = 90.

    +200 pb → interés extra 90 × 0,02 = 1,8. tax shield 0,8 → ΔFCF −1,44.
    FCF 200 → 198,56. Cobertura 2,5 → 198,56/80 = 2,4820.
    """
    result = stress_layer.compute(_stress_series())
    st2 = result.get("ST2_rates_+200bps")
    assert st2 is not None
    approx_dec(st2.coverage_after, "2.482")


def test_st3_breakeven_del_dividendo() -> None:
    """Cobertura base 2,5 → breakeven = 1 − 1/2,5 = 0,6.

    La caja libre puede caer un 60% antes de no cubrir el dividendo.
    """
    result = stress_layer.compute(_stress_series())
    approx_dec(result.breakeven_fcf_drop, "0.6")


def test_los_parametros_de_stress_son_editables() -> None:
    """La UI puede pedir un shock distinto del default."""
    result = stress_layer.compute(_stress_series(), StressParams(revenue_drops=(dec("0.50"),)))
    st1 = result.by_family("ST1")
    assert len(st1) == 1
    assert "50%" in st1[0].parameter


def test_sin_margen_estimable_no_hay_st1() -> None:
    """Un solo ejercicio no da para estimar el apalancamiento operativo."""
    serie = StatementSeries(
        security=SecuritySnapshot(
            ticker="X", sector=SectorInternal.INDUSTRIALS, accounting_std=AccountingStd.GAAP
        ),
        statements=(_stress_year(2024),),
        as_of=date(2025, 3, 31),
    )
    result = stress_layer.compute(serie)
    assert result.contribution_margin is None
    assert result.by_family("ST1") == ()


# ══ CAPA 4 — SÍNTESIS ════════════════════════════════════════════════


def test_una_empresa_sana_no_tiene_ninguna_pregunta_roja() -> None:
    """Las 4 preguntas existen siempre y ninguna sale roja para una empresa
    sólida. (No se exige verde en todas: una empresa buena pero estable puede
    quedar en ámbar en 'caja' por un F-Score que premia la mejora, no el nivel.)"""
    result = _synthesize(_healthy_series())
    assert {q.key for q in result.questions} == {
        "accounting",
        "cash",
        "dividend",
        "resilience",
    }
    for question in result.questions:
        assert question.verdict != "stressed", f"{question.key}: {question.red_signals}"


def test_el_veredicto_de_dividendo_de_una_empresa_sana_es_healthy() -> None:
    assert _synthesize(_healthy_series()).dividend_verdict == "healthy"


# ── Matriz de seguridad (regla probada con entradas construidas) ──────


def _forensic_with(**bands: str) -> forensic_layer.ForensicResult:
    """Un ForensicResult del último año con las bandas indicadas.

    Prueba la REGLA de la matriz de seguridad sin depender de que un fixture
    sintético produzca por casualidad exactamente esas bandas.
    """
    from app.modules.investment.analysis.engine.types import MetricResult

    # El F-Score se juzga por VALOR (≥7), no por banda: su value refleja la banda
    # para que la regla (f_score.value >= 7) se ejercite de verdad.
    f_score_value = {"healthy": dec(8), "caution": dec(5), "stressed": dec(2)}
    metrics = []
    for key, band in bands.items():
        value = f_score_value[band] if key == "f_score" else dec(1)
        metrics.append(
            MetricResult(
                key=key,
                fiscal_year=2024,
                value=value,
                status="ok",
                provenance=Provenance.DERIVED,
                band=band,  # type: ignore[arg-type]
            )
        )
    return forensic_layer.ForensicResult(metrics=tuple(metrics))


def _b4_checked() -> dict[str, FlagEvaluation]:
    """B4 comprobada y limpia. Es el estado normal de una empresa con datos, y
    hay que declararlo: desde PHASE-44.17, una B4 que NO se ha podido comprobar
    impide el sello de «Conservador» en vez de contarse como «no está en rojo»."""
    return {
        "B4_dividend_funded_externally": FlagEvaluation(
            key="B4_dividend_funded_externally", outcome="clear", years_evaluated=(2024,)
        )
    }


def test_perfil_conservador_exige_las_cinco_condiciones_en_verde() -> None:
    forensic = _forensic_with(
        m_score="healthy",
        z_score="healthy",
        FZ="healthy",
        f_score="healthy",
        accruals="healthy",
    )
    profile = synthesis._safety_profile(forensic, {}, _b4_checked(), 2024)
    assert profile.label == "conservative"
    assert profile.blocking_reasons == ()


def test_perfil_vigilar_lista_lo_que_impide_ser_conservador() -> None:
    forensic = _forensic_with(
        m_score="healthy",
        z_score="healthy",
        FZ="healthy",
        f_score="caution",  # F-Score < 7
        accruals="healthy",
    )
    profile = synthesis._safety_profile(forensic, {}, _b4_checked(), 2024)
    assert profile.label == "watch"
    assert any("F-Score" in reason for reason in profile.blocking_reasons)


def test_z_score_rojo_fuerza_evitar() -> None:
    forensic = _forensic_with(
        m_score="healthy", z_score="stressed", FZ="healthy", f_score="healthy", accruals="healthy"
    )
    profile = synthesis._safety_profile(forensic, {}, _b4_checked(), 2024)
    assert profile.label == "avoid"
    assert any("insolvencia" in reason for reason in profile.blocking_reasons)


def test_manipulacion_probable_fuerza_evitar() -> None:
    """M-Score rojo Y accruals rojo a la vez → evitar (la conjunción, no cada
    uno por su cuenta)."""
    forensic = _forensic_with(
        m_score="stressed",
        z_score="healthy",
        FZ="healthy",
        f_score="healthy",
        accruals="stressed",
    )
    profile = synthesis._safety_profile(forensic, {}, _b4_checked(), 2024)
    assert profile.label == "avoid"


def test_m_score_rojo_solo_no_fuerza_evitar() -> None:
    """M rojo sin accruals rojo no basta para 'evitar' (es la conjunción)."""
    forensic = _forensic_with(
        m_score="stressed",
        z_score="healthy",
        FZ="healthy",
        f_score="healthy",
        accruals="healthy",
    )
    profile = synthesis._safety_profile(forensic, {}, _b4_checked(), 2024)
    assert profile.label != "avoid"


def test_b4_rojo_fuerza_evitar() -> None:
    forensic = _forensic_with(
        m_score="healthy", z_score="healthy", FZ="healthy", f_score="healthy", accruals="healthy"
    )
    profile = synthesis._safety_profile(
        forensic, {"B4_dividend_funded_externally": "red"}, _b4_checked(), 2024
    )
    assert profile.label == "avoid"


def _señal(nombre: str, band: str | None, *, reason: str | None = None) -> synthesis.QuestionSignal:
    """Señal de prueba. `band=None` = candidata que no puntúa."""
    return synthesis.QuestionSignal(
        key=nombre,
        label=nombre,
        kind="metric",
        band=band,  # type: ignore[arg-type]
        value=None,
        status=None,
        counted=band is not None,
        reason=None if band is not None else (reason or "no calculable"),
        outcome="scored" if band is not None else "unchecked",
    )


def test_una_pregunta_es_roja_si_una_señal_nucleo_es_roja() -> None:
    """El semáforo: rojo si ≥1 rojo (no media ponderada)."""
    verdict = synthesis._aggregate(
        "test",
        "k",
        [_señal("a", "healthy"), _señal("b", "healthy"), _señal("c", "stressed")],
    )
    assert verdict.verdict == "stressed"
    assert verdict.red_signals == ("c",)
    assert verdict.evaluated_count == 3 and verdict.unavailable_count == 0


def test_una_pregunta_es_ambar_solo_con_dos_o_mas_ambar() -> None:
    un_ambar = synthesis._aggregate("t", "k", [_señal("a", "healthy"), _señal("b", "caution")])
    assert un_ambar.verdict == "healthy", "un solo ámbar no tiñe la pregunta"
    dos_ambar = synthesis._aggregate("t", "k", [_señal("a", "caution"), _señal("b", "caution")])
    assert dos_ambar.verdict == "caution"


def test_las_señales_no_computables_no_cuentan() -> None:
    """Una métrica sin banda (not_computable) no aporta ni verde ni rojo."""
    verdict = synthesis._aggregate(
        "t", "k", [_señal("x", None), _señal("y", None), _señal("a", "healthy")]
    )
    assert verdict.verdict == "healthy"
    assert verdict.red_signals == () and verdict.amber_signals == ()


def test_una_señal_que_no_puntua_sigue_publicandose_con_su_motivo() -> None:
    """Lo que se comprobó y no pudo puntuar es información, no silencio: sin
    esto, «sano» y «no hay evidencia» son indistinguibles desde el cliente."""
    verdict = synthesis._aggregate(
        "t", "k", [_señal("x", None, reason="falta la partida 'cogs'"), _señal("a", "healthy")]
    )
    assert len(verdict.signals) == 2
    assert verdict.evaluated_count == 1
    assert verdict.unavailable_count == 1
    no_contada = next(s for s in verdict.signals if not s.counted)
    assert no_contada.reason == "falta la partida 'cogs'"


def test_una_señal_sin_banda_exige_explicar_por_que() -> None:
    """El invariante que impide un 'no cuenta' mudo en pantalla."""
    with pytest.raises(ValueError, match="DEBE explicar por qué"):
        synthesis.QuestionSignal(
            key="x",
            label="X",
            kind="metric",
            band=None,
            value=None,
            status=None,
            counted=False,
        )


def test_todas_las_preguntas_publican_sus_señales_candidatas() -> None:
    """Las cuatro preguntas traen su lista completa, no sólo lo que salió mal."""
    resultado = _synthesize(_healthy_series())
    esperado = {"accounting": 10, "cash": 8, "dividend": 9, "resilience": 8}
    for question in resultado.questions:
        assert len(question.signals) == esperado[question.key], question.key
        assert question.evaluated_count + question.unavailable_count == len(question.signals)


def test_ninguna_señal_viaja_como_clave_cruda() -> None:
    """La regresión de la pantalla del veredicto: se llegó a imprimir
    `M-Score · B4_dividend_funded_externally` porque la señal ERA la clave."""
    resultado = _synthesize(_healthy_series())
    for question in resultado.questions:
        for signal in question.signals:
            assert signal.label != signal.key, f"{signal.key} viaja sin etiqueta"
            assert "_" not in signal.label, f"{signal.key}: {signal.label!r} parece una clave"


def test_una_financiera_no_puede_pintar_verde_por_ausencia_de_prueba() -> None:
    """En una financiera los 8 forenses salen `not_computable`, así que la
    pregunta de contabilidad cae al `else` del semáforo y sale VERDE. El
    veredicto no cambia (es la regla del DESIGN), pero ahora el cliente PUEDE
    detectarlo: las señales forenses vienen con `counted=False` y su motivo."""
    serie = _healthy_series()
    financiera = StatementSeries(
        security=SecuritySnapshot(
            ticker="BANK",
            sector=SectorInternal.FINANCIALS,
            accounting_std=AccountingStd.GAAP,
            is_financial=True,
        ),
        statements=serie.statements,
        as_of=serie.as_of,
    )
    accounting = _synthesize(financiera).question("accounting")
    assert accounting is not None
    forenses = [s for s in accounting.signals if s.key in {"m_score", "F7", "accruals"}]
    assert len(forenses) == 3
    assert all(not s.counted for s in forenses), "ningún forense debería puntuar en una financiera"
    assert all(s.reason for s in forenses), "y cada uno explica por qué"


# ══ PHASE-44.17 — evaluabilidad de las banderas ══════════════════════
#
# Una `Flag` sólo existe cuando salta, así que «no hay bandera» era la misma
# respuesta para «comprobado y limpio» y para «la regla no llegó a ejecutarse».
# La síntesis traducía las dos a «no se ha encendido», que se lee como limpio.


def _sin_coste_de_ventas() -> StatementSeries:
    """La misma empresa sana, pero sin coste de ventas — como McDonald's, que
    presenta sus gastos por naturaleza y no publica `cogs` anual."""
    serie = _healthy_series()
    return StatementSeries(
        security=serie.security,
        statements=tuple(replace(s, cogs=None) for s in serie.statements),
        as_of=serie.as_of,
    )


def _flag_signals(resultado: synthesis.SynthesisResult) -> dict[str, synthesis.QuestionSignal]:
    return {
        signal.key: signal
        for question in resultado.questions
        for signal in question.signals
        if signal.kind == "flag"
    }


def test_toda_bandera_usada_como_señal_tiene_evaluacion_publicada() -> None:
    """El gate de cobertura, simétrico al default pesimista de `_flag_signal`.

    Sin él, el arreglo cambia un falso VERDE por un falso GRIS universal: si
    alguien añade una regla y olvida publicar su evaluación, todas las empresas
    verían «no se ha podido comprobar», incluidas aquellas donde sí se comprobó.
    Se ejecuta sobre dos series a propósito —una completa y una degenerada de un
    solo ejercicio— porque la evaluación tiene que publicarse SIEMPRE, también
    cuando la regla no tiene con qué correr.
    """
    for serie in (_healthy_series(), _sin_coste_de_ventas()):
        resultado = _synthesize(serie)
        publicadas = _flag_signals(resultado)
        assert set(synthesis.QUESTION_FLAG_KEYS) <= set(publicadas)
        for key in synthesis.QUESTION_FLAG_KEYS:
            reason = publicadas[key].reason or ""
            assert "el motor no publicó la evaluación" not in reason, (
                f"{key} llega a la síntesis sin evaluación: su capa no la publica. "
                "Publícala en la capa que la calcula, no la excluyas de aquí."
            )


def test_una_regla_que_no_se_pudo_ejecutar_no_dice_que_no_se_ha_encendido() -> None:
    """El defecto exacto: sin `cogs`, C3 (inventario vs coste de ventas) no se
    ejecuta ni un ejercicio, no emite bandera, y salía como «no se ha encendido»
    — que se lee como comprobado y limpio."""
    señales = _flag_signals(_synthesize(_sin_coste_de_ventas()))
    c3 = señales["C3_inventory_vs_cogs"]
    assert c3.outcome == "unchecked"
    assert c3.reason is not None
    assert "no se ha encendido" not in c3.reason
    assert "cogs" in c3.reason, "el motivo tiene que nombrar la partida que falta"


def test_una_regla_comprobada_y_limpia_se_distingue_de_una_que_no_se_pudo() -> None:
    """La otra mitad: con datos completos, C3 sí se comprueba y sale limpia."""
    señales = _flag_signals(_synthesize(_healthy_series()))
    assert señales["C3_inventory_vs_cogs"].outcome == "clear"
    assert señales["C3_inventory_vs_cogs"].reason == "se comprobó y no se encendió"


def test_los_contadores_separan_lo_limpio_de_lo_que_no_se_pudo() -> None:
    """`unavailable_count` metía en un cubo cuatro cosas: la pantalla decía «7 no
    disponibles» donde había 2 huecos reales y 5 banderas limpias."""
    accounting = _synthesize(_healthy_series()).question("accounting")
    assert accounting is not None
    assert accounting.clear_count > 0, "las banderas limpias son evidencia, no huecos"
    assert accounting.evaluated_count + accounting.clear_count + accounting.unchecked_count + sum(
        1 for s in accounting.signals if s.outcome == "informational"
    ) == len(accounting.signals)
    # Y el total antiguo se conserva: los runs guardados lo tienen.
    assert accounting.unavailable_count == len(accounting.signals) - accounting.evaluated_count


def test_el_sello_conservador_no_se_hereda_de_una_b4_que_no_se_pudo_comprobar() -> None:
    """B4 es una de las cuatro condiciones que fuerzan «Evitar». Se leía del mapa
    de banderas encendidas, así que una B4 no evaluable se traducía en «no está
    en rojo» y el sello subía sin haberla comprobado."""
    forensic = _forensic_with(
        m_score="healthy", z_score="healthy", FZ="healthy", f_score="healthy", accruals="healthy"
    )
    sin_evaluar = {
        "B4_dividend_funded_externally": FlagEvaluation(
            key="B4_dividend_funded_externally",
            outcome="not_computable",
            reason="falta la caja libre",
        )
    }
    profile = synthesis._safety_profile(forensic, {}, sin_evaluar, 2024)
    assert profile.label == "watch"
    assert any("no se ha podido comprobar" in reason for reason in profile.blocking_reasons)


def test_la_racha_evaluable_tiene_que_ser_de_anios_consecutivos() -> None:
    """`runs` busca ventanas consecutivas, así que con años evaluables sueltos la
    regla NO puede encenderse jamás: decir «comprobado y limpio» ahí afirmaría
    una comprobación imposible."""
    salteados = flag_rules.evaluate_windowed_rule(
        "C1_receivables_vs_revenue",
        fired=False,
        evaluable=[2016, 2018, 2020],
        unevaluable={},
        sustained=2,
    )
    assert salteados.outcome == "not_computable"
    seguidos = flag_rules.evaluate_windowed_rule(
        "C1_receivables_vs_revenue",
        fired=False,
        evaluable=[2019, 2020],
        unevaluable={},
        sustained=2,
    )
    assert seguidos.outcome == "clear"


def test_el_motivo_distingue_el_cero_imputado_del_dato_que_falta() -> None:
    """Tres modos de ausencia, no dos: falta el dato, valía cero, o el filing no
    lo publica y la ingesta lo supone cero. Redactar el motivo sin mirar la
    procedencia produce una frase falsa."""
    base = _healthy_year(2023, revenue=1200, dividends=72)
    siguiente = _healthy_year(2024, revenue=1300, dividends=78)

    falta = evolution_layer.growth_of("cogs", siguiente, replace(base, cogs=None))
    assert falta.reason is not None and "falta la partida 'cogs'" in falta.reason

    cero_real = evolution_layer.growth_of("inventory", siguiente, replace(base, inventory=dec(0)))
    assert cero_real.reason is not None and "valía cero" in cero_real.reason

    cero_imputado = evolution_layer.growth_of(
        "inventory",
        siguiente,
        replace(
            base,
            inventory=dec(0),
            item_provenance={**base.item_provenance, "inventory": Provenance.IMPUTED_ZERO},
        ),
    )
    assert cero_imputado.reason is not None
    assert "supone cero" in cero_imputado.reason
    assert "valía cero" not in cero_imputado.reason


# ── Perfil "Evitar" ───────────────────────────────────────────────────


def _distressed_year(fiscal_year: int) -> CanonicalStatement:
    """Empresa al borde: mucha deuda, poca caja, patrimonio fino."""
    return CanonicalStatement(
        fiscal_year=fiscal_year,
        fiscal_year_end=date(fiscal_year, 12, 31),
        accounting_std=AccountingStd.GAAP,
        cash=dec(20),
        current_financial_assets=dec(0),
        receivables=dec(200),
        inventory=dec(300),
        current_assets=dec(520),
        ppe_net=dec(400),
        goodwill=dec(300),
        total_assets=dec(1220),
        short_term_debt=dec(300),
        ltd_current_portion=dec(100),
        accounts_payable=dec(150),
        current_liabilities=dec(600),
        long_term_debt=dec(500),
        total_liabilities=dec(1150),
        retained_earnings=dec(-200),
        equity=dec(70),
        revenue=dec(1000),
        cogs=dec(850),
        sga_expense=dec(120),
        depreciation_amortization=dec(40),
        impairments=dec(0),
        gains_on_sale_of_business=dec(0),
        ebit=dec(30),
        interest_expense=dec(60),
        taxes=dec(0),
        taxes_paid=dec(0),
        net_income=dec(-30),
        shares_basic=dec(100),
        cfo=dec(10),
        capex=dec(50),
        dividends_paid=dec(40),
        debt_change=dec(80),
    )


def test_una_empresa_en_quiebra_tecnica_es_perfil_evitar() -> None:
    """Z'' en rojo (o el dividendo financiado con deuda) fuerza 'evitar'."""
    serie = StatementSeries(
        security=SecuritySnapshot(
            ticker="MALA", sector=SectorInternal.INDUSTRIALS, accounting_std=AccountingStd.GAAP
        ),
        statements=(_distressed_year(2023), _distressed_year(2024)),
        as_of=date(2025, 3, 31),
    )
    result = _synthesize(serie)
    assert result.safety_profile.label == "avoid"
    assert result.safety_profile.blocking_reasons


def test_el_dividendo_financiado_con_deuda_fuerza_evitar() -> None:
    """B4 rojo es una condición suficiente de 'evitar' (DESIGN §5)."""
    serie = StatementSeries(
        security=SecuritySnapshot(
            ticker="B4", sector=SectorInternal.INDUSTRIALS, accounting_std=AccountingStd.GAAP
        ),
        statements=(_distressed_year(2023), _distressed_year(2024)),
        as_of=date(2025, 3, 31),
    )
    result = _synthesize(serie)
    assert result.safety_profile.label == "avoid"


# ── Financieras y empresas sin dividendo ──────────────────────────────


def test_las_financieras_tienen_dividendo_no_aplicable() -> None:
    serie = _healthy_series()
    financiera = StatementSeries(
        security=SecuritySnapshot(
            ticker="BANK",
            sector=SectorInternal.FINANCIALS,
            accounting_std=AccountingStd.GAAP,
            is_financial=True,
        ),
        statements=serie.statements,
        as_of=serie.as_of,
    )
    assert _synthesize(financiera).dividend_verdict == "not_applicable"


def test_una_empresa_que_no_reparte_tiene_dividendo_no_aplicable() -> None:
    base = _healthy_series()
    sin_dividendo = StatementSeries(
        security=base.security,
        statements=tuple(
            CanonicalStatement(
                **{
                    f.name: getattr(s, f.name)
                    for f in s.__dataclass_fields__.values()
                    if f.name != "dividends_paid"
                },
                dividends_paid=dec(0),
            )
            for s in base.statements
        ),
        as_of=base.as_of,
    )
    assert _synthesize(sin_dividendo).dividend_verdict == "not_applicable"


# ── Confianza ─────────────────────────────────────────────────────────


def test_confianza_completa_y_fresca() -> None:
    """10 partidas núcleo completas en 4 años, cierre a 90 días → 1,0 × 1,0."""
    result = _synthesize(_healthy_series())
    approx_dec(result.confidence.completeness_core, "1")
    approx_dec(result.confidence.staleness_factor, "1")
    approx_dec(result.confidence.value, "1")
    assert result.confidence.days_stale == 90


def test_la_frescura_penaliza_los_datos_viejos() -> None:
    """Último cierre a más de 18 meses → factor 0,4."""
    base = _healthy_series()
    viejo = StatementSeries(
        security=base.security,
        statements=base.statements,
        as_of=date(2026, 8, 1),  # ~19 meses tras el cierre 2024-12-31
    )
    result = _synthesize(viejo)
    approx_dec(result.confidence.staleness_factor, "0.4")


def test_un_hueco_nucleo_baja_la_completitud() -> None:
    """Si falta 'cfo' en un año, la completitud baja de 1,0."""
    base = _healthy_series()
    con_hueco = list(base.statements)
    primero = con_hueco[0]
    con_hueco[0] = CanonicalStatement(
        **{
            f.name: getattr(primero, f.name)
            for f in primero.__dataclass_fields__.values()
            if f.name != "cfo"
        },
        cfo=None,
    )
    serie = StatementSeries(security=base.security, statements=tuple(con_hueco), as_of=base.as_of)
    result = _synthesize(serie)
    # 40 celdas núcleo, 1 hueco → 39/40 = 0,975
    approx_dec(result.confidence.completeness_core, "0.975")


def test_una_partida_imputada_a_cero_no_cuenta_como_sourced() -> None:
    """§5: los imputed_zero se listan aparte, no suben la completitud."""
    base = _healthy_series()
    primero = base.statements[0]
    imputado = CanonicalStatement(
        **{f.name: getattr(primero, f.name) for f in primero.__dataclass_fields__.values()},
    )
    imputado = CanonicalStatement(
        fiscal_year=primero.fiscal_year,
        fiscal_year_end=primero.fiscal_year_end,
        accounting_std=primero.accounting_std,
        **{item: getattr(primero, item) for item in synthesis.CORE_ITEMS if item != "capex"},
        capex=dec(0),
        item_provenance={"capex": Provenance.IMPUTED_ZERO},
    )
    serie = StatementSeries(
        security=base.security,
        statements=(imputado, *base.statements[1:]),
        as_of=base.as_of,
    )
    result = _synthesize(serie)
    assert result.confidence.imputed_core_count == 1
    # 40 celdas, 1 imputada (no sourced) → 39/40
    approx_dec(result.confidence.completeness_core, "0.975")


# ── Matriz de banderas ────────────────────────────────────────────────


def test_la_sintesis_recopila_las_flags_de_todas_las_capas() -> None:
    """Las banderas de coherencia/forense/dividendo se juntan para el panel."""
    serie = StatementSeries(
        security=SecuritySnapshot(
            ticker="FLAG", sector=SectorInternal.INDUSTRIALS, accounting_std=AccountingStd.GAAP
        ),
        statements=(_distressed_year(2023), _distressed_year(2024)),
        as_of=date(2025, 3, 31),
    )
    result = _synthesize(serie)
    keys = {f.key for f in result.flags}
    # La empresa dudosa dispara al menos el dividendo financiado con deuda (B4).
    assert "B4_dividend_funded_externally" in keys
