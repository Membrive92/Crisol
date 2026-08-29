"""Lo que el frontend enlaza desde el veredicto tiene que EXISTIR en el motor.

`packages/ui/src/investment-report-sections.ts` dice adónde lleva cada señal.
Dos de esas afirmaciones son sobre el motor y el frontend no puede
comprobarlas: que la serie `fcf_cfo` existe (la señal «tendencia de la caja
libre» resalta esa fila) y que ninguna clave de bandera es también una métrica
(una bandera con sitio en una matriz volvería a enlazar a ninguna parte).
Aquí, donde están las claves, sí.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.modules.investment.analysis.engine.catalog import ALL_METRIC_KEYS
from app.modules.investment.analysis.engine.evolution import HORIZONTAL_ITEMS
from app.modules.investment.analysis.engine.flag_catalog import FLAG_LABELS

FRONT = Path(__file__).resolve().parents[2] / "packages/ui/src/investment-report-sections.ts"


def test_la_serie_que_resalta_la_tendencia_de_la_caja_libre_existe() -> None:
    """`DERIVED_PLACEMENT.fcf_trend.highlight` nombra una serie de Evolución.

    Si el motor la renombra, el enlace aterriza sin fila marcada — y el test
    del frontend no puede verlo porque compara el registro consigo mismo.
    """
    keys = {key for key, _label, _extract in HORIZONTAL_ITEMS}
    assert "fcf_cfo" in keys, sorted(keys)

    fuente = FRONT.read_text(encoding="utf-8")
    m = re.search(r"fcf_trend:\s*\{[^}]*highlight:\s*'([a-z_]+)'", fuente)
    assert m, "el frontend ya no declara la fila que resalta fcf_trend"
    assert m.group(1) in keys, f"el frontend resalta {m.group(1)!r}, que no es una serie del motor"


def test_ninguna_bandera_es_tambien_una_metrica() -> None:
    """Una bandera con sitio en una matriz volvería a ser un enlace a ninguna parte."""
    solapadas = set(FLAG_LABELS) & set(ALL_METRIC_KEYS)
    assert solapadas == set(), sorted(solapadas)
