"""Adapter de precios yfinance (PHASE-44.11.B, ARCHITECTURE §8.1).

Proveedor **primario**: gratis, sin API key y multi-mercado, que es lo que
Finnhub no da (US-only). No es oficial —es un cliente de los endpoints públicos
de Yahoo—, así que se asume que se romperá alguna vez: el diseño ya es
*staleness-tolerant* (un fallo conserva la última cotización y la marca stale) y
la versión va **pineada** en `pyproject.toml`.

Cuatro hechos de la librería, **verificados ejecutándola** (lección PHASE-44.6:
la forma de salida se prueba, no se deduce leyendo la fuente) contra KO, ULVR.L,
IBE.MC, ALV.DE y MC.PA con yfinance 1.5.2:

1. `fast_info` devuelve **`float`**, no `Decimal` (`87.58999633789062`). Se
   convierte con `Decimal(str(...))` y se cuantiza a los 6 decimales de la
   columna. `float` está prohibido en cuanto el número deja esta frontera.
2. `currency` de un valor de Londres es literalmente **`'GBp'`** — peniques.
   4743.0 GBp son 47,43 GBP. Sin la división, el valor de mercado sale 100 veces
   mayor (ver regla 2 de `base.py`).
3. Un símbolo inexistente **lanza `KeyError: 'exchangeTimezoneName'`** al leer
   `last_price` o `currency`, mientras `previous_close` devuelve `None` sin
   quejarse. No hay un "None limpio" que comprobar: hay que capturar ancho.
4. `yf.Tickers` **no batchea de verdad**: agrupa objetos y cada `fast_info`
   dispara su propia petición perezosa. El throttling por símbolo sigue siendo
   necesario, así que no se usa — el lote se recorre serializado aquí.

Y uno de arquitectura: yfinance es **síncrono** (requests/curl_cffi). Cada
lectura va a un hilo con `asyncio.to_thread` para no bloquear el event loop de
FastAPI durante segundos.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from app.modules.investment.pricing.adapters.base import Quote, QuoteError, QuoteRequest

logger = logging.getLogger(__name__)

#: Plaza del catálogo → sufijo de símbolo Yahoo.
#:
#: Las claves son el vocabulario REAL de `securities.exchange`, que produce
#: `catalog/venues.normalize_venue`: las cuatro etiquetas de la SEC o un MIC ISO
#: 10383 de cuatro caracteres. El plan de la fase traía esta tabla escrita como
#: `{LSE, BME, XETRA, EPA, AMS, ...}`, que son etiquetas coloquiales de bolsa y
#: **ninguna sobrevive a `normalize_venue`** (`'LSE'` tiene 3 caracteres y no está
#: en el vocabulario SEC → `UNKNOWN`; `'XETRA'` tiene 5 → `UNKNOWN`). Escrita
#: así no habría acertado una sola fila y toda posición europea habría caído en
#: "exchange sin mapeo", en silencio.
_SUFFIX_BY_VENUE: dict[str, str] = {
    # SEC — el símbolo Yahoo de un valor estadounidense va desnudo.
    "NYSE": "",
    "NASDAQ": "",
    "CBOE": "",
    "OTC": "",
    # MIC ISO 10383. Sólo pueden llegar cuando exista el proveedor externo del
    # buscador (ADR-0008, Entrega 5): hoy el catálogo es 100 % emisores SEC.
    "XLON": ".L",  # London Stock Exchange
    "XMAD": ".MC",  # BME / Bolsa de Madrid
    "XETR": ".DE",  # Xetra
    "XFRA": ".F",  # Frankfurt (parqué)
    "XPAR": ".PA",  # Euronext París
    "XAMS": ".AS",  # Euronext Ámsterdam
    "XBRU": ".BR",  # Euronext Bruselas
    "XLIS": ".LS",  # Euronext Lisboa
    "XMIL": ".MI",  # Borsa Italiana
    "MTAA": ".MI",  # Borsa Italiana (MTA, mismo sufijo)
    "XSWX": ".SW",  # SIX Swiss
    "XVTX": ".SW",  # SIX Swiss (segmento blue chip)
    "XWBO": ".VI",  # Viena
    "XCSE": ".CO",  # Copenhague
    "XSTO": ".ST",  # Estocolmo
    "XHEL": ".HE",  # Helsinki
    "XOSL": ".OL",  # Oslo
}

#: `UNKNOWN` → símbolo desnudo (decisión del usuario, 2026-08-02).
#:
#: No es un mapeo más: es qué hacer cuando NO hay plaza. El fichero de la SEC
#: deja ~181 tickers sin `exchange`, y tratarlos como "sin mapeo" los dejaría
#: sin valorar para siempre siendo valores US perfectamente cotizables. La red
#: que hace esto seguro es la regla D4: si algún día un valor europeo llega con
#: `UNKNOWN` y Yahoo devuelve su homónimo estadounidense, la divisa del
#: proveedor (USD) discrepará de la del catálogo (EUR) y la posición se marca.
_UNKNOWN_VENUE_SUFFIX = ""

#: Divisas en **subunidad** → (divisa ISO real, divisor). Verificado: Yahoo
#: devuelve `'GBp'` para ULVR.L y el precio va en peniques.
#:
#: El match es por la cadena EXACTA que escribe Yahoo, y eso es deliberado:
#: `'GBp'` (peniques) y `'GBP'` (libras) se distinguen **sólo por el case**, así
#: que normalizar a mayúsculas antes de comparar borraría la diferencia y
#: multiplicaría por 100 el valor de toda posición londinense.
_SUBUNIT: dict[str, tuple[str, Decimal]] = {
    "GBp": ("GBP", Decimal(100)),  # peniques
    "ZAc": ("ZAR", Decimal(100)),  # céntimos de rand
}

#: Códigos de subunidad que NO colisionan con ningún ISO-4217 real, así que
#: aquí sí se puede comparar en mayúsculas sin ambigüedad.
_SUBUNIT_UNAMBIGUOUS: dict[str, tuple[str, Decimal]] = {
    "GBX": ("GBP", Decimal(100)),  # alias de penique
    "ILA": ("ILS", Decimal(100)),  # agorot
}

#: Los 6 decimales de `price_quotes.price` (`Numeric(20, 6)`).
_QUANTUM = Decimal("0.000001")


def suffix_for_venue(venue: str) -> str | None:
    """Sufijo Yahoo de una plaza, o `None` si no hay mapeo. Acceso PÚBLICO al
    mapa para el cross-check del alta `ext:` (PHASE-44.14): el sufijo del
    símbolo resuelto debe casar con el MIC elegido en el directorio, y la
    comparación tiene que usar ESTE mapa — dos copias divergirían."""
    return _SUFFIX_BY_VENUE.get(venue.strip().upper())


def to_yahoo_symbol(ticker: str, exchange: str) -> str | None:
    """`(ticker, exchange)` → símbolo Yahoo, o `None` si la plaza no tiene mapeo.

    `None` NO es un fallo del sistema: es "no sé cómo se llama este valor en
    Yahoo", y se traduce en una exclusión estándar con motivo. Inventar un
    sufijo sería peor: devolvería el precio de otro valor.

    Args:
        ticker: el ticker del catálogo (`securities.ticker`).
        exchange: la plaza ya normalizada (`securities.exchange`).

    Returns:
        El símbolo con su sufijo (`'KO'`, `'ULVR.L'`), o `None` si la plaza es
        desconocida y no es `UNKNOWN`.
    """
    symbol = ticker.strip().upper()
    if not symbol:
        return None
    venue = exchange.strip().upper()
    if venue in ("", "UNKNOWN"):
        return symbol + _UNKNOWN_VENUE_SUFFIX
    suffix = _SUFFIX_BY_VENUE.get(venue)
    if suffix is None:
        return None
    return symbol + suffix


_Normalized = tuple[str | None, Decimal, Decimal | None]


def _normalize_currency(raw: object, price: Decimal, prev: Decimal | None) -> _Normalized:
    """Divisa del proveedor → ISO-4217, dividiendo si venía en subunidad.

    Yahoo emite `'GBp'` para Londres: el número está en **peniques**. Se
    devuelve `'GBP'` con los importes entre 100. Una subunidad nunca llega a
    persistirse — el llamante lo comprueba con un assert.

    Returns:
        `(divisa ISO o None, precio, cierre anterior)`. `None` sólo cuando el
        proveedor no declara divisa en absoluto.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None, price, prev
    code = raw.strip()

    subunit = _SUBUNIT.get(code) or _SUBUNIT_UNAMBIGUOUS.get(code.upper())
    if subunit is not None:
        iso, divisor = subunit
        return iso, price / divisor, (prev / divisor if prev is not None else None)

    return code.upper(), price, prev


def _to_decimal(value: object) -> Decimal | None:
    """`float` del proveedor → `Decimal` cuantizado. `bool` es un `int` en
    Python y nunca es un precio, así que se rechaza explícitamente."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not result.is_finite():
        return None
    return result.quantize(_QUANTUM)


class YFinanceAdapter:
    """Implementación de `PriceAdapter` sobre yfinance.

    Serializa el lote con una pausa entre símbolos: el endpoint no es oficial y
    un ráfaga corta invita a que Yahoo corte por IP. Con carteras de decenas de
    posiciones el coste es de segundos y sólo se paga cuando el TTL caduca.
    """

    def __init__(self, *, throttle_seconds: float = 1.0, timeout_seconds: int = 15) -> None:
        self._throttle = max(0.0, throttle_seconds)
        self._timeout = timeout_seconds

    @property
    def enabled(self) -> bool:
        """Siempre activo: no necesita credencial. Es la razón de ser del
        cambio de proveedor por defecto."""
        return True

    async def quotes(self, requests: Sequence[QuoteRequest]) -> dict[str, Quote | QuoteError]:
        results: dict[str, Quote | QuoteError] = {}
        pending: list[tuple[QuoteRequest, str]] = []

        for request in requests:
            symbol = to_yahoo_symbol(request.ticker, request.exchange)
            if symbol is None:
                results[request.key] = QuoteError(
                    reason=f"plaza sin equivalencia en el proveedor ({request.exchange})"
                )
                continue
            pending.append((request, symbol))

        for index, (request, symbol) in enumerate(pending):
            if index > 0 and self._throttle:
                await asyncio.sleep(self._throttle)
            results[request.key] = await asyncio.to_thread(self._fetch_one, symbol)

        return results

    def _fetch_one(self, symbol: str) -> Quote | QuoteError:
        """Lectura SÍNCRONA de un símbolo. Corre en un hilo.

        Captura `Exception` a propósito: el probe demostró que un símbolo
        inexistente sale por `KeyError('exchangeTimezoneName')`, no por una
        excepción de red, y la lista de lo que puede lanzar un cliente no
        oficial no es enumerable. Lo que no puede pasar es que un símbolo malo
        tumbe el lote entero.
        """
        try:
            fast_info = self._fast_info(symbol)
            price = _to_decimal(fast_info.get("last_price"))
            if price is None or price <= 0:
                return QuoteError(reason="el proveedor no devuelve precio para este símbolo")
            prev_close = _to_decimal(fast_info.get("previous_close"))
            currency, price, prev_close = _normalize_currency(
                fast_info.get("currency"), price, prev_close
            )
            return Quote(
                price=price,
                prev_close=prev_close,
                currency=currency,
                as_of=datetime.now(UTC),
            )
        except Exception as exc:
            logger.info("yfinance: sin cotización para %s (%s)", symbol, type(exc).__name__)
            return QuoteError(reason="el proveedor no cubre este símbolo o no respondió")

    def _fast_info(self, symbol: str) -> dict[str, object]:
        """Aísla el único punto que toca la librería (facilita el monkeypatch).

        El import vive aquí dentro y no a nivel de módulo: yfinance arrastra
        pandas y su import cuesta ~1 s, que se pagaría en CADA arranque del
        backend aunque nadie mire la cartera (misma razón que el parquet de
        `edgartools` en ADR-0008).
        """
        import yfinance as yf

        # El logger de yfinance escribe "$X: possibly delisted" por su cuenta;
        # aquí un símbolo desconocido ya es un `QuoteError` con su motivo.
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)

        fast_info = yf.Ticker(symbol).fast_info
        # Se leen los tres campos de golpe: acceder a `last_price` es lo que
        # dispara la petición, y así un símbolo malo falla una vez y no tres.
        return {
            "last_price": fast_info.last_price,
            "previous_close": fast_info.previous_close,
            "currency": fast_info.currency,
        }


# ── Comodidades del alta desde el directorio (PHASE-44.14, ADR-0010) ──
#
# La IDENTIDAD del alta `ext:` viene de FIRDS y no de aquí; estas dos funciones
# son la comodidad y la red de seguridad: resolver el símbolo de pricing por
# ISIN y comprobar que el símbolo elegido cotiza de verdad. Van en este fichero
# porque es el ÚNICO que conoce yfinance, y son síncronas — el caller las saca
# del event loop con `asyncio.to_thread`.


def search_symbols_by_isin(isin: str) -> list[str]:
    """Símbolos de EQUITY que Yahoo asocia a un ISIN, en su orden.

    Verificado en el spike del 2026-08-07: 7 de 8 ISINs devuelven exactamente
    un símbolo (`ES0148396007` → `ITX.MC`); Unilever devuelve cero tanto aquí
    como en `Lookup`. Por eso el alta tiene bypass manual: una lista vacía NO es
    un error, es «escribe el ticker a mano».

    Captura `Exception` a propósito, como `_fetch_one`: la lista de lo que puede
    lanzar un cliente no oficial no es enumerable, y aquí el fallo de red y el
    «no lo conozco» degradan igual — al formulario manual.
    """
    import yfinance as yf

    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    try:
        quotes = yf.Search(isin.strip().upper(), max_results=8).quotes
    except Exception as exc:
        logger.info("yfinance: búsqueda por ISIN falló (%s)", type(exc).__name__)
        return []
    symbols: list[str] = []
    for quote in quotes:
        if quote.get("quoteType") == "EQUITY":
            symbol = str(quote.get("symbol") or "").strip().upper()
            if symbol:
                symbols.append(symbol)
    return symbols


def probe_symbol(symbol: str) -> Quote | QuoteError:
    """Valida por cotización: ¿este símbolo existe y en qué divisa cotiza?

    Es la «regla universal» del alta ext: (plan E5 §4.4): nada se persiste sin
    haber visto una cotización real. Reutiliza `_fetch_one` — la misma
    normalización de subunidades (GBp→GBP ÷100) que el refresco de cartera, no
    una segunda copia que pueda divergir.
    """
    return YFinanceAdapter(throttle_seconds=0)._fetch_one(symbol.strip().upper())
