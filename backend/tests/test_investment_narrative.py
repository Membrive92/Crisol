"""Las frases del veredicto (PHASE-44.24.B).

Goldens de TEXTO: la frase exacta por (pregunta × estado). Cambiar una plantilla
significa cambiar un golden, conscientemente y con su bump de versión.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from app.modules.investment.analysis.presentation.narrative import (
    DIVIDEND_TEMPLATES,
    EVIDENCE_TEMPLATES,
    HEADLINE_TEMPLATES,
    NARRATIVE_VERSION,
    NEXT_CHECK_TEMPLATES,
    QUESTION_TEMPLATES,
    QUESTION_TOPIC,
    RESCUE_TEMPLATES,
    headline,
    next_checks,
    question_sentence,
    templates_fingerprint,
)

TEMPLATE_FINGERPRINTS: dict[str, str] = {
    "1.0.0": "716fc8daebd7186e7470afcbc39621703ed2df66d5942b4b2c84b4b810d6c9bb",
}
"""Huella del TEXTO de las plantillas, por versión de narrativa.

Cuando este test falle la pregunta no es «cómo lo silencio» sino «¿he cambiado
lo que el informe DICE?». Si la respuesta es sí: sube `NARRATIVE_VERSION`,
añade su entrada al historial y registra aquí la huella que el propio fallo
imprime.

Se hashea el TEXTO y no las claves: con las claves, cambiar «holgado» por
«cómodo» pasaría sin bump — y ése es exactamente el cambio que hay que ver.
"""


def _question(**overrides: Any) -> dict[str, Any]:
    """Una pregunta del motor actual (≥ 1.6.0), con todo registrado."""
    base: dict[str, Any] = {
        "key": "accounting",
        "verdict": "healthy",
        "signals": [
            {"key": "m_score", "label": "M-Score de Beneish", "counted": True, "band": "healthy"}
        ],
        "evaluated_count": 5,
        "unavailable_count": 2,
        "clear_count": 2,
        "unchecked_count": 0,
        "audited": True,
        "red_signals": [],
        "amber_signals": [],
    }
    base.update(overrides)
    return base


# ── El gate de las plantillas ─────────────────────────────────────────


def test_las_plantillas_no_cambian_sin_mover_narrative_version() -> None:
    actual = templates_fingerprint()
    esperada = TEMPLATE_FINGERPRINTS.get(NARRATIVE_VERSION)
    assert esperada is not None, (
        f"NARRATIVE_VERSION={NARRATIVE_VERSION} no tiene huella registrada. "
        f"Añade a TEMPLATE_FINGERPRINTS: {NARRATIVE_VERSION!r}: {actual!r}"
    )
    assert actual == esperada, (
        "el TEXTO de alguna plantilla ha cambiado. Si es a propósito, sube "
        f"NARRATIVE_VERSION y registra: {NARRATIVE_VERSION!r}: {actual!r}"
    )


def test_ninguna_plantilla_escribe_un_numero_a_mano() -> None:
    """Los únicos números de una plantilla son sus parámetros.

    La regex del glosario busca PISTAS («por encima de», «del corte») y aquí no
    hacen falta: tras quitar los `{...}`, una plantilla no puede contener ningún
    dígito. Así se caza «−2,22», «1,5» y «30 %» sin depender de cómo esté
    redactada la frase que los rodea — que es lo que le fallaba a la versión
    basada en pistas.
    """
    placeholders = re.compile(r"\{[^}]*\}")
    culpables: list[str] = []
    grupos = {
        "questions": QUESTION_TEMPLATES,
        "evidence": EVIDENCE_TEMPLATES,
        "rescue": RESCUE_TEMPLATES,
        "headline": HEADLINE_TEMPLATES,
        "dividend": DIVIDEND_TEMPLATES,
        "next_check": NEXT_CHECK_TEMPLATES,
        "topic": QUESTION_TOPIC,
    }
    for nombre, grupo in grupos.items():
        for clave, texto in grupo.items():
            desnuda = placeholders.sub("", texto)
            if any(caracter.isdigit() for caracter in desnuda):
                culpables.append(f"{nombre}.{clave}: {desnuda!r}")
    assert culpables == [], culpables


def test_hay_una_plantilla_por_estado_de_presentacion() -> None:
    """Los seis: los tres colores más los tres que NO son un color."""
    assert set(QUESTION_TEMPLATES) == {
        "healthy",
        "caution",
        "stressed",
        "no-evidence",
        "not-audited",
        "not-recorded",
    }
    assert set(QUESTION_TOPIC) == {"accounting", "cash", "dividend", "resilience"}


# ── Goldens ───────────────────────────────────────────────────────────


def test_golden_pregunta_verde_con_desenlaces() -> None:
    frase, evidencia = question_sentence(_question())
    assert evidencia.state == "evaluated"
    assert frase == (
        "La contabilidad: sin señales en contra. Se evaluaron 5 señales, 2 se "
        "comprobaron y salieron limpias y 0 no se pudieron comprobar."
    )


def test_golden_pregunta_roja_cita_las_dos_peores() -> None:
    frase, _ = question_sentence(
        _question(key="dividend", verdict="stressed"),
        worst=["Payout sobre caja libre", "Años de dividendo en caja"],
    )
    assert frase == (
        "El dividendo frente a la caja: hay un problema — Payout sobre caja libre y "
        "Años de dividendo en caja. Se evaluaron 5 señales, 2 se comprobaron y "
        "salieron limpias y 0 no se pudieron comprobar."
    )


def test_golden_un_run_sin_desenlaces_no_dice_comprobadas_y_limpias() -> None:
    """El run de JNJ es de motor 1.3.0: allí esa distinción NO existía.

    Decirlo regeneraría en prosa el falso limpio que el motor 1.5.0 quitó, que es
    la razón por la que `outcomes_recorded` es un eje aparte del estado.
    """
    pregunta = _question()
    del pregunta["clear_count"]
    del pregunta["unchecked_count"]
    frase, evidencia = question_sentence(pregunta)
    assert evidencia.outcomes_recorded is False
    assert "comprobaron y salieron limpias" not in frase
    assert frase == (
        "La contabilidad: sin señales en contra. Se evaluaron 5 señales y 2 no "
        "puntuaron; el motor de entonces no distinguía las comprobadas y limpias de "
        "las que no se pudieron mirar."
    )


def test_golden_un_run_de_motor_100_no_esconde_sus_rojos() -> None:
    """El caso de McDonald's, que es el único valor analizado antes de 44.9.

    Su pregunta del dividendo es `stressed` con una etiqueta roja registrada.
    Esconderla tras «no es auditable» tiraría el único dato que ese run da — y
    sería la lección de PHASE-44.16 al revés.
    """
    frase, evidencia = question_sentence(
        {
            "key": "dividend",
            "verdict": "stressed",
            "red_signals": ["Años de dividendo en caja"],
            "amber_signals": ["Payout sobre caja libre"],
        }
    )
    assert evidencia.state == "not-recorded"
    assert "Años de dividendo en caja" in frase
    assert frase == (
        "El dividendo frente a la caja: este análisis lo produjo un motor anterior, "
        "que no registraba qué señales se evaluaron, así que su veredicto no es "
        "auditable. Lo que sí quedó registrado: Años de dividendo en caja y Payout "
        "sobre caja libre."
    )


def test_golden_una_pregunta_no_auditada_dice_que_falta_y_lo_que_si_puntuo() -> None:
    frase, evidencia = question_sentence(
        _question(
            key="resilience",
            verdict="stressed",
            audited=False,
            unaudited_reasons=["Z''-Score: no se pudo calcular"],
            signals=[
                {
                    "key": "S2",
                    "label": "Cobertura de intereses",
                    "counted": True,
                    "band": "stressed",
                }
            ],
        )
    )
    assert evidencia.state == "not-audited"
    assert frase == (
        "La resistencia a un golpe: el veredicto no se sostiene. Falta lo que decide "
        "esta pregunta (Z''-Score: no se pudo calcular). Lo que sí quedó registrado: "
        "Cobertura de intereses."
    )


def test_golden_sin_evidencia_no_se_presenta_como_verde() -> None:
    frase, evidencia = question_sentence(
        _question(evaluated_count=0, signals=[{"key": "m_score", "counted": False, "band": None}])
    )
    assert evidencia.state == "no-evidence"
    assert frase == (
        "La contabilidad: no hay nada que juzgar. Se miraron 1 señales y ninguna pudo "
        "puntuar, así que un verde aquí sería ausencia de prueba y no buena salud."
    )


def test_golden_titular_de_cada_perfil() -> None:
    assert headline(
        safety_label="conservative", blocking_reasons=[], dividend_verdict="healthy"
    ) == (
        "Perfil conservador: las cinco condiciones del motor se cumplen. El dividendo cabe en la caja."
    )
    assert headline(
        safety_label="avoid",
        blocking_reasons=["Z''-Score en rojo (riesgo de insolvencia)"],
        dividend_verdict="stressed",
    ) == (
        "Perfil a evitar: Z''-Score en rojo (riesgo de insolvencia). El dividendo está en riesgo."
    )
    assert headline(safety_label="watch", blocking_reasons=[], dividend_verdict=None) == (
        "Perfil a vigilar: no se ha registrado el motivo. Sin dividendo que juzgar aquí."
    )


# ── Qué miraría a continuación ────────────────────────────────────────


def test_una_pregunta_permanentemente_no_auditable_no_aporta_nada_que_vigilar() -> None:
    """El banco cuyo escenario de stress salía rojo dentro de una pregunta gris.

    Se reconoce porque NO declara portantes: el motor la declara no auditable
    dijeran lo que dijeran sus señales.
    """
    banco = _question(
        key="resilience",
        verdict="stressed",
        audited=False,
        load_bearing=[],
        unaudited_reasons=["la resiliencia de una financiera es capital regulatorio"],
    )
    checks = next_checks([banco], sentences={"resilience": [("Escenario de stress", "cruzado")]})
    assert all("Escenario de stress" not in c.text for c in checks)


def test_una_pregunta_temporalmente_no_auditada_si_aporta_pero_con_su_aviso() -> None:
    """Una contabilidad sin M-Score pero con los accruals en rojo es un hallazgo
    real: callarlo por un tecnicismo es peor que decirlo con su matiz."""
    pregunta = _question(
        audited=False,
        load_bearing=["m_score", "accruals"],
        unaudited_reasons=["M-Score: no se pudo calcular"],
    )
    checks = next_checks([pregunta], sentences={"accounting": [("Accruals de Sloan", "cruzado")]})
    assert len(checks) == 1
    assert "Accruals de Sloan" in checks[0].text
    assert "no está auditada" in checks[0].text


def test_nada_que_vigilar_esta_prohibido_si_algo_no_se_pudo_auditar() -> None:
    """Sería un «todo bien» construido sobre lo que no se ha mirado."""
    sin_auditar = _question(key="resilience", audited=False, load_bearing=["z_score"])
    checks = next_checks([sin_auditar], sentences={})
    assert len(checks) == 1
    assert checks[0].key == "blocked"
    assert "no se han podido auditar" in checks[0].text


def test_sin_nada_que_vigilar_se_dice_cuanto_se_ha_comprobado() -> None:
    """Un «todo bien» sin recuento no se puede distinguir de un «no se ha mirado
    nada»: es el falso verde que esta familia de fases lleva cerrando."""
    checks = next_checks([_question()], sentences={})
    assert len(checks) == 1
    assert checks[0].key == "nothing"
    assert "5 señales evaluadas" in checks[0].text


@pytest.mark.parametrize("limit", [1, 2, 3])
def test_que_miraria_no_pasa_de_su_limite(limit: int) -> None:
    pregunta = _question(verdict="stressed")
    checks = next_checks(
        [pregunta],
        sentences={"accounting": [(f"señal {i}", "cruzado") for i in range(6)]},
        limit=limit,
    )
    assert len(checks) == limit
