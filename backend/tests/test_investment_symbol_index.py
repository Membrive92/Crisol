"""Contrato con el parquet de emisores de `edgartools` (PHASE-44.8 E2).

**Este test llama a la librería de verdad, y ésa es su razón de ser.** El resto
de la fase se prueba con filas sintéticas, que verifican la lógica pero no la
integración: si `edgartools` renombra la función o la columna, el índice se queda
vacío y el buscador enmudece **sin lanzar nada** — el modo de fallo se lee como
«no hay coincidencias», no como un bug. Es la lección [PHASE-44.6] aplicada aquí:
la forma de salida de una librería se prueba, no se deduce.

Dos trampas concretas que este fichero vigila, ambas descubiertas ejecutándola:

1. `get_company_tickers(as_dataframe=False)` devuelve la tabla **sin la columna
   `exchange`**, pese a que su docstring la promete. Con esa vía todas las plazas
   habrían salido `UNKNOWN` en silencio, y con ellas el desempate NYSE > OTC que
   decide qué fila representa a cada emisor.
2. No hace red. El parquet viene empaquetado, y de eso depende que el buscador
   funcione sin conexión.
"""

from __future__ import annotations

import pytest

from app.modules.investment.catalog import symbol_index
from app.modules.investment.catalog.venues import UNKNOWN

pytestmark = pytest.mark.usefixtures("_real_symbol_index")


@pytest.fixture
def _real_symbol_index():  # type: ignore[no-untyped-def]
    """Fuerza el índice REAL, y lo deja como estaba al terminar."""
    symbol_index.reset_index_for_tests()
    yield
    symbol_index.reset_index_for_tests()


def test_el_indice_carga_y_tiene_el_tamano_esperado() -> None:
    """Cero filas con la librería instalada = su API cambió. Falla ruidosamente
    en vez de dejar el buscador mudo."""
    index = symbol_index.load_index()
    assert index.size > 9000, f"el parquet trajo {index.size} filas"
    assert symbol_index.index_ready() is True
    assert len(index.vocabulary) > 5000


def test_la_columna_de_plaza_llega_informada() -> None:
    """La trampa nº1: existe una vía de carga que la pierde entera.

    Se exige una MAYORÍA con plaza conocida, no el 100 %: el fichero real trae
    224 nulos legítimos y fijar el número exacto sería un test que se rompe cada
    vez que la SEC actualiza su listado.
    """
    rows = symbol_index.load_index().rows
    conocidas = sum(1 for r in rows if r.venue != UNKNOWN)
    assert conocidas > len(rows) * 0.9, f"sólo {conocidas}/{len(rows)} tienen plaza"
    assert {r.venue for r in rows} >= {"NYSE", "NASDAQ", "OTC"}


def test_mcdonalds_esta_con_su_cik_y_su_plaza_reales() -> None:
    """Ancla concreta: si esto cambia, cambió el fichero, no el código."""
    hits = symbol_index.search_index("MCD", limit=5)
    mcd = next(r for r in hits if r.ticker == "MCD")
    assert mcd.cik == 63908
    assert mcd.venue == "NYSE"
    assert "MCDONALD" in mcd.name.upper()


def test_encuentra_lo_que_la_gente_teclea() -> None:
    """La deuda que abrió esta entrega: `Macdonald` daba cero.

    La SEC escribe `MCDONALDS CORP` —sin apóstrofo—, así que ninguna subcadena
    de `Macdonald` casa. Lo resuelve el fuzzy sobre tokens.
    """
    for query in ("mcdonald", "Macdonald", "MCDONALDS"):
        tickers = [r.ticker for r in symbol_index.search_index(query, limit=5)]
        assert "MCD" in tickers, f"{query!r} no encontró McDonald's"


def test_los_duplicados_del_mismo_emisor_no_salen_dos_veces() -> None:
    """`Banco Santander, S.A.` está como SAN/NYSE y BCDRF/OTC con el mismo CIK."""
    rows = symbol_index.search_index("santander", limit=10)
    ciks = [r.cik for r in rows]
    assert len(ciks) == len(set(ciks)), "un emisor debe aparecer una sola vez"
    assert "SAN" in [r.ticker for r in rows]


def test_no_devuelve_aditxt_a_quien_busca_inditex() -> None:
    """`ITX` es subcadena de `ADITXT`. Con un `LIKE %itx%` sale `ADTX`."""
    assert "ADTX" not in [r.ticker for r in symbol_index.search_index("itx", limit=10)]
