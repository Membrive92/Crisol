"""Qué se puede AFIRMAR del veredicto de una pregunta (PHASE-44.24.B).

Réplica en Python de `questionEvidence` de `packages/ui`. Son dos
implementaciones de la misma regla, así que un fixture compartido las ata: sin
él, cambiar la regla en un lado deja al otro contando otra historia sobre la
misma empresa.

Se replica en vez de mandar el estado desde el cliente porque las frases se
componen aquí (entrega B), y una frase que dijera «verde» sobre una pregunta que
la pantalla pinta gris sería peor que no tener frase.

**Ausente no es cero, ni `False`.** Un `AnalysisRun` es JSONB persistido y la
tabla contiene runs de todas las versiones del motor: los campos que llegaron
después no están, y colapsarlos con su valor por defecto inventa un dato
(lección PHASE-44.16). Por eso todo se pregunta con `in` y no con `.get()`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

QuestionEvidence = Literal["evaluated", "no-evidence", "not-recorded", "not-audited"]


@dataclass(frozen=True)
class Evidence:
    """El estado de una pregunta y si su run registró desenlaces por señal."""

    state: QuestionEvidence
    outcomes_recorded: bool
    """Si el run distingue «se comprobó y salió limpia» de «no se pudo
    comprobar» (motor ≥ 1.5.0).

    Es un eje INDEPENDIENTE del estado, y por eso viaja aparte: una pregunta
    puede estar perfectamente evaluada en un run de 1.3.0 y aun así no permitir
    decir «las cinco banderas, comprobadas y limpias» — allí ese desglose no
    existía, y afirmarlo regeneraría en prosa el falso limpio que 1.5.0 quitó.
    """


def evidence_of(question: Mapping[str, Any]) -> Evidence:
    """El estado de evidencia de una pregunta persistida.

    Mismo orden de comprobaciones que la versión de TypeScript, y por el mismo
    motivo cada uno:

    1. Sin `signals` o sin `evaluated_count` → el motor de aquel día no
       registraba el desglose (< 1.1.0). No se sabe si el verde es salud o
       ausencia de prueba, y fingir que se sabe fue el bug que costó un crash.
    2. `audited is False` → falta un PORTANTE (motor ≥ 1.6.0). `undefined` no es
       `False`: en los runs anteriores la distinción no se registraba.
    3. Cero señales evaluadas habiendo candidatas → el verde sería por ausencia
       de prueba.
    """
    if "signals" not in question or "evaluated_count" not in question:
        return Evidence(state="not-recorded", outcomes_recorded=False)

    outcomes = "clear_count" in question and "unchecked_count" in question
    if question.get("audited") is False:
        return Evidence(state="not-audited", outcomes_recorded=outcomes)

    evaluated = question.get("evaluated_count") or 0
    signals = question.get("signals") or []
    if evaluated == 0 and len(signals) > 0:
        return Evidence(state="no-evidence", outcomes_recorded=outcomes)
    return Evidence(state="evaluated", outcomes_recorded=outcomes)


def scored_labels(question: Mapping[str, Any], band: str) -> list[str]:
    """Las etiquetas de las señales que PUNTUARON en una banda.

    Se usa en los estados degradados: una pregunta no auditada puede tener un
    rojo real, y la frase tiene que nombrarlo en vez de esconderlo tras «no se
    ha podido comprobar». Es la mitad honesta de la honestidad.
    """
    labels: list[str] = []
    for signal in question.get("signals") or []:
        if not isinstance(signal, Mapping):
            continue
        if signal.get("counted") and signal.get("band") == band:
            labels.append(str(signal.get("label") or signal.get("key") or ""))
    return [label for label in labels if label]


def legacy_labels(question: Mapping[str, Any], band: str) -> list[str]:
    """Las etiquetas que un run de motor < 1.1.0 SÍ registró.

    `red_signals` y `amber_signals` son ETIQUETAS, no claves —lo son desde
    siempre—, así que se usan tal cual. Que la pregunta no traiga desglose no
    significa que no dijera nada: en McDonald's hay dos preguntas en rojo con
    tres etiquetas entre las dos, y esconderlas tras «este análisis lo produjo un
    motor anterior» sería tirar el dato que sí existe.
    """
    key = "red_signals" if band == "stressed" else "amber_signals"
    return [str(label) for label in (question.get(key) or []) if label]
