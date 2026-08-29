"""Las frases del veredicto (PHASE-44.24.B).

El informe contestaba las cuatro preguntas con un color y un desglose. Esto
añade la frase: qué se ha mirado, qué ha salido y por qué el semáforo dice lo
que dice — en la voz del proyecto y sin que nadie tenga que interpretarlo.

**Deterministas.** Ni LLM, ni azar, ni nada que no se pueda reproducir de un run
guardado. Mismo run + misma `NARRATIVE_VERSION` ⇒ misma frase, carácter a
carácter, y hay goldens que lo afirman.

**Las plantillas son DATOS y no f-strings**, que es lo que permite las dos cosas
que el plan pedía y con f-strings eran imposibles: hashearlas para que cambiar
una obligue a mover la versión —con f-strings lo único hashebale es el fuente
del módulo, así que un comentario forzaría un bump y el gate se volvería ruido—
y escanearlas para que ninguna escriba un corte a mano, que caduca en silencio.

**Seis estados por pregunta, no tres.** El semáforo sólo se puede nombrar cuando
la evidencia lo sostiene: `questionEvidence` tiene cuatro estados y tres de
ellos NO son un color. Más un modificador independiente —si el run registró
desenlaces por señal— porque en un run de 1.1.0-1.4.0 no se puede decir «se
comprobó y salió limpia»: allí esa distinción no existía, y afirmarla
regeneraría en prosa el falso limpio que el motor 1.5.0 quitó.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.modules.investment.analysis.presentation.evidence import (
    Evidence,
    evidence_of,
    legacy_labels,
    scored_labels,
)

NARRATIVE_VERSION = "1.0.0"
"""Versión de los TEXTOS, independiente de la del motor.

Sube cuando cambia una plantilla. Es distinta de `ENGINE_VERSION` a propósito:
una frase no forma parte de la reproducibilidad de un análisis —los números son
los mismos— así que reescribir una no puede obligar a reejecutar nada ni marcar
como caducado un run que sigue siendo válido.

Historial:
- 1.0.0 — PHASE-44.24.B: las cuatro preguntas, el titular y «qué miraría a
  continuación».
"""


# ── Plantillas ────────────────────────────────────────────────────────

QUESTION_TEMPLATES: Mapping[str, str] = {
    # Evaluada: el color se puede nombrar porque hay evidencia detrás.
    "healthy": "{tema}: sin señales en contra. {evidencia}.",
    "caution": "{tema}: hay algo que vigilar — {peores}. {evidencia}.",
    "stressed": "{tema}: hay un problema — {peores}. {evidencia}.",
    # Los tres estados que NO son un color.
    "no-evidence": (
        "{tema}: no hay nada que juzgar. Se miraron {candidatas} señales y ninguna "
        "pudo puntuar, así que un verde aquí sería ausencia de prueba y no buena salud."
    ),
    "not-audited": (
        "{tema}: el veredicto no se sostiene. Falta lo que decide esta pregunta "
        "({portantes}). {rescate}"
    ),
    "not-recorded": (
        "{tema}: este análisis lo produjo un motor anterior, que no registraba qué "
        "señales se evaluaron, así que su veredicto no es auditable. {rescate}"
    ),
}
"""Una plantilla por estado de presentación de una pregunta.

`{tema}` lo aporta cada pregunta y `{evidencia}` el desglose de lo comprobado,
que depende del modificador de desenlaces. `{rescate}` es lo que el run SÍ
registró aunque no se pueda auditar: esconderlo sería tirar el dato que existe.
"""

EVIDENCE_TEMPLATES: Mapping[str, str] = {
    "with_outcomes": (
        "Se evaluaron {evaluadas} señales, {limpias} se comprobaron y salieron limpias "
        "y {sin_comprobar} no se pudieron comprobar"
    ),
    # Un run de 1.1.0-1.4.0 no distingue «limpia» de «no se pudo»: decirlo sería
    # afirmar una comprobación que aquel motor no hizo.
    "without_outcomes": (
        "Se evaluaron {evaluadas} señales y {sin_puntuar} no puntuaron; el motor de "
        "entonces no distinguía las comprobadas y limpias de las que no se pudieron mirar"
    ),
}

RESCUE_TEMPLATES: Mapping[str, str] = {
    "with_labels": "Lo que sí quedó registrado: {etiquetas}.",
    # Si no hay nada registrado se dice, en vez de dejar la frase colgando.
    "empty": "No registró ninguna señal en rojo ni en ámbar.",
}

HEADLINE_TEMPLATES: Mapping[str, str] = {
    "conservative": "Perfil conservador: las cinco condiciones del motor se cumplen. {dividendo}",
    "watch": "Perfil a vigilar: {bloqueo}. {dividendo}",
    "avoid": "Perfil a evitar: {bloqueo}. {dividendo}",
}

DIVIDEND_TEMPLATES: Mapping[str, str] = {
    "healthy": "El dividendo cabe en la caja.",
    "caution": "El dividendo pide vigilancia.",
    "stressed": "El dividendo está en riesgo.",
    "not_applicable": "Sin dividendo que juzgar aquí.",
}

NEXT_CHECK_TEMPLATES: Mapping[str, str] = {
    "signal": "{etiqueta}: {distancia}.",
    "unaudited": "{etiqueta}: {distancia} — en una pregunta que no está auditada.",
    "nothing": (
        "Nada que vigilar en este análisis: {evaluadas} señales evaluadas y ninguna "
        "en ámbar ni en rojo."
    ),
    # Prohibido decir «nada que vigilar» cuando hay preguntas sin auditar: sería
    # un «todo bien» construido sobre lo que no se ha mirado.
    "blocked": (
        "No se puede decir qué vigilar: {cuantas} de las cuatro preguntas no se han "
        "podido auditar. Vuelve a ejecutar el análisis."
    ),
}

QUESTION_TOPIC: Mapping[str, str] = {
    "accounting": "La contabilidad",
    "cash": "La generación de caja",
    "dividend": "El dividendo frente a la caja",
    "resilience": "La resistencia a un golpe",
}


def templates_fingerprint() -> str:
    """Huella del TEXTO de todas las plantillas.

    Del texto y no de las claves: un gate que hasheara los nombres dejaría pasar
    un cambio de «holgado» a «cómodo» sin bump, que es exactamente el cambio que
    hay que ver. Lo que esta huella NO cubre —el código que las compone y el
    formateo— lo cubren los goldens.
    """
    payload = {
        "questions": dict(sorted(QUESTION_TEMPLATES.items())),
        "evidence": dict(sorted(EVIDENCE_TEMPLATES.items())),
        "rescue": dict(sorted(RESCUE_TEMPLATES.items())),
        "headline": dict(sorted(HEADLINE_TEMPLATES.items())),
        "dividend": dict(sorted(DIVIDEND_TEMPLATES.items())),
        "next_check": dict(sorted(NEXT_CHECK_TEMPLATES.items())),
        "topic": dict(sorted(QUESTION_TOPIC.items())),
    }
    blob = json.dumps(payload, separators=(",", ":"), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ── Composición ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class NextCheck:
    """Un bullet de «qué miraría a continuación»."""

    key: str
    text: str


def _join(labels: Sequence[str]) -> str:
    """`a`, `a y b`, `a, b y c` — como se dice en voz alta."""
    items = [label for label in labels if label]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} y {items[-1]}"


def _evidence_sentence(question: Mapping[str, Any], evidence: Evidence) -> str:
    evaluated = int(question.get("evaluated_count") or 0)
    if evidence.outcomes_recorded:
        return EVIDENCE_TEMPLATES["with_outcomes"].format(
            evaluadas=evaluated,
            limpias=int(question.get("clear_count") or 0),
            sin_comprobar=int(question.get("unchecked_count") or 0),
        )
    return EVIDENCE_TEMPLATES["without_outcomes"].format(
        evaluadas=evaluated, sin_puntuar=int(question.get("unavailable_count") or 0)
    )


def _rescue_sentence(question: Mapping[str, Any], *, legacy: bool) -> str:
    """Lo que el run registró aunque su veredicto no se pueda auditar.

    En un run de motor 1.0.0 no hay desglose, pero `red_signals` y
    `amber_signals` SÍ están y son etiquetas legibles: McDonald's tiene dos
    preguntas en rojo con tres etiquetas entre las dos. Esconderlas tras «no es
    auditable» tiraría el único dato que ese run sí da.
    """
    getter = legacy_labels if legacy else scored_labels
    labels = [*getter(question, "stressed"), *getter(question, "caution")]
    if not labels:
        return RESCUE_TEMPLATES["empty"]
    return RESCUE_TEMPLATES["with_labels"].format(etiquetas=_join(labels))


def question_sentence(
    question: Mapping[str, Any], *, worst: Sequence[str] = ()
) -> tuple[str, Evidence]:
    """La frase de una pregunta y el estado en que se ha compuesto.

    `worst` son las etiquetas de las dos peores señales, ya ordenadas por la
    capa de severidad: la frase cita lo que más duele, no lo primero que la
    síntesis construyó.
    """
    evidence = evidence_of(question)
    topic = QUESTION_TOPIC.get(str(question.get("key") or ""), "Esta pregunta")

    if evidence.state == "not-recorded":
        return (
            QUESTION_TEMPLATES["not-recorded"].format(
                tema=topic, rescate=_rescue_sentence(question, legacy=True)
            ),
            evidence,
        )
    if evidence.state == "not-audited":
        reasons = [str(r) for r in (question.get("unaudited_reasons") or []) if r]
        return (
            QUESTION_TEMPLATES["not-audited"].format(
                tema=topic,
                portantes=_join(reasons) or "no se ha registrado qué falta",
                rescate=_rescue_sentence(question, legacy=False),
            ),
            evidence,
        )
    if evidence.state == "no-evidence":
        return (
            QUESTION_TEMPLATES["no-evidence"].format(
                tema=topic, candidatas=len(question.get("signals") or [])
            ),
            evidence,
        )

    band = str(question.get("verdict") or "healthy")
    template = QUESTION_TEMPLATES.get(band, QUESTION_TEMPLATES["healthy"])
    return (
        template.format(
            tema=topic,
            peores=_join(worst) or "sin señales que destacar",
            evidencia=_evidence_sentence(question, evidence),
        ),
        evidence,
    )


def headline(
    *, safety_label: str, blocking_reasons: Sequence[str], dividend_verdict: str | None
) -> str:
    """El titular: perfil de seguridad y dividendo, en una frase."""
    dividend = DIVIDEND_TEMPLATES.get(
        str(dividend_verdict or "not_applicable"), DIVIDEND_TEMPLATES["not_applicable"]
    )
    template = HEADLINE_TEMPLATES.get(safety_label, HEADLINE_TEMPLATES["watch"])
    if safety_label == "conservative":
        return template.format(dividendo=dividend)
    return template.format(
        bloqueo=_join([str(r) for r in blocking_reasons][:2]) or "no se ha registrado el motivo",
        dividendo=dividend,
    )


def next_checks(
    questions: Sequence[Mapping[str, Any]],
    *,
    sentences: Mapping[str, Sequence[tuple[str, str]]],
    limit: int = 3,
) -> list[NextCheck]:
    """Qué miraría a continuación: hasta tres señales, las peores primero.

    `sentences` son, por pregunta, los pares (etiqueta, distancia) de sus
    señales ámbar y rojas YA ordenadas por severidad.

    Tres reglas, y cada una viene de un caso concreto:

    1. **Las preguntas permanentemente no auditables se excluyen enteras.** El
       motor declara «¿aguanta un golpe?» no auditable en banca, y hasta el
       motor 1.7.0 su escenario de stress podía salir rojo ahí dentro: sin esta
       regla, un banco tendría como titular «vigila el escenario de stress»
       justo debajo del chip gris que dice que esa pregunta no se ha auditado.
       Se reconocen porque no declaran portantes: `load_bearing` vacío y
       `audited` en falso.
    2. **Las temporalmente no auditadas SÍ entran**, con el aviso. Una
       contabilidad sin M-Score pero con los accruals en rojo es un hallazgo
       real, y callarlo por un tecnicismo es peor que decirlo con su matiz.
    3. **«Nada que vigilar» está prohibido si alguna pregunta no se pudo
       auditar.** Sería un «todo bien» construido sobre lo que no se ha mirado,
       que es el falso verde que esta familia de fases lleva cerrando desde
       PHASE-44.9.
    """
    unauditable = 0
    collected: list[NextCheck] = []
    evaluated_total = 0

    for question in questions:
        key = str(question.get("key") or "")
        evidence = evidence_of(question)
        evaluated_total += int(question.get("evaluated_count") or 0)

        permanent = evidence.state == "not-audited" and not (question.get("load_bearing") or [])
        if evidence.state in ("not-recorded", "not-audited"):
            unauditable += 1
        if permanent:
            continue

        template = (
            NEXT_CHECK_TEMPLATES["unaudited"]
            if evidence.state == "not-audited"
            else NEXT_CHECK_TEMPLATES["signal"]
        )
        for label, distance in sentences.get(key, ()):
            collected.append(
                NextCheck(
                    key=f"{key}:{label}",
                    text=template.format(etiqueta=label, distancia=distance),
                )
            )

    if collected:
        return collected[:limit]
    if unauditable:
        return [
            NextCheck(
                key="blocked",
                text=NEXT_CHECK_TEMPLATES["blocked"].format(cuantas=unauditable),
            )
        ]
    return [
        NextCheck(
            key="nothing",
            text=NEXT_CHECK_TEMPLATES["nothing"].format(evaluadas=evaluated_total),
        )
    ]
