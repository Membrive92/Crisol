"""Índice en memoria de los emisores que conoce la SEC (PHASE-44.8 E2, ADR-0008).

Único fichero del proyecto que sabe DE DÓNDE sale el índice. El resto del
catálogo consume `search_index()` y recibe `IndexRow`, así que cambiar la fuente
(parquet empaquetado → fichero vivo de la SEC → otra librería) no toca nada más.

**Por qué en memoria y no una tabla.** Son 10.365 filas que llegan en 0,3 s desde
un parquet empaquetado con `edgartools`. Una tabla obligaría a un seed, a un cron
y a mantener la sincronía con la SEC — y el ARCHITECTURE del módulo rechaza
explícitamente el scheduler aquí. El índice se carga perezosamente la primera vez
que alguien busca y se queda.

**Sin red.** Ésta es la propiedad que hace útil al buscador: `get_company_tickers`
lee el parquet que viene dentro del paquete. Verificado con la red cortada.

Dos trampas de la librería, ambas encontradas ejecutándola y no leyéndola
(lección [PHASE-44.6]):

1. `get_company_tickers(as_dataframe=False)` devuelve la tabla **sin la columna
   `exchange`**, pese a que el docstring la promete. Con esa vía todas las plazas
   habrían salido `UNKNOWN` —en silencio— y con ellas el desempate NYSE > OTC que
   decide qué fila representa a cada emisor. Por eso se usa la de pandas.
2. El `exchange` de 224 filas es nulo, y llega como `float('nan')` de pandas, no
   como `None`: hay que preguntar por él con cuidado o `normalize_venue` recibe
   la cadena `'NAN'` y la trata como un MIC de tres letras.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from app.modules.investment.catalog.ranking import IndexRow, tokenize
from app.modules.investment.catalog.venues import normalize_venue

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SymbolIndex:
    """El índice cargado. `vocabulary` es el conjunto de tokens para el fuzzy."""

    rows: tuple[IndexRow, ...]
    vocabulary: tuple[str, ...]

    @property
    def size(self) -> int:
        return len(self.rows)


_EMPTY = SymbolIndex(rows=(), vocabulary=())

#: El índice se construye una vez. `Lock` y no `functools.lru_cache` porque hace
#: falta poder distinguir «no cargado todavía» de «cargado y vacío» —
#: `index_ready()` es lo que permite a la UI decir «el índice no está disponible»
#: en vez de pintar cero resultados como si no hubiera coincidencias.
_lock = threading.Lock()
_index: SymbolIndex | None = None


def _build() -> SymbolIndex:
    """Lee el parquet empaquetado y materializa las filas. Bloqueante."""
    # `import` dentro de la función a propósito: `edgar` arrastra pandas y son
    # ~1 s de arranque que no se pagan si nadie busca. Además `pandas` entra
    # como transitiva de `edgartools` y no está declarada en `pyproject.toml`
    # (anotado en el backlog); tenerla contenida aquí acota el daño el día que
    # eso se resuelva.
    from edgar import get_company_tickers

    frame = get_company_tickers()
    rows: list[IndexRow] = []
    vocabulary: set[str] = set()

    for record in frame.itertuples(index=False):
        ticker = str(getattr(record, "ticker", "") or "").strip().upper()
        name = str(getattr(record, "company", "") or "").strip()
        if not ticker or not name:
            continue
        try:
            cik = int(record.cik)
        except (AttributeError, TypeError, ValueError):
            # Sin CIK no hay identidad con la que colapsar ni con la que
            # ingerir: la fila no sirve para nada de lo que hace este módulo.
            continue

        raw_venue = getattr(record, "exchange", None)
        # Los nulos de pandas son `float('nan')`, que es `!= nan` consigo mismo.
        # Pasarlos por `str()` daría `'NAN'`, que `normalize_venue` aceptaría
        # como MIC de tres letras... y no lo es.
        venue_text = None if raw_venue is None or raw_venue != raw_venue else str(raw_venue)
        venue = normalize_venue(venue_text)

        tokens = tokenize(name)
        vocabulary.update(t for t in tokens if len(t) >= 3)
        rows.append(
            IndexRow(
                cik=cik,
                ticker=ticker,
                venue=venue,
                name=name,
                name_upper=name.upper(),
                tokens=tokens,
            )
        )

    return SymbolIndex(rows=tuple(rows), vocabulary=tuple(sorted(vocabulary)))


def load_index() -> SymbolIndex:
    """Devuelve el índice, construyéndolo la primera vez. Bloqueante.

    Un fallo al construirlo **no** propaga: el buscador debe seguir sirviendo la
    capa del catálogo local aunque la librería cambie de API. Pero tampoco se
    finge éxito — el índice queda vacío y `index_ready()` dice `False`, que es
    lo que la pantalla necesita para no presentar «0 resultados» como si fuera
    una respuesta.
    """
    global _index
    if _index is not None:
        return _index
    with _lock:
        if _index is not None:
            return _index
        try:
            built = _build()
        except Exception:
            logger.exception("symbol_index: no se pudo construir el índice de la SEC")
            built = _EMPTY
        else:
            if not built.rows:
                # Cero filas con la librería instalada significa que su API
                # cambió (renombró la función o la columna). Es el modo de fallo
                # traicionero: no lanza nada y el buscador se queda mudo.
                logger.warning("symbol_index: el parquet de edgartools devolvió 0 filas")
            else:
                logger.info("symbol_index: %s emisores cargados", built.size)
        _index = built
        return _index


def index_ready() -> bool:
    """Si el índice tiene filas utilizables. `False` mientras no se haya cargado."""
    return _index is not None and bool(_index.rows)


#: Por debajo de tantos aciertos exactos se intenta el fuzzy. No se dispara
#: siempre porque corregir la ortografía de una consulta que YA encuentra cosas
#: sólo puede empeorar la lista.
_FUZZY_TRIGGER = 3


def search_index(q: str, *, limit: int, allow_fuzzy: bool = True) -> list[IndexRow]:
    """Busca en el índice. Bloqueante — el caller lo saca del event loop.

    El fuzzy es una red de seguridad, no la vía principal: sólo entra cuando el
    emparejado exacto se queda corto. Es lo que hace que `Macdonald` encuentre
    `MCDONALDS CORP` (la SEC lo escribe sin apóstrofo, así que no hay subcadena
    que valga) sin ensuciar las consultas que ya funcionan.

    **`allow_fuzzy=False` existe porque «último recurso» tiene que serlo entre
    TODAS las capas, no dentro de ésta.** Con el directorio UE/UK sembrado
    (PHASE-44.14) apareció el caso que lo demuestra: `allianz` tiene CERO
    coincidencias exactas en la SEC, así que el fuzzy proponía `ALLIANT` y
    `ALLIANCE` —otras empresas— y esas filas llenaban el cupo **antes** de que
    el directorio, que tiene `Allianz SE` con coincidencia exacta de nombre,
    llegase a tener sitio. El buscador por capas pide primero lo exacto de aquí,
    luego el directorio, y sólo entonces vuelve a por el fuzzy.
    """
    query = q.strip()
    if not query:
        return []

    index = load_index()
    if not index.rows:
        return []

    from app.modules.investment.catalog.ranking import fuzzy_token_candidates, rank_rows

    hits = rank_rows(index.rows, query, limit=limit)
    if not allow_fuzzy or len(hits) >= _FUZZY_TRIGGER:
        return hits

    candidates = fuzzy_token_candidates(index.vocabulary, query)
    if not candidates:
        return hits

    seen = {row.cik for row in hits}
    extra: list[IndexRow] = []
    for token in candidates:
        for row in rank_rows(index.rows, token, limit=limit):
            if row.cik not in seen:
                seen.add(row.cik)
                extra.append(row)
    return (hits + extra)[:limit]


def reset_index_for_tests() -> None:
    """Vacía la caché. Sólo para tests — un índice cargado sobrevive al módulo."""
    global _index
    with _lock:
        _index = None


def set_index_for_tests(rows: tuple[IndexRow, ...]) -> None:
    """Sustituye el índice por uno controlado.

    Los tests de la API no deben depender del contenido del parquet: son 10.365
    emisores reales y cualquier aserción sobre «qué sale primero» se rompería con
    un bump de la librería por motivos que no tienen nada que ver con el código
    que prueban. El contrato con la librería lo verifica un test aparte, que sí
    la llama de verdad.
    """
    global _index
    vocabulary = sorted({token for row in rows for token in row.tokens if len(token) >= 3})
    with _lock:
        _index = SymbolIndex(rows=rows, vocabulary=tuple(vocabulary))
