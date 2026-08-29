"""Qué ha cambiado entre dos análisis de la misma empresa (PHASE-44.24.F).

La tabla guarda un `AnalysisRun` por ejecución, así que la pregunta natural
—«¿esto ha empeorado o he cambiado yo el motor?»— tiene respuesta, pero hasta
ahora había que compararlos a ojo abriendo dos pestañas.

**La distinción que gobierna todo el módulo**: un cambio entre dos runs puede
venir de la EMPRESA (publicó otro ejercicio, sus números se movieron) o del
MÉTODO (subió el motor, se recalibraron los umbrales). Presentarlos juntos sería
peor que no comparar: leer «el Z''-Score pasó de verde a ámbar» como una
degradación del negocio cuando lo que cambió fue el corte es exactamente la
conclusión equivocada.

Por eso `comparable` es una precondición y no una etiqueta: si el motor o los
umbrales difieren, NO se emite ni un solo cambio de empresa.

Capa PURA: recibe los dos payloads y los `RestatementFlag` ya cargados; no toca
BD ni reloj.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.modules.investment.analysis.engine import forensic
from app.modules.investment.analysis.presentation.evidence import evidence_of

__all__ = [
    "BandChange",
    "FlagChange",
    "QuestionChange",
    "RestatementNote",
    "RunDiff",
    "ScoreChange",
    "diff_runs",
]


@dataclass(frozen=True)
class ScoreChange:
    """Un score forense entre los dos análisis."""

    key: str
    before: str | None
    after: str | None
    band_before: str | None
    band_after: str | None


@dataclass(frozen=True)
class BandChange:
    """Una métrica que ha cambiado de banda."""

    key: str
    band_before: str | None
    band_after: str | None
    value_before: str | None
    value_after: str | None


@dataclass(frozen=True)
class FlagChange:
    """Una bandera que se ha encendido o apagado."""

    key: str
    label: str | None
    severity: str | None
    appeared: bool


@dataclass(frozen=True)
class QuestionChange:
    """Una de las cuatro preguntas, con su veredicto y su evidencia."""

    key: str
    verdict_before: str | None
    verdict_after: str | None
    evidence_before: str
    evidence_after: str


@dataclass(frozen=True)
class RestatementNote:
    """Una reexpresión detectada ENTRE las dos fechas de análisis.

    No es un cambio del run: es la explicación de por qué los números se
    movieron sin que la empresa publicara un ejercicio nuevo.
    """

    fiscal_year: int
    filing_a: str
    filing_b: str
    item_count: int


@dataclass(frozen=True)
class RunDiff:
    """El resultado de comparar dos análisis.

    `comparable` gobierna qué se rellena: con `False`, `company_changes` está
    VACÍO por construcción y sólo hay `method_changes`.
    """

    comparable: bool
    base_id: str
    target_id: str
    base_date: datetime | None
    target_date: datetime | None
    method_changes: list[str] = field(default_factory=list)
    years_added: list[int] = field(default_factory=list)
    years_removed: list[int] = field(default_factory=list)
    safety_before: str | None = None
    safety_after: str | None = None
    dividend_before: str | None = None
    dividend_after: str | None = None
    questions: list[QuestionChange] = field(default_factory=list)
    scores: list[ScoreChange] = field(default_factory=list)
    bands: list[BandChange] = field(default_factory=list)
    flags: list[FlagChange] = field(default_factory=list)
    restatements: list[RestatementNote] = field(default_factory=list)
    #: Frase única cuando la comparación no puede aislar la causa.
    caveat: str | None = None


#: Los ocho forenses, DERIVADOS del catálogo del motor.
#:
#: Escritos a mano tenían dos claves inventadas (`x_score`, `c_score`) y les
#: faltaban dos reales (`F7`, `FZ`), así que dos scores caían en el bloque de
#: métricas corrientes. Una lista a mano de lo que otro módulo publica caduca
#: en silencio: la única señal habría sido un agrupamiento raro en pantalla.
_SCORE_KEYS: tuple[str, ...] = tuple(d.key for d in forensic.METRIC_CATALOG)


def diff_runs(
    base: Mapping[str, Any],
    target: Mapping[str, Any],
    restatements: Sequence[Mapping[str, Any]] = (),
) -> RunDiff:
    """Compara dos payloads de análisis de la MISMA empresa.

    @param base el análisis más antiguo (el punto de partida).
    @param target el más reciente.
    @param restatements reexpresiones con `fiscal_year`, `filing_a`, `filing_b`,
        `divergences` y `detected_at`, ya filtradas por el servicio a la ventana
        entre las dos fechas.
    """
    base_date = _as_datetime(base.get("run_date"))
    target_date = _as_datetime(target.get("run_date"))

    method = _method_changes(base, target)
    comparable = not method

    diff = RunDiff(
        comparable=comparable,
        base_id=str(base.get("id", "")),
        target_id=str(target.get("id", "")),
        base_date=base_date,
        target_date=target_date,
        method_changes=method,
        restatements=[_note(row) for row in restatements],
    )

    base_years = list(base.get("years_covered") or [])
    target_years = list(target.get("years_covered") or [])
    years_added = sorted(set(target_years) - set(base_years))
    years_removed = sorted(set(base_years) - set(target_years))

    if not comparable:
        # Con el método cambiado NO se emite ni un cambio de empresa. Si además
        # cambiaron los ejercicios, se dice que las dos causas se mezclan: sin
        # esa frase, el usuario leería «cambió el motor» y descartaría un
        # ejercicio nuevo que sí explica parte del movimiento.
        caveat = (
            "Los dos análisis no se calcularon con el mismo método, así que sus "
            "colores no son comparables. No se listan cambios de la empresa."
        )
        if years_added or years_removed:
            caveat += (
                " Además cubren ejercicios distintos, así que las dos causas —el "
                "método y los datos— se mezclan y no se pueden separar."
            )
        return _replace(diff, caveat=caveat, years_added=years_added, years_removed=years_removed)

    return _replace(
        diff,
        years_added=years_added,
        years_removed=years_removed,
        safety_before=_safety(base),
        safety_after=_safety(target),
        dividend_before=_verdict(base).get("dividend_verdict"),
        dividend_after=_verdict(target).get("dividend_verdict"),
        questions=_question_changes(base, target),
        scores=_score_changes(base, target),
        bands=_band_changes(base, target),
        flags=_flag_changes(base, target),
        caveat=(
            "Los dos análisis cubren ejercicios distintos: parte de lo que se "
            "mueve es que hay un cierre nuevo, no que los números anteriores "
            "hayan cambiado."
            if (years_added or years_removed)
            else None
        ),
    )


# ── Método ────────────────────────────────────────────────────────────


def _method_changes(base: Mapping[str, Any], target: Mapping[str, Any]) -> list[str]:
    """Qué del MÉTODO difiere. Vacío = los dos runs son comparables."""
    changes: list[str] = []
    if base.get("engine_version") != target.get("engine_version"):
        changes.append(
            f"el motor pasó de {base.get('engine_version')} a {target.get('engine_version')}"
        )
    if base.get("thresholds_version") != target.get("thresholds_version"):
        changes.append(
            "la calibración de umbrales pasó de "
            f"{base.get('thresholds_version')} a {target.get('thresholds_version')}"
        )
    return changes


# ── Empresa ───────────────────────────────────────────────────────────


def _question_changes(base: Mapping[str, Any], target: Mapping[str, Any]) -> list[QuestionChange]:
    """Las cuatro preguntas: veredicto Y evidencia.

    La evidencia va aparte del veredicto a propósito: pasar de «verde auditado»
    a «verde sin evidencia» no mueve el color pero es una pérdida real de
    respaldo, y sin este eje sería invisible.
    """
    before = {q.get("key"): q for q in _verdict(base).get("questions") or []}
    after = {q.get("key"): q for q in _verdict(target).get("questions") or []}
    result: list[QuestionChange] = []
    for key in [k for k in after if k is not None]:
        old = before.get(key)
        new = after[key]
        if old is None:
            continue
        cambio = QuestionChange(
            key=str(key),
            verdict_before=old.get("verdict"),
            verdict_after=new.get("verdict"),
            evidence_before=evidence_of(old).state,
            evidence_after=evidence_of(new).state,
        )
        if (
            cambio.verdict_before != cambio.verdict_after
            or cambio.evidence_before != cambio.evidence_after
        ):
            result.append(cambio)
    return result


def _score_changes(base: Mapping[str, Any], target: Mapping[str, Any]) -> list[ScoreChange]:
    """Los ocho forenses del ejercicio del dictamen de cada run.

    Se comparan los de SU propio último ejercicio y no los del mismo año: lo que
    el usuario quiere saber es si el dictamen de hoy es peor que el de antes.
    """
    before = _latest_metrics(base)
    after = _latest_metrics(target)
    result: list[ScoreChange] = []
    for key in _SCORE_KEYS:
        old = before.get(key)
        new = after.get(key)
        if old is None and new is None:
            continue
        cambio = ScoreChange(
            key=key,
            before=_str_or_none(old, "value"),
            after=_str_or_none(new, "value"),
            band_before=_str_or_none(old, "band"),
            band_after=_str_or_none(new, "band"),
        )
        if (cambio.before, cambio.band_before) != (cambio.after, cambio.band_after):
            result.append(cambio)
    return result


def _band_changes(base: Mapping[str, Any], target: Mapping[str, Any]) -> list[BandChange]:
    """Toda métrica que haya cambiado de BANDA en el ejercicio del dictamen.

    Sólo la banda, no el valor: un ratio que se mueve del 1,41 al 1,42 no es
    noticia, y listarlo enterraría los que sí cruzaron un corte.
    """
    before = _latest_metrics(base)
    after = _latest_metrics(target)
    result: list[BandChange] = []
    for key in sorted(set(before) | set(after)):
        if key in _SCORE_KEYS:
            continue  # ya salen en su propio bloque
        old = before.get(key)
        new = after.get(key)
        band_before = _str_or_none(old, "band")
        band_after = _str_or_none(new, "band")
        if band_before == band_after:
            continue
        result.append(
            BandChange(
                key=key,
                band_before=band_before,
                band_after=band_after,
                value_before=_str_or_none(old, "value"),
                value_after=_str_or_none(new, "value"),
            )
        )
    return result


def _flag_changes(base: Mapping[str, Any], target: Mapping[str, Any]) -> list[FlagChange]:
    before = {f.get("key"): f for f in base.get("flags") or []}
    after = {f.get("key"): f for f in target.get("flags") or []}
    result: list[FlagChange] = []
    for key in sorted(set(after) - set(before), key=str):
        flag = after[key]
        result.append(
            FlagChange(
                key=str(key),
                label=flag.get("label"),
                severity=flag.get("severity"),
                appeared=True,
            )
        )
    for key in sorted(set(before) - set(after), key=str):
        flag = before[key]
        result.append(
            FlagChange(
                key=str(key),
                label=flag.get("label"),
                severity=flag.get("severity"),
                appeared=False,
            )
        )
    return result


# ── Utilidades ────────────────────────────────────────────────────────


def _verdict(run: Mapping[str, Any]) -> Mapping[str, Any]:
    verdict = run.get("verdict")
    return verdict if isinstance(verdict, Mapping) else {}


def _safety(run: Mapping[str, Any]) -> str | None:
    profile = _verdict(run).get("safety_profile")
    if isinstance(profile, Mapping):
        label = profile.get("label")
        return str(label) if label is not None else None
    return None


def _latest_metrics(run: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Las métricas del ÚLTIMO ejercicio de este run, por clave.

    Un run puede traer la misma clave repetida por ejercicio; nos quedamos con
    la del año más alto, que es el que alimenta el dictamen.
    """
    years = run.get("years_covered") or []
    latest = max(years) if years else None
    result: dict[str, Mapping[str, Any]] = {}
    for metric in _all_metrics(run):
        key = metric.get("key")
        if key is None:
            continue
        if latest is not None and metric.get("fiscal_year") != latest:
            continue
        result[str(key)] = metric
    return result


def _all_metrics(run: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Las métricas de las CUATRO capas que las publican.

    Mismo reparto que `collectRunMetrics` en `packages/ui`: no hay una lista
    plana en el payload, y olvidar un bloque no falla — deja sus métricas fuera
    de la comparación como si no hubieran cambiado nunca.
    """
    scores = run.get("scores_detail")
    bloques: list[Any] = []
    if isinstance(scores, Mapping):
        bloques.extend([scores.get("base_ratios"), scores.get("forensic")])
    bloques.extend([run.get("evolution"), run.get("dividend_analysis")])
    metrics: list[Mapping[str, Any]] = []
    for bloque in bloques:
        if not isinstance(bloque, Mapping):
            continue
        for metric in bloque.get("metrics") or []:
            if isinstance(metric, Mapping):
                metrics.append(metric)
    return metrics


def _str_or_none(metric: Mapping[str, Any] | None, field_name: str) -> str | None:
    if metric is None:
        return None
    value = metric.get(field_name)
    return None if value is None else str(value)


def _note(row: Mapping[str, Any]) -> RestatementNote:
    divergences = row.get("divergences") or []
    return RestatementNote(
        fiscal_year=int(row.get("fiscal_year", 0)),
        filing_a=str(row.get("filing_a", "")),
        filing_b=str(row.get("filing_b", "")),
        item_count=len(divergences) if isinstance(divergences, list) else 0,
    )


def _as_datetime(value: Any) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _replace(diff: RunDiff, **changes: Any) -> RunDiff:
    from dataclasses import replace

    return replace(diff, **changes)
