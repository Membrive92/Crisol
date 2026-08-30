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
    concerns_intro,
    exit_sentence,
    headline,
    models_disagree,
    next_checks,
    question_sentence,
    strengths_intro,
    stress_margin_sentence,
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
    drove_verdict: bool = False
    """Si esta señal hizo cierta una condición de «Evitar» que se cumple.

    NO es lo mismo que estar en rojo: el escenario de stress tiñe su pregunta y
    no está en la matriz del sello. Confundir «tiñó la pregunta» con «disparó el
    perfil» es la costura que el lector no podía coser (PHASE-44.25)."""
    evidence_sentences: tuple[str, ...] = ()
    """Frases YA persistidas que dan cuerpo a una señal sin número.

    La del escenario de stress salía «Valor —· Riesgo · Distancia —»: la fila
    más severa de la pregunta era la más hueca, con sus cifras tres cards más
    abajo. Las frases las redactó el motor que produjo el run, así que también
    llegan a los runs viejos."""


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
class ReportConditionSignal:
    """El enriquecimiento de una señal de la matriz: lo que la capa de lectura
    calcula y el run no guarda.

    El valor, la banda y la etiqueta ya viajan DENTRO de la condición del run:
    duplicarlos aquí sería tener dos fuentes para el mismo número. La pantalla
    cruza por CLAVE, que es el puente que esta fase viene a construir.
    """

    key: str
    distance: SignalDistance | None
    threshold_origin: Origin


@dataclass(frozen=True)
class ReportSummary:
    """El sumario del Dictamen, seleccionado y ENUNCIADO aquí (PHASE-44.26).

    La selección vive en el servidor junto a las frases que la nombran: qué
    entra y en qué orden ES parte de lo que la frase afirma, y tenerlos en
    capas distintas sería dos fuentes para la misma decisión. Las claves viajan
    para que la pantalla pinte las filas con número, unidad y enlace — los
    números no van en la prosa.

    Reglas (las mismas que el selector del cliente, que queda como fallback
    para backends anteriores):
    - Una pregunta PERMANENTEMENTE no auditable no aporta a ninguna lista.
    - «Qué preocupa»: toda señal que puntuó en rojo o ámbar, rojas primero; el
      tope max(6, nº de rojas) jamás esconde una roja.
    - «Qué está bien»: los verdes de preguntas con evidencia EVALUADA — un
      verde por ausencia de prueba no es una fortaleza.
    """

    concerns_intro: str
    concern_keys: tuple[str, ...]
    concerns_overflow: int
    strengths_intro: str
    strength_keys: tuple[str, ...]
    strengths_overflow: int
    stress_sentences: tuple[str, ...] = ()
    stress_margin: str | None = None


@dataclass(frozen=True)
class ReportWhy:
    """Por qué este veredicto (PHASE-44.25).

    Sólo existe si el run trae la matriz evaluada. Para un run anterior es
    `None` —precondición, no etiqueta—: reconstruirlo con la regla de HOY
    afirmaría sobre aquel análisis algo que su motor no comprobó.
    """

    decided_by: tuple[str, ...]
    """Las claves de las condiciones de «Evitar» que se cumplen."""
    exit_sentence: str
    models_disagree: str | None = None
    signals: tuple[ReportConditionSignal, ...] = ()


@dataclass(frozen=True)
class ReportLayer:
    threshold_profile: ThresholdProfile
    questions: tuple[ReportQuestion, ...]
    narrative_version: str = NARRATIVE_VERSION
    """La versión de los TEXTOS. Viaja para que un dictamen impreso pueda citar
    las tres versiones y siga siendo reproducible."""
    headline: str = ""
    next_checks: tuple[NextCheck, ...] = ()
    why: ReportWhy | None = None
    summary: ReportSummary | None = None
    """`None` en runs sin señales estructuradas (motor < 1.1.0): sin desglose
    no hay con qué seleccionar, y el cliente cae a `next_checks`."""


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


_SUMMARY_CAP = 6


def _build_summary(
    narrated: Sequence[tuple[Mapping[str, Any], Evidence, Mapping[str, Any], list[Any]]],
    verdict: Mapping[str, Any],
) -> ReportSummary | None:
    """El sumario del Dictamen. Ver `ReportSummary` para las reglas."""
    con_desglose = [
        (question, evidence, señales)
        for question, evidence, _, señales in narrated
        if question.get("signals") is not None
    ]
    if not con_desglose:
        return None

    def _permanente(question: Mapping[str, Any], evidence: Evidence) -> bool:
        # El predicado de la regla 1 de next_checks: no auditable Y sin
        # portantes declarados — la financiera. Sus señales no aportan a
        # ninguna lista, ni en rojo ni en verde.
        return evidence.state == "not-audited" and not (question.get("load_bearing") or [])

    elegibles = [
        (question, evidence, señales)
        for question, evidence, señales in con_desglose
        if not _permanente(question, evidence)
    ]

    def _puntuadas(banda: str, solo_evaluadas: bool) -> list[Mapping[str, Any]]:
        out: list[Mapping[str, Any]] = []
        for question, evidence, señales in elegibles:
            if solo_evaluadas and (
                evidence.state != "evaluated" or not int(question.get("evaluated_count") or 0)
            ):
                continue
            for señal in señales:
                if señal.get("counted") and señal.get("band") == banda:
                    out.append(señal)
        return out

    rojas = _puntuadas("stressed", solo_evaluadas=False)
    ambar = _puntuadas("caution", solo_evaluadas=False)
    tope = max(_SUMMARY_CAP, len(rojas))
    preocupan = (rojas + ambar)[:tope]
    verdes = _puntuadas("healthy", solo_evaluadas=True)
    fortalezas = verdes[:_SUMMARY_CAP]

    def _labels(señales: Sequence[Mapping[str, Any]]) -> list[str]:
        return [str(s.get("label") or s.get("key") or "") for s in señales]

    stress = verdict.get("stress")
    stress_sentences: tuple[str, ...] = ()
    stress_margin: str | None = None
    if isinstance(stress, Mapping):
        stress_sentences = tuple(
            str(scenario.get("sentence"))
            for scenario in stress.get("scenarios") or []
            if isinstance(scenario, Mapping) and scenario.get("sentence")
        )
        stress_margin = stress_margin_sentence(stress.get("breakeven_fcf_drop"))

    return ReportSummary(
        concerns_intro=concerns_intro(_labels(preocupan)),
        concern_keys=tuple(str(s.get("key") or "") for s in preocupan),
        concerns_overflow=len(rojas) + len(ambar) - len(preocupan),
        strengths_intro=strengths_intro(_labels(fortalezas)),
        strength_keys=tuple(str(s.get("key") or "") for s in fortalezas),
        strengths_overflow=len(verdes) - len(fortalezas),
        stress_sentences=stress_sentences,
        stress_margin=stress_margin,
    )


def _decisive_keys(conditions: Sequence[Mapping[str, Any]]) -> set[str]:
    """Las claves de señal que hacen cierta una condición de «Evitar» cumplida."""
    return {
        str(signal.get("key") or "")
        for condition in conditions
        if condition.get("rule") == "avoid" and condition.get("met") is True
        for signal in (condition.get("signals") or [])
        if isinstance(signal, Mapping)
    } - {""}


def _condition_signals(
    conditions: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Las señales de todas las condiciones, SIN repetir clave.

    Cinco métricas se comparten entre las diez condiciones (el X-Score aparece
    en la de «Evitar» y en la de «Conservador»): enriquecer dos veces la misma
    clave daría dos filas idénticas y una de ellas sobra.
    """
    vistas: set[str] = set()
    out: list[Mapping[str, Any]] = []
    for condition in conditions:
        for signal in condition.get("signals") or []:
            if not isinstance(signal, Mapping):
                continue
            key = str(signal.get("key") or "")
            if not key or key in vistas:
                continue
            vistas.add(key)
            out.append(signal)
    return out


def _stress_sentences(verdict: Mapping[str, Any]) -> tuple[str, ...]:
    """Las frases de los escenarios que dejan de cubrir.

    Están persistidas desde PHASE-44.5 con sus dos coberturas dentro, y nadie
    las cruzaba con la señal que resumen. Se leen con tolerancia porque un run
    viejo puede no traer el bloque entero.
    """
    stress = verdict.get("stress")
    if not isinstance(stress, Mapping):
        return ()
    out: list[str] = []
    for scenario in stress.get("scenarios") or []:
        if not isinstance(scenario, Mapping):
            continue
        after = scenario.get("coverage_after")
        sentence = scenario.get("sentence")
        if after is None or not sentence:
            continue
        try:
            coverage = Decimal(str(after))
        except (ArithmeticError, ValueError):
            continue
        if coverage < 1:
            out.append(str(sentence))
    return tuple(out)


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
    safety = verdict.get("safety_profile")
    conditions = [c for c in ((safety or {}).get("conditions") or []) if isinstance(c, Mapping)]
    decisive = _decisive_keys(conditions)
    stress_sentences = _stress_sentences(verdict)
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
                        drove_verdict=str(signal.get("key") or "") in decisive,
                        # Sólo si la señal está señalando un problema: las
                        # frases explican por qué la cobertura se rompe, y bajo
                        # una señal limpia dirían lo contrario de lo que se lee.
                        evidence_sentences=(
                            stress_sentences
                            if signal.get("key") == "stress"
                            and signal.get("band") in ("stressed", "caution")
                            else ()
                        ),
                    )
                    for rank, (_, signal, distance) in enumerate(enriched)
                ),
            )
        )
    safety_label = str((safety or {}).get("label") or "watch")
    why = (
        ReportWhy(
            decided_by=tuple(
                str(c.get("key") or "")
                for c in conditions
                if c.get("rule") == "avoid" and c.get("met") is True
            ),
            exit_sentence=exit_sentence(safety_label=safety_label, conditions=conditions),
            models_disagree=models_disagree(conditions),
            signals=tuple(
                ReportConditionSignal(
                    key=str(signal.get("key") or ""),
                    distance=distance_to_cut(
                        _as_metric(signal),
                        used.get(str(signal.get("key") or "")),
                        unit=(
                            definition.unit.value
                            if (definition := definition_for(str(signal.get("key") or "")))
                            is not None
                            else None
                        ),
                    ),
                    threshold_origin=threshold_origin(
                        str(signal.get("key") or ""),
                        persisted=thresholds_used,
                        used=used,
                        generic=ALL_DEFAULT_THRESHOLDS,
                        profile=profile_thresholds,
                    ),
                )
                for signal in _condition_signals(conditions)
            ),
        )
        # Precondición, no etiqueta: sin la matriz evaluada no se compone un
        # porqué con la regla de hoy sobre un run de otro motor.
        if conditions
        else None
    )
    return ReportLayer(
        threshold_profile=profile,
        questions=tuple(questions),
        narrative_version=NARRATIVE_VERSION,
        why=why,
        summary=_build_summary(narrated, verdict),
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
                            str(s.get("key") or ""),
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
