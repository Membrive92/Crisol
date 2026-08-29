"""La capa de lectura que se adjunta a un run al servirlo (PHASE-44.24.C).

Ensambla lo que las piezas puras calculan —distancia, orden, procedencia— en la
forma que la pantalla consume. PURA: recibe el run ya persistido y el mundo de
hoy por parámetro, y no toca ni BD ni reloj.

Lo que NO hace todavía: las frases del veredicto, el titular y «qué miraría a
continuación», que llegan en la entrega B. Esta capa deja el sitio hecho.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.modules.investment.analysis.engine.catalog import ALL_DEFAULT_THRESHOLDS, definition_for
from app.modules.investment.analysis.engine.types import (
    Band,
    MetricResult,
    MetricStatus,
    ThresholdSpec,
)
from app.modules.investment.analysis.presentation.distance import SignalDistance, distance_to_cut
from app.modules.investment.analysis.presentation.evidence import Evidence
from app.modules.investment.analysis.presentation.narrative import (
    NARRATIVE_VERSION,
    NextCheck,
    headline,
    next_checks,
    question_sentence,
)
from app.modules.investment.analysis.presentation.ordering import severity_key
from app.modules.investment.analysis.presentation.origin import (
    Origin,
    ThresholdProfile,
    threshold_origin,
)
from app.modules.investment.analysis.presentation.rehydrate import rehydrate_thresholds


@dataclass(frozen=True)
class ReportSignal:
    """Una señal del veredicto, enriquecida para poder leerla."""

    key: str
    status: MetricStatus | None
    """Se publica para que la pantalla imprima la marca de aproximación junto al
    valor. Un número citado sin su `*` es un número que miente sobre su propia
    fiabilidad (regla 3 de honestidad)."""
    severity_rank: int
    """Posición en el orden de severidad, 0 = peor. Se publica ya resuelta para
    que las dos apps no tengan que reimplementar la comparación."""
    distance: SignalDistance | None
    threshold_origin: Origin


@dataclass(frozen=True)
class ReportQuestion:
    key: str
    signals: tuple[ReportSignal, ...]
    evidence: str = "evaluated"
    """El estado en que se puede leer el veredicto: sólo uno de los cuatro es un
    color. Se publica para que la pantalla y la frase no puedan discrepar."""
    outcomes_recorded: bool = False
    """Si el run distingue «comprobada y limpia» de «no se pudo comprobar»."""
    sentence: str = ""
    """La frase determinista de esta pregunta (PHASE-44.24.B)."""


@dataclass(frozen=True)
class ReportLayer:
    threshold_profile: ThresholdProfile
    questions: tuple[ReportQuestion, ...]
    narrative_version: str = NARRATIVE_VERSION
    """La versión de los TEXTOS. Viaja para que un dictamen impreso pueda citar
    las tres versiones y siga siendo reproducible."""
    headline: str = ""
    next_checks: tuple[NextCheck, ...] = ()


def _as_metric(signal: Mapping[str, Any]) -> MetricResult | None:
    """Una señal persistida vista como métrica, para poder medirle la distancia.

    Las señales de bandera y las derivadas no traen valor, así que devuelven
    `None` y se quedan sin gradiente — que es exactamente lo que son: evidencia
    binaria, no un roce con la raya.
    """
    value = signal.get("value")
    if value is None:
        return None
    band = signal.get("band")
    status = signal.get("status") or "ok"
    if status not in ("ok", "approximation"):
        return None
    try:
        parsed = Decimal(str(value))
    except (ArithmeticError, ValueError):
        return None
    return MetricResult(
        key=str(signal.get("key") or ""),
        fiscal_year=0,
        value=parsed,
        status=status,  # type: ignore[arg-type]
        provenance="sourced",  # type: ignore[arg-type]
        band=band if band in ("healthy", "caution", "stressed") else None,  # type: ignore[arg-type]
    )


def _sort_value(signal: Mapping[str, Any], distance: SignalDistance | None) -> tuple[Any, ...]:
    """La clave de orden de una señal PERSISTIDA.

    `severity_key` trabaja sobre `QuestionSignal`, que es un dataclass del
    engine; aquí lo que hay es el diccionario que quedó guardado. Se compone la
    misma clave a mano en vez de reconstruir el dataclass, porque un run viejo
    puede no traer todos sus campos y el constructor tiene invariantes que
    lanzarían.
    """

    class _Shim:
        key = str(signal.get("key") or "")
        band: Band | None = (
            signal.get("band") if signal.get("band") in ("healthy", "caution", "stressed") else None
        )

    return severity_key(_Shim, distance)  # type: ignore[arg-type]


def _worst_labels(
    signals: Sequence[Mapping[str, Any]], distances: Mapping[str, SignalDistance | None]
) -> list[str]:
    """Las etiquetas de las dos peores señales que PUNTUARON, ya en orden.

    Sólo las que puntúan: citar una señal que no cuenta como si explicara el
    veredicto sería atribuirle un peso que no tiene.
    """
    labels: list[str] = []
    for signal in signals:
        if not signal.get("counted"):
            continue
        if signal.get("band") not in ("stressed", "caution"):
            continue
        labels.append(str(signal.get("label") or signal.get("key") or ""))
    return [label for label in labels if label][:2]


def build_report(
    *,
    verdict: Mapping[str, Any],
    thresholds_used: Mapping[str, Any] | None,
    profile: ThresholdProfile,
    profile_thresholds: Mapping[str, ThresholdSpec],
) -> ReportLayer:
    """La capa de lectura de un run.

    `profile_thresholds` es la resolución de HOY para este valor, y sólo se usa
    para derivar la procedencia de los runs que no la registran (motor < 1.7.0).
    """
    used = rehydrate_thresholds(thresholds_used)
    questions: list[ReportQuestion] = []
    narrated: list[
        tuple[Mapping[str, Any], Evidence, Mapping[str, SignalDistance | None], list[Any]]
    ] = []
    for raw_question in verdict.get("questions") or []:
        if not isinstance(raw_question, Mapping):
            continue
        signals = [s for s in (raw_question.get("signals") or []) if isinstance(s, Mapping)]
        enriched: list[tuple[tuple[Any, ...], Mapping[str, Any], SignalDistance | None]] = []
        for signal in signals:
            key = str(signal.get("key") or "")
            definition = definition_for(key)
            distance = distance_to_cut(
                _as_metric(signal),
                used.get(key),
                unit=definition.unit.value if definition is not None else None,
            )
            enriched.append((_sort_value(signal, distance), signal, distance))
        enriched.sort(key=lambda item: item[0])
        ordered_signals = [signal for _, signal, _ in enriched]
        distances = {str(s.get("key") or ""): d for _, s, d in enriched}
        sentence, evidence = question_sentence(
            raw_question, worst=_worst_labels(ordered_signals, distances)
        )
        narrated.append((raw_question, evidence, distances, ordered_signals))
        questions.append(
            ReportQuestion(
                key=str(raw_question.get("key") or ""),
                evidence=evidence.state,
                outcomes_recorded=evidence.outcomes_recorded,
                sentence=sentence,
                signals=tuple(
                    ReportSignal(
                        key=str(signal.get("key") or ""),
                        status=signal.get("status"),
                        severity_rank=rank,
                        distance=distance,
                        threshold_origin=threshold_origin(
                            str(signal.get("key") or ""),
                            persisted=thresholds_used,
                            used=used,
                            generic=ALL_DEFAULT_THRESHOLDS,
                            profile=profile_thresholds,
                        ),
                    )
                    for rank, (_, signal, distance) in enumerate(enriched)
                ),
            )
        )
    return ReportLayer(
        threshold_profile=profile,
        questions=tuple(questions),
        narrative_version=NARRATIVE_VERSION,
        headline=headline(
            safety_label=str((verdict.get("safety_profile") or {}).get("label") or "watch"),
            blocking_reasons=[
                str(r)
                for r in ((verdict.get("safety_profile") or {}).get("blocking_reasons") or [])
            ],
            dividend_verdict=verdict.get("dividend_verdict"),
        ),
        next_checks=tuple(
            next_checks(
                [q for q, _, _, _ in narrated],
                sentences={
                    str(q.get("key") or ""): [
                        (
                            str(s.get("label") or s.get("key") or ""),
                            _distance_phrase(distances.get(str(s.get("key") or ""))),
                        )
                        for s in signals
                        if s.get("counted") and s.get("band") in ("stressed", "caution")
                    ]
                    for q, _, distances, signals in narrated
                },
            )
        ),
    )


def _distance_phrase(distance: SignalDistance | None) -> str:
    """La distancia en una frase MÍNIMA para el bullet.

    Aquí no se formatea por unidad —eso es de `packages/ui`, que lo hace igual
    en las dos apps— así que se dice lo estructural: de qué lado del corte está.
    La pantalla puede enriquecerlo con el número si quiere.
    """
    if distance is None:
        return "sin distancia que medir"
    if distance.side == "outside":
        return f"ya ha cruzado hacia el {'rojo' if distance.next_band == 'stressed' else 'ámbar'}"
    return f"se acerca al {'rojo' if distance.next_band == 'stressed' else 'ámbar'}"
