"""La capa de lectura del informe (PHASE-44.24.C).

Distancia al corte, orden por severidad y procedencia de la vara. Todo PURO:
estos tests no levantan base de datos ni tocan el reloj.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.modules.investment.analysis.engine.catalog import ALL_DEFAULT_THRESHOLDS
from app.modules.investment.analysis.engine.sector_profiles import resolve_thresholds
from app.modules.investment.analysis.engine.synthesis import QuestionSignal
from app.modules.investment.analysis.engine.types import MetricResult, ThresholdSpec
from app.modules.investment.analysis.presentation.distance import distance_to_cut
from app.modules.investment.analysis.presentation.evidence import evidence_of
from app.modules.investment.analysis.presentation.ordering import sort_signals
from app.modules.investment.analysis.presentation.origin import threshold_origin
from app.modules.investment.analysis.presentation.rehydrate import (
    recorded_origin,
    rehydrate_thresholds,
)
from app.modules.investment.enums import AccountingStd, SectorInternal, ThresholdDirection
from app.modules.investment.fundamentals.canonical import Provenance


def _metric(key: str, value: Decimal | None, band: str | None, status: str = "ok") -> MetricResult:
    return MetricResult(
        key=key,
        fiscal_year=2024,
        value=value,
        status=status,  # type: ignore[arg-type]
        provenance=Provenance.SOURCED,
        band=band,  # type: ignore[arg-type]
        reason=None if value is not None else "no se pudo",
    )


# ── Rehidratación ─────────────────────────────────────────────────────


def test_un_corte_persistido_con_la_escala_de_la_columna_vuelve_como_numero() -> None:
    """La trampa que hace que este módulo exista.

    `thresholds_used` guarda texto, y cuando la spec vino de la tabla trae la
    escala de `Numeric(12, 6)`. Comparar cadenas marcaría como «calibrado
    distinto» TODO run producido con la tabla sembrada — lo contrario de lo que
    se quiere decir.
    """
    specs = rehydrate_thresholds(
        {
            "S1": {
                "metric_key": "S1",
                "direction": "lower_better",
                "low_alarm": None,
                "low_ok": None,
                "high_ok": "0.600000",
                "high_alarm": "0.750000",
                "model_variant": None,
                "applies": True,
            }
        }
    )
    assert specs["S1"].high_ok == Decimal("0.6"), "iguales como número"
    assert str(specs["S1"].high_ok) != "0.6", "y distintos como cadena: por eso no se compara texto"


def test_un_run_sin_thresholds_used_no_inventa_specs() -> None:
    """Los runs anteriores a PHASE-44.9 traen `{}`, y eso ES la información."""
    assert rehydrate_thresholds({}) == {}
    assert rehydrate_thresholds(None) == {}


def test_una_spec_ilegible_se_descarta_entera_en_vez_de_quedarse_a_medias() -> None:
    """Sin dirección no se puede bandear nada, y fingir que sí es peor que el hueco."""
    specs = rehydrate_thresholds({"X": {"direction": "inventada", "high_ok": "1"}})
    assert specs == {}


def test_origin_ausente_no_es_generic() -> None:
    """Un run anterior al motor 1.7.0 no registró la procedencia.

    Colapsarlo con `generic` afirmaría que se midió con la vara del catálogo, que
    es justo lo que no se sabe.
    """
    persisted = {"S1": {"direction": "lower_better", "high_ok": "0.6", "applies": True}}
    assert recorded_origin(persisted, "S1") is None
    con_origen = {"S1": {**persisted["S1"], "origin": "sector"}}
    assert recorded_origin(con_origen, "S1") == "sector"


# ── Distancia ─────────────────────────────────────────────────────────


def _regions(spec: ThresholdSpec) -> list[Decimal]:
    """Un valor en cada región de una spec, deducido de sus propios cortes."""
    cuts = [
        c for c in (spec.low_alarm, spec.low_ok, spec.high_ok, spec.high_alarm) if c is not None
    ]
    if not cuts:
        return []
    step = max(abs(min(cuts)), abs(max(cuts)), Decimal(1)) / 4
    return [min(cuts) - step, *cuts, max(cuts) + step]


@pytest.mark.parametrize(
    "sector", [SectorInternal.UNKNOWN, SectorInternal.UTILITIES, SectorInternal.FINANCIALS]
)
def test_la_distancia_se_calcula_para_todas_las_specs_del_catalogo(
    sector: SectorInternal,
) -> None:
    """El barrido que un grid escrito a mano no da.

    Una rejilla «3 direcciones × 2 lados × 8 unidades» suena exhaustiva y no
    contiene S7 —banda de un solo lado— ni Q5 —cortes iguales—, que son las dos
    formas que rompen la aritmética ingenua. Aquí se recorren las specs REALES,
    de tres perfiles distintos, con un valor en cada una de sus regiones.
    """
    specs = resolve_thresholds(sector, AccountingStd.GAAP)
    assert specs, "el perfil no resolvió ninguna spec: el barrido no comprueba nada"
    for key, spec in specs.items():
        for value in _regions(spec):
            band = spec.band_for(value)
            metric = _metric(key, value, band)
            distance = distance_to_cut(metric, spec)
            if distance is None:
                assert not spec.applies, f"{key}: sin distancia con la vara aplicable"
                continue
            if distance.cut is None:
                assert distance.missing_reason, f"{key}: sin corte y sin motivo"
            else:
                assert distance.absolute is not None and distance.absolute >= 0


def test_sin_valor_o_sin_vara_no_hay_distancia() -> None:
    spec = ALL_DEFAULT_THRESHOLDS["S1"]
    assert distance_to_cut(None, spec) is None
    assert distance_to_cut(_metric("S1", None, None, "not_computable"), spec) is None
    assert distance_to_cut(_metric("S1", Decimal("1"), None), None) is None
    apagada = ThresholdSpec(
        metric_key="S1",
        direction=ThresholdDirection.LOWER_BETTER,
        high_ok=Decimal("0.6"),
        applies=False,
        not_applicable_reason="en banca el apalancamiento ES el negocio",
    )
    assert distance_to_cut(_metric("S1", Decimal("9"), None), apagada) is None


def test_una_banda_de_un_solo_lado_lo_declara_en_vez_de_inventar_un_corte() -> None:
    """S7: banda central con `low_ok`, `high_ok` y `high_alarm`, SIN `low_alarm`.

    Por debajo de la banda sale ámbar y no puede salir rojo nunca — poca deuda no
    es un riesgo. Ahí no hay corte siguiente, y fabricar uno sería peor que el
    hueco.
    """
    s7 = ALL_DEFAULT_THRESHOLDS["S7"]
    assert s7.low_alarm is None, "S7 ha cambiado de forma: este test ya no prueba lo que dice"
    fuera_por_abajo = Decimal("0.5")
    assert s7.band_for(fuera_por_abajo) == "caution"
    distance = distance_to_cut(_metric("S7", fuera_por_abajo, "caution"), s7)
    assert distance is not None
    assert distance.cut is None and distance.relative is None
    assert distance.missing_reason


def test_con_cortes_iguales_la_banda_que_se_cruza_es_la_roja() -> None:
    """Q5 y T3 tienen `high_ok == high_alarm`: la región ámbar es VACÍA.

    Una etiqueta que dijera «a X del ámbar» nombraría una banda que para esta
    métrica no existe.
    """
    q5 = ALL_DEFAULT_THRESHOLDS["Q5"]
    assert q5.high_ok == q5.high_alarm, "Q5 ha cambiado: este test ya no prueba el caso degenerado"
    dentro = q5.high_ok - Decimal("0.01") if q5.high_ok else Decimal(0)
    distance = distance_to_cut(_metric("Q5", dentro, q5.band_for(dentro)), q5)
    assert distance is not None
    assert distance.next_band == "stressed"


def test_un_corte_negativo_no_produce_una_distancia_relativa_negativa() -> None:
    """El M-Score corta en negativo.

    Con `abs / corte` en vez de `abs / |corte|`, un M-Score muy dentro del rojo
    daría una relativa NEGATIVA y el orden por severidad lo colocaría como el
    menos grave de los rojos — al revés de lo que es.
    """
    m = ALL_DEFAULT_THRESHOLDS["m_score"]
    assert m.high_ok is not None and m.high_ok < 0, "el corte del M-Score ya no es negativo"
    muy_dentro_del_rojo = Decimal("1.5")
    distance = distance_to_cut(_metric("m_score", muy_dentro_del_rojo, "stressed"), m, unit="times")
    assert distance is not None and distance.relative is not None
    assert distance.relative > 0


def test_en_una_puntuacion_no_se_publica_distancia_relativa() -> None:
    """Los cortes del X-Score están en −1,04 y −0,25.

    La misma distancia absoluta da relativas de 0,2 y 0,8 según con cuál se
    divida, sin que ninguna informe de nada. La pantalla enseña la absoluta.
    """
    fz = ALL_DEFAULT_THRESHOLDS["FZ"]
    distance = distance_to_cut(_metric("FZ", Decimal("0.5"), "stressed"), fz, unit="score")
    assert distance is not None
    assert distance.absolute is not None
    assert distance.relative is None


def test_con_el_corte_en_cero_no_se_divide() -> None:
    cero = ThresholdSpec(
        metric_key="T2",
        direction=ThresholdDirection.HIGHER_BETTER,
        low_alarm=Decimal(0),
        low_ok=Decimal(0),
    )
    distance = distance_to_cut(_metric("T2", Decimal("-0.2"), "stressed"), cero)
    assert distance is not None
    assert distance.absolute == Decimal("0.2")
    assert distance.relative is None


# ── Orden ─────────────────────────────────────────────────────────────


def _signal(key: str, band: str | None, *, counted: bool = True) -> QuestionSignal:
    return QuestionSignal(
        key=key,
        label=key,
        kind="metric" if counted else "flag",
        band=band,  # type: ignore[arg-type]
        value=None,
        status=None,
        counted=counted,
        reason=None if counted else "se comprobó y no se encendió",
        outcome="scored" if counted else "clear",
    )


def _distance(relative: str, side: str = "outside") -> object:
    from app.modules.investment.analysis.presentation.distance import SignalDistance

    return SignalDistance(
        cut=Decimal(1),
        absolute=Decimal(relative),
        relative=Decimal(relative),
        side=side,  # type: ignore[arg-type]
        next_band="stressed",
    )


def test_una_senal_roja_sin_gradiente_va_antes_que_una_con_gradiente() -> None:
    """El par que el orden dejaba indefinido.

    Una bandera encendida no tiene distancia que medir. Tratarla como distancia
    cero la colocaría «exactamente en el corte», es decir la MENOS grave de las
    rojas — cuando una bandera que salta es evidencia binaria y ya ha demostrado
    lo suyo.
    """
    bandera = _signal("B4_dividend_funded_externally", "stressed")
    metrica = _signal("D2", "stressed")
    ordenadas = sort_signals([(metrica, _distance("2.1")), (bandera, None)])  # type: ignore[arg-type]
    assert next(s.key for s, _ in ordenadas) == "B4_dividend_funded_externally"


def test_lo_rojo_va_antes_que_lo_ambar_y_lo_sin_banda_al_final() -> None:
    señales = [
        (_signal("verde", "healthy"), None),
        (_signal("sin_banda", None, counted=False), None),
        (_signal("rojo", "stressed"), None),
        (_signal("ambar", "caution"), None),
    ]
    ordenadas = [s.key for s, _ in sort_signals(señales)]  # type: ignore[arg-type]
    assert ordenadas == ["rojo", "ambar", "verde", "sin_banda"]


def test_un_empate_exacto_se_resuelve_por_clave_y_es_reproducible() -> None:
    """El ÚNICO caso en que el desempate alfabético decide algo.

    Sin este test, romper el desempate no tumbaría nada: todos los demás pares
    los decide la banda o la distancia, y el criterio final quedaría sin
    ejercitar.
    """
    a = (_signal("Z_metrica", "stressed"), _distance("2.0"))
    b = (_signal("A_metrica", "stressed"), _distance("2.0"))
    assert [s.key for s, _ in sort_signals([a, b])] == ["A_metrica", "Z_metrica"]  # type: ignore[arg-type]
    assert [s.key for s, _ in sort_signals([b, a])] == ["A_metrica", "Z_metrica"]  # type: ignore[arg-type]


def test_mas_dentro_del_rojo_es_peor() -> None:
    poco = (_signal("D2", "stressed"), _distance("0.1"))
    mucho = (_signal("D3", "stressed"), _distance("3.0"))
    assert [s.key for s, _ in sort_signals([poco, mucho])] == ["D3", "D2"]  # type: ignore[arg-type]


# ── Procedencia ───────────────────────────────────────────────────────


def _persisted(spec: ThresholdSpec, *, origin: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "metric_key": spec.metric_key,
        "direction": spec.direction.value,
        "low_alarm": None if spec.low_alarm is None else str(spec.low_alarm),
        "low_ok": None if spec.low_ok is None else str(spec.low_ok),
        "high_ok": None if spec.high_ok is None else str(spec.high_ok),
        "high_alarm": None if spec.high_alarm is None else str(spec.high_alarm),
        "model_variant": spec.model_variant,
        "applies": spec.applies,
        "not_applicable_reason": spec.not_applicable_reason,
    }
    if origin is not None:
        payload["origin"] = origin
    return payload


def _origin(key: str, persisted: dict[str, object], sector: SectorInternal) -> str:
    raw = {key: persisted}
    return threshold_origin(
        key,
        persisted=raw,
        used=rehydrate_thresholds(raw),
        generic=ALL_DEFAULT_THRESHOLDS,
        profile=resolve_thresholds(sector, AccountingStd.GAAP),
    )


def test_un_run_del_motor_nuevo_lee_la_procedencia_en_vez_de_inferirla() -> None:
    """Y no se deja influir por lo que hoy diga la calibración.

    Se persiste un corte que NO coincide con nada de hoy y se declara `sector`:
    si la función estuviera derivando, saldría `earlier_calibration`.
    """
    spec = ALL_DEFAULT_THRESHOLDS["S1"]
    inventado = _persisted(spec, origin="sector")
    inventado["high_ok"] = "42.000000"
    assert _origin("S1", inventado, SectorInternal.UNKNOWN) == "sector"


def test_un_run_antiguo_deriva_y_reconoce_la_vara_generica() -> None:
    spec = ALL_DEFAULT_THRESHOLDS["S1"]
    assert _origin("S1", _persisted(spec), SectorInternal.UNKNOWN) == "generic"


def test_un_run_antiguo_con_cortes_de_otra_calibracion_lo_dice() -> None:
    """El valor que el borrador del plan no tenía.

    Con sólo `generic`/`sector`, cualquier recalibración genérica posterior al
    run se leería como «banda sectorial» — «perfil actual: unknown» para una
    empresa sin perfil, que es el falso «esto parece un bug» que la fase quita.
    """
    spec = ALL_DEFAULT_THRESHOLDS["S1"]
    viejo = _persisted(spec)
    viejo["high_ok"] = "0.123456"
    assert _origin("S1", viejo, SectorInternal.UNKNOWN) == "earlier_calibration"


def test_una_metrica_que_el_run_no_registro_no_se_confunde_con_la_generica() -> None:
    """Un run de 1.3.0 tiene `thresholds_used` y no tiene S7 ni S8."""
    assert (
        threshold_origin(
            "S7",
            persisted={},
            used={},
            generic=ALL_DEFAULT_THRESHOLDS,
            profile=ALL_DEFAULT_THRESHOLDS,
        )
        == "not_recorded"
    )


def test_una_vara_apagada_se_declara_antes_de_mirar_ningun_default() -> None:
    banco = resolve_thresholds(SectorInternal.FINANCIALS, AccountingStd.GAAP, is_financial=True)
    apagadas = [key for key, spec in banco.items() if not spec.applies]
    assert apagadas, "el perfil financiero ya no apaga ninguna métrica"
    key = apagadas[0]
    assert _origin(key, _persisted(banco[key]), SectorInternal.FINANCIALS) == "not_applicable"


def test_unos_cortes_us_gaap_sobre_cuentas_que_no_lo_son_se_declaran() -> None:
    ifrs = resolve_thresholds(SectorInternal.UNKNOWN, AccountingStd.IFRS)
    sin_calibrar = [key for key, spec in ifrs.items() if spec.model_variant == "uncalibrated"]
    assert sin_calibrar, "ya no se marca nada como sin calibrar"
    key = sin_calibrar[0]
    assert _origin(key, _persisted(ifrs[key]), SectorInternal.UNKNOWN) == "uncalibrated"


# ── El fixture COMPARTIDO con el frontend (PHASE-44.24.B) ─────────────


def _evidence_cases() -> list[dict[str, object]]:
    """Los casos que también lee `vitest`.

    Vive en `packages/ui/src/__fixtures__/` y no en `backend/tests/` porque es
    el único sitio que las DOS suites encuentran sin salirse de su patrón: el
    `include` de vitest es `src/**`, y aquí se resuelve por ruta relativa igual
    que ya hace el gate de cobertura de pantalla.
    """
    import json

    path = (
        Path(__file__).resolve().parents[2]
        / "packages"
        / "ui"
        / "src"
        / "__fixtures__"
        / "question-evidence.json"
    )
    assert path.exists(), f"el fixture compartido no está en {path}"
    return list(json.loads(path.read_text(encoding="utf-8"))["cases"])


def test_el_fixture_de_evidencia_no_ha_encogido() -> None:
    """Un fixture que se queda con dos casos pasa las dos suites y no ata nada."""
    casos = _evidence_cases()
    assert len(casos) >= 12
    assert {str(c["expected"]) for c in casos} == {
        "evaluated",
        "no-evidence",
        "not-recorded",
        "not-audited",
    }


def test_ningun_caso_del_fixture_usa_null_donde_la_clave_debe_faltar() -> None:
    """La trampa que haría que el fixture no atara nada.

    Con `null`, Python —que pregunta con `in`— y TypeScript —que compara con
    `undefined`— toman ramas DISTINTAS, así que el caso pasaría en un lado y
    fallaría en el otro, o peor: pasaría en los dos por caminos que no son el
    mismo. Los runs persistidos nunca llevan `null` ahí.
    """
    for caso in _evidence_cases():
        question = caso["question"]
        assert isinstance(question, dict)
        for key in ("signals", "evaluated_count", "clear_count", "unchecked_count", "audited"):
            assert question.get(key, "AUSENTE") is not None, f"{caso['name']}: {key} es null"


@pytest.mark.parametrize("caso", _evidence_cases(), ids=lambda c: str(c["name"]))
def test_el_estado_de_evidencia_coincide_con_el_del_frontend(caso: dict[str, object]) -> None:
    question = caso["question"]
    assert isinstance(question, dict)
    resultado = evidence_of(question)
    assert resultado.state == caso["expected"], caso["name"]
    assert resultado.outcomes_recorded == caso["outcomes_recorded"], caso["name"]


# ── El porqué del veredicto (PHASE-44.25) ─────────────────────────────
#
# El caso es el que reportó el usuario: McDonald's sale «Evitar» por el X-Score
# y el lector no puede reconstruir el argumento — el titular nombra una señal
# que la tabla no marca, junto a un Z''-Score en verde que nadie concilia, y la
# fila más severa de la pregunta (el escenario de stress) sale sin número.


def _condicion(
    key: str,
    rule: str,
    text: str,
    met: bool | None,
    *,
    inverse: str = "",
    signals: list[dict] | None = None,
    reason: str | None = None,
) -> dict:
    return {
        "key": key,
        "rule": rule,
        "text": text,
        "met": met,
        "reason": reason,
        "inverse": inverse,
        "signals": signals or [],
    }


def _señal_cond(key: str, label: str, band: str | None, value: str | None) -> dict:
    return {
        "key": key,
        "label": label,
        "kind": "metric",
        "band": band,
        "value": value,
        "status": "ok",
    }


def _verdict_mcd() -> dict:
    """El veredicto de un run como el de MCD: «Evitar» por el X-Score."""
    return {
        "safety_profile": {
            "label": "avoid",
            "blocking_reasons": ["X-Score en rojo (riesgo de quiebra)"],
            "conditions": [
                _condicion(
                    "avoid_manipulation",
                    "avoid",
                    "M-Score y accruals ambos en rojo (manipulación probable)",
                    False,
                    inverse="el M-Score o los accruals salieran del rojo",
                    signals=[
                        _señal_cond("m_score", "M-Score de Beneish", "healthy", "-2.6"),
                        _señal_cond("accruals", "Accruals de Sloan", "healthy", "0.035"),
                    ],
                ),
                _condicion(
                    "avoid_insolvency",
                    "avoid",
                    "Z''-Score en rojo (riesgo de insolvencia)",
                    False,
                    inverse="el Z''-Score saliera del rojo",
                    signals=[_señal_cond("z_score", "Z''-Score de Altman", "healthy", "5.20")],
                ),
                _condicion(
                    "avoid_bankruptcy",
                    "avoid",
                    "X-Score en rojo (riesgo de quiebra)",
                    True,
                    inverse="el X-Score saliera del rojo",
                    signals=[_señal_cond("FZ", "X-Score de Zmijewski", "stressed", "0.87")],
                ),
                _condicion(
                    "avoid_dividend_funding",
                    "avoid",
                    "dividendo financiado con deuda o emisión",
                    False,
                    inverse="el dividendo dejara de financiarse con deuda o emisión",
                    signals=[],
                ),
                _condicion(
                    "cons_fz",
                    "conservative",
                    "X-Score no está en verde",
                    True,
                    inverse="el X-Score se pusiera en verde",
                    signals=[_señal_cond("FZ", "X-Score de Zmijewski", "stressed", "0.87")],
                ),
            ],
        },
        "dividend_verdict": "stressed",
        "stress": {
            "scenarios": [
                {
                    "key": "ST1",
                    "coverage_before": "1.08",
                    "coverage_after": "0.92",
                    "sentence": "Con las ventas cayendo un 10 %, la cobertura pasa de 1,08 a 0,92.",
                },
                {
                    "key": "ST2",
                    "coverage_before": "1.08",
                    "coverage_after": "1.05",
                    "sentence": "Con los tipos subiendo, la cobertura pasa de 1,08 a 1,05.",
                },
            ]
        },
        "questions": [
            {
                "key": "resilience",
                "verdict": "stressed",
                "evaluated_count": 8,
                "clear_count": 0,
                "unchecked_count": 0,
                "audited": True,
                "load_bearing": ["z_score"],
                "signals": [
                    {
                        "key": "FZ",
                        "label": "X-Score de Zmijewski",
                        "kind": "metric",
                        "counted": True,
                        "band": "stressed",
                        "value": "0.87",
                        "status": "ok",
                    },
                    {
                        "key": "stress",
                        "label": "Escenario de stress (deja de cubrir)",
                        "kind": "derived",
                        "counted": True,
                        "band": "stressed",
                        "value": None,
                    },
                    {
                        "key": "z_score",
                        "label": "Z''-Score de Altman",
                        "kind": "metric",
                        "counted": True,
                        "band": "healthy",
                        "value": "5.20",
                        "status": "ok",
                    },
                ],
            }
        ],
    }


def _report(verdict: dict):
    from app.modules.investment.analysis.presentation.origin import ThresholdProfile
    from app.modules.investment.analysis.presentation.report import build_report

    return build_report(
        verdict=verdict,
        thresholds_used={},
        profile=ThresholdProfile(
            effective="generic", sector="consumer_discretionary", is_financial=False, is_reit=False
        ),
        profile_thresholds=ALL_DEFAULT_THRESHOLDS,
    )


def test_la_senal_que_disparo_el_sello_va_marcada() -> None:
    """El titular nombraba el X-Score y ninguna fila lo marcaba: el lector tenía
    que reconocer que «X-Score en rojo» y la fila `FZ 0,87` son lo mismo."""
    layer = _report(_verdict_mcd())
    por_clave = {s.key: s for s in layer.questions[0].signals}

    assert por_clave["FZ"].drove_verdict is True
    # Roja pero NO decisiva: el stress tiñe la pregunta y no está en la matriz.
    assert por_clave["stress"].drove_verdict is False
    assert por_clave["z_score"].drove_verdict is False


def test_la_fila_del_stress_deja_de_estar_hueca() -> None:
    """Sus cifras estaban persistidas con la frase ya redactada, tres cards más
    abajo, y nadie las cruzaba con la fila que las resume."""
    layer = _report(_verdict_mcd())
    stress = next(s for s in layer.questions[0].signals if s.key == "stress")

    assert len(stress.evidence_sentences) == 1, "sólo los escenarios que dejan de cubrir"
    assert "1,08" in stress.evidence_sentences[0]
    # El escenario que SÍ cubre (1,05) no se cita: no explica el rojo.
    assert all("1,05" not in frase for frase in stress.evidence_sentences)


def test_el_porque_dice_que_condicion_decidio_y_que_lo_sacaria() -> None:
    layer = _report(_verdict_mcd())
    assert layer.why is not None
    assert layer.why.decided_by == ("avoid_bankruptcy",)
    assert layer.why.exit_sentence.startswith(
        "Dejaría de ser «Evitar» si el X-Score saliera del rojo"
    )
    assert "Vigilar" in layer.why.exit_sentence


def test_la_discrepancia_entre_los_dos_modelos_se_dice() -> None:
    """X-Score en rojo justo encima de un Z''-Score en verde, sin una línea que
    lo explique, es la contradicción que rompe la lectura."""
    layer = _report(_verdict_mcd())
    assert layer.why is not None
    assert layer.why.models_disagree is not None
    assert "X-Score de Zmijewski" in layer.why.models_disagree
    assert "Z''-Score de Altman" in layer.why.models_disagree


def test_sin_discrepancia_no_se_inventa_la_frase() -> None:
    verdict = _verdict_mcd()
    for condicion in verdict["safety_profile"]["conditions"]:
        if condicion["key"] == "avoid_insolvency":
            condicion["signals"][0]["band"] = "stressed"
    layer = _report(verdict)

    assert layer.why is not None
    assert layer.why.models_disagree is None


def test_un_run_sin_la_matriz_evaluada_no_recibe_porque_inventado() -> None:
    """Precondición, no etiqueta: componerlo con la regla de HOY afirmaría sobre
    aquel análisis algo que su motor no comprobó."""
    verdict = _verdict_mcd()
    verdict["safety_profile"].pop("conditions")
    layer = _report(verdict)

    assert layer.why is None
    assert all(not s.drove_verdict for q in layer.questions for s in q.signals)
    # Pero las frases del escenario SÍ llegan: son un hecho persistido del run.
    stress = next(s for s in layer.questions[0].signals if s.key == "stress")
    assert stress.evidence_sentences


def test_el_contrafactual_calla_lo_que_no_se_pudo_comprobar() -> None:
    """Prometer que algo bastaría sin haberlo mirado es la promesa vacía que
    PHASE-44.17 quitó de las banderas."""
    from app.modules.investment.analysis.presentation.narrative import exit_sentence

    conditions = [
        _condicion(
            "avoid_bankruptcy",
            "avoid",
            "X-Score en rojo",
            True,
            inverse="el X-Score saliera del rojo",
        ),
        _condicion(
            "avoid_manipulation",
            "avoid",
            "M-Score y accruals ambos en rojo",
            None,
            inverse="el M-Score o los accruals salieran del rojo",
            reason="no se calculó en este ejercicio",
        ),
    ]
    frase = exit_sentence(safety_label="avoid", conditions=conditions)

    assert "el X-Score saliera del rojo" in frase
    assert "el M-Score o los accruals salieran del rojo" not in frase
    assert "quedaría por comprobar" in frase
    assert "M-Score y accruals ambos en rojo" in frase


def test_el_bullet_de_que_miraria_enlaza_con_su_senal() -> None:
    """`key` era `pregunta:ETIQUETA` y una etiqueta no localiza nada: ya
    divergieron una vez («M-Score» vs «M-Score de Beneish»)."""
    layer = _report(_verdict_mcd())
    con_clave = [c for c in layer.next_checks if c.signal_key]

    assert con_clave, "ningún bullet trae la clave de su señal"
    assert {c.signal_key for c in con_clave} <= {"FZ", "stress", "z_score"}


# ── El sumario del Dictamen (PHASE-44.26) ─────────────────────────────
#
# La selección vive AQUÍ junto a las frases que la nombran: qué entra y en qué
# orden es parte de lo que la frase afirma. El selector del cliente queda como
# fallback para backends anteriores.


def test_el_sumario_nombra_lo_que_pesa_y_lo_que_sale_limpio() -> None:
    layer = _report(_verdict_mcd())

    assert layer.summary is not None
    # Rojas primero, con la frase que las nombra — sin números: los números van
    # en las filas, formateados por unidad en la capa compartida.
    assert layer.summary.concern_keys[0] in ("FZ", "stress")
    assert "X-Score de Zmijewski" in layer.summary.concerns_intro
    assert not any(c.isdigit() for c in layer.summary.concerns_intro)
    # El verde de la misma pregunta sale en la otra lista.
    assert "z_score" in layer.summary.strength_keys
    assert "Z''-Score de Altman" in layer.summary.strengths_intro.replace("\\", "")


def test_el_sumario_recorta_ambar_pero_jamas_una_roja() -> None:
    verdict = _verdict_mcd()
    señales = verdict["questions"][0]["signals"]
    # Ocho rojas más las de MCD: todas las rojas salen.
    for i in range(8):
        señales.append(
            {
                "key": f"r{i}",
                "label": f"Roja {i}",
                "kind": "metric",
                "counted": True,
                "band": "stressed",
                "value": "1",
                "status": "ok",
            }
        )
    layer = _report(verdict)

    assert layer.summary is not None
    rojas = [k for k in layer.summary.concern_keys]
    assert len(rojas) >= 10  # las 8 sintéticas + FZ + stress


def test_una_financiera_no_aporta_ni_rojo_ni_verde_al_sumario() -> None:
    verdict = _verdict_mcd()
    # La pregunta pasa a permanentemente no auditable: sin portantes.
    verdict["questions"][0]["audited"] = False
    verdict["questions"][0]["load_bearing"] = []
    layer = _report(verdict)

    assert layer.summary is not None
    assert layer.summary.concern_keys == ()
    assert layer.summary.strength_keys == ()
    assert layer.summary.concerns_intro == ""


def test_un_verde_sin_evidencia_no_es_fortaleza_en_el_servidor() -> None:
    verdict = _verdict_mcd()
    # La pregunta queda no auditada TEMPORALMENTE (con portantes): sus rojas
    # siguen listándose con su matiz; sus verdes no son fortaleza.
    verdict["questions"][0]["audited"] = False
    layer = _report(verdict)

    assert layer.summary is not None
    assert "FZ" in layer.summary.concern_keys
    assert layer.summary.strength_keys == ()


def test_el_sumario_trae_el_stress_con_su_margen() -> None:
    verdict = _verdict_mcd()
    verdict["stress"]["breakeven_fcf_drop"] = "0.07"
    layer = _report(verdict)

    assert layer.summary is not None
    assert len(layer.summary.stress_sentences) == 2
    assert layer.summary.stress_margin == (
        "La caja libre podría caer un 7 % antes de dejar de cubrir el dividendo."
    )


def test_un_run_sin_desglose_no_recibe_sumario_inventado() -> None:
    verdict = _verdict_mcd()
    for question in verdict["questions"]:
        question.pop("signals")
    layer = _report(verdict)

    assert layer.summary is None
