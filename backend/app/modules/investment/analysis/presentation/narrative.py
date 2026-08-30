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
from decimal import Decimal
from typing import Any

from app.modules.investment.analysis.presentation.evidence import (
    Evidence,
    evidence_of,
    legacy_labels,
    scored_labels,
)

NARRATIVE_VERSION = "1.2.0"
"""Versión de los TEXTOS, independiente de la del motor.

Sube cuando cambia una plantilla. Es distinta de `ENGINE_VERSION` a propósito:
una frase no forma parte de la reproducibilidad de un análisis —los números son
los mismos— así que reescribir una no puede obligar a reejecutar nada ni marcar
como caducado un run que sigue siendo válido.

Historial:
- 1.0.0 — PHASE-44.24.B: las cuatro preguntas, el titular y «qué miraría a
  continuación».
- 1.1.0 — PHASE-44.25: el veredicto argumenta.

  1. **El contrafactual** (`PROFILE_WHY_TEMPLATES`): qué tendría que cambiar
     para salir del sello. Se compone de los giros que el motor persiste con
     cada condición, y NUNCA nombra una que no se pudo comprobar: afirmar que
     algo bastaría cuando no se ha podido mirar es la misma promesa vacía que
     PHASE-44.17 quitó de las banderas.
  2. **La discrepancia entre los dos modelos de insolvencia** se enuncia cuando
     se da. La explicación de fondo sigue viviendo en la ficha del score, junto
     a la fórmula; esta frase la SEÑALA y apunta a ella.
  3. **La evidencia se cuenta por bandas** (`with_bands`). «Se evaluaron 8
     señales, 0 se comprobaron y salieron limpias» es cierto y se lee como «las
     8 salieron mal»: `clear_count` sólo cuenta banderas y la pregunta de la
     resistencia no tiene ninguna, así que sus ceros son estructurales. Lo que
     explica el color es 6 en verde y 2 en rojo, y eso ya viajaba por señal sin
     que ninguna frase lo agregara.
  4. **El titular deja de tragarse motivos** (`avoid_more` / `watch_more`):
     cortaba en los dos primeros sin decir que había más.
  5. El titular de «Conservador» deja de decir «las cinco condiciones»: el
     motor comprueba seis. Un recuento en prosa caduca en silencio.
- 1.2.0 — PHASE-44.26: el sumario del Dictamen se compone en el servidor.

  La primera entrega del rediseño (prosa primero, auditoría plegada) enseñaba
  «qué preocupa» y «qué está bien» como listas de DATOS seleccionadas en el
  cliente. La prueba manual del usuario pidió más: «un informe en texto
  desarrollado… en el formato actual lo tienes pero dividido y sin apenas
  explicar». Eso es prosa, y la prosa del veredicto se compone aquí.

  Con ella, la SELECCIÓN de las dos listas también se muda al servidor
  (`build_report`): tenerla en el cliente y las frases aquí habría sido dos
  fuentes para la misma decisión — qué entra y en qué orden ES parte de lo que
  la frase afirma. El selector del cliente queda como fallback para backends
  anteriores, documentado como tal.

  Tres plantillas nuevas (`SUMMARY_TEMPLATES`): la entrada de «lo que pesa en
  contra» y la de «lo que sale limpio» —que NOMBRAN señales, sin números: los
  números van en las filas de datos, formateados por unidad en la capa
  compartida— y el margen de caída de la caja libre, cuyo número entra por
  placeholder como en las frases de stress del propio motor.
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
    # Lo que de verdad explica el color de la pregunta (PHASE-44.25).
    # Sin cardinal delante: «Puntuaron 1 señales» no concuerda, y el gate de
    # plantillas prohíbe escribir el número a mano para arreglarlo. El desglose
    # ya lleva sus cifras.
    "with_bands": "Señales que puntúan: {desglose}",
    "with_bands_and_rest": "Señales que puntúan: {desglose}; además, {resto}",
    # Ninguna puntuó: no hay desglose que dar, y el recuento sí.
    "none_scored": "Ninguna de las {candidatas} señales pudo puntuar",
}

BAND_COUNT_TEMPLATES: Mapping[str, str] = {
    "healthy": "{n} en verde",
    "caution": "{n} en ámbar",
    "stressed": "{n} en rojo",
}
"""Los trozos del desglose. Se omiten los que valen cero: «0 en ámbar» ocupa el
mismo sitio que una noticia y no la es."""

REST_TEMPLATES: Mapping[str, str] = {
    "clear": "{n} se comprobaron y salieron limpias",
    "unchecked": "{n} no se pudieron comprobar",
}

RESCUE_TEMPLATES: Mapping[str, str] = {
    "with_labels": "Lo que sí quedó registrado: {etiquetas}.",
    # Si no hay nada registrado se dice, en vez de dejar la frase colgando.
    "empty": "No registró ninguna señal en rojo ni en ámbar.",
}

HEADLINE_TEMPLATES: Mapping[str, str] = {
    # Sin recuento: el motor comprueba seis condiciones y la frase decía cinco.
    # Un cardinal en prosa caduca en cuanto la matriz gana una condición.
    "conservative": "Perfil conservador: todas las condiciones del motor se cumplen. {dividendo}",
    "watch": "Perfil a vigilar: {bloqueo}. {dividendo}",
    "avoid": "Perfil a evitar: {bloqueo}. {dividendo}",
    # Con más de dos motivos el titular citaba dos y se comía el resto en
    # silencio (PHASE-44.25).
    "watch_more": "Perfil a vigilar: {bloqueo}, y {mas} condiciones más. {dividendo}",
    "avoid_more": "Perfil a evitar: {bloqueo}, y {mas} condiciones más. {dividendo}",
}

SUMMARY_TEMPLATES: Mapping[str, str] = {
    # Nombran señales; los NÚMEROS no van aquí: viajan en las filas de datos y
    # los formatea la capa compartida por unidad, igual en las tres superficies.
    "concerns_intro": "Lo que más pesa en contra: {nombres}.",
    "strengths_intro": "Del lado bueno, con la comprobación superada: {nombres}.",
    # El margen entra por placeholder, como los números de las frases de
    # stress que el motor persiste.
    "stress_margin": (
        "La caja libre podría caer un {margen} antes de dejar de cubrir el dividendo."
    ),
}

PROFILE_WHY_TEMPLATES: Mapping[str, str] = {
    # El contrafactual. Redactado por inversión de la regla —«dejaría de»— y
    # nunca como consejo: el informe comprueba reglas, no recomienda comprar.
    "avoid_exit": (
        "Dejaría de ser «Evitar» si {cambios}. Pasaría a «Vigilar»; para «Conservador» "
        "tendrían que cumplirse además todas sus condiciones"
    ),
    # Lo que no se pudo comprobar NO entra en el contrafactual: decir que algo
    # bastaría sin haberlo mirado es una promesa vacía (familia PHASE-44.17).
    "avoid_exit_unknown": "Y quedaría por comprobar: {pendientes}",
    "watch_exit": "Sería «Conservador» si {cambios}",
    "watch_exit_unknown": "Y quedaría por comprobar: {pendientes}",
    "conservative_fall": "Perdería el sello si {condiciones}",
    "models_disagree": (
        "Los dos modelos de insolvencia no coinciden: {rojo} está en rojo y {sano} en "
        "verde. La discrepancia es en sí el hallazgo — cada score explica qué mide en "
        "su ficha, y su desglose está en la pestaña Forense"
    ),
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
        "band_count": dict(sorted(BAND_COUNT_TEMPLATES.items())),
        "rest": dict(sorted(REST_TEMPLATES.items())),
        "profile_why": dict(sorted(PROFILE_WHY_TEMPLATES.items())),
        "summary": dict(sorted(SUMMARY_TEMPLATES.items())),
    }
    blob = json.dumps(payload, separators=(",", ":"), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ── Composición ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class NextCheck:
    """Un bullet de «qué miraría a continuación»."""

    key: str
    text: str
    signal_key: str | None = None
    """La clave REAL de la señal, para que el bullet pueda enlazar con su fila.

    `key` es `pregunta:ETIQUETA` y una etiqueta no sirve para localizar nada:
    ya divergieron una vez («M-Score» vs «M-Score de Beneish»). Es `None` en los
    bullets que no hablan de una señal concreta («nada que vigilar»)."""


def _join(labels: Sequence[str]) -> str:
    """`a`, `a y b`, `a, b y c` — como se dice en voz alta."""
    items = [label for label in labels if label]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} y {items[-1]}"


def _evidence_sentence(question: Mapping[str, Any], evidence: Evidence) -> str:
    """Qué se comprobó, en la forma que EXPLICA el color de la pregunta.

    La versión anterior citaba «{limpias} se comprobaron y salieron limpias y
    {sin_comprobar} no se pudieron comprobar», y esos dos contadores sólo miran
    banderas: en «¿aguanta un golpe?», que no tiene ninguna, valen cero por
    construcción. La frase salía «Se evaluaron 8 señales, 0 se comprobaron y
    salieron limpias», que se lee como «las 8 salieron mal» cuando 6 estaban en
    verde (PHASE-44.25).

    El desglose por bandas es lo que sostiene el semáforo, y ya viajaba por
    señal sin que ninguna frase lo agregara.
    """
    evaluated = int(question.get("evaluated_count") or 0)
    clear = int(question.get("clear_count") or 0)
    unchecked = int(question.get("unchecked_count") or 0)
    signals = [s for s in (question.get("signals") or []) if isinstance(s, Mapping)]

    # Un run sin señales estructuradas (motor 1.0.0) no permite desglosar: se
    # dice lo que aquel motor sí registró, ni más ni menos.
    if not evidence.outcomes_recorded or not signals:
        if evidence.outcomes_recorded:
            return EVIDENCE_TEMPLATES["with_outcomes"].format(
                evaluadas=evaluated, limpias=clear, sin_comprobar=unchecked
            )
        return EVIDENCE_TEMPLATES["without_outcomes"].format(
            evaluadas=evaluated, sin_puntuar=int(question.get("unavailable_count") or 0)
        )

    counts: dict[str, int] = {"stressed": 0, "caution": 0, "healthy": 0}
    for signal in signals:
        if not signal.get("counted"):
            continue
        band = str(signal.get("band") or "")
        if band in counts:
            counts[band] += 1
    scored = sum(counts.values())

    if not scored:
        return EVIDENCE_TEMPLATES["none_scored"].format(candidatas=len(signals))

    # Las peores primero, y los ceros fuera: «0 en ámbar» ocupa el sitio de una
    # noticia sin serlo.
    breakdown = _join(
        [
            BAND_COUNT_TEMPLATES[band].format(n=counts[band])
            for band in ("stressed", "caution", "healthy")
            if counts[band]
        ]
    )
    rest = _join(
        [
            REST_TEMPLATES[key].format(n=n)
            for key, n in (("clear", clear), ("unchecked", unchecked))
            if n
        ]
    )
    if rest:
        return EVIDENCE_TEMPLATES["with_bands_and_rest"].format(desglose=breakdown, resto=rest)
    return EVIDENCE_TEMPLATES["with_bands"].format(desglose=breakdown)


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


#: Cuántos motivos caben en el titular antes de resumir el resto.
_HEADLINE_REASONS = 2


def headline(
    *, safety_label: str, blocking_reasons: Sequence[str], dividend_verdict: str | None
) -> str:
    """El titular: perfil de seguridad y dividendo, en una frase.

    Cita los dos primeros motivos y DICE cuántos más hay. Antes cortaba en dos
    sin avisar, así que con tres condiciones cumplidas la tercera desaparecía
    del titular y sólo sobrevivía en la card (PHASE-44.25).
    """
    dividend = DIVIDEND_TEMPLATES.get(
        str(dividend_verdict or "not_applicable"), DIVIDEND_TEMPLATES["not_applicable"]
    )
    if safety_label == "conservative":
        return HEADLINE_TEMPLATES["conservative"].format(dividendo=dividend)

    reasons = [str(r) for r in blocking_reasons]
    base = safety_label if safety_label in ("avoid", "watch") else "watch"
    extra = len(reasons) - _HEADLINE_REASONS
    if extra > 0:
        return HEADLINE_TEMPLATES[f"{base}_more"].format(
            bloqueo=_join(reasons[:_HEADLINE_REASONS]),
            mas=extra,
            dividendo=dividend,
        )
    return HEADLINE_TEMPLATES[base].format(
        bloqueo=_join(reasons) or "no se ha registrado el motivo",
        dividendo=dividend,
    )


def _conditions_of(conditions: Sequence[Mapping[str, Any]], rule: str) -> list[Mapping[str, Any]]:
    return [c for c in conditions if isinstance(c, Mapping) and c.get("rule") == rule]


def exit_sentence(*, safety_label: str, conditions: Sequence[Mapping[str, Any]]) -> str:
    """Qué tendría que cambiar para salir del sello (PHASE-44.25).

    Se compone de los giros que el motor persistió con cada condición, así que
    un run viejo —que no los trae— no recibe frase en vez de una compuesta con
    la regla de hoy.

    Una condición que NO se pudo comprobar nunca entra en «bastaría con»: se
    dice aparte, porque prometer que algo bastaría sin haberlo mirado es la
    misma promesa vacía que PHASE-44.17 quitó de las banderas.
    """
    if not conditions:
        return ""

    if safety_label == "conservative":
        return PROFILE_WHY_TEMPLATES["conservative_fall"].format(
            condiciones="se cumpliera cualquiera de las condiciones de «Evitar» o dejara "
            "de cumplirse alguna de las suyas"
        )

    rule = "avoid" if safety_label == "avoid" else "conservative"
    relevant = _conditions_of(conditions, rule)
    changes = [str(c.get("inverse") or "") for c in relevant if c.get("met") is True]
    pending = [str(c.get("text") or "") for c in relevant if c.get("met") is None]

    changes = [c for c in changes if c]
    if not changes and not pending:
        return ""

    parts: list[str] = []
    if changes:
        key = "avoid_exit" if safety_label == "avoid" else "watch_exit"
        parts.append(PROFILE_WHY_TEMPLATES[key].format(cambios=_join(changes)))
    if pending:
        key = "avoid_exit_unknown" if safety_label == "avoid" else "watch_exit_unknown"
        parts.append(PROFILE_WHY_TEMPLATES[key].format(pendientes=_join(pending)))
    return ". ".join(parts) + "."


def concerns_intro(labels: Sequence[str]) -> str:
    """La entrada de «qué preocupa», nombrando las señales que se listan."""
    if not labels:
        return ""
    return SUMMARY_TEMPLATES["concerns_intro"].format(nombres=_join(list(labels)))


def strengths_intro(labels: Sequence[str]) -> str:
    """La entrada de «qué está bien». Sólo nombra lo que la lista enseña."""
    if not labels:
        return ""
    return SUMMARY_TEMPLATES["strengths_intro"].format(nombres=_join(list(labels)))


def stress_margin_sentence(breakeven: Any) -> str | None:
    """El margen de caída de la caja libre, en una frase.

    Vivía sólo como número en la card de stress de web, compuesto en JSX — la
    única pieza del sumario que el servidor no decía. `None` sin dato: no se
    inventa un margen.
    """
    if breakeven is None:
        return None
    try:
        valor = Decimal(str(breakeven))
    except (ArithmeticError, ValueError):
        return None
    if valor < 0:
        return None
    pct = (valor * 100).quantize(Decimal("1"))
    return SUMMARY_TEMPLATES["stress_margin"].format(margen=f"{pct} %".replace(".", ","))


#: Los dos modelos de insolvencia, por la condición que los evalúa.
_INSOLVENCY_PAIR = ("avoid_insolvency", "avoid_bankruptcy")


def models_disagree(conditions: Sequence[Mapping[str, Any]]) -> str | None:
    """Los dos modelos de quiebra en extremos opuestos, dicho en voz alta.

    Ver un X-Score en rojo justo encima de un Z''-Score en verde, sin una línea
    que lo explique, es la contradicción que hace que el veredicto no se
    entienda. La explicación de fondo vive en la ficha de cada score, junto a la
    fórmula; esta frase señala el hecho de ESTE run y apunta allí.
    """
    by_key = {str(c.get("key") or ""): c for c in conditions if isinstance(c, Mapping)}
    lecturas: dict[str, tuple[str, str]] = {}
    for key in _INSOLVENCY_PAIR:
        condition = by_key.get(key)
        if condition is None:
            return None
        signals = [s for s in (condition.get("signals") or []) if isinstance(s, Mapping)]
        if not signals:
            return None
        band = str(signals[0].get("band") or "")
        label = str(signals[0].get("label") or signals[0].get("key") or "")
        if not band or not label:
            return None
        lecturas[key] = (band, label)

    bandas = {key: value[0] for key, value in lecturas.items()}
    if set(bandas.values()) != {"stressed", "healthy"}:
        return None
    rojo = next(label for band, label in lecturas.values() if band == "stressed")
    sano = next(label for band, label in lecturas.values() if band == "healthy")
    return PROFILE_WHY_TEMPLATES["models_disagree"].format(rojo=rojo, sano=sano) + "."


def next_checks(
    questions: Sequence[Mapping[str, Any]],
    *,
    sentences: Mapping[str, Sequence[tuple[str, str, str]]],
    limit: int = 3,
) -> list[NextCheck]:
    """Qué miraría a continuación: hasta tres señales, las peores primero.

    `sentences` son, por pregunta, las ternas (clave, etiqueta, distancia) de
    sus señales ámbar y rojas YA ordenadas por severidad. La clave viaja para
    que el bullet enlace con la fila que lo produce.

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
        for signal_key, label, distance in sentences.get(key, ()):
            collected.append(
                NextCheck(
                    key=f"{key}:{label}",
                    text=template.format(etiqueta=label, distancia=distance),
                    signal_key=signal_key or None,
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
