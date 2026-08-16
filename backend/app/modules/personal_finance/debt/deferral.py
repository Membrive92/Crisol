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

**Cierra o no cierra, sin aproximar.** Si la suma no cuadra, no se marca
ninguna compra y se dice por qué: una aproximación marcaría compras que no son
del ciclo —o dejaría fuera algunas que sí— y el usuario no tendría forma de
saber cuáles.

La única holgura es de REDONDEO, y está acotada por el número de movimientos
(`CENT_TOLERANCE_PER_MOVEMENT`). Medido contra datos reales: el ciclo de junio
de 2026 suma 700,27 € contra un recibo de 700,26 €. Un céntimo. Exigir
coincidencia perfecta convertía un ciclo perfectamente identificable en «faltan
datos», que es un diagnóstico falso y manda al usuario a buscar un fichero que
no existe.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
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
    closes: bool
    """El ciclo está determinado y se puede declarar.

    Se llamaba `closes_exactly` cuando la coincidencia tenía que ser al
    céntimo. Ya no lo es —ver `CENT_TOLERANCE_PER_MOVEMENT`— así que ese nombre
    habría pasado a mentir en el caso más frecuente, que es justo cuando un
    nombre engaña más.
    """
    difference: Decimal
    """Lo que le falta al tramo para sumar el recibo. `0` cuando es exacto.

    Se publica para que la pantalla pueda decirlo: cerrar por 700,27 cuando el
    recibo dice 700,26 es válido, pero no es lo mismo que cerrar exacto y no
    debe presentarse igual.
    """
    reason: str

    @property
    def is_exact(self) -> bool:
        return self.difference == 0

    @property
    def count(self) -> int:
        return len(self.purchases)


#: Holgura por movimiento, para absorber redondeos del banco sin abrir la mano.
#:
#: Un tramo de N movimientos admite hasta N céntimos de diferencia: cada línea
#: puede aportar como mucho un redondeo. Acotarla al número de movimientos —en
#: vez de un margen fijo o un porcentaje— es lo que impide que cuadre un tramo
#: EQUIVOCADO: entre dos ciclos reales hay euros de diferencia, nunca céntimos,
#: así que ampliar la ventana no puede hacer aparecer una segunda respuesta.
#:
#: Un tramo exacto SIEMPRE gana sobre uno tolerado, y la diferencia viaja a la
#: pantalla para que un cierre por redondeo no se presente como exacto.
CENT_TOLERANCE_PER_MOVEMENT = Decimal("0.01")

#: Cuántos días antes del corte puede terminar el ciclo.
#:
#: `until` es la fecha del CARGO, y el banco cobra unos días después de cerrar
#: la facturación: en los datos medidos, entre 3 y 7. Buscar el final del tramo
#: dentro de esa ventana es lo que permite acertar sin conocer la fecha exacta
#: de cierre, que el extracto no publica.
#:
#: Acotarla importa: sin ventana, una compra aislada de meses atrás que
#: coincidiera con el importe del recibo cerraría el ciclo por casualidad.
CYCLE_END_WINDOW_DAYS = 15


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
        return CycleSelection(
            (), Decimal(0), False, Decimal(0), "El recibo tiene que ser un importe positivo."
        )

    eligible = [p for p in purchases if until is None or p.occurred_at <= until]
    if not eligible:
        return CycleSelection(
            (),
            Decimal(0),
            False,
            target,
            "No hay compras registradas en la tarjeta antes de ese cierre.",
        )

    # Desempate determinista. Las filas de un extracto caen todas a medianoche
    # de su día, así que un día entero es UN grupo empatado: sin un criterio
    # fijo, qué compras entran dependería del orden en que la BD las devuelva.
    # Por importe primero (estable y visible) y por id después, que sólo decide
    # entre filas indistinguibles.
    eligible.sort(key=lambda p: (p.occurred_at, p.amount, str(p.id)))

    # Cuánto puede BAJAR todavía la suma si se sigue caminando hacia atrás:
    # las devoluciones entran con importe negativo, así que pararse en cuanto
    # se pasa del recibo cortaría antes de que una devolución anterior lo
    # devolviera a su sitio. `refunds_before[i]` es el total (negativo) de las
    # devoluciones que quedan por recorrer cuando ya se ha incluido `i`.
    refunds_before: list[Decimal] = []
    running = Decimal(0)
    for purchase in eligible:
        refunds_before.append(running)
        if purchase.amount < 0:
            running += purchase.amount

    # `until` acota por ARRIBA, no marca el final exacto del ciclo. La fecha
    # que se conoce es la del CARGO (el banco cobra unos días después de
    # cerrar), así que fijar ahí el final del tramo arrastra las compras de esos
    # días, que ya son del ciclo siguiente. Se prueban por tanto todos los
    # finales posibles hasta el corte y gana el MÁS TARDÍO que cierre: el ciclo
    # acaba tan tarde como pueda antes del cobro.
    #
    # Sigue sin haber elección entre subconjuntos —sólo tramos CONTIGUOS— así
    # que el resultado es único y reproducible; lo que se amplía es dónde puede
    # terminar, no qué combinaciones valen.
    # Sin corte no se sabe dónde puede acabar el ciclo, así que sólo se admite
    # el final natural: el movimiento más reciente.
    if until is None:
        primeros_finales = [len(eligible) - 1]
    else:
        ventana = until - timedelta(days=CYCLE_END_WINDOW_DAYS)
        primeros_finales = [
            i for i in range(len(eligible) - 1, -1, -1) if eligible[i].occurred_at >= ventana
        ] or [len(eligible) - 1]

    mejor_fallo = (Decimal(0), Decimal(0))
    for end in primeros_finales:
        accumulated = Decimal(0)
        picked: list[CyclePurchase] = []
        tolerated: tuple[Decimal, int, list[CyclePurchase], Decimal] | None = None

        for index in range(end, -1, -1):
            accumulated += eligible[index].amount
            picked.append(eligible[index])
            difference = target - accumulated
            allowed = CENT_TOLERANCE_PER_MOVEMENT * len(picked)

            if difference == 0:
                return CycleSelection(
                    tuple(reversed(picked)),
                    accumulated,
                    True,
                    Decimal(0),
                    f"{len(picked)} movimientos suman exactamente el recibo.",
                )
            if abs(difference) <= allowed and (
                tolerated is None
                or abs(difference) < tolerated[0]
                or (abs(difference) == tolerated[0] and len(picked) < tolerated[1])
            ):
                tolerated = (abs(difference), len(picked), list(picked), accumulated)

            # Salida anticipada: se abandona este final cuando ni recorriendo
            # todo lo que queda podría la suma volver al entorno del recibo.
            if accumulated + refunds_before[index] > target + allowed:
                break

        if tolerated is not None:
            _diff, _n, movimientos, total = tolerated
            signo = "más" if total > target else "menos"
            return CycleSelection(
                tuple(reversed(movimientos)),
                total,
                True,
                target - total,
                (
                    f"{len(movimientos)} movimientos suman {total}, "
                    f"{abs(target - total)} {signo} que el recibo ({target}). "
                    "Es un redondeo del banco, no un ciclo distinto."
                ),
            )
        if end == primeros_finales[0]:
            mejor_fallo = (accumulated, target - accumulated)

    accumulated, _ = mejor_fallo
    return CycleSelection(
        (),
        accumulated,
        False,
        target - accumulated,
        (
            "Las compras registradas en la tarjeta no suman el importe del recibo "
            f"({target}). Probablemente falte por importar parte del ciclo: sin el "
            "ciclo completo, marcar unas cuantas repartiría el gasto entre categorías "
            "que no son las suyas."
        ),
    )
