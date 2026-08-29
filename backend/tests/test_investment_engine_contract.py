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

import ast
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


_CUT_IN_PROSE = re.compile(
    # Las formas en que se escribe un corte en español, incluido el SIGNO.
    r"(por (encima|debajo) de|superior(es)? al?|inferior(es)? al?|mayor(es)? que|"
    r"menor(es)? que|m[áa]s de|menos de|baja de|sube de|a partir de|"
    r"del corte|corte de|umbral de|[<>≥≤])"
    r"\s*(el\s*)?[−+-]?\d",
    re.IGNORECASE,
)
"""Un umbral escrito en prosa. Vive a nivel de módulo porque lo comparten el
glosario de métricas, el de partidas y las fichas de score: con una copia por
gate, endurecer uno dejaría los otros con la versión débil.

**Qué se amplió en PHASE-44.24.A** respecto a la versión de 44.23: el signo
(`[−+-]?`) y las pistas «del corte», «corte de» y «umbral de». La revisión
adversarial midió que la versión anterior **no cazaba** el ejemplo del propio
documento de alcance —«M-Score −2,61 (holgado del corte −2,22)»— porque exigía un
dígito sin signo justo detrás de la pista. Un gate que no caza el caso que
motivó escribirlo comprueba presencia, no efecto."""


def _token_overlap(a: str, b: str) -> float:
    """Qué fracción de las palabras con carga de `b` ya está en `a`.

    Sirve para distinguir un «por qué importa» de un «qué mide» reescrito con
    otras palabras: al redactar sesenta porqués seguidos, la salida natural es
    parafrasear el qué, y entonces el campo ocupa sitio sin añadir nada.
    """

    def significant(text: str) -> set[str]:
        return set(re.findall(r"[a-záéíóúñü]{4,}", text.lower()))

    words_b = significant(b)
    if not words_b:
        return 1.0
    return len(significant(a) & words_b) / len(words_b)


ENGINE_SHAPE_FINGERPRINTS: dict[str, str] = {
    "1.2.0": "2cf02897a604ce2c15cb2bacf7021524f16165cef8a09f488df66fd7b85e50c2",
    "1.3.0": "e2b85cac6d825000ae449b6c4b31449db01fb2db1f2007b7dfcc69fa77d6f41d",
    "1.4.0": "8a3f235739b1c0684343bb5412a057c1097e503e5a43da108753ff71ab971620",
    "1.5.0": "589e12a914b05bec80096449da5644c0b8e45193175aef84ef9a2a0ea41ff599",
    "1.6.0": "bd234d92e86b07e7e7147471d56e9617265016be1efaf61f354f0cd65851dd5a",
    "1.7.0": "082325f38f165ec92096b658ca128995f069a70f711abc65a576e4ec3e2d3520",
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


# ── 3. Toda métrica y toda partida tienen definición ──────────────────
#
# PHASE-44.23. La pantalla ofrece una «i» por fila; si el glosario se queda
# atrás, la fila la pierde EN SILENCIO — no hay error, simplemente deja de haber
# afordance, y nadie lo nota hasta que un usuario pregunta qué es esa fila.
#
# El gate es de doble sentido a propósito: falta una definición (métrica nueva
# sin documentar) y sobra una (métrica renombrada o retirada, definición
# huérfana que ya no describe nada).


def test_toda_metrica_del_catalogo_tiene_definicion() -> None:
    from app.modules.investment.analysis.engine.catalog import ALL_METRIC_KEYS
    from app.modules.investment.analysis.engine.glossary import METRIC_HELP

    del_catalogo = set(ALL_METRIC_KEYS)
    del_glosario = set(METRIC_HELP)
    assert del_catalogo - del_glosario == set(), "métricas sin definición para la «i»"
    assert del_glosario - del_catalogo == set(), "definiciones huérfanas: la métrica ya no existe"


def test_toda_partida_canonica_tiene_definicion() -> None:
    from app.modules.investment.fundamentals.canonical import CANONICAL_ITEM_DEFINITIONS
    from app.modules.investment.fundamentals.glossary import ITEM_HELP

    del_catalogo = {d.key for d in CANONICAL_ITEM_DEFINITIONS}
    del_glosario = set(ITEM_HELP)
    assert del_catalogo - del_glosario == set(), "partidas sin definición para la «i»"
    assert del_glosario - del_catalogo == set(), "definiciones huérfanas: la partida ya no existe"


def test_las_definiciones_son_utiles_y_no_tautologicas() -> None:
    """Una definición vacía, o que repite la etiqueta, cumple el gate anterior y
    no informa de nada. El límite superior es de presentación: el texto se
    despliega bajo la fila de una tabla y tres frases es lo que cabe sin tapar
    los números que se venían a comparar."""
    from app.modules.investment.analysis.engine.catalog import ALL_METRIC_DEFINITIONS
    from app.modules.investment.fundamentals.canonical import CANONICAL_ITEM_DEFINITIONS

    pobres: list[str] = []
    for definition in (*ALL_METRIC_DEFINITIONS, *CANONICAL_ITEM_DEFINITIONS):
        texto = definition.help.strip()
        etiqueta = definition.label.strip().lower()
        if len(texto) < 40:
            pobres.append(f"{definition.key}: demasiado corta ({len(texto)})")
        elif len(texto) > 320:
            pobres.append(f"{definition.key}: demasiado larga ({len(texto)})")
        elif texto.lower().rstrip(".") == etiqueta:
            pobres.append(f"{definition.key}: repite la etiqueta")
    assert pobres == [], pobres


def test_las_fichas_de_metrica_son_utiles_en_sus_tres_campos() -> None:
    """PHASE-44.24.A.1 — el gate de 44.23 miraba UN campo; ahora hay tres.

    Sin esto, `why` y `reading` entrarían sin ninguna comprobación: el gate de
    longitud y el de umbrales-en-prosa sólo tocaban `help`, que hoy es `what`.
    Dos tercios del texto nuevo quedarían fuera de vigilancia justo donde más
    fácil es colar un corte («menos es mejor por debajo de 1,5»).

    `reading` tiene un mínimo más bajo a propósito: «Más alto, mejor.» es una
    lectura legítima y completa, y exigirle cuarenta caracteres obligaría a
    rellenar con paja.
    """
    from app.modules.investment.analysis.engine.catalog import ALL_METRIC_DEFINITIONS
    from app.modules.investment.analysis.engine.glossary import METRIC_HELP

    pobres: list[str] = []
    for definition in ALL_METRIC_DEFINITIONS:
        ficha = METRIC_HELP[definition.key]
        campos = (
            ("what", ficha.what, 40, 320),
            ("why", ficha.why, 40, 320),
            ("reading", ficha.reading, 10, 200),
        )
        for campo, texto, minimo, maximo in campos:
            limpio = texto.strip()
            if len(limpio) < minimo:
                pobres.append(f"{definition.key}.{campo}: demasiado corta ({len(limpio)})")
            elif len(limpio) > maximo:
                pobres.append(f"{definition.key}.{campo}: demasiado larga ({len(limpio)})")
            if (m := _CUT_IN_PROSE.search(limpio)) is not None:
                pobres.append(f"{definition.key}.{campo}: escribe un umbral, {m.group(0)!r}")
        if ficha.what.strip().lower().rstrip(".") == definition.label.strip().lower():
            pobres.append(f"{definition.key}: 'what' repite la etiqueta")
        if _token_overlap(ficha.what, ficha.why) > 0.6:
            pobres.append(f"{definition.key}: 'why' repite 'what' en vez de decir por qué importa")
    assert pobres == [], pobres


def test_ninguna_definicion_escribe_un_umbral_a_mano() -> None:
    """Las bandas se calibran por sector (PHASE-44.21) y viajan en el propio run
    (`thresholds_used`). Un corte escrito en prosa caduca en silencio y acaba
    contradiciendo al semáforo que tiene al lado — es el mecanismo exacto de las
    tres etiquetas que mintieron en PHASE-44.9, aplicado a un texto más largo y
    por tanto más creíble.

    Se cazan las formas en que se escribe un corte en español: «por encima de
    1,5», «superior al 30 %», «> 2», «menor que 0,8», y desde PHASE-44.24
    también con signo («del corte -2,22»), que es la forma que se le escapaba.

    Recorre el `help` de métricas y partidas. En una métrica, `help` es su
    `what`: los otros dos campos los cubre el gate de arriba, y los dos juntos
    son lo que garantiza que no queda texto sin vigilar.
    """
    from app.modules.investment.analysis.engine.catalog import ALL_METRIC_DEFINITIONS
    from app.modules.investment.fundamentals.canonical import CANONICAL_ITEM_DEFINITIONS

    culpables = [
        f"{d.key}: {m.group(0)!r}"
        for d in (*ALL_METRIC_DEFINITIONS, *CANONICAL_ITEM_DEFINITIONS)
        if (m := _CUT_IN_PROSE.search(d.help))
    ]
    assert culpables == [], culpables


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


# ── 4. Los scores forenses y sus variables tienen ficha ───────────────
#
# PHASE-44.24.A. `score-breakdown-card.tsx` imprimía la clave cruda del motor:
# el usuario leía `DSRI`, `TATA` y `P4_cfo_supera_beneficio` en pantalla. Es la
# misma regresión que PHASE-44.9 cerró para las señales del veredicto
# (`B4_dividend_funded_externally`), y se cierra igual: la etiqueta sale del
# engine, no de un diccionario escrito en la pantalla.


def _score_component_keys_by_score() -> dict[str, set[str]]:
    """Las variables que el motor EMITE, por escaneo estático de `forensic.py`.

    Estático y no ejecutando `forensic.compute`, por el mismo motivo que el
    escáner de banderas de arriba: una ejecución sólo destapa lo que la fixture
    del test da la casualidad de ejercitar, y aquí hay al menos una rama
    condicional viva —el check de inventario sale del cómputo en los sectores sin
    inventario material (PHASE-44.21)— así que una fixture de una eléctrica
    dejaría `C3` fuera del conjunto emitido Y fuera de la ficha, y el test pasaría
    en verde con la variable sin documentar.

    Acotado POR FUNCIÓN, no por módulo: `forensic.py` construye otros diccionarios
    con claves de cadena (la evidencia de una bandera, por ejemplo) y un escaneo
    del fichero entero los recogería como si fueran componentes.
    """

    functions = {
        "compute_m_score": "m_score",
        "compute_z_score": "z_score",
        "compute_f_score": "f_score",
        "compute_c_score": "F7",
    }
    tree = ast.parse((_ENGINE_DIR / "forensic.py").read_text(encoding="utf-8"))
    found: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in functions:
            continue
        keys: set[str] = set()
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Dict):
                continue
            for key in inner.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
        found[functions[node.name]] = keys
    return found


def test_todo_score_forense_tiene_ficha() -> None:
    from app.modules.investment.analysis.engine.forensic import METRIC_KEYS
    from app.modules.investment.analysis.engine.score_help import SCORE_HELP

    del_motor = set(METRIC_KEYS)
    de_la_ficha = set(SCORE_HELP)
    assert del_motor - de_la_ficha == set(), "scores sin ficha para la «i» del informe"
    assert de_la_ficha - del_motor == set(), "fichas huérfanas: el score ya no existe"


def test_toda_variable_de_un_score_tiene_etiqueta() -> None:
    """En las DOS direcciones y por score.

    Que el total cuadre no basta: si una variable se moviera de un score a otro
    la suma seguiría dando lo mismo y la pantalla enseñaría la etiqueta
    equivocada bajo la tarjeta equivocada.
    """
    from app.modules.investment.analysis.engine.score_help import SCORE_HELP

    emitidas = _score_component_keys_by_score()
    assert emitidas, "el escáner no ha encontrado ninguna función de score: se ha quedado obsoleto"
    problemas: list[str] = []
    for score_key, keys in emitidas.items():
        ficha = SCORE_HELP.get(score_key)
        catalogadas = set(ficha.components) if ficha is not None else set()
        for falta in sorted(keys - catalogadas):
            problemas.append(f"{score_key}.{falta}: se emite y su clave cruda acabaría en pantalla")
        for sobra in sorted(catalogadas - keys):
            problemas.append(f"{score_key}.{sobra}: catalogada pero el motor ya no la emite")
    assert problemas == [], problemas


def test_los_scores_sin_desglose_no_declaran_variables() -> None:
    """`accruals`, `F5`, `F6` y `FZ` son un ratio único, no un agregado.

    Declararles variables sería documentar un desglose que la pantalla nunca va a
    pintar, y el usuario buscaría un desplegable que no existe.
    """
    from app.modules.investment.analysis.engine.score_help import SCORE_HELP

    con_desglose = set(_score_component_keys_by_score())
    for key, ficha in SCORE_HELP.items():
        if key not in con_desglose:
            assert (
                not ficha.components
            ), f"{key} no publica desglose y sin embargo declara variables"


def test_las_fichas_de_score_son_utiles_y_no_escriben_umbrales() -> None:
    """Los mismos tres criterios que el glosario de métricas, por campo.

    El de los umbrales importa más aquí que en ninguna parte: la ficha de un
    score se lee justo al lado de su banda, así que un corte escrito en prosa se
    contradice con el semáforo que tiene debajo en cuanto la calibración cambie.
    """
    from app.modules.investment.analysis.engine.score_help import SCORE_HELP

    pobres: list[str] = []
    for key, ficha in SCORE_HELP.items():
        for campo, texto in (("what", ficha.what), ("why", ficha.why), ("reading", ficha.reading)):
            limpio = texto.strip()
            if len(limpio) < 40:
                pobres.append(f"{key}.{campo}: demasiado corta ({len(limpio)})")
            elif len(limpio) > 320:
                pobres.append(f"{key}.{campo}: demasiado larga ({len(limpio)})")
            if (m := _CUT_IN_PROSE.search(limpio)) is not None:
                pobres.append(f"{key}.{campo}: escribe un umbral, {m.group(0)!r}")
        if _token_overlap(ficha.what, ficha.why) > 0.6:
            pobres.append(f"{key}: 'why' repite 'what' en vez de decir por qué importa")
        for component_key, component in ficha.components.items():
            if len(component.label.strip()) < 3:
                pobres.append(f"{key}.{component_key}: etiqueta vacía")
            if component.label.strip() == component_key:
                pobres.append(f"{key}.{component_key}: la etiqueta es la clave cruda")
            if len(component.what.strip()) < 40:
                pobres.append(f"{key}.{component_key}: definición demasiado corta")
            if (m := _CUT_IN_PROSE.search(component.what)) is not None:
                pobres.append(f"{key}.{component_key}: escribe un umbral, {m.group(0)!r}")
    assert pobres == [], pobres


def test_toda_bandera_tiene_ficha() -> None:
    """PHASE-44.24.A.2 — en las dos direcciones, contra `FLAG_LABELS`.

    Nombrar una bandera sin explicarla deja al usuario con un titular
    («Dividendo financiado con deuda o emisión») y sin saber qué hacer con él,
    que es medio camino. El sentido contrario también importa: una ficha
    huérfana describe una regla que el motor ya no tiene.
    """
    from app.modules.investment.analysis.engine.flag_catalog import FLAG_HELP

    del_catalogo = set(FLAG_LABELS)
    de_la_ficha = set(FLAG_HELP)
    assert del_catalogo - de_la_ficha == set(), "banderas nombradas pero sin explicar"
    assert de_la_ficha - del_catalogo == set(), "fichas huérfanas: la bandera ya no existe"


def test_las_fichas_de_bandera_son_utiles_y_no_escriben_umbrales() -> None:
    """Los mismos criterios que las fichas de score, más uno propio.

    `how_to_verify` es lo que convierte una bandera en una escuela de lectura
    forense en vez de en un oráculo: sin él, el usuario sabe que algo pasa y no
    dónde mirar. Y el gate de umbrales muerde aquí especialmente, porque el
    MENSAJE de la bandera encendida sí cita sus cortes —los redacta el motor con
    los valores del run— y la tentación al escribir la ficha es repetirlos a
    mano, donde caducan.
    """
    from app.modules.investment.analysis.engine.flag_catalog import FLAG_HELP

    pobres: list[str] = []
    for key, ficha in FLAG_HELP.items():
        campos = (
            ("what", ficha.what, 40),
            ("why", ficha.why, 40),
            ("reading", ficha.reading, 20),
            ("how_to_verify", ficha.how_to_verify, 20),
        )
        for campo, texto, minimo in campos:
            limpio = texto.strip()
            if len(limpio) < minimo:
                pobres.append(f"{key}.{campo}: demasiado corta ({len(limpio)})")
            elif len(limpio) > 320:
                pobres.append(f"{key}.{campo}: demasiado larga ({len(limpio)})")
            if (m := _CUT_IN_PROSE.search(limpio)) is not None:
                pobres.append(f"{key}.{campo}: escribe un umbral, {m.group(0)!r}")
        if ficha.what.strip().lower().rstrip(".") == FLAG_LABELS[key].strip().lower():
            pobres.append(f"{key}: la definición repite la etiqueta")
        if _token_overlap(ficha.what, ficha.why) > 0.6:
            pobres.append(f"{key}: 'why' repite 'what' en vez de decir por qué importa")
    assert pobres == [], pobres
