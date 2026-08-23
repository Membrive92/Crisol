"""Fechas de movimiento: una fecha CIVIL no tiene zona, pero la columna sí.

**El problema que resuelve.** `transactions.occurred_at` es `TIMESTAMPTZ`, o sea
un instante. Pero lo que llega del mundo es una fecha CIVIL: «13/02/2026» es el
día que imprime el banco, y no tiene hora ni zona. Para guardarla hay que elegir
una, y hasta PHASE-47 se elegía por accidente: si el valor llegaba *naive*,
asyncpg lo codifica con `astimezone(utc)`, y `astimezone()` sobre un naive asume
la zona **del proceso**. Con el backend en Europe/Madrid, «13/02/2026» acababa
persistido como `2026-02-12T23:00:00Z`.

Medido en la base real del usuario antes del arreglo: **469 de 491** filas vivas
desplazadas un día, 14 de ellas incluso de mes natural — una transferencia de
4.267,47 € contando en marzo siendo del 1 de abril. Y como la pantalla formatea
en hora local mientras los filtros de rango se construyen en UTC, un movimiento
que la app muestra el día 13 quedaba FUERA de un rango que empieza el día 13.

**La regla.** Un naive se ANCLA en UTC; no se convierte. Convertirlo asumiría
que venía expresado en alguna zona local, que es exactamente la suposición que
causó el desplazamiento. Lo que sí trae zona (un ISO con offset) se traslada a
UTC, para que la columna sea homogénea y dos escrituras del mismo instante no
queden con representaciones distintas.

**Dónde va.** En los schemas de ENTRADA, que es la frontera por la que el dato
llega desde fuera. Ponerlo en el servicio dejaría fuera a quien llame por otra
ruta; ponerlo en la columna no es posible, porque para cuando SQLAlchemy la
escribe la zona ya se ha perdido.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator


def anchor_naive_in_utc(value: datetime) -> datetime:
    """Ancla un `datetime` sin zona en UTC; traslada a UTC el que sí la trae.

    Idempotente: aplicarlo dos veces da lo mismo que aplicarlo una.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


CivilDatetime = Annotated[datetime, AfterValidator(anchor_naive_in_utc)]
"""`datetime` de entrada que nunca queda a merced de la zona del proceso.

Úsalo en todo schema que RECIBA una fecha de movimiento desde fuera (creación y
edición de transacciones, confirmación de tickets, transferencias). En los
schemas de RESPUESTA no hace falta: lo que sale de la columna ya es aware.
"""
