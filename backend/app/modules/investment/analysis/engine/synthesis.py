"""Capa 4 — síntesis (PHASE-44.5, DESIGN §5).

Lo que la UI muestra PRIMERO. No calcula ratios nuevos: agrega los de las capas
anteriores por **reglas explícitas** (no una media ponderada opaca), de modo que
cada veredicto se pueda abrir y ver exactamente qué señales lo producen.

- **Cuatro preguntas**: ¿la contabilidad es de fiar? · ¿genera caja de verdad? ·
  ¿el dividendo cabe en la caja? · ¿aguanta un golpe? Cada una → semáforo:
  rojo si cualquiera de sus señales núcleo está roja; ámbar si ≥2 ámbar; verde
  en el resto.
- **Matriz de seguridad**: perfil Conservador / Vigilar / Evitar por reglas
  booleanas sobre los scores forenses y B4.
- **`dividend_verdict`**: healthy/caution/stressed, o not_applicable si la
  empresa no reparte o es financiera.
- **Confianza** = completitud núcleo × factor de frescura. Las partidas
  imputadas a cero NO cuentan como sourced.
- **Matriz de banderas**: todas las flags de todas las capas, con severidad y
  evidencia. Nada se agrega sin poder abrirse.

Recibe los resultados YA CALCULADOS de cada capa (el servicio los encadena): así
la síntesis es pura y testeable sin recomputar el engine entero.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Literal, NamedTuple

from app.modules.investment.analysis.engine.base_ratios import BaseRatiosResult
from app.modules.investment.analysis.engine.catalog import definition_for
from app.modules.investment.analysis.engine.conventions import (
    STALENESS_FRESH_DAYS,
    STALENESS_STALE_DAYS,
)
from app.modules.investment.analysis.engine.dividend import DividendResult
from app.modules.investment.analysis.engine.evolution import EvolutionResult
from app.modules.investment.analysis.engine.flag_catalog import flag_label
from app.modules.investment.analysis.engine.forensic import ForensicResult
from app.modules.investment.analysis.engine.stress import StressResult
from app.modules.investment.analysis.engine.types import (
    Band,
    Flag,
    FlagEvaluation,
    MetricResult,
    MetricStatus,
    SecuritySnapshot,
    Severity,
    StatementSeries,
)
from app.modules.investment.enums import SectorInternal
from app.modules.investment.fundamentals.canonical import Provenance

CORE_ITEMS: tuple[str, ...] = (
    "revenue",
    "ebit",
    "net_income",
    "cfo",
    "capex",
    "dividends_paid",
    "total_assets",
    "equity",
    "current_assets",
    "current_liabilities",
)
"""Partidas núcleo para la completitud [DESIGN §5]: sin ellas no hay análisis."""

DividendVerdict = Literal["healthy", "caution", "stressed", "not_applicable"]
SafetyLabel = Literal["conservative", "watch", "avoid"]

SignalOutcome = Literal["scored", "clear", "unchecked", "informational"]
"""Qué le pasó a una señal candidata (PHASE-44.17).

`unavailable_count` metía en un solo cubo cuatro cosas distintas: no se pudo
calcular, la bandera **no saltó** —que es una buena noticia—, es informativa por
diseño, y no aplica. Medido en McDonald's, la pregunta «¿la contabilidad es de
fiar?» salía con `evaluated=3, unavailable=7`, y de esas 7 sólo 2 eran huecos
reales: la pantalla **subestimaba** la evidencia mientras el veredicto verde la
**sobreestimaba**.

- `scored` — puntuó en el semáforo.
- `clear` — se comprobó y no saltó. Es evidencia positiva, no ausencia.
- `unchecked` — no se pudo comprobar. Es ausencia de evidencia.
- `informational` — no puntúa por diseño (banderas `info`).
"""

SafetyRuleKind = Literal["avoid", "conservative"]
"""A qué lista pertenece una condición de la matriz de seguridad.

Cambia el significado de `met`: en una condición de «Evitar», cumplirse es lo
MALO; en una de «Conservador», lo bueno. La pantalla necesita saberlo para no
tener que deducirlo del orden (PHASE-44.25)."""


# ── Salida ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class QuestionSignal:
    """Una señal candidata de una pregunta, HAYA PUNTUADO O NO (PHASE-44.9).

    Hasta ahora una pregunta sólo publicaba dos tuplas de cadenas con los
    nombres de lo que salió rojo o ámbar. Eso impedía tres cosas a la vez:

    1. **Enseñar el valor** junto a la señal. El nombre no se podía cruzar con
       la métrica: por clave no viajaba, y por etiqueta ya divergían («M-Score»
       aquí vs «M-Score de Beneish» en el catálogo).
    2. **Distinguir verde de sin-evidencia.** En una financiera los 8 forenses
       salen `not_computable`, ninguna señal de contabilidad se evalúa y
       `_aggregate` cae al `else` → la pregunta pinta VERDE por ausencia de
       prueba. Con `counted` y los contadores, quien pinta puede decir «no se
       ha podido comprobar» en vez de «sano».
    3. **Listar lo que se comprobó y salió bien**, que es la mitad del porqué.
    """

    key: str
    """La clave REAL: `m_score`, `B4_dividend_funded_externally`, `stress`…"""
    label: str
    kind: Literal["metric", "flag", "derived"]
    """`derived` = señal que no es ni métrica ni bandera del catálogo: la
    tendencia del FCF y el peor escenario de stress, que la síntesis compone."""
    band: Band | None
    value: Decimal | None
    status: MetricStatus | None
    counted: bool
    """Si aportó al semáforo. `False` no es «está bien»: es «no cuenta»."""
    reason: str | None = None
    """Por qué no contó, en español. Obligatorio si `counted` es `False`."""
    outcome: SignalOutcome = "unchecked"
    """Qué le pasó, sin colapsar «limpia» con «no se pudo» (PHASE-44.17).

    El default es el PESIMISTA a propósito: si alguien construye una señal sin
    declararlo, sale «no se ha comprobado» y no «limpia». Un default optimista
    convierte cualquier olvido en un verde silencioso, que es exactamente el
    defecto que esta fase viene a quitar. La coherencia con `counted` la fuerza
    el `__post_init__`, así que el default sólo puede aplicar a señales que no
    puntúan."""

    def __post_init__(self) -> None:
        if not self.counted and not self.reason:
            raise ValueError(f"{self.key}: una señal que no puntúa DEBE explicar por qué")
        if self.counted != (self.outcome == "scored"):
            raise ValueError(
                f"{self.key}: counted={self.counted} incoherente con outcome={self.outcome!r} — "
                "una señal puntúa si y sólo si su desenlace es 'scored'"
            )


@dataclass(frozen=True)
class QuestionVerdict:
    key: str
    question: str
    verdict: Band
    red_signals: tuple[str, ...] = ()
    amber_signals: tuple[str, ...] = ()
    signals: tuple[QuestionSignal, ...] = ()
    """TODAS las señales candidatas, con su valor y su banda. `red_signals` y
    `amber_signals` se conservan porque los runs ya guardados las tienen."""
    evaluated_count: int = 0
    """Cuántas señales tenían banda conocida y por tanto puntuaron."""
    unavailable_count: int = 0
    """Cuántas se miraron y no pudieron puntuar. Si `evaluated_count` es 0 y
    esta no, el veredicto es «sin evidencia», no «sano».

    Se conserva con su significado original —todas las que no puntúan— porque
    los runs ya guardados lo tienen y renombrarlo cambiaría lo que dicen. Lo que
    hacía falta era PARTIRLO, y eso son los dos campos de abajo."""
    clear_count: int = 0
    """Comprobadas y limpias: la bandera se pudo evaluar y no saltó. Es evidencia
    POSITIVA — sin separarla, la pantalla contaba como huecos las cinco banderas
    limpias de McDonald's y decía «7 no disponibles» sobre 2 huecos reales."""
    unchecked_count: int = 0
    """No se pudieron comprobar. Éstas sí son ausencia de evidencia."""
    load_bearing: tuple[str, ...] = ()
    """Las señales PORTANTES de esta pregunta (PHASE-44.21).

    No todas las señales pesan lo mismo: el M-Score responde «¿la contabilidad es
    de fiar?» y el peso de los extraordinarios sólo matiza. Una proporción las
    trataría igual —y por eso no se usa una proporción—, así que cada pregunta
    declara de cuáles depende su veredicto."""
    audited: bool = False
    """Si TODOS los portantes se pudieron evaluar.

    El default es el pesimista: una pregunta que nadie ha auditado no se presume
    auditada. Cuando es `False`, la pantalla la pinta en gris — el cuarto estado
    de pregunta— en vez de enseñar un verde que se sostiene en el silencio."""
    unaudited_reasons: tuple[str, ...] = ()
    """Qué portante falta y por qué. Obligatorio cuando `audited` es `False`."""
    notes: tuple[str, ...] = ()
    """Avisos sobre el ALCANCE de un veredicto que sí se sostiene: en una
    financiera, un verde de contabilidad es verde con cobertura forense limitada,
    y decirlo es la diferencia entre un verde honesto y uno que promete de más."""


@dataclass(frozen=True)
class ConditionSignal:
    """Una señal implicada en una condición de la matriz, con su lectura.

    La condición se AUTO-CONTIENE: quien pinta la card no tiene que cruzarla con
    `questions[].signals` para enseñar el número que la hizo cierta o falsa. Esa
    dependencia es justo la que hoy obliga a la pantalla a emparejar por cadenas
    de texto (PHASE-44.25).
    """

    key: str
    """La clave REAL de la métrica o la bandera: `FZ`, `m_score`, `B4_…`."""
    label: str
    kind: Literal["metric", "flag"]
    band: Band | None
    value: Decimal | None
    status: MetricStatus | None = None


@dataclass(frozen=True)
class SafetyConditionResult:
    """Una condición de la matriz de seguridad, EVALUADA (PHASE-44.25).

    Las diez se evalúan y se publican siempre, también en un perfil «Evitar»:
    antes se retornaba en cuanto una de «Evitar» se cumplía, así que «qué
    tendría que cambiar para salir» ni siquiera se calculaba, y la pantalla
    rellenaba ese hueco infiriendo de `blocking_reasons` — con lo que
    fabricaba ✓ de condiciones que nadie había comprobado.

    `met=None` es el tri-estado honesto (familia PHASE-44.17): «no se pudo
    comprobar» no es «no se cumple». En una financiera los scores forenses
    salen `not_computable` y sus condiciones no se pueden afirmar ni negar.
    """

    key: str
    rule: SafetyRuleKind
    text: str
    """La afirmación, byte-igual a la que viaja en `blocking_reasons`."""
    met: bool | None
    reason: str | None = None
    """Por qué no se pudo comprobar. Obligatorio si `met` es None."""
    signals: tuple[ConditionSignal, ...] = ()
    inverse: str = ""
    """El giro contrafactual, SIN números: «el X-Score saliera del rojo».

    Se persiste con la condición en vez de leerse del catálogo al servir para
    que el run se auto-contenga: componer el contrafactual de un run viejo con
    la redacción de HOY volvería a mezclar lo que aquel análisis dijo con la
    regla vigente, que es justo lo que esta fase viene a separar."""

    def __post_init__(self) -> None:
        if self.met is None and not self.reason:
            raise ValueError(f"{self.key}: una condición no comprobable DEBE explicar por qué")


@dataclass(frozen=True)
class SafetyProfile:
    label: SafetyLabel
    blocking_reasons: tuple[str, ...] = ()
    """Qué impide un perfil mejor (para 'watch' y 'avoid'): las condiciones de
    Conservador que no se cumplen, o las de Evitar que sí."""
    conditions: tuple[SafetyConditionResult, ...] = ()
    """Las diez condiciones evaluadas (PHASE-44.25). Aditivo: los runs
    anteriores no lo tienen y la pantalla lo trata como ausente, nunca como
    vacío — no se reconstruye con la regla de HOY sobre un run de otro motor."""


@dataclass(frozen=True)
class Confidence:
    value: Decimal
    completeness_core: Decimal
    staleness_factor: Decimal
    imputed_core_count: int
    latest_fiscal_year_end: date | None
    days_stale: int | None


DividendVerdictSource = Literal["dividend", "resilience", "both"]
"""Qué pregunta decidió el veredicto del dividendo (PHASE-44.25).

Es el peor de «¿el dividendo cabe en la caja?» y «¿aguanta un golpe?», así que
el hero puede decir «el dividendo está en riesgo» con la pregunta del dividendo
en VERDE. Sin este campo, el payload no permitía saber cuál de las dos lo
decidió y el lector se quedaba con una contradicción aparente."""


@dataclass(frozen=True)
class SynthesisResult:
    questions: tuple[QuestionVerdict, ...]
    safety_profile: SafetyProfile
    dividend_verdict: DividendVerdict
    confidence: Confidence
    flags: tuple[Flag, ...]
    dividend_verdict_source: DividendVerdictSource | None = None
    """Aditivo, y por eso va al final: los runs anteriores no lo traen y la
    pantalla lo omite en vez de inventarlo."""

    def question(self, key: str) -> QuestionVerdict | None:
        for verdict in self.questions:
            if verdict.key == key:
                return verdict
        return None


# ── Señales ───────────────────────────────────────────────────────────


def _band_signal(key: str, metric: MetricResult | None) -> QuestionSignal:
    """Señal a partir de una métrica. Siempre devuelve algo: una métrica que no
    se pudo calcular es información, no ausencia."""
    label = definition_for(key)
    name = label.label if label is not None else key
    if metric is None:
        return QuestionSignal(
            key=key,
            label=name,
            kind="metric",
            band=None,
            value=None,
            status=None,
            counted=False,
            reason="no se calculó en este ejercicio",
            outcome="unchecked",
        )
    if metric.band is None:
        return QuestionSignal(
            key=key,
            label=name,
            kind="metric",
            band=None,
            value=metric.value,
            status=metric.status,
            counted=False,
            reason=(
                # El motivo de la métrica manda siempre que exista: un
                # `not_applicable` trae el suyo («el filing no publica deuda a
                # corto y se supone cero») y una métrica degradada por una regla
                # cruzada también («cobra antes de pagar»). «No tiene banda
                # absoluta que aplicar» es la frase de último recurso.
                metric.reason
                or "no tiene banda absoluta que aplicar"
            ),
            # Con número y sin banda, la métrica SÍ se calculó: no puntúa porque
            # no hay vara (o no aplica a este sector), que es distinto de no
            # haberla podido calcular. Sin esa distinción, una métrica sana sin
            # banda absoluta contaría como hueco.
            outcome="unchecked" if metric.status in MetricResult.VALUELESS else "informational",
        )
    return QuestionSignal(
        key=key,
        label=name,
        kind="metric",
        band=metric.band,
        value=metric.value,
        status=metric.status,
        counted=True,
        outcome="scored",
    )


def _flag_signal(
    key: str,
    flags: Mapping[str, Severity],
    evaluations: Mapping[str, FlagEvaluation],
) -> QuestionSignal:
    """Señal a partir de una bandera: `red`→stressed, `amber`→caution.

    Las `info` NO entran en el semáforo por diseño, y una bandera que no ha
    saltado tampoco — pero ambas se publican: «se comprobó y no se encendió» es
    justo lo que el usuario necesita para fiarse de un verde.

    **El default es pesimista** (PHASE-44.17). Sin evaluación de la regla, la
    señal sale «no se ha podido comprobar», no «limpia». Antes el default era el
    optimista y ése era el bug: una regla que abortaba por falta de un dato —C3
    sin coste de ventas no se ejecuta ni un año— producía exactamente la misma
    ausencia de bandera que una comprobada y limpia, y la frase que salía era
    «no se ha encendido». Con el pesimista, añadir una regla y olvidar publicar
    su evaluación SE VE; con el optimista, pinta verde.

    Es un default y no un error porque el gate que impide olvidarlo vive en los
    tests (`test_investment_engine_contract`): en producción, ante la duda, se
    dice que no se sabe.
    """
    severity = flags.get(key)
    name = flag_label(key)
    if severity == "red":
        band: Band = "stressed"
    elif severity == "amber":
        band = "caution"
    else:
        evaluation = evaluations.get(key)
        reason: str
        outcome: SignalOutcome
        if severity == "info":
            reason, outcome = "bandera informativa: no puntúa", "informational"
        elif evaluation is None:
            reason, outcome = (
                "no se ha podido comprobar: el motor no publicó la evaluación de esta regla",
                "unchecked",
            )
        elif evaluation.outcome == "not_computable":
            reason, outcome = f"no se ha podido comprobar: {evaluation.reason}", "unchecked"
        elif evaluation.outcome == "not_applicable":
            # No se plantea en este sector. NO es «no se pudo comprobar» —eso
            # invita a ingerir datos que no existen— ni «limpia», que sería
            # apuntarse una comprobación que nadie ha hecho.
            reason, outcome = f"no aplica en este sector: {evaluation.reason}", "informational"
        else:
            reason, outcome = "se comprobó y no se encendió", "clear"
        return QuestionSignal(
            key=key,
            label=name,
            kind="flag",
            band=None,
            value=None,
            status=None,
            counted=False,
            reason=reason,
            outcome=outcome,
        )
    return QuestionSignal(
        key=key,
        label=name,
        kind="flag",
        band=band,
        value=None,
        status=None,
        counted=True,
        outcome="scored",
    )


def _derived_signal(
    key: str,
    label: str,
    band: Band | None,
    reason: str | None,
    outcome: SignalOutcome = "unchecked",
) -> QuestionSignal:
    """Señal compuesta por la propia síntesis (tendencia del FCF, stress).

    `outcome` lo declara quien llama porque sólo él sabe cuál de los dos «sin
    banda» es: «la caja libre no decrece» es una comprobación limpia y «no hay
    serie de caja libre» es un hueco, y las dos llegaban aquí igual.
    """
    if band is None:
        return QuestionSignal(
            key=key,
            label=label,
            kind="derived",
            band=None,
            value=None,
            status=None,
            counted=False,
            reason=reason or "no se pudo evaluar",
            outcome=outcome,
        )
    return QuestionSignal(
        key=key,
        label=label,
        kind="derived",
        band=band,
        value=None,
        status=None,
        counted=True,
        outcome="scored",
    )


def _aggregate(question: str, key: str, signals: list[QuestionSignal]) -> QuestionVerdict:
    """Semáforo de una pregunta: rojo si ≥1 rojo; ámbar si ≥2 ámbar; verde
    resto (DESIGN §5).

    Ojo con el «verde el resto»: si NINGUNA señal puntúa, el resultado también
    es verde. Por eso se publican `evaluated_count` y `unavailable_count` — sin
    ellos, «sano» y «no hay evidencia» son indistinguibles desde fuera.
    """
    counted = [s for s in signals if s.counted]
    reds = tuple(s.label for s in counted if s.band == "stressed")
    ambers = tuple(s.label for s in counted if s.band == "caution")
    if reds:
        verdict: Band = "stressed"
    elif len(ambers) >= 2:
        verdict = "caution"
    else:
        verdict = "healthy"
    return QuestionVerdict(
        key=key,
        question=question,
        verdict=verdict,
        red_signals=reds,
        amber_signals=ambers,
        signals=tuple(signals),
        evaluated_count=len(counted),
        unavailable_count=len(signals) - len(counted),
        clear_count=sum(1 for s in signals if s.outcome == "clear"),
        unchecked_count=sum(1 for s in signals if s.outcome == "unchecked"),
    )


# ── Portantes: de qué señales depende cada veredicto ──────────────────

LOAD_BEARING: Mapping[str, tuple[str, ...]] = {
    "accounting": ("m_score", "accruals"),
    "cash": ("Q1", "fcf_trend"),
    "dividend": ("D2", "B4_dividend_funded_externally"),
    "resilience": ("z_score", "S2"),
}
"""Las señales de las que depende cada pregunta, en el perfil genérico.

**Por qué no una proporción.** La guarda anterior era todo-o-nada
(`evaluated_count == 0`), y McDonald's salía «verde confiado» con 3 señales de
10 aunque las dos pruebas que responden a la contabilidad —M-Score y accruals—
estuvieran muertas. Sustituirla por «al menos el 40% evaluado» habría tratado
igual una señal cualquiera que el M-Score. Lo que decide no es cuántas, es
CUÁLES."""

LOAD_BEARING_FINANCIALS: Mapping[str, tuple[str, ...]] = {
    "accounting": ("Q1", "C2_income_without_cash"),
    "cash": ("Q1",),
    "dividend": ("D1", "B4_dividend_funded_externally"),
}
"""En una financiera el forense entero está apagado, así que la contabilidad se
audita con lo que sí es medible: la conversión de beneficio en caja (Q1) y su
cruce interanual (C2). La pregunta 4 no tiene portantes porque no se audita —ver
`NOT_AUDITABLE`—, y la 3 se juzga sobre beneficio (D1), no sobre caja libre."""

LOAD_BEARING_REIT: Mapping[str, tuple[str, ...]] = {
    "accounting": ("m_score", "Q1"),
    "dividend": ("D6", "B4_dividend_funded_externally"),
}
"""En una socimi los accruals están apagados (la amortización del inmueble domina
los devengos) y el payout se juzga sobre FFO, no sobre caja libre."""

NOT_AUDITABLE: Mapping[str, Mapping[str, str]] = {
    "financials": {
        "resilience": (
            "la resiliencia de una entidad financiera es capital regulatorio "
            "—CET1, LCR, colchones— y eso no está en el canónico de un 10-K. "
            "Fingir que se audita con un Z''-Score sería calcular basura y "
            "pintarle un semáforo: hace falta el motor bancario, que es otra "
            "familia de modelos"
        )
    }
}
"""Preguntas que en un perfil NO se pueden auditar, dijeran lo que dijeran sus
señales. Es un gris permanente y honesto, no un hueco temporal."""

QUESTION_NOTES: Mapping[str, Mapping[str, str]] = {
    "financials": {
        "accounting": (
            "cobertura forense limitada: en una financiera no corren Beneish, "
            "Altman ni Piotroski, así que este veredicto se sostiene sólo en la "
            "calidad del beneficio"
        )
    }
}


def _profile_key(security: SecuritySnapshot) -> str | None:
    if security.is_financial or security.sector is SectorInternal.FINANCIALS:
        return "financials"
    if security.is_reit:
        return "reit"
    return None


def load_bearing_for(question_key: str, security: SecuritySnapshot) -> tuple[str, ...]:
    """Los portantes de una pregunta para este valor.

    Un perfil sólo redefine las preguntas que cambia; el resto hereda las
    genéricas, igual que los umbrales.
    """
    profile = _profile_key(security)
    if profile == "financials":
        return LOAD_BEARING_FINANCIALS.get(question_key, LOAD_BEARING[question_key])
    if profile == "reit":
        return LOAD_BEARING_REIT.get(question_key, LOAD_BEARING[question_key])
    return LOAD_BEARING.get(question_key, ())


def _audit(
    question: QuestionVerdict,
    security: SecuritySnapshot,
    signals: Mapping[str, QuestionSignal],
) -> QuestionVerdict:
    """Decide si el veredicto de una pregunta está auditado, y lo ajusta.

    Los portantes se buscan en TODAS las señales del run, no sólo en las de su
    pregunta: en una financiera, la contabilidad se audita con Q1, que vive en la
    pregunta de la caja. Lo que importa es si esa comprobación se hizo, no en qué
    bloque se pinta.

    Dos efectos sobre el veredicto, y ninguno lo mejora nunca:

    1. Sin todos los portantes evaluados, la pregunta NO está auditada y la
       pantalla la pinta gris. El verde se gana.
    2. Un portante en ámbar impide el verde aunque sea el único ámbar. Las
       no-portantes modulan por acumulación (dos ámbares tiñen); las portantes
       mandan por sí solas.
    """
    profile = _profile_key(security)
    permanent = NOT_AUDITABLE.get(profile or "", {}).get(question.key)
    if permanent is not None:
        return replace(question, load_bearing=(), audited=False, unaudited_reasons=(permanent,))

    keys = load_bearing_for(question.key, security)
    missing: list[str] = []
    verdict = question.verdict
    for key in keys:
        signal = signals.get(key)
        if signal is None:
            missing.append(f"{key}: el motor no publicó esta señal")
            continue
        if signal.outcome not in ("scored", "clear"):
            missing.append(f"{signal.label}: {signal.reason or 'no se pudo evaluar'}")
            continue
        if signal.band == "caution" and verdict == "healthy":
            verdict = "caution"
    note = QUESTION_NOTES.get(profile or "", {}).get(question.key)
    return replace(
        question,
        verdict=verdict,
        load_bearing=keys,
        audited=not missing,
        unaudited_reasons=tuple(missing),
        notes=(note,) if note is not None else (),
    )


# ── Cálculo ───────────────────────────────────────────────────────────


def compute(
    series: StatementSeries,
    base: BaseRatiosResult,
    evolution: EvolutionResult,
    forensic: ForensicResult,
    dividend: DividendResult,
    stress: StressResult,
) -> SynthesisResult:
    """Sintetiza los resultados de las cinco capas en el veredicto de alto nivel."""
    year = series.years[-1] if series.years else 0

    all_flags = tuple([*base.flags, *evolution.flags, *forensic.flags, *dividend.flags])
    flag_severity: dict[str, Severity] = {}
    for flag in all_flags:
        # Si un mismo key aparece con varias severidades, gana la peor.
        current = flag_severity.get(flag.key)
        if current is None or _severity_rank(flag.severity) > _severity_rank(current):
            flag_severity[flag.key] = flag.severity

    evaluations: dict[str, FlagEvaluation] = {
        evaluation.key: evaluation
        for evaluation in [*evolution.flag_evaluations, *dividend.flag_evaluations]
    }

    questions = (
        _question_accounting(base, evolution, forensic, dividend, flag_severity, evaluations, year),
        _question_cash(base, evolution, forensic, dividend, year),
        _question_dividend(dividend, flag_severity, evaluations, year),
        _question_resilience(base, forensic, stress, year, series.security),
    )
    # Los portantes se resuelven contra TODAS las señales del run: en una
    # financiera, la pregunta de la contabilidad se audita con Q1, que se pinta
    # en la de la caja.
    all_signals = {signal.key: signal for question in questions for signal in question.signals}
    audited = tuple(_audit(question, series.security, all_signals) for question in questions)

    safety = _safety_profile(forensic, flag_severity, evaluations, year)
    verdict, verdict_source = _dividend_verdict(series, audited)
    confidence = _confidence(series)

    return SynthesisResult(
        questions=audited,
        safety_profile=safety,
        dividend_verdict=verdict,
        dividend_verdict_source=verdict_source,
        confidence=confidence,
        flags=all_flags,
    )


def _severity_rank(severity: Severity) -> int:
    return {"info": 0, "amber": 1, "red": 2}[severity]


# ── Las cuatro preguntas ──────────────────────────────────────────────


ACCOUNTING_FLAG_KEYS: tuple[str, ...] = (
    "Q4_tax_anomaly",
    "Q4_tax_persistently_low",
    "C1_receivables_vs_revenue",
    "C2_income_without_cash",
    "C3_inventory_vs_cogs",
)
DIVIDEND_FLAG_KEYS: tuple[str, ...] = (
    "B1_debt_competes_with_dividend",
    "B2_interest_priority",
    "B4_dividend_funded_externally",
)
QUESTION_FLAG_KEYS: tuple[str, ...] = ACCOUNTING_FLAG_KEYS + DIVIDEND_FLAG_KEYS
"""Las ocho banderas que la síntesis usa como señal.

Se enumeran aquí —y las preguntas se construyen desde estas tuplas— para que el
gate de cobertura pueda comprobar que TODA clave usada tiene evaluación
publicada. Sin esa simetría, el default pesimista de `_flag_signal` convertiría
un olvido en un gris universal, que es cambiar un falso verde por un falso gris.
"""


def _question_accounting(
    base: BaseRatiosResult,
    evolution: EvolutionResult,
    forensic: ForensicResult,
    dividend: DividendResult,
    flags: Mapping[str, Severity],
    evaluations: Mapping[str, FlagEvaluation],
    year: int,
) -> QuestionVerdict:
    """¿La contabilidad es de fiar? ← M-Score + F7 + accruals + Q3/Q4/Q5 +
    C1/C2/C3 (restatements se añaden cuando exista su fase)."""
    signals = [
        _band_signal("m_score", forensic.get("m_score", year)),
        _band_signal("F7", forensic.get("F7", year)),
        _band_signal("accruals", forensic.get("accruals", year)),
        _band_signal("Q3", dividend.get("Q3", year)),
        _band_signal("Q5", dividend.get("Q5", year)),
        *(_flag_signal(key, flags, evaluations) for key in ACCOUNTING_FLAG_KEYS),
    ]
    return _aggregate("¿La contabilidad es de fiar?", "accounting", signals)


def _question_cash(
    base: BaseRatiosResult,
    evolution: EvolutionResult,
    forensic: ForensicResult,
    dividend: DividendResult,
    year: int,
) -> QuestionVerdict:
    """¿Genera caja de verdad? ← Q1/Q2 + F-Score + R7/R9b/R10 + E3 + tendencia FCF."""
    signals = [
        _band_signal("Q1", dividend.get("Q1", year)),
        _band_signal("Q2", dividend.get("Q2", year)),
        _band_signal("f_score", forensic.get("f_score", year)),
        _band_signal("R7", base.get("R7", year)),
        _band_signal("R9b", base.get("R9b", year)),
        _band_signal("R10", base.get("R10", year)),
        _band_signal("E3", evolution.get("E3", year)),
        _fcf_trend_signal(evolution),
    ]
    return _aggregate("¿Genera caja de verdad?", "cash", signals)


def _question_dividend(
    dividend: DividendResult,
    flags: Mapping[str, Severity],
    evaluations: Mapping[str, FlagEvaluation],
    year: int,
) -> QuestionVerdict:
    """¿El dividendo cabe en la caja? ← D2/D3/D4/D5 (o D6) + B1/B2/B3/B4."""
    signals = [
        _band_signal("D2", dividend.get("D2", year)),
        _band_signal("D3", dividend.get("D3", year)),
        _band_signal("D4", dividend.get("D4", year)),
        _band_signal("D5", dividend.get("D5", year)),
        _band_signal("D6", dividend.get("D6", year)),
        _band_signal("B3", dividend.get("B3", year)),
        *(_flag_signal(key, flags, evaluations) for key in DIVIDEND_FLAG_KEYS),
    ]
    return _aggregate("¿El dividendo cabe en la caja?", "dividend", signals)


def _question_resilience(
    base: BaseRatiosResult,
    forensic: ForensicResult,
    stress: StressResult,
    year: int,
    security: SecuritySnapshot,
) -> QuestionVerdict:
    """¿Aguanta un golpe? ← ST1-ST3 + Z'' + FZ + L4 + S2/S4/S5/S6."""
    signals = [
        _band_signal("z_score", forensic.get("z_score", year)),
        _band_signal("FZ", forensic.get("FZ", year)),
        _band_signal("L4", base.get("L4", year)),
        _band_signal("S2", base.get("S2", year)),
        _band_signal("S4", base.get("S4", year)),
        _band_signal("S5", base.get("S5", year)),
        _band_signal("S6", base.get("S6", year)),
        _stress_signal(stress, security),
    ]
    return _aggregate("¿Aguanta un golpe?", "resilience", signals)


def _fcf_trend_signal(evolution: EvolutionResult) -> QuestionSignal:
    """Tendencia de la caja libre (E1): un CAGR negativo del FCF es mala señal
    de generación de caja, más allá de la foto del último año."""
    fcf = evolution.series_for("fcf_cfo")
    if fcf is None or fcf.cagr is None:
        return _derived_signal(
            "fcf_trend",
            "Tendencia de la caja libre",
            None,
            (fcf.cagr_reason if fcf is not None else None) or "no hay serie de caja libre",
        )
    if fcf.cagr < 0:
        return _derived_signal(
            "fcf_trend", "Tendencia de la caja libre (decreciente)", "stressed", None
        )
    return _derived_signal(
        "fcf_trend", "Tendencia de la caja libre", None, "la caja libre no decrece", "clear"
    )


def _stress_signal(stress: StressResult, security: SecuritySnapshot) -> QuestionSignal:
    """Los escenarios de stress (ST1-ST3): si algún shock razonable deja de
    cubrir el dividendo, la resiliencia está comprometida.

    - Cobertura tras un shock < 1,0 → roja (deja de cubrir).
    - Cobertura tras un shock entre 1,0 y 1,15 → ámbar (queda al límite).
    - Poco margen de caída antes del breakeven (ST3 < 15%) → ámbar.

    **En una financiera no puntúa** (PHASE-44.24.M). El motor declara esta
    pregunta permanentemente NO AUDITABLE en banca —la resiliencia de una
    entidad financiera es capital regulatorio y no está en un 10-K— y sin
    embargo seguía calculando el escenario y podía pintarlo ROJO dentro de esa
    misma pregunta. El resultado era una contradicción en la propia pantalla: un
    chip gris de «no auditada» con una señal roja debajo. Sale como no
    comprobada, con el motivo, y así no puede llegar ni a la tabla de señales ni
    a lo que la pantalla proponga vigilar.
    """
    if _profile_key(security) == "financials":
        return _derived_signal(
            "stress",
            "Escenario de stress",
            None,
            NOT_AUDITABLE["financials"]["resilience"],
            "unchecked",
        )
    worst: Band | None = None
    for scenario in stress.scenarios:
        coverage = scenario.coverage_after
        if coverage is None:
            continue
        if coverage < Decimal(1):
            return _derived_signal(
                "stress", "Escenario de stress (deja de cubrir)", "stressed", None
            )
        if coverage < Decimal("1.15"):
            worst = "caution"
    if (
        stress.breakeven_fcf_drop is not None
        and stress.breakeven_fcf_drop < Decimal("0.15")
        and worst is None
    ):
        worst = "caution"
    if worst is not None:
        return _derived_signal("stress", "Escenario de stress (al límite)", worst, None)
    # Sin escenarios con cobertura calculable no se ha comprobado nada; con
    # ellos, que ninguno comprometa la cobertura ES el resultado.
    checked = any(scenario.coverage_after is not None for scenario in stress.scenarios)
    return _derived_signal(
        "stress",
        "Escenario de stress",
        None,
        stress.not_computable_reason or "ningún escenario compromete la cobertura",
        "clear" if checked else "unchecked",
    )


# ── Matriz de seguridad ───────────────────────────────────────────────


class SafetyConditionDef(NamedTuple):
    """Una condición de la matriz, DECLARADA (PHASE-44.25).

    La regla vive junto a la fórmula, como el catálogo de métricas, y viaja
    como dato — escribirla en la pantalla es el mecanismo exacto que dejó la
    checklist del veredicto con cinco condiciones cuando el motor evalúa seis,
    y casada con el motor por igualdad de cadena.

    - `text` es la afirmación tal y como se persiste en `blocking_reasons`
      cuando esta condición es la que bloquea: byte-igual a la de siempre, para
      que los runs guardados y los goldens del titular no se muevan.
    - `inverse` es el giro contrafactual, SIN números: los cortes se calibran
      por sector y un umbral escrito en prosa caduca en silencio (PHASE-44.21).
      El número lo pone la capa que pinta, desde el `thresholds_used` del run.
    - `signal_keys` son las claves REALES de las señales implicadas. Es el
      puente que faltaba: con él, la condición enlaza con su fila y con su
      ficha sin que nadie tenga que emparejar etiquetas.
    """

    key: str
    rule: SafetyRuleKind
    text: str
    inverse: str
    signal_keys: tuple[str, ...]


SAFETY_MATRIX: tuple[SafetyConditionDef, ...] = (
    SafetyConditionDef(
        key="avoid_manipulation",
        rule="avoid",
        text="M-Score y accruals ambos en rojo (manipulación probable)",
        inverse="el M-Score o los accruals salieran del rojo",
        signal_keys=("m_score", "accruals"),
    ),
    SafetyConditionDef(
        key="avoid_insolvency",
        rule="avoid",
        text="Z''-Score en rojo (riesgo de insolvencia)",
        inverse="el Z''-Score saliera del rojo",
        signal_keys=("z_score",),
    ),
    SafetyConditionDef(
        key="avoid_bankruptcy",
        rule="avoid",
        text="X-Score en rojo (riesgo de quiebra)",
        inverse="el X-Score saliera del rojo",
        signal_keys=("FZ",),
    ),
    SafetyConditionDef(
        key="avoid_dividend_funding",
        rule="avoid",
        text="dividendo financiado con deuda o emisión",
        inverse="el dividendo dejara de financiarse con deuda o emisión",
        signal_keys=("B4_dividend_funded_externally",),
    ),
    SafetyConditionDef(
        key="cons_m_score",
        rule="conservative",
        text="M-Score no está en verde",
        inverse="el M-Score se pusiera en verde",
        signal_keys=("m_score",),
    ),
    SafetyConditionDef(
        key="cons_z_score",
        rule="conservative",
        text="Z''-Score no está en verde",
        inverse="el Z''-Score se pusiera en verde",
        signal_keys=("z_score",),
    ),
    SafetyConditionDef(
        key="cons_fz",
        rule="conservative",
        text="X-Score no está en verde",
        inverse="el X-Score se pusiera en verde",
        signal_keys=("FZ",),
    ),
    SafetyConditionDef(
        key="cons_f_score",
        rule="conservative",
        text="F-Score < 7",
        inverse="el F-Score llegara a su corte",
        signal_keys=("f_score",),
    ),
    SafetyConditionDef(
        key="cons_accruals",
        rule="conservative",
        text="Accruals no están en verde",
        inverse="los accruals se pusieran en verde",
        signal_keys=("accruals",),
    ),
    SafetyConditionDef(
        key="cons_b4_checked",
        rule="conservative",
        text="no se ha podido comprobar si el dividendo se financia con deuda o emisión",
        inverse="se pudiera comprobar si el dividendo se financia con deuda o emisión",
        signal_keys=("B4_dividend_funded_externally",),
    ),
)
"""Las diez condiciones del sello, en el ORDEN en que se evalúan.

El orden importa: `blocking_reasons` se deriva recorriéndolas, y su contenido
tiene que salir byte-igual al del motor 1.7.0 para no mover los goldens del
titular ni el significado de los runs guardados.

Las de `conservative` están redactadas en NEGATIVO —«M-Score no está en
verde»— porque eso es lo que se persiste cuando bloquean el sello. La condición
se cumple (`met=True`) cuando el negativo es cierto, es decir cuando FALTA algo
para «Conservador»: en esa lista, `met=True` es la mala noticia igual que en la
de «Evitar». Un solo significado de `met` para las diez.
"""


def _safety_profile(
    forensic: ForensicResult,
    flags: Mapping[str, Severity],
    evaluations: Mapping[str, FlagEvaluation],
    year: int,
) -> SafetyProfile:
    """Conservador / Vigilar / Evitar por reglas explícitas (DESIGN §5).

    El sello es lo primero que se lee del informe, así que sus condiciones no
    pueden darse por cumplidas sin comprobarlas. B4 —«el dividendo se financia
    con deuda o emisión»— es una de las cuatro que fuerzan «Evitar», y se leía
    del mapa optimista de banderas: si no se pudo evaluar, la ausencia de
    bandera se traducía en «no está en rojo» y el sello subía sin haberlo
    comprobado (PHASE-44.17).

    Desde PHASE-44.25 las DIEZ condiciones se evalúan siempre y se publican en
    `conditions`. Antes se retornaba en cuanto una de «Evitar» se cumplía, así
    que las de «Conservador» no llegaban a calcularse y no había forma de decir
    qué haría falta para salir del sello — la pantalla lo rellenaba infiriendo
    de `blocking_reasons` y acababa afirmando que se cumplían condiciones que
    nadie había comprobado.

    `label` y `blocking_reasons` se DERIVAN de las condiciones y salen
    byte-iguales a los del motor 1.7.0: es lo que permite que los runs
    guardados y los goldens del titular no se muevan.
    """
    m = forensic.get("m_score", year)
    z = forensic.get("z_score", year)
    fz = forensic.get("FZ", year)
    f_score = forensic.get("f_score", year)
    accruals = forensic.get("accruals", year)
    b4_red = flags.get("B4_dividend_funded_externally") == "red"
    b4 = evaluations.get("B4_dividend_funded_externally")
    b4_unchecked = b4 is None or b4.outcome == "not_computable"

    metrics: dict[str, MetricResult | None] = {
        "m_score": m,
        "z_score": z,
        "FZ": fz,
        "f_score": f_score,
        "accruals": accruals,
    }

    def _cond_signals(definition: SafetyConditionDef) -> tuple[ConditionSignal, ...]:
        """Las señales implicadas, con su lectura, para que la card no tenga que
        cruzarse con `questions[].signals` para enseñar el número."""
        out: list[ConditionSignal] = []
        for key in definition.signal_keys:
            if key in metrics:
                metric = metrics[key]
                catalogued = definition_for(key)
                out.append(
                    ConditionSignal(
                        key=key,
                        label=catalogued.label if catalogued is not None else key,
                        kind="metric",
                        band=_band(metric),
                        value=metric.value if metric is not None else None,
                        status=metric.status if metric is not None else None,
                    )
                )
            else:
                out.append(
                    ConditionSignal(
                        key=key,
                        label=flag_label(key),
                        kind="flag",
                        band=None,
                        value=None,
                        status=None,
                    )
                )
        return tuple(out)

    def _holds(metric: MetricResult | None, band: Band) -> tuple[bool | None, str | None]:
        """¿La métrica está en esa banda? `None` = no se pudo comprobar.

        Antes una banda ausente colapsaba en «no se cumple», que en la lista de
        «Evitar» se lee como una comprobación superada (familia PHASE-44.17).
        """
        actual = _band(metric)
        if actual is None:
            return None, (
                metric.reason
                if metric is not None and metric.reason
                else "no se calculó en este ejercicio"
            )
        return actual == band, None

    # `met` significa lo MISMO en las diez: «la afirmación de `text` es cierta».
    # En «Evitar» eso dispara el sello; en «Conservador» —redactadas en negativo,
    # que es como se persisten— eso es lo que FALTA para el sello.
    # Cada entrada es (met, motivo si no se pudo, texto efectivo si difiere).
    evaluated: dict[str, tuple[bool | None, str | None, str | None]] = {}

    m_red, m_red_why = _holds(m, "stressed")
    acc_red, acc_red_why = _holds(accruals, "stressed")
    if m_red is False or acc_red is False:
        # Basta que UNA esté fuera del rojo para que la conjunción sea falsa,
        # aunque la otra no se haya podido calcular.
        evaluated["avoid_manipulation"] = (False, None, None)
    elif m_red is None or acc_red is None:
        evaluated["avoid_manipulation"] = (None, m_red_why or acc_red_why, None)
    else:
        evaluated["avoid_manipulation"] = (m_red and acc_red, None, None)

    z_red, z_red_why = _holds(z, "stressed")
    evaluated["avoid_insolvency"] = (z_red, z_red_why, None)
    fz_red, fz_red_why = _holds(fz, "stressed")
    evaluated["avoid_bankruptcy"] = (fz_red, fz_red_why, None)
    # La bandera es evidencia binaria: o saltó o no. `b4_unchecked` gobierna la
    # sexta condición de Conservador, que es donde esa incertidumbre pesa.
    evaluated["avoid_dividend_funding"] = (b4_red, None, None)

    m_green, m_green_why = _holds(m, "healthy")
    evaluated["cons_m_score"] = (None if m_green is None else not m_green, m_green_why, None)
    z_green, z_green_why = _holds(z, "healthy")
    evaluated["cons_z_score"] = (None if z_green is None else not z_green, z_green_why, None)
    fz_green, fz_green_why = _holds(fz, "healthy")
    evaluated["cons_fz"] = (None if fz_green is None else not fz_green, fz_green_why, None)
    evaluated["cons_f_score"] = (
        not (f_score is not None and f_score.value is not None and f_score.value >= 7),
        None,
        None,
    )
    acc_green, acc_green_why = _holds(accruals, "healthy")
    evaluated["cons_accruals"] = (None if acc_green is None else not acc_green, acc_green_why, None)
    # El texto EFECTIVO de ésta lleva el motivo entre paréntesis: es lo que se
    # persiste desde PHASE-44.17 y lo que leen los runs ya guardados.
    evaluated["cons_b4_checked"] = (
        b4_unchecked,
        None,
        "no se ha podido comprobar si el dividendo se financia con deuda o emisión "
        f"({b4.reason if b4 is not None and b4.reason else 'sin evaluación de la regla'})",
    )

    conditions = tuple(
        SafetyConditionResult(
            key=definition.key,
            rule=definition.rule,
            text=evaluated[definition.key][2] or definition.text,
            met=evaluated[definition.key][0],
            reason=evaluated[definition.key][1],
            signals=_cond_signals(definition),
            inverse=definition.inverse,
        )
        for definition in SAFETY_MATRIX
    )

    avoid_reasons = tuple(c.text for c in conditions if c.rule == "avoid" and c.met is True)
    if avoid_reasons:
        return SafetyProfile(label="avoid", blocking_reasons=avoid_reasons, conditions=conditions)

    # Una condición de Conservador que no se pudo comprobar tampoco se da por
    # cumplida: el verde se gana. `met is not False` incluye ese `None`.
    unmet = tuple(c.text for c in conditions if c.rule == "conservative" and c.met is not False)
    if not unmet:
        return SafetyProfile(label="conservative", conditions=conditions)
    return SafetyProfile(label="watch", blocking_reasons=unmet, conditions=conditions)


def _band(metric: MetricResult | None) -> Band | None:
    return metric.band if metric is not None else None


# ── Veredicto de dividendo ────────────────────────────────────────────


def _dividend_verdict(
    series: StatementSeries, questions: tuple[QuestionVerdict, ...]
) -> tuple[DividendVerdict, DividendVerdictSource | None]:
    """not_applicable si la empresa es financiera o no reparte; si no, el peor de
    las preguntas 3 (cabe en la caja) y 4 (aguanta un golpe).

    Devuelve también CUÁL de las dos lo decidió (PHASE-44.25): el veredicto
    puede venir entero de la resistencia con la pregunta del dividendo en
    verde, y sin decirlo el hero contradice a la pantalla de abajo.
    """
    if series.security.is_financial:
        return "not_applicable", None
    latest = series.latest
    dividends = latest.dividends_paid if latest is not None else None
    if dividends is None or dividends == 0:
        return "not_applicable", None

    by_key = {q.key: q.verdict for q in questions}
    dividend = by_key.get("dividend")
    resilience = by_key.get("resilience")

    def _source(band: Band) -> DividendVerdictSource:
        if dividend == band and resilience == band:
            return "both"
        return "dividend" if dividend == band else "resilience"

    if "stressed" in (dividend, resilience):
        return "stressed", _source("stressed")
    if "caution" in (dividend, resilience):
        return "caution", _source("caution")
    return "healthy", "both"


# ── Confianza ─────────────────────────────────────────────────────────


def _confidence(series: StatementSeries) -> Confidence:
    """`completeness_core × staleness_factor` [DESIGN §5, Dec.16].

    Completitud: fracción de las 10 partidas núcleo con status SOURCED en cada
    año de la serie. Un `imputed_zero` NO cuenta como sourced (se lista aparte).
    Frescura: 1,0 si el último cierre <9 meses de la fecha de análisis; 0,7 si
    9-18m; 0,4 si >18m.
    """
    statements = series.statements
    total = len(CORE_ITEMS) * len(statements) if statements else 0
    sourced = 0
    imputed = 0
    for statement in statements:
        for item in CORE_ITEMS:
            value = statement.get(item)
            provenance = statement.provenance_of(item)
            if value is not None and provenance is Provenance.SOURCED:
                sourced += 1
            elif provenance is Provenance.IMPUTED_ZERO:
                imputed += 1
    completeness = Decimal(sourced) / Decimal(total) if total else Decimal(0)

    latest = series.latest
    days_stale: int | None = None
    fye: date | None = None
    staleness = Decimal("0.4")
    if latest is not None:
        fye = latest.fiscal_year_end
        days_stale = (series.as_of - fye).days
        if days_stale < STALENESS_FRESH_DAYS:
            staleness = Decimal("1.0")
        elif days_stale < STALENESS_STALE_DAYS:
            staleness = Decimal("0.7")
        else:
            staleness = Decimal("0.4")

    return Confidence(
        value=completeness * staleness,
        completeness_core=completeness,
        staleness_factor=staleness,
        imputed_core_count=imputed,
        latest_fiscal_year_end=fye,
        days_stale=days_stale,
    )
