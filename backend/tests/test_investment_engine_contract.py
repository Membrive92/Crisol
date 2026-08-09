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
from typing import Literal, get_args, get_origin

from app.modules.investment.analysis import engine as engine_pkg
from app.modules.investment.analysis.engine.catalog import ALL_METRIC_KEYS
from app.modules.investment.analysis.engine.flag_catalog import FLAG_LABELS
from app.modules.investment.analysis.engine.version import ENGINE_VERSION

_ENGINE_DIR = Path(engine_pkg.__file__).parent


ENGINE_SHAPE_FINGERPRINTS: dict[str, str] = {
    "1.2.0": "2cf02897a604ce2c15cb2bacf7021524f16165cef8a09f488df66fd7b85e50c2",
    "1.3.0": "e2b85cac6d825000ae449b6c4b31449db01fb2db1f2007b7dfcc69fa77d6f41d",
    "1.4.0": "8a3f235739b1c0684343bb5412a057c1097e503e5a43da108753ff71ab971620",
    "1.5.0": "589e12a914b05bec80096449da5644c0b8e45193175aef84ef9a2a0ea41ff599",
    "1.6.0": "bd234d92e86b07e7e7147471d56e9617265016be1efaf61f354f0cd65851dd5a",
}
"""Huella de la forma de salida por versión de engine.

Cuando este test falle, la pregunta NO es «cómo silencio esto» sino «¿he
cambiado el contrato del engine?». Si la respuesta es sí: sube `ENGINE_VERSION`,
añade su entrada al historial de `version.py`, y añade aquí la huella nueva que
el propio fallo imprime. Si es no, has roto algo sin querer.

**Sólo se comprueba la versión vigente**; las anteriores quedan como registro. Y
las de 1.2.0 y 1.3.0 se calcularon con la definición de `_engine_shape` ANTERIOR
a PHASE-44.17, que no miraba los dominios de los `Literal` — así que no son
comparables con las de hoy y no se pueden recalcular sin el código de entonces.
"""


def _literal_domains() -> dict[str, list[str]]:
    """Los valores admitidos por cada alias `Literal` que el engine publica.

    Sin esto, el gate NO ve un cambio de significado: PHASE-44.17 añadió
    `not_applicable` a `MetricStatus` —un estado nuevo con reglas propias— y la
    huella salió IDÉNTICA, porque `fields()` enumera nombres de campo y el
    dominio de un `Literal` no es un campo. El propio bump que la fase necesitaba
    habría dependido de que alguien se acordara.

    Se indexa por NOMBRE y no por módulo a propósito: `MetricStatus` se importa
    en media docena de módulos del engine, y clavarle el módulo haría que mover
    un import cambiase la huella. Un alias no puede tener dos dominios distintos
    —si los tuviera, el `assert` de abajo lo diría en vez de mezclarlos—.
    """
    domains: dict[str, list[str]] = {}
    for module_info in pkgutil.iter_modules([str(_ENGINE_DIR)]):
        module = importlib.import_module(f"{engine_pkg.__name__}.{module_info.name}")
        for name in dir(module):
            obj = getattr(module, name)
            if get_origin(obj) is not Literal:
                continue
            values = sorted(str(value) for value in get_args(obj))
            previous = domains.get(name)
            assert previous is None or previous == values, (
                f"el alias Literal '{name}' tiene dos dominios distintos en el engine: "
                f"{previous} y {values}"
            )
            domains[name] = values
    return domains


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
        "literals": dict(sorted(_literal_domains().items())),
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


_FLAG_SIGNAL_LITERAL = re.compile(r"""_flag_signal\(\s*["']""")


def test_ninguna_bandera_entra_en_una_pregunta_por_la_puerta_de_atras() -> None:
    """Las claves de bandera de las preguntas salen de `QUESTION_FLAG_KEYS`.

    El gate de cobertura (en los tests de síntesis) comprueba que toda clave de
    esa tupla tenga evaluación publicada. Si alguien añade `_flag_signal("X", …)`
    con la clave escrita a mano, se salta la tupla y por tanto se salta el gate:
    la señal saldría con el default pesimista —«no se ha podido comprobar»— para
    todas las empresas, y nada avisaría de que le falta su evaluación.
    """
    synthesis_source = (_ENGINE_DIR / "synthesis.py").read_text(encoding="utf-8")
    assert not _FLAG_SIGNAL_LITERAL.search(synthesis_source), (
        "hay un `_flag_signal` con la clave escrita a mano: añádela a "
        "QUESTION_FLAG_KEYS y publica su evaluación en la capa que la calcula"
    )


def test_el_catalogo_de_banderas_no_tiene_entradas_muertas() -> None:
    """Al revés: una etiqueta para una bandera que ya no se emite es documentación
    caducada, que es la lección de PHASE-43."""
    huerfanas = set(FLAG_LABELS) - _emitted_flag_keys()
    assert not huerfanas, f"nombradas pero ya no emitidas: {sorted(huerfanas)}"
