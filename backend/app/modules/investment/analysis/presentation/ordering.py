"""El orden en que se leen las señales de una pregunta (PHASE-44.24.C).

Hoy salen en el orden en que la síntesis las construye, que es el orden en que
se escribieron. Con diez señales por pregunta, eso obliga a recorrerlas todas
para encontrar la que duele.

**Es un orden TOTAL**, y esa palabra es el trabajo: una comparación que deje
pares sin decidir hace que «las dos peores» —lo que la narrativa de la entrega B
va a citar— se elijan al azar entre empatados que no son iguales.
"""

from __future__ import annotations

from decimal import Decimal

from app.modules.investment.analysis.engine.synthesis import QuestionSignal
from app.modules.investment.analysis.presentation.distance import SignalDistance

_BAND_RANK = {"stressed": 0, "caution": 1, "healthy": 2}
"""Primero lo que está mal. Sin banda va al final: no es que esté bien, es que
no puntúa, y la pantalla ya lo dice en su fila."""

_NO_BAND = 3

_WITHOUT_GRADIENT = 0
_WITH_GRADIENT = 1
"""Dentro de una banda, **una señal sin gradiente va PRIMERO**.

Una bandera encendida, una señal derivada o una métrica de puntuación no tienen
distancia relativa que medir. La alternativa —tratarlas como distancia cero—
colocaría una bandera roja como «exactamente en el corte», es decir la MENOS
grave de las rojas, que es justo al revés: una bandera que salta es evidencia
binaria y ya ha demostrado lo suyo, no un roce con la raya.
"""


def severity_key(
    signal: QuestionSignal, distance: SignalDistance | None
) -> tuple[int, int, Decimal, str]:
    """La clave de orden de una señal. Menor es peor.

    Cuatro componentes, y ninguno sobra:

    1. La banda. Lo rojo antes que lo ámbar, y lo sin-banda al final.
    2. Si tiene gradiente. Sin él va primero dentro de su banda (ver arriba).
    3. La distancia relativa, con signo: más dentro de la banda mala es peor, y
       más cerca de cruzarla también. Se niega para que «más» ordene antes.
    4. La clave, sólo para desempatar iguales EXACTOS y que el orden sea
       reproducible. Es el último criterio y sólo entre indistinguibles: un
       desempate alfabético que decidiera algo sería la ausencia de criterio.

    Nunca se compara `None` con un número —el centinela va en el componente 2—
    porque en Python eso lanza y en TypeScript se convierte en cero en silencio,
    que es peor.
    """
    band_rank = _BAND_RANK.get(signal.band or "", _NO_BAND)
    relative = distance.relative if distance is not None else None
    if relative is None:
        return (band_rank, _WITHOUT_GRADIENT, Decimal(0), signal.key)
    # Fuera de la banda: cuanto más dentro de lo malo, peor. Dentro: cuanto más
    # cerca del corte, peor. Las dos se ordenan igual negando la relativa
    # cuando está fuera y usándola tal cual cuando está dentro.
    scored = -relative if distance is not None and distance.side == "outside" else relative
    return (band_rank, _WITH_GRADIENT, scored, signal.key)


def sort_signals(
    signals: list[tuple[QuestionSignal, SignalDistance | None]],
) -> list[tuple[QuestionSignal, SignalDistance | None]]:
    """Las señales de peor a mejor, de forma determinista."""
    return sorted(signals, key=lambda pair: severity_key(pair[0], pair[1]))
