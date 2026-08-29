"""A qué distancia está una señal de su corte (PHASE-44.24.C).

El semáforo es binario: verde, ámbar o rojo. Pero «rojo por un pelo» y «rojo por
el triple» piden cosas distintas, y hasta ahora la pantalla no las distinguía.

**Lo que NO se calcula aquí es el texto.** Esta capa devuelve el corte, la
distancia absoluta y la relativa; cómo se dice —«a 3 pp del verde» para un
margen, «2,1× dentro del rojo» para una cobertura— lo compone `packages/ui`, que
ya sabe formatear por unidad y lo hace igual en las dos apps.

Las cuatro formas del catálogo que obligan a que esto sea más que una resta
—todas reales, ninguna hipotética— están documentadas en `distance_to_cut`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.modules.investment.analysis.engine.types import Band, MetricResult, ThresholdSpec
from app.modules.investment.enums import ThresholdDirection

Side = Literal["inside", "outside"]
NextBand = Literal["caution", "stressed"]


@dataclass(frozen=True)
class SignalDistance:
    """La distancia de un valor al corte que decide su banda."""

    cut: Decimal | None
    """El corte relevante. `None` cuando no hay ninguno hacia donde medir, y
    entonces `missing_reason` dice por qué."""
    absolute: Decimal | None
    """`|valor − corte|`, en la unidad de la métrica."""
    relative: Decimal | None
    """`absoluta / |corte|`. `None` con corte cero —no se divide por él— y en las
    métricas de puntuación, donde no significa nada: los cortes del X-Score están
    en −1,04 y −0,25, así que la misma distancia da relativas de 0,2 y 0,8 sin
    que ninguna informe. Ahí la pantalla enseña sólo la absoluta."""
    side: Side
    """`inside` = dentro de la banda que le toca; `outside` = ya la ha cruzado."""
    next_band: NextBand
    """Qué banda cruzaría si siguiera moviéndose en la dirección mala. Con
    cortes iguales NUNCA es `caution`: esa región es vacía."""
    missing_reason: str | None = None
    """Por qué no hay corte hacia donde medir. Un número inventado aquí sería
    peor que el hueco."""


_NO_SCALE_UNITS = frozenset({"score"})
"""Unidades en las que la distancia relativa no significa nada.

Una puntuación de un modelo publicado sólo tiene sentido contra sus propios
cortes, que pueden ser negativos y estar muy juntos; dividir por ellos produce
un número con la forma de un dato y sin su contenido.
"""


def distance_to_cut(
    metric: MetricResult | None,
    spec: ThresholdSpec | None,
    *,
    unit: str | None = None,
) -> SignalDistance | None:
    """La distancia de una métrica al corte que decide su banda.

    Devuelve `None` —no hay distancia que medir— cuando:

    - no hay métrica, no hay valor, o el estado no trae número (`not_computable`,
      `not_applicable`): una señal de bandera o derivada nunca tiene valor;
    - no hay spec, o la vara no aplica a este (sector × norma): medir contra un
      corte que el motor descartó a propósito sería inventar una comparación.

    Las cuatro formas reales del catálogo que esto tiene que soportar:

    1. **Banda de un solo lado.** S7 (endeudamiento) es `BAND` con `low_ok`,
       `high_ok` y `high_alarm`, y **sin `low_alarm`**: por debajo de la banda
       sale ámbar y no puede salir rojo nunca. Ahí no hay corte siguiente, y se
       dice en vez de fabricar uno.
    2. **Cortes iguales.** Q5 y T3 tienen `high_ok == high_alarm`, así que la
       región ámbar es vacía: la banda que se cruza es la roja, y una etiqueta
       que dijera «a X del ámbar» nombraría algo que no existe.
    3. **Cortes negativos.** El M-Score corta en −2,22 y el X-Score en −1,04.
       La relativa se calcula sobre `|corte|`: con el signo, un M-Score muy
       dentro del rojo daría una relativa negativa y el orden por severidad lo
       colocaría como el MENOS grave de los rojos.
    4. **Corte cero.** T2 tiene `low_alarm == low_ok == 0`. No se divide.
    """
    if metric is None or metric.value is None or spec is None or not spec.applies:
        return None
    value = metric.value

    if spec.direction is ThresholdDirection.HIGHER_BETTER:
        cut, next_band, side = _higher_better(value, spec, metric.band)
    elif spec.direction is ThresholdDirection.LOWER_BETTER:
        cut, next_band, side = _lower_better(value, spec, metric.band)
    else:
        cut, next_band, side = _central(value, spec, metric.band)

    if cut is None:
        return SignalDistance(
            cut=None,
            absolute=None,
            relative=None,
            side=side,
            next_band=next_band,
            missing_reason=(
                "no hay corte de alarma por este lado de la banda: la métrica no "
                "puede empeorar más en esta dirección"
            ),
        )

    absolute = abs(value - cut)
    relative: Decimal | None = None
    if cut != 0 and (unit or "") not in _NO_SCALE_UNITS:
        relative = absolute / abs(cut)
    return SignalDistance(
        cut=cut, absolute=absolute, relative=relative, side=side, next_band=next_band
    )


def _higher_better(
    value: Decimal, spec: ThresholdSpec, band: Band | None
) -> tuple[Decimal | None, NextBand, Side]:
    """Más es mejor: se cae hacia abajo, primero al ámbar y luego al rojo."""
    if band == "stressed":
        return spec.low_alarm, "stressed", "outside"
    if band == "caution":
        # Ya ha cruzado el suelo del verde; lo siguiente es el rojo. Con los dos
        # cortes iguales la región ámbar no existe y no se llega aquí.
        return spec.low_alarm, "stressed", "outside"
    return spec.low_ok, _next_band_down(spec), "inside"


def _lower_better(
    value: Decimal, spec: ThresholdSpec, band: Band | None
) -> tuple[Decimal | None, NextBand, Side]:
    """Menos es mejor: se sube hacia el ámbar y luego al rojo."""
    if band == "stressed":
        return spec.high_alarm, "stressed", "outside"
    if band == "caution":
        return spec.high_alarm, "stressed", "outside"
    return spec.high_ok, _next_band_up(spec), "inside"


def _central(
    value: Decimal, spec: ThresholdSpec, band: Band | None
) -> tuple[Decimal | None, NextBand, Side]:
    """Banda central: dentro se mide al corte MÁS CERCANO de los dos.

    Fuera, al de alarma del lado en el que está — que puede no existir (S7 por
    debajo de su banda), y entonces se declara.
    """
    if band == "healthy":
        candidates = [c for c in (spec.low_ok, spec.high_ok) if c is not None]
        if not candidates:
            return None, "caution", "inside"
        nearest = min(candidates, key=lambda cut: abs(value - cut))
        return nearest, "caution", "inside"
    # Fuera de la banda sana: hacia el lado en que está.
    below = spec.low_ok is not None and value < spec.low_ok
    alarm = spec.low_alarm if below else spec.high_alarm
    return alarm, "stressed", "outside"


def _next_band_down(spec: ThresholdSpec) -> NextBand:
    """Con `low_ok == low_alarm` no hay ámbar: por debajo se entra en rojo."""
    if spec.low_ok is not None and spec.low_ok == spec.low_alarm:
        return "stressed"
    return "caution" if spec.low_alarm is not None else "stressed"


def _next_band_up(spec: ThresholdSpec) -> NextBand:
    """Con `high_ok == high_alarm` no hay ámbar: por encima se entra en rojo."""
    if spec.high_ok is not None and spec.high_ok == spec.high_alarm:
        return "stressed"
    return "caution" if spec.high_alarm is not None else "stressed"
