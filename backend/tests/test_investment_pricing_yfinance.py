"""Tests del adapter yfinance (PHASE-44.11.B).

**Cero red**: se monkeypatchea `_fast_info`, el único punto que toca la
librería. Los valores de retorno NO son inventados — son los que devolvió el
probe en vivo contra KO, ULVR.L, IBE.MC, ALV.DE y MC.PA con yfinance 1.5.2
(`float`, no `Decimal`; `'GBp'` literal en Londres; `KeyError` en un símbolo
inexistente). Si la librería cambia esa forma, el smoke de la sub-fase G lo
destapa; estos tests fijan lo que hacemos NOSOTROS con ella.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.investment.pricing.adapters.base import Quote, QuoteError, QuoteRequest
from app.modules.investment.pricing.adapters.yfinance import YFinanceAdapter, to_yahoo_symbol


def _adapter() -> YFinanceAdapter:
    # Sin throttle: los tests no esperan un segundo por símbolo.
    return YFinanceAdapter(throttle_seconds=0.0)


def _patch(monkeypatch: pytest.MonkeyPatch, payloads: dict[str, object]) -> list[str]:
    """Sustituye la lectura de la librería. Devuelve la lista de símbolos pedidos."""
    asked: list[str] = []

    def fake(self: YFinanceAdapter, symbol: str) -> dict[str, object]:
        asked.append(symbol)
        payload = payloads[symbol]
        if isinstance(payload, Exception):
            raise payload
        return payload  # type: ignore[return-value]

    monkeypatch.setattr(YFinanceAdapter, "_fast_info", fake)
    return asked


# --------------------------------------------------------------------------
# Mapeo (ticker, exchange) → símbolo Yahoo
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ticker", "exchange", "expected"),
    [
        ("KO", "NYSE", "KO"),
        ("MSFT", "NASDAQ", "MSFT"),
        ("ko", "nyse", "KO"),  # se normaliza a mayúsculas
        ("ULVR", "XLON", "ULVR.L"),
        ("IBE", "XMAD", "IBE.MC"),
        ("ALV", "XETR", "ALV.DE"),
        ("MC", "XPAR", "MC.PA"),
        ("ASML", "XAMS", "ASML.AS"),
        # Decisión del usuario (2026-08-02): sin plaza → símbolo desnudo. Hoy el
        # catálogo es 100 % SEC, así que acierta; la red es el flag de divisa.
        ("KO", "UNKNOWN", "KO"),
        ("KO", "", "KO"),
    ],
)
def test_symbol_mapping(ticker: str, exchange: str, expected: str) -> None:
    assert to_yahoo_symbol(ticker, exchange) == expected


def test_symbol_mapping_unknown_venue_is_none_not_a_guess() -> None:
    """Una plaza fuera de la tabla NO se traduce a un sufijo inventado.

    Inventarlo devolvería el precio de OTRO valor, que es peor que no cotizar.
    """
    assert to_yahoo_symbol("XYZ", "XTKS") is None  # Tokio: aún sin sufijo mapeado
    assert to_yahoo_symbol("", "NYSE") is None


def test_plan_venue_labels_are_not_the_repo_vocabulary() -> None:
    """Regresión de la corrección del plan (PHASE-44.11.B).

    El plan traía la tabla escrita como `{LSE, BME, XETRA, EPA, ...}`. Ninguna
    de esas etiquetas sobrevive a `catalog.venues.normalize_venue`, así que si
    alguien las reintroduce como claves, el mapeo no acertará una sola fila y
    toda posición europea caerá en "sin mapeo" EN SILENCIO. Este test fija que
    las claves buenas son los MIC.
    """
    from app.modules.investment.catalog.venues import UNKNOWN, normalize_venue

    for coloquial in ("LSE", "BME", "XETRA", "EPA", "AMS", "MIL", "SWX"):
        assert normalize_venue(coloquial) == UNKNOWN

    assert normalize_venue("XLON") == "XLON"
    assert to_yahoo_symbol("ULVR", normalize_venue("XLON")) == "ULVR.L"


# --------------------------------------------------------------------------
# Cotización
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_us_quote_converts_float_to_decimal(monkeypatch: pytest.MonkeyPatch) -> None:
    """La librería devuelve `float`; nada aguas abajo puede verlo."""
    _patch(
        monkeypatch,
        {"KO": {"last_price": 87.58999633789062, "previous_close": 88.2981, "currency": "USD"}},
    )

    results = await _adapter().quotes([QuoteRequest(key="k", ticker="KO", exchange="NYSE")])
    quote = results["k"]

    assert isinstance(quote, Quote)
    assert isinstance(quote.price, Decimal)
    assert quote.price == Decimal("87.589996")  # cuantizado a los 6 decimales de la columna
    assert quote.prev_close == Decimal("88.298100")
    assert quote.currency == "USD"


@pytest.mark.asyncio
async def test_london_pence_are_divided_and_relabelled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test de regresión de D4 — el que impide el ×100.

    Yahoo devuelve 4743.0 **GBp** para ULVR.L. Sin dividir, una posición de 100
    acciones valdría 474.300 libras en vez de 4.743.
    """
    _patch(
        monkeypatch,
        {"ULVR.L": {"last_price": 4743.0, "previous_close": 4850.0, "currency": "GBp"}},
    )

    results = await _adapter().quotes([QuoteRequest(key="k", ticker="ULVR", exchange="XLON")])
    quote = results["k"]

    assert isinstance(quote, Quote)
    assert quote.currency == "GBP"  # nunca 'GBp'
    assert quote.price == Decimal("47.430000")
    assert quote.prev_close == Decimal("48.500000")


@pytest.mark.asyncio
async def test_real_pounds_are_not_divided(monkeypatch: pytest.MonkeyPatch) -> None:
    """`'GBP'` en mayúsculas son libras de verdad. La diferencia con `'GBp'` es
    SÓLO el case, así que este test es el que vigila que nadie 'simplifique'
    normalizando a mayúsculas antes de comparar."""
    _patch(
        monkeypatch,
        {"XYZ.L": {"last_price": 12.5, "previous_close": 12.0, "currency": "GBP"}},
    )

    results = await _adapter().quotes([QuoteRequest(key="k", ticker="XYZ", exchange="XLON")])
    quote = results["k"]

    assert isinstance(quote, Quote)
    assert quote.currency == "GBP"
    assert quote.price == Decimal("12.500000")  # sin dividir


@pytest.mark.asyncio
async def test_gbx_alias_also_divides(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, {"A.L": {"last_price": 200.0, "previous_close": None, "currency": "GBX"}})

    results = await _adapter().quotes([QuoteRequest(key="k", ticker="A", exchange="XLON")])
    quote = results["k"]

    assert isinstance(quote, Quote)
    assert quote.currency == "GBP"
    assert quote.price == Decimal("2.000000")
    assert quote.prev_close is None


@pytest.mark.asyncio
async def test_unmapped_exchange_is_an_excluded_position_not_a_crash() -> None:
    """Plaza sin equivalencia → exclusión estándar CON motivo, sin tocar la red."""
    results = await _adapter().quotes([QuoteRequest(key="k", ticker="X", exchange="XTKS")])
    error = results["k"]

    assert isinstance(error, QuoteError)
    assert "XTKS" in error.reason


@pytest.mark.asyncio
async def test_missing_symbol_raises_keyerror_and_does_not_kill_the_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El modo de fallo REAL, verificado en el probe.

    Un símbolo inexistente sale por `KeyError('exchangeTimezoneName')`, no por
    una excepción de red: un `except (HTTPError, ValueError)` no lo cazaría y se
    llevaría por delante el lote entero.
    """
    _patch(
        monkeypatch,
        {
            "NOEXISTE.XX": KeyError("exchangeTimezoneName"),
            "KO": {"last_price": 87.5, "previous_close": 88.0, "currency": "USD"},
        },
    )

    results = await _adapter().quotes(
        [
            QuoteRequest(key="bad", ticker="NOEXISTE", exchange="UNKNOWN"),
            QuoteRequest(key="good", ticker="KO", exchange="NYSE"),
        ]
    )

    assert isinstance(results["bad"], QuoteError)
    assert isinstance(results["good"], Quote)  # el lote sobrevive


@pytest.mark.asyncio
async def test_network_failure_is_an_error_not_an_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch, {"KO": ConnectionError("boom")})

    results = await _adapter().quotes([QuoteRequest(key="k", ticker="KO", exchange="NYSE")])

    assert isinstance(results["k"], QuoteError)


@pytest.mark.asyncio
async def test_zero_or_negative_price_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un 0 no es un precio: es como varios proveedores dicen "no lo cubro"."""
    _patch(monkeypatch, {"KO": {"last_price": 0.0, "previous_close": 1.0, "currency": "USD"}})

    results = await _adapter().quotes([QuoteRequest(key="k", ticker="KO", exchange="NYSE")])

    assert isinstance(results["k"], QuoteError)


@pytest.mark.asyncio
async def test_every_request_gets_an_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contrato: una entrada por `key`, pase lo que pase. Si faltara alguna, el
    refresco la trataría como "no refrescada" sin saber por qué."""
    _patch(
        monkeypatch,
        {
            "KO": {"last_price": 87.5, "previous_close": 88.0, "currency": "USD"},
            "BAD.XX": KeyError("exchangeTimezoneName"),
        },
    )

    requests = [
        QuoteRequest(key="a", ticker="KO", exchange="NYSE"),
        QuoteRequest(key="b", ticker="BAD", exchange="UNKNOWN"),
        QuoteRequest(key="c", ticker="Z", exchange="XTKS"),  # sin mapeo, ni se pide
    ]
    results = await _adapter().quotes(requests)

    assert set(results) == {"a", "b", "c"}


@pytest.mark.asyncio
async def test_unmapped_symbols_never_reach_the_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una plaza sin mapeo no gasta una petición: se resuelve antes de salir."""
    asked = _patch(
        monkeypatch, {"KO": {"last_price": 1.0, "previous_close": None, "currency": "USD"}}
    )

    await _adapter().quotes(
        [
            QuoteRequest(key="a", ticker="Z", exchange="XTKS"),
            QuoteRequest(key="b", ticker="KO", exchange="NYSE"),
        ]
    )

    assert asked == ["KO"]
