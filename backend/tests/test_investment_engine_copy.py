"""Las razones que el informe IMPRIME (PHASE-44.24.E.7).

Una razón del motor no es un log: se pinta bajo la etiqueta de una fila y es lo
único que el usuario tiene para saber por qué su empresa no tiene ese número.
Interpolar la clave del motor —«falta la partida 'ltd_current_portion'»— le pide
que aprenda un vocabulario interno para leer su propio informe.

No hay bump de versión (Dec.F): la política de `version.py` es «fórmula o
métrica nueva», la huella del motor no cambia, y un bump de patch pondría el
aviso «este análisis lo produjo un motor anterior» en TODOS los runs guardados
por un cambio de redacción.
"""

from __future__ import annotations

import re

from app.modules.investment.analysis.engine.types import Amount, item_label
from app.modules.investment.fundamentals.canonical import CANONICAL_ITEM_DEFINITIONS

# Una clave del motor: minúsculas con guiones bajos, entre comillas simples.
# Es la forma exacta que producía la interpolación vieja.
_CLAVE_CRUDA = re.compile(r"'[a-z][a-z0-9_]{3,}'")


def test_las_49_partidas_tienen_etiqueta_humana() -> None:
    """El fallback a la clave existe, pero no debe alcanzarlo ninguna real."""
    sin_etiqueta = [d.key for d in CANONICAL_ITEM_DEFINITIONS if item_label(d.key) == d.key]
    assert sin_etiqueta == [], sin_etiqueta


def test_la_etiqueta_es_la_del_catalogo_y_no_una_copia() -> None:
    """Si alguien renombra una partida, la frase la sigue.

    Escribir los nombres a mano aquí sería el mecanismo que dejó tres rótulos
    mintiendo en 44.9: dos fuentes para el mismo dato.
    """
    for definicion in CANONICAL_ITEM_DEFINITIONS:
        assert item_label(definicion.key) == definicion.label


def test_una_partida_ausente_se_explica_con_su_nombre_humano() -> None:
    razon = Amount.absent("ltd_current_portion").reason
    assert razon is not None
    assert "Deuda a largo con vencimiento corriente" in razon
    assert "ltd_current_portion" not in razon


def test_ninguna_razon_por_defecto_cita_una_clave_del_motor() -> None:
    """Recorre las 49 y comprueba que ninguna frase deja escapar la clave.

    Se prueba sobre las 49 REALES y no sobre un ejemplo: el defecto vuelve por
    una partida cuyo nombre nadie miró, no por la que se arregló.
    """
    culpables: list[str] = []
    for definicion in CANONICAL_ITEM_DEFINITIONS:
        razon = Amount.absent(definicion.key).reason or ""
        if _CLAVE_CRUDA.search(razon):
            culpables.append(f"{definicion.key}: {razon!r}")
    assert culpables == [], culpables


def test_el_detector_caza_una_clave_cruda() -> None:
    """La sonda del propio detector.

    Sin esto, el test de arriba sólo demuestra que hoy no hay ninguna — no que
    se detectaría si volviera.
    """
    assert _CLAVE_CRUDA.search("falta la partida 'ltd_current_portion'") is not None
    assert _CLAVE_CRUDA.search("el filing no publica Existencias") is None
    # Una palabra corriente entrecomillada no es una clave: sin el guión bajo y
    # con menos de cuatro letras, no tiene la forma.
    assert _CLAVE_CRUDA.search("el importe es 'n/a'") is None
