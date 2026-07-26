"""Vocabulario de plazas de cotización — `securities.exchange` (PHASE-44.8 E1,
ADR-0008).

`exchange` guarda **una plaza**, y hasta ahora el frontend escribía ahí `'US'`,
que es un país. El daño no es cosmético: la restricción única de la tabla es
`(ticker, exchange)`, así que `MCD/US` y `MCD/NYSE` son filas distintas para el
mismo emisor — dos ingestas, dos `AnalysisRun` y los lotes de cartera repartidos
entre dos ids.

Vocabulario:

- De la SEC: `NYSE`, `NASDAQ`, `OTC`, `CBOE` — su etiqueta normalizada a
  mayúsculas. Verificado que son los cuatro únicos valores que toma el campo
  `exchange` de `company_tickers_exchange.json` (más 181 nulos).
- De un proveedor externo (Entrega 5): el **MIC ISO 10383 real** que devuelva
  (`XMAD`, `XAMS`, `XETR`…).
- `UNKNOWN` para lo que no se sabe todavía.

**No se fabrica un MIC para las filas de la SEC.** Su fichero no lo trae, y
adivinarlo (¿`XNYS` o `XNGS`?) sería inventar un dato que luego nadie podría
distinguir de uno real. Las mayúsculas no son un capricho: los tests ya persisten
`NYSE` (`tests/test_investment_catalog.py:118`) y el validador del schema sube a
mayúsculas el `nyse` de la línea 97.

Módulo PURO: sin BD, sin red, sin reloj.
"""

from __future__ import annotations

UNKNOWN = "UNKNOWN"

#: Plazas de la SEC, con su etiqueta humana y su prominencia. `rank` ordena los
#: resultados del buscador cuando un mismo emisor cotiza en varias (la Entrega 2
#: colapsa por CIK y se queda con la de menor `rank`): una cotización principal
#: pesa más que un OTC, que suele ser el ADR no patrocinado del mismo emisor.
_SEC_VENUES: dict[str, tuple[str, int]] = {
    "NYSE": ("NYSE", 0),
    "NASDAQ": ("Nasdaq", 1),
    "CBOE": ("Cboe", 2),
    "OTC": ("OTC", 3),
}

#: Lo que NUNCA es una plaza, por mucho que llegue en ese campo. `US` es el valor
#: que escribía `security-search.tsx` y el que sigue mandando el móvil legacy.
_NOT_A_VENUE = frozenset({"US", "USA", "EEUU", "GLOBAL", ""})

#: Alias observados en fuentes reales → vocabulario. La SEC escribe `Nasdaq`.
_ALIASES: dict[str, str] = {
    "NASDAQ GLOBAL SELECT": "NASDAQ",
    "NASDAQ CAPITAL MARKET": "NASDAQ",
    "NYSE AMERICAN": "NYSE",
    "NYSE ARCA": "NYSE",
    "BATS": "CBOE",
    "OTC MARKETS": "OTC",
    "OTCQB": "OTC",
    "OTCQX": "OTC",
    "PINK": "OTC",
}


def normalize_venue(raw: str | None) -> str:
    """Cualquier cosa que llegue → un valor del vocabulario.

    Un país (`'US'`) o una cadena vacía se convierten en `UNKNOWN`, no en una
    plaza inventada: es la diferencia entre «no lo sé» y «afirmo que cotiza
    aquí». La Entrega 2 repunta los `UNKNOWN` a su plaza real cuando el índice
    de la SEC esté cableado.

    Un MIC de cuatro letras (`XMAD`) se acepta tal cual: es un código ISO válido
    y es lo que devolverá el proveedor externo de la Entrega 5.

    Args:
        raw: el valor recibido, de un cliente o de una fuente externa.

    Returns:
        Un valor del vocabulario, siempre en mayúsculas.
    """
    if raw is None:
        return UNKNOWN
    value = raw.strip().upper()
    if value in _NOT_A_VENUE:
        return UNKNOWN
    if value in _SEC_VENUES:
        return value
    if value in _ALIASES:
        return _ALIASES[value]
    # MIC ISO 10383: cuatro alfanuméricos. Se respeta sin traducir.
    if len(value) == 4 and value.isalnum():
        return value
    return UNKNOWN


def venue_label(venue: str) -> str:
    """Etiqueta para pintar en la UI. Un MIC desconocido se muestra tal cual —
    mejor `XMAD` que una traducción inventada."""
    known = _SEC_VENUES.get(venue.upper())
    return known[0] if known else venue.upper()


def venue_rank(venue: str) -> int:
    """Prominencia para ordenar. Lo no catalogado va al final, no en medio."""
    known = _SEC_VENUES.get(venue.upper())
    return known[1] if known else 99


def is_known_venue(venue: str) -> bool:
    """Si la plaza está en el vocabulario de la SEC (no vale un MIC externo).
    Lo usa el test que vigila que nadie vuelva a colar un país en la columna."""
    return venue.upper() in _SEC_VENUES
