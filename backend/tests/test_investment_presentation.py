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
