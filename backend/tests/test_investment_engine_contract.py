"""Contrato del engine — el gate que faltaba (PHASE-44.9).

`version.py` afirmaba desde PHASE-44.2 que *«el golden test falla si el output
del engine cambia sin que esta constante se mueva: es el gate que impide tocar
una fórmula en silencio»*. **Ese gate no existía**: el único test que tocaba
`ENGINE_VERSION` comprobaba que fuese semver. La prueba de que hacía falta es que
las capas 1.5, 2, 3, 3.5 y 4 entraron enteras sin mover la constante de 1.0.0.

Aquí está. Dos contratos:

1. **Huella de la FORMA de la salida** — claves de métrica, claves de bandera y
   los campos de cada dataclass que el engine publica. Cambiar cualquiera de
   esas cosas obliga a subir `ENGINE_VERSION` y a actualizar la huella en el
   mismo commit. Es la forma, no los valores: así una fixture actualizada no da
   un rojo espurio, pero renombrar un campo o añadir una métrica sí.

2. **Toda bandera emitida tiene nombre** — si alguien añade una `Flag` y no la
   nombra en `flag_catalog`, su clave cruda acabaría impresa en la pantalla del
   veredicto, que es exactamente la regresión que PHASE-44.9 vino a cerrar.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import pkgutil
import re
from dataclasses import fields, is_dataclass
from pathlib import Path

from app.modules.investment.analysis import engine as engine_pkg
from app.modules.investment.analysis.engine.catalog import ALL_METRIC_KEYS
from app.modules.investment.analysis.engine.flag_catalog import FLAG_LABELS
from app.modules.investment.analysis.engine.version import ENGINE_VERSION

_ENGINE_DIR = Path(engine_pkg.__file__).parent


ENGINE_SHAPE_FINGERPRINTS: dict[str, str] = {
    "1.2.0": "2cf02897a604ce2c15cb2bacf7021524f16165cef8a09f488df66fd7b85e50c2",
    "1.3.0": "e2b85cac6d825000ae449b6c4b31449db01fb2db1f2007b7dfcc69fa77d6f41d",
}
"""Huella de la forma de salida por versión de engine.

Cuando este test falle, la pregunta NO es «cómo silencio esto» sino «¿he
cambiado el contrato del engine?». Si la respuesta es sí: sube `ENGINE_VERSION`,
añade su entrada al historial de `version.py`, y añade aquí la huella nueva que
el propio fallo imprime. Si es no, has roto algo sin querer.
"""


def _engine_shape() -> dict[str, object]:
    """Descripción canónica de la FORMA que publica el engine."""
    dataclasses_shape: dict[str, list[str]] = {}
    for module_info in pkgutil.iter_modules([str(_ENGINE_DIR)]):
        module = importlib.import_module(f"{engine_pkg.__name__}.{module_info.name}")
        for name in dir(module):
            obj = getattr(module, name)
            if not is_dataclass(obj) or not isinstance(obj, type):
                continue
            # Sólo las definidas AQUÍ: las importadas de otro módulo del engine
            # ya se recogen en el suyo, y las de fuera no son contrato nuestro.
            if getattr(obj, "__module__", "") != module.__name__:
                continue
            dataclasses_shape[f"{module_info.name}.{name}"] = sorted(f.name for f in fields(obj))
    return {
        "metric_keys": sorted(ALL_METRIC_KEYS),
        "flag_keys": sorted(FLAG_LABELS),
        "dataclasses": dict(sorted(dataclasses_shape.items())),
    }


def _fingerprint(shape: dict[str, object]) -> str:
    blob = json.dumps(shape, separators=(",", ":"), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def test_la_forma_del_engine_no_cambia_sin_mover_engine_version() -> None:
    shape = _engine_shape()
    actual = _fingerprint(shape)
    esperada = ENGINE_SHAPE_FINGERPRINTS.get(ENGINE_VERSION)

    assert esperada is not None, (
        f"ENGINE_VERSION={ENGINE_VERSION} no tiene huella registrada. "
        f"Añade a ENGINE_SHAPE_FINGERPRINTS: {ENGINE_VERSION!r}: {actual!r}"
    )
    assert actual == esperada, (
        "La forma de salida del engine ha cambiado y ENGINE_VERSION sigue en "
        f"{ENGINE_VERSION}. Sube la versión, documenta el cambio en el historial de "
        f"version.py y registra la huella nueva: {actual!r}.\n"
        f"Forma actual: {json.dumps(shape, ensure_ascii=False, indent=1)[:2000]}"
    )


def test_engine_version_es_semver_y_tiene_historial() -> None:
    partes = ENGINE_VERSION.split(".")
    assert len(partes) == 3 and all(p.isdigit() for p in partes)
    version_doc = (_ENGINE_DIR / "version.py").read_text(encoding="utf-8")
    assert (
        f"- {ENGINE_VERSION} —" in version_doc
    ), "cada versión del engine se documenta en el historial de version.py"


# ── Banderas ──────────────────────────────────────────────────────────

_FLAG_EMISSION = re.compile(
    # Tres formas de emitir en el engine: el helper `_flag("KEY", …)`, el
    # constructor `Flag(key="KEY", …)` y las reglas parametrizadas que reciben
    # `key="KEY"` (`_gap_rule`, así nacen C1 y C3).
    r"""(?:_flag\(\s*\n?\s*["']|Flag\(\s*\n?\s*key=["']|\bkey=["'])([A-Za-z0-9_]+)["']""",
)

_NOT_FLAGS = frozenset(ALL_METRIC_KEYS)
"""Las claves de métrica también aparecen como `key="…"` al construir
`ScoreBreakdown` y series de la evolutiva. No son banderas."""


def _emitted_flag_keys() -> set[str]:
    """Las claves de bandera que el engine puede emitir, por escaneo de fuente.

    Es un escaneo estático a propósito: ejecutar el engine sólo destaparía las
    banderas que SALTAN con las fixtures que haya, y justo las raras son las que
    se quedarían sin nombre.
    """
    keys: set[str] = set()
    for path in _ENGINE_DIR.glob("*.py"):
        keys.update(_FLAG_EMISSION.findall(path.read_text(encoding="utf-8")))
    return keys - _NOT_FLAGS


def test_toda_bandera_emitida_tiene_nombre_legible() -> None:
    emitidas = _emitted_flag_keys()
    assert emitidas, "el escáner no ha encontrado ninguna bandera: la regex se ha quedado obsoleta"
    sin_nombre = emitidas - set(FLAG_LABELS)
    assert not sin_nombre, (
        f"estas banderas se emiten sin nombre y su clave cruda acabaría en pantalla: "
        f"{sorted(sin_nombre)}. Añádelas a flag_catalog.FLAG_LABELS."
    )


def test_el_catalogo_de_banderas_no_tiene_entradas_muertas() -> None:
    """Al revés: una etiqueta para una bandera que ya no se emite es documentación
    caducada, que es la lección de PHASE-43."""
    huerfanas = set(FLAG_LABELS) - _emitted_flag_keys()
    assert not huerfanas, f"nombradas pero ya no emitidas: {sorted(huerfanas)}"
