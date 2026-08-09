"""Parser de los ficheros FULINS de FIRDS (PHASE-44.14, ADR-0010).

FIRDS es el registro regulatorio de instrumentos: ESMA publica el universo
UE/EEA y la FCA el de UK, semanalmente, en XML ISO 20022 (`auth.017.001.02`).
Este módulo convierte esos ficheros en filas de `listing_directory`.

**Streaming obligatorio.** Los ficheros reales del 2026-08-01 miden 366 MB
(ESMA parte 1) y 809 MB (FCA) descomprimidos; se recorren con
`lxml.iterparse` liberando cada elemento. Cargarlos enteros está prohibido.

**El MIC que se almacena es el OPERATIVO, no el segmento.** Éste es el hallazgo
que obligó a desviarse de la letra del plan (verificado contra los ficheros
reales y el registro ISO 10383 el 2026-08-07): FIRDS reporta el mercado
principal alemán como `XETA` (segmento «Regulierter Markt» de Xetra), nunca como
`XETR`, y la Bolsa de Madrid como `XMAD`, que a su vez es un segmento del
operativo `BMEX`. Con el filtro literal del plan («los MICs del mapa de
sufijos») Alemania entera quedaba fuera — Allianz no aparecía en ninguna plaza.
La normalización segmento→operativo de `SEED_SEGMENT_TO_OPERATING` hace que la
columna `mic` hable el mismo vocabulario que `securities.exchange` y que el mapa
de sufijos del proveedor de precios.

Módulo sin BD ni red: recibe un manejador de fichero y produce registros. El
I/O de descarga vive en `scripts/seed_listing_directory.py`.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

# lxml no publica stubs (PEP 561) — mismo tratamiento que APScheduler en
# `core/scheduler.py`: se silencia el aviso aquí, el resto del módulo tipa.
from lxml import etree  # type: ignore[import-untyped]

_NS = "urn:iso:std:iso:20022:tech:xsd:auth.017.001.02"


def _q(tag: str) -> str:
    return f"{{{_NS}}}{tag}"


#: Prefijos CFI (ISO 10962) admitidos. `ES` = acciones ordinarias/preferentes.
#: Ampliar a ETFs algún día es añadir `'CE'` aquí y re-ejecutar el seed —
#: decisión del usuario ya tomada (plan E5 §9): NO entran ahora.
INCLUDE_CFI_PREFIXES: tuple[str, ...] = ("ES",)

#: Segmento FIRDS admitido → MIC OPERATIVO que se almacena.
#:
#: Curado contra el registro ISO 10383 (CSV oficial de iso20022.org, consultado
#: el 2026-08-07) y contra la distribución real de los FULINS. Entran SÓLO los
#: segmentos de **mercado regulado principal**; quedan fuera por construcción:
#:
#: - Los MTF pan-europeos (Aquis `AQE*`, CBOE `CEU*`, Turquoise `TQE*`,
#:   Euronext-tras-Brexit `EBLX/ENTW`…): cotizan lo mismo que la plaza
#:   principal y duplicarían cada emisor N veces.
#: - Los tablones de cotización alemanes (Frankfurt `FRA*` — 12.298 filas de
#:   equity ella sola —, Stuttgart, Múnich, Hamburgo, Düsseldorf, y el
#:   Freiverkehr de Xetra `XETB`): cotizan el mundo entero por cruce, incluidos
#:   los valores US que ya tienen identidad vía EDGAR. Por eso `XFRA` tampoco
#:   se siembra aunque el mapa de sufijos sepa cotizarlo (`.F` queda para altas
#:   manuales).
#: - Los mercados SME/growth (AIM `AIMX`, Euronext Growth `ALX*`/`EXGM`, First
#:   North `FN*`, Xetra Scale `XETS`, BME Growth): decisión de alcance, no
#:   técnica — puede revisarse añadiendo filas aquí.
#: - Los segmentos de facility (dark, midpoint, after-hours `MTAH`, subastas a
#:   demanda, multi-divisa `XAMC`/`XPMC`): mismas admisiones que su mercado
#:   principal con matices que aquí no aportan.
#:
#: Los tres segmentos regulados de Xetra (`XETA`/`XETU`/`XEMA`) colapsan al
#: mismo `(isin, XETR)`; `_PRIORITY` decide cuál manda cuando aparecen varios.
SEED_SEGMENT_TO_OPERATING: dict[str, str] = {
    # España — BME. `XMAD` es el segmento SIBE del operativo `BMEX`; se almacena
    # `XMAD` porque es lo que ya habla el mapa de sufijos y la columna exchange.
    "XMAD": "XMAD",
    # UK — LSE Main Market (del fichero de la FCA).
    "XLON": "XLON",
    # Alemania — Xetra, mercado regulado (parqué, off-book y midpoint).
    "XETA": "XETR",
    "XETU": "XETR",
    "XEMA": "XETR",
    # Euronext.
    "XPAR": "XPAR",
    "XAMS": "XAMS",
    "XBRU": "XBRU",
    "XLIS": "XLIS",
    # Italia — Borsa Italiana / Euronext Milan.
    "MTAA": "XMIL",
    "XMIL": "XMIL",
    # Austria — Wiener Börse, mercado oficial.
    "WBAH": "XWBO",
    "WBMA": "XWBO",
    "XVIE": "XWBO",
    "XWBO": "XWBO",
    # Nórdicos — Nasdaq OMX y Oslo Børs.
    "XCSE": "XCSE",
    "XSTO": "XSTO",
    "XHEL": "XHEL",
    "XOSL": "XOSL",
}

#: Venues cuya fuente autoritativa es la FCA (jurisdicción UK). El resto del
#: mapa pertenece a ESMA.
#:
#: La partición NO es cosmética: el FULINS de la FCA trae también registros de
#: venues europeos (Kontron y Commerzbank en XETR, valores de Oslo y Estocolmo…)
#: — verificado contra el fichero real del 2026-08-01, donde lo cazó el dry-run
#: del seed con un choque de PK. Cada registro se queda con la jurisdicción de
#: su regulador: sin esto, el mismo `(isin, mic)` entra por las dos fuentes y
#: la sincronización por-fuente (que asume particiones disjuntas) revienta.
UK_VENUES: frozenset[str] = frozenset({"XLON"})


def partition_for_source(
    records: dict[tuple[str, str], FirdsRecord], *, source: str
) -> dict[tuple[str, str], FirdsRecord]:
    """Se queda con las filas de la jurisdicción de `source` (`ESMA` | `FCA`)."""
    if source == "FCA":
        return {k: v for k, v in records.items() if k[1] in UK_VENUES}
    return {k: v for k, v in records.items() if k[1] not in UK_VENUES}


#: Cuando dos segmentos colapsan al mismo `(isin, operativo)` en una pasada,
#: manda el de menor rango: el parqué principal sobre el off-book/midpoint.
#: Determinista — el resultado del seed no depende del orden del fichero.
_PRIORITY: dict[str, int] = {
    "XMAD": 0,
    "XLON": 0,
    "XPAR": 0,
    "XAMS": 0,
    "XBRU": 0,
    "XLIS": 0,
    "XETA": 0,
    "MTAA": 0,
    "WBAH": 0,
    "XVIE": 1,
    "XWBO": 0,
    "XCSE": 0,
    "XSTO": 0,
    "XHEL": 0,
    "XOSL": 0,
    "XMIL": 1,
    "XETU": 1,
    "WBMA": 1,
    "XEMA": 2,
}


@dataclass(frozen=True, slots=True)
class FirdsRecord:
    """Una fila candidata a `listing_directory`, ya filtrada y normalizada."""

    isin: str
    mic: str
    """MIC OPERATIVO (normalizado), no el segmento del fichero."""
    segment_mic: str
    """El segmento con el que reportó FIRDS — sólo para la prioridad de colapso."""
    name: str
    short_name: str | None
    currency: str
    cfi: str
    lei: str | None
    first_trade_date: date | None
    termination_date: date | None


def _parse_date(value: str | None) -> date | None:
    """`FrstTradDt` llega como datetime ISO (`2022-11-11T07:30:00Z`) y
    `TermntnDt` a veces como fecha a secas. Se queda la fecha."""
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def parse_fulins(fh, *, today: date) -> Iterator[FirdsRecord]:  # type: ignore[no-untyped-def]
    """Recorre un FULINS descomprimido y produce las filas que pasan el filtro.

    Filtro (plan E5 §2.4): CFI en `INCLUDE_CFI_PREFIXES`, segmento en
    `SEED_SEGMENT_TO_OPERATING`, y sin `TermntnDt` pasada. `today` viene del
    caller — este módulo no mira el reloj (misma disciplina que el engine).

    NO deduplica: el mismo `(isin, operativo)` puede salir varias veces (tres
    segmentos de Xetra, o el mismo par repetido entre ficheros). El colapso lo
    hace `collapse_records`, que necesita ver el lote entero.
    """
    for _, elem in etree.iterparse(fh, events=("end",), tag=_q("RefData")):
        gnl = elem.find(_q("FinInstrmGnlAttrbts"))
        ven = elem.find(_q("TradgVnRltdAttrbts"))
        if gnl is not None and ven is not None:
            cfi = gnl.findtext(_q("ClssfctnTp")) or ""
            segment = (ven.findtext(_q("Id")) or "").strip().upper()
            operating = SEED_SEGMENT_TO_OPERATING.get(segment)
            if cfi.startswith(INCLUDE_CFI_PREFIXES) and operating is not None:
                isin = (gnl.findtext(_q("Id")) or "").strip().upper()
                currency = (gnl.findtext(_q("NtnlCcy")) or "").strip().upper()
                termination = _parse_date(ven.findtext(_q("TermntnDt")))
                expired = termination is not None and termination <= today
                if len(isin) == 12 and currency and not expired:
                    yield FirdsRecord(
                        isin=isin,
                        mic=operating,
                        segment_mic=segment,
                        name=(gnl.findtext(_q("FullNm")) or "").strip(),
                        short_name=(gnl.findtext(_q("ShrtNm")) or "").strip() or None,
                        currency=currency,
                        cfi=cfi,
                        lei=(elem.findtext(_q("Issr")) or "").strip() or None,
                        first_trade_date=_parse_date(ven.findtext(_q("FrstTradDt"))),
                        termination_date=termination,
                    )
        # Liberar memoria: sin esto, 800 MB de XML acaban residentes.
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]


def collapse_records(records: Iterator[FirdsRecord]) -> dict[tuple[str, str], FirdsRecord]:
    """Un `(isin, operativo)` → un registro, eligiendo el segmento de mayor
    prioridad. Determinista: no depende del orden de los ficheros."""
    best: dict[tuple[str, str], FirdsRecord] = {}
    for record in records:
        key = (record.isin, record.mic)
        current = best.get(key)
        if current is None or _PRIORITY.get(record.segment_mic, 99) < _PRIORITY.get(
            current.segment_mic, 99
        ):
            best[key] = record
    return best
