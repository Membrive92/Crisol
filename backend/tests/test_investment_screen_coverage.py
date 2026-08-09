"""El catálogo del motor y lo que la pantalla puede pintar no pueden divergir.

**Por qué este gate existe** (PHASE-44.20): la capa compartida
`packages/ui/src/investment-report-sections.ts` cubría **57 de las 64** métricas
del catálogo. Las otras siete (`DUPONT_OM/TAX/FIN`, `E3`, `E4`, `T2`, `T3`)
estaban escritas a mano en tres ficheros de web, así que móvil —que renderiza
estrictamente desde el fichero compartido— no las pintaba nunca.

**Por qué el gate vive en el backend y no en `vitest`.** Hacen falta las dos
puntas: las 64 claves sólo las conoce el engine (Python) y la lista de pantalla
sólo está en TypeScript. Ponerlo en el frontend obligaría a duplicar las 64 en un
fichero TS — que es exactamente la clase de lista escrita a mano que este gate
viene a evitar. Aquí el catálogo se importa de verdad.

**Por qué es una búsqueda de texto y no un parseo.** No hay intérprete de TS en
el entorno del backend. Buscar la clave entrecomillada es tosco pero no puede
derivar: si alguien retira `'E3'` del fichero compartido, la búsqueda falla. El
riesgo contrario —que la clave aparezca en un comentario y no en una lista— se
acota comprobando que está dentro de un array de métricas, no en cualquier sitio.

**Por qué en `make verify` no bastaría**: verificado en `.github/workflows/ci.yml`
— CI **no ejecuta `make verify`**. Corre `pytest` en el job de backend, así que
un gate escrito aquí sí muerde en cada push.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.modules.investment.analysis.engine.catalog import ALL_METRIC_KEYS

_SECTIONS = (
    Path(__file__).resolve().parents[2]
    / "packages"
    / "ui"
    / "src"
    / "investment-report-sections.ts"
)


def _keys_on_screen() -> set[str]:
    """Las claves entrecomilladas que aparecen dentro de un array del fichero.

    Se buscan sólo dentro de `[...]` para que una clave nombrada de pasada en una
    nota o en un comentario no cuente como «tiene sitio en pantalla».
    """
    source = _SECTIONS.read_text(encoding="utf-8")
    # Fuera los comentarios de bloque: sus ejemplos no son contenido pintado.
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = re.sub(r"//[^\n]*", "", source)
    keys: set[str] = set()
    for array in re.findall(r"\[([^\[\]]*)\]", source, flags=re.DOTALL):
        keys.update(re.findall(r"'([A-Za-z0-9_]+)'", array))
    return keys


def test_el_fichero_compartido_existe() -> None:
    """Si alguien lo mueve, este gate tiene que gritar, no pasar en verde."""
    assert _SECTIONS.is_file(), f"no encuentro {_SECTIONS}"


def test_toda_metrica_del_catalogo_tiene_sitio_en_pantalla() -> None:
    """El invariante: lo que el motor calcula, alguna pestaña lo enseña.

    Sin esto, añadir una métrica al engine y olvidar darle sitio no falla en
    ninguna parte: la métrica simplemente no existe para el usuario, en las dos
    apps o en una sola.
    """
    faltan = sorted(set(ALL_METRIC_KEYS) - _keys_on_screen())
    assert not faltan, (
        f"{len(faltan)} métricas del catálogo no tienen sitio en ninguna pestaña: "
        f"{', '.join(faltan)}. Añádelas a la sección que les corresponda en "
        f"packages/ui/src/investment-report-sections.ts — si se pintan sólo desde "
        f"un tab de web, móvil no las verá nunca."
    )


def test_la_pantalla_no_pinta_claves_que_el_motor_no_calcula() -> None:
    """El sentido contrario: una fila fantasma saldría siempre vacía.

    Se acota a las claves con forma de `metric_key` para no tropezar con los
    nombres de pestaña ni con los campos del cuadre DuPont, que no son métricas.
    """
    catalogo = set(ALL_METRIC_KEYS)
    sospechosas = {
        key
        for key in _keys_on_screen()
        if re.fullmatch(r"[A-Z]+[0-9]+[a-z]?|[a-z]+_[a-z]+", key) and key not in catalogo
    }
    # `check_three` / `check_five` son campos del punto DuPont, no métricas.
    sospechosas -= {"check_three", "check_five"}
    assert not sospechosas, (
        f"la pantalla referencia claves que el motor no calcula: {sorted(sospechosas)}. "
        "Saldrían como filas siempre vacías."
    )


@pytest.mark.parametrize("key", ["DUPONT_OM", "DUPONT_TAX", "DUPONT_FIN", "E3", "E4", "T2", "T3"])
def test_las_siete_que_faltaban_estan(key: str) -> None:
    """Regresión nominal de PHASE-44.20.

    El test general de arriba las cubre, pero éste las nombra: si alguien vuelve
    a sacar una de la capa compartida para escribirla a mano en un tab de web, el
    fallo dirá CUÁL y no «faltan 1».
    """
    assert key in _keys_on_screen()
