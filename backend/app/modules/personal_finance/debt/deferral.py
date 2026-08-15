"""PHASE-47.E2 — El ciclo aplazado: qué compras cubre un recibo financiado.

Cuando el banco financia el recibo de una tarjeta, ese recibo salda un CICLO de
facturación: las compras hechas entre dos cierres. Esas compras siguen siendo
gasto —se hicieron, tienen categoría y fecha— pero no salieron de la cuenta ese
mes; saldrán como cuota durante los años siguientes.

Para poder decirlo hay que saber QUÉ compras cubre el recibo, y el extracto no
lo dice: no trae el ciclo, sólo el importe total. Pero el importe basta, porque
un recibo es la suma exacta de las compras del ciclo. Medido contra los datos
del usuario, cuatro ciclos cierran **al céntimo**.

La derivación va aquí, PURA y sin BD, por lo mismo que el resto del dominio de
deuda: la decide una aritmética que se puede probar con una lista de números, y
mezclarla con la sesión la volvería inauditable.

**Cierre exacto o nada.** Si la suma no cuadra al céntimo, no se marca ninguna
compra y se dice por qué. Es deliberado: una aproximación marcaría compras que
no son del ciclo —o dejaría fuera algunas que sí— y el usuario no tendría forma
de saber cuáles. Pasa de verdad: el recibo de 990,02 € de junio no cierra
porque faltan compras de mayo en la app, y la respuesta correcta ahí es «faltan
datos», no «he elegido unas cuantas».
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CyclePurchase:
    """Una compra candidata a formar parte del ciclo."""

    id: uuid.UUID
    occurred_at: datetime
    amount: Decimal
    description: str | None


@dataclass(frozen=True, slots=True)
class CycleSelection:
    """Qué compras forman el ciclo, o por qué no se ha podido decidir."""

    purchases: tuple[CyclePurchase, ...]
    total: Decimal
    closes_exactly: bool
    reason: str

    @property
    def count(self) -> int:
        return len(self.purchases)


def select_deferred_cycle(
    purchases: list[CyclePurchase],
    target: Decimal,
    *,
    until: datetime | None = None,
) -> CycleSelection:
    """Las compras, de más reciente a más antigua, que suman EXACTO el recibo.

    Se recorre hacia atrás desde el cierre porque un ciclo es contiguo y
    termina donde el banco lo corta: las compras anteriores pertenecen a
    recibos ya pagados. Acumular hacia atrás encuentra el corte sin necesitar
    la fecha de cierre, que el extracto no publica.

    En cuanto la suma PASA del importe sin haberlo igualado, se para y no
    devuelve nada. Seguir buscando una combinación que cuadre sería elegir
    entre subconjuntos —muchos suman lo mismo— y esa elección no la puede
    tomar el sistema: distintos subconjuntos reparten el gasto entre
    categorías distintas.

    `until` acota por arriba: sólo cuentan las compras anteriores al cierre.
    Sin él entrarían las del ciclo siguiente, que aún no se ha facturado.
    """
    if target <= 0:
        return CycleSelection((), Decimal(0), False, "El recibo tiene que ser un importe positivo.")

    eligible = [p for p in purchases if until is None or p.occurred_at <= until]
    if not eligible:
        return CycleSelection(
            (), Decimal(0), False, "No hay compras registradas en la tarjeta antes de ese cierre."
        )

    eligible.sort(key=lambda p: (p.occurred_at, str(p.id)))

    accumulated = Decimal(0)
    picked: list[CyclePurchase] = []
    for purchase in reversed(eligible):
        accumulated += purchase.amount
        picked.append(purchase)
        if accumulated == target:
            return CycleSelection(
                tuple(reversed(picked)),
                accumulated,
                True,
                f"{len(picked)} compras suman exactamente el recibo.",
            )
        if accumulated > target:
            break

    return CycleSelection(
        (),
        accumulated,
        False,
        (
            "Las compras registradas en la tarjeta no suman el importe del recibo "
            f"({target}). Probablemente falte por importar parte del ciclo: sin el "
            "ciclo completo, marcar unas cuantas repartiría el gasto entre categorías "
            "que no son las suyas."
        ),
    )
