"""PHASE-47.A — Huella de cabecera de un fichero importado.

Sirve para responder a una pregunta que hasta ahora nadie hacía: **¿este fichero
tiene pinta de ser de otra cuenta?** En julio de 2026 el extracto de la tarjeta
se importó eligiendo la cuenta del banco. No falló nada —19 filas OK, cero
errores—, pero 17 compras quedaron colgando de la cuenta equivocada y un
aplazamiento entró por partida doble. La señal que lo destapó fue comparar el
recuento de compras entre meses, no la aplicación.

La huella es de la CABECERA, no del contenido: dos extractos del mismo banco y
la misma cuenta comparten columnas mes tras mes, y los de productos distintos
(cuenta corriente vs. tarjeta) no suelen compartirlas. Es una señal débil por
diseño —de ahí que sea un aviso y no una prohibición—, pero es la única que
habría cazado julio: era la primera importación de ese fichero, así que el
solape de duplicados (F.2) no tenía nada que ver.

**De dónde tiene que venir `columns`**: de la cabecera que el parser DETECTA,
que viaja aparte, nunca de las claves de las filas que devuelve. Los dos
smart-parsers emiten claves fijas por contrato (`SMART_FORCED_MAPPING`), así que
alimentar esta función con `rows[0].keys()` produce **la misma constante para
todos los ficheros de todos los bancos** — una señal que no discrimina nada y
que se lee como «no hay nada sospechoso». Fue el defecto que la revisión
adversarial de 47.A destapó con cuatro tests en verde encima.

Puro: sin BD, sin red, sin reloj.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

__all__ = ["header_fingerprint", "normalise_columns"]


def normalise_columns(columns: Iterable[str]) -> list[str]:
    """Nombres de columna comparables entre exportaciones del mismo producto.

    `trim` + `casefold` + colapso de espacios internos, y se ordena: el banco
    puede reordenar columnas entre exportaciones sin que eso signifique que el
    fichero es de otra cuenta. Las columnas vacías se descartan (un XLSX de
    banco trae columnas fantasma a la derecha, y su número varía por fichero).
    """
    seen: set[str] = set()
    out: list[str] = []
    for raw in columns:
        cleaned = " ".join(str(raw).split()).casefold()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return sorted(out)


def header_fingerprint(columns: Iterable[str]) -> str | None:
    """SHA-256 de la cabecera normalizada. `None` si no queda ninguna columna.

    `None` significa «no se ha podido calcular», no «cabecera vacía»: quien la
    consuma no debe compararla con nada. Distinguirlo importa porque un `""`
    casaría consigo mismo y haría saltar el aviso en todos los ficheros sin
    cabecera reconocible a la vez.
    """
    names = normalise_columns(columns)
    if not names:
        return None
    raw = "|".join(names).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
