"""Relevancia y colapso de resultados del buscador (PHASE-44.8 E2, ADR-0008).

Módulo **PURO**: sin BD, sin red, sin reloj, sin pandas. Recibe filas ya
materializadas (`IndexRow`) y decide qué sale y en qué orden, de modo que la
relevancia es determinista y se puede probar sin levantar nada.

Las tres reglas que gobiernan esto salen de mirar el fichero real de la SEC, no
de la intuición (10.365 tickers, 7.992 CIKs, sondeado el 2026-08-07):

1. **El colapso es por CIK, no por `(ticker, plaza)`.** Un emisor aparece varias
   veces: `Banco Santander, S.A.` está como `SAN`/NYSE y como `BCDRF`/OTC con el
   MISMO cik 891478; `Santander UK plc` sale dos veces (`SNTUF`, `STNDF`) y
   `Santander Bank Polska` otras dos (`BKZHY`, `BKZHF`). Sin colapsar, buscar
   «santander» devuelve 8 filas de las que 3 son duplicados, y la buena —la
   cotización principal— queda sepultada.

2. **La subcadena de nombre sólo vale para consultas largas.** `ITX` es
   subcadena de `ADITXT`, así que un `LIKE %itx%` devuelve `ADTX · Aditxt, Inc.`
   para quien busca Inditex. Con consultas cortas se exige que un token
   EMPIECE por lo tecleado, que es como se escribe el principio de un nombre.

3. **El fuzzy va contra los TOKENS, no contra el nombre entero.** La SEC escribe
   `MCDONALDS CORP` (sin apóstrofo), y comparar `MACDONALD` con el nombre
   completo no pasa del umbral por culpa del ` CORP`. Contra el vocabulario de
   tokens sí: `MACDONALD` → `MCDONALDS`.
"""

from __future__ import annotations

import difflib
from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.investment.catalog.venues import venue_rank

#: Por debajo de esta longitud, una consulta NO activa el predicado de subcadena
#: de nombre (regla 2 del docstring). Cuatro caracteres es donde deja de haber
#: colisiones tontas: con 3 basta `ITX` dentro de `ADITXT` para envenenar la
#: lista.
MIN_SUBSTRING_QUERY = 4

#: Idem para el fuzzy: corregir la ortografía de algo de 3 letras es adivinar.
MIN_FUZZY_QUERY = 5

#: Umbral de `difflib`. 0,8 acepta `MACDONALD`→`MCDONALDS` y `COCACOLA`→
#: `COCA-COLA` y rechaza `SANTANDR`→`STANDARD`, que es el falso positivo que
#: aparece al bajarlo.
FUZZY_CUTOFF = 0.8

#: Tickers que la gente teclea y que no existen en NINGUNA de las capas locales
#: — ni el índice de la SEC (E2) ni el directorio FIRDS UE/UK (PHASE-44.14).
#: Verificado contra ambos el 2026-08-07: esta lista es de ausencias
#: COMPROBADAS, no una colección de sinónimos, y ésa es la razón de que el
#: motivo viva aquí y no en el mensaje de un commit.
#:
#: Con el directorio sembrado, Inditex, Iberdrola y BMW SALEN de verdad (sus
#: `ShrtNm` de FIRDS llevan el ticker local — `ITX/AC 0.03`), así que quedaron
#: FUERA de esta lista: avisar de «no existe» sobre una consulta que devuelve
#: resultados sería mentir en la otra dirección. Lo que queda es la frontera
#: suiza (ADR-0010 §5): SIX no reporta ni a ESMA ni a la FCA, y sus valores
#: entran por alta manual o por su ADR estadounidense.
MISSING_NON_US_ISSUERS: dict[str, str] = {
    "NESN": "Nestlé",
    "ROG": "Roche",
    "NOVN": "Novartis",
}

#: Igual que la anterior, pero el motivo de la ausencia es la estructura del
#: fondo, no el país.
MISSING_OPEN_END_ETFS: dict[str, str] = {
    "VOO": "Vanguard S&P 500 ETF",
    "VTI": "Vanguard Total Stock Market ETF",
    "IVV": "iShares Core S&P 500 ETF",
    "SCHD": "Schwab US Dividend Equity ETF",
}


@dataclass(frozen=True, slots=True)
class IndexRow:
    """Una fila del índice de la SEC, ya normalizada.

    `tokens` se precalcula al construir el índice: hacerlo por consulta serían
    10.365 particiones de cadena por pulsación.
    """

    cik: int
    ticker: str
    venue: str
    name: str
    name_upper: str
    tokens: tuple[str, ...]


def tokenize(name: str) -> tuple[str, ...]:
    """Parte un nombre en tokens comparables.

    Los separadores salen de los nombres reales: `Coca-Cola Consolidated, Inc.`,
    `Banco Santander, S.A.`, `Moelis & Co`. El guion se parte además de
    conservarse entero, para que tanto `COCA` como `COCA-COLA` encuentren la
    fila.
    """
    cleaned = name.upper()
    for sep in (",", ".", "/", "&", "(", ")", "'"):
        cleaned = cleaned.replace(sep, " ")
    parts: list[str] = []
    for raw in cleaned.split():
        if not raw:
            continue
        parts.append(raw)
        if "-" in raw:
            parts.extend(p for p in raw.split("-") if p)
    # `dict.fromkeys` deduplica conservando el orden — importa porque el primer
    # token es el más significativo del nombre.
    return tuple(dict.fromkeys(parts))


def relevance_score(row: IndexRow, q: str) -> int:
    """Cuánto encaja `row` con la consulta. `0` = no encaja (se descarta).

    Los tramos están separados por 100 para que la prominencia de plaza (0-99,
    de `venue_rank`) desempate DENTRO de un tramo y nunca salte de tramo: que
    una coincidencia exacta de ticker en OTC gane a un prefijo de nombre en NYSE
    es deliberado; al revés sería que la plaza decidiera la relevancia.
    """
    query = q.strip().upper()
    if not query:
        return 0

    base = 0
    if row.ticker == query:
        base = 1000
    elif row.ticker.startswith(query) and len(query) >= 2:
        base = 900
    elif any(t == query for t in row.tokens):
        base = 800
    elif any(t.startswith(query) for t in row.tokens):
        base = 700
    elif row.name_upper.startswith(query):
        base = 600
    elif len(query) >= MIN_SUBSTRING_QUERY and query in row.name_upper:
        base = 500

    if base == 0:
        return 0
    return base - venue_rank(row.venue)


def fuzzy_token_candidates(vocabulary: tuple[str, ...], q: str) -> tuple[str, ...]:
    """Tokens del vocabulario que se parecen a `q` (ortografía aproximada).

    Se llama SÓLO cuando el emparejado exacto se queda corto: es una red de
    seguridad para `Macdonald`, no la vía principal. Devolver aquí de más
    ensuciaría los resultados buenos.
    """
    query = q.strip().upper()
    if len(query) < MIN_FUZZY_QUERY:
        return ()
    return tuple(difflib.get_close_matches(query, vocabulary, n=3, cutoff=FUZZY_CUTOFF))


def collapse_by_cik(rows: Sequence[tuple[IndexRow, int]]) -> list[tuple[IndexRow, int]]:
    """Un emisor, una fila: se queda la de plaza más prominente.

    **Por CIK y no por `(ticker, plaza)`**, que es la parte contraintuitiva: las
    filas antiguas del catálogo llevan `exchange='US'` y el índice dice `NYSE`,
    así que el par no coincidiría y el mismo emisor saldría dos veces — pulsando
    la segunda se crearía un `Security` duplicado, que es justo el daño que este
    buscador viene a evitar.

    Empate de plaza: gana la de mayor puntuación y, si también empata, el ticker
    más corto (`SAN` antes que `BCDRF` — el principal suele serlo).
    """
    best: dict[int, tuple[IndexRow, int]] = {}
    for row, score in rows:
        current = best.get(row.cik)
        if current is None:
            best[row.cik] = (row, score)
            continue
        cur_row, cur_score = current
        challenger = (venue_rank(row.venue), -score, len(row.ticker), row.ticker)
        incumbent = (venue_rank(cur_row.venue), -cur_score, len(cur_row.ticker), cur_row.ticker)
        if challenger < incumbent:
            # La puntuación que sobrevive es la MEJOR de las dos, no la de la
            # fila elegida: si el usuario tecleó el ticker OTC exacto, ese
            # emisor debe seguir arriba aunque se le muestre su línea principal.
            best[row.cik] = (row, max(score, cur_score))
        elif score > cur_score:
            best[row.cik] = (cur_row, score)
    return list(best.values())


#: Tokens que son forma jurídica o ruido societario, no parte del nombre. No
#: cuentan para decidir cuál de dos coincidencias es «más exacta»: `Banco
#: Santander, S.A.` y `BANCO SANTANDER CHILE` tienen los mismos tokens útiles
#: más uno, y ese uno (CHILE) es lo que las distingue.
_LEGAL_FORM_TOKENS = frozenset(
    {
        "S",
        "A",
        "SA",
        "SAB",
        "CV",
        "DE",
        "NV",
        "AG",
        "AB",
        "AS",
        "ASA",
        "OYJ",
        "PLC",
        "LTD",
        "LIMITED",
        "INC",
        "INCORPORATED",
        "CORP",
        "CORPORATION",
        "CO",
        "COMPANY",
        "GROUP",
        "HOLDING",
        "HOLDINGS",
        "THE",
        "SE",
        "SPA",
        "GMBH",
        "KGAA",
        "NPV",
        "ORD",
        "CLASS",
        "TRUST",
    }
)


def name_specificity(row: IndexRow) -> int:
    """Cuántos tokens SIGNIFICATIVOS tiene el nombre. Menos = más exacto.

    Es el desempate entre coincidencias de la misma fuerza, y sale de mirar el
    dato: buscar «santander» empata a `Banco Santander, S.A.` (2 tokens útiles),
    `Banco Santander (Brasil) S.A.` (3) y `BANCO SANTANDER CHILE` (3), y sin
    esto ordenaba el ticker alfabéticamente — así que la matriz salía tercera,
    detrás de sus dos filiales. Quien busca un emisor por su nombre quiere el
    que se llama ASÍ, no el que se llama así **y además** otra cosa.
    """
    return sum(1 for token in row.tokens if token not in _LEGAL_FORM_TOKENS)


def rank_rows(rows: Sequence[IndexRow], q: str, *, limit: int) -> list[IndexRow]:
    """Puntúa, descarta lo que no encaja, colapsa por emisor y ordena.

    El orden es determinista y en cascada: puntuación (que ya incluye la
    prominencia de plaza), luego el nombre más exacto, y el ticker sólo como
    último recurso para que dos filas idénticas no bailen entre ejecuciones.
    """
    matched = [(row, score) for row in rows if (score := relevance_score(row, q)) > 0]
    collapsed = collapse_by_cik(matched)
    collapsed.sort(key=lambda item: (-item[1], name_specificity(item[0]), item[0].ticker))
    return [row for row, _ in collapsed[:limit]]


def missing_issuer_notice(q: str) -> str | None:
    """Aviso cuando lo buscado es algo que la SEC no lista, con su motivo.

    Existe porque el vacío miente: `ITX` no devuelve nada no porque Inditex no
    exista, sino porque el índice es de emisores de la SEC e Inditex no lo es.
    Un desplegable en blanco se lee como «esa empresa no existe», que es una
    conclusión distinta y falsa.
    """
    key = q.strip().upper()
    issuer = MISSING_NON_US_ISSUERS.get(key)
    if issuer is not None:
        return (
            f"«{key}» es el ticker de {issuer} en la bolsa suiza (SIX), que no "
            "reporta a los registros que cubre este buscador (SEC, ESMA y FCA). "
            "Se puede llevar en cartera dándolo de alta a mano, o analizar vía "
            "su ADR estadounidense si lo tiene."
        )
    fund = MISSING_OPEN_END_ETFS.get(key)
    if fund is not None:
        return (
            f"«{key}» ({fund}) no presenta cuentas propias ante la SEC: los ETF "
            "de estructura abierta no tienen CIK. Sí están los constituidos como "
            "trust, por ejemplo SPY o QQQ."
        )
    return None
