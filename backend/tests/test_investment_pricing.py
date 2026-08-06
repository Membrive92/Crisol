"""Tests de precios / summary (PHASE-44.7).

Con un `PriceAdapter` mockeado: con cotización y sin ella.

Desde PHASE-44.11 el summary también convierte a la divisa base, así que estos
tests siembran tasas: sin ellas la posición quedaría FUERA de los totales por
falta de tipo de cambio, que es el comportamiento correcto pero no lo que aquí
se quiere medir. El fetch real está bloqueado en toda la suite (`conftest`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from decimal import Decimal

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.main import app
from app.modules.currency.models import ExchangeRate
from app.modules.investment.fundamentals.adapters.base import SecurityIdentity
from app.modules.investment.fundamentals.adapters.factory import get_fundamentals_adapter
from app.modules.investment.pricing.adapters.base import Quote, QuoteError, QuoteRequest
from app.modules.investment.pricing.adapters.factory import get_price_adapter


@pytest_asyncio.fixture(autouse=True)
async def _seed_today_rates(test_engine) -> AsyncIterator[None]:  # type: ignore[no-untyped-def]
    """Tasas EUR→USD/GBP del día, para que la valoración en base sea posible."""
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        today = datetime.now(UTC).date()
        for quote, rate in (("USD", "1"), ("GBP", "1")):
            db.add(
                ExchangeRate(
                    rate_date=today,
                    base="EUR",
                    quote=quote,
                    rate=Decimal(rate),
                    source="test",
                    fetched_at=datetime.now(UTC),
                )
            )
        await db.commit()
    yield


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


_MCD = SecurityIdentity(
    ticker="MCD",
    cik="0000063908",
    name="MCDONALDS CORP",
    sic="5812",
    is_reit=False,
    is_financial=False,
)


class _FundAdapter:
    async def resolve(self, ticker: str) -> SecurityIdentity:
        return _MCD

    async def fetch_facts(self, identity: SecurityIdentity, *, refresh: bool = False) -> tuple[()]:
        return ()


class _PriceAdapter:
    """Doble del `PriceAdapter`. Contrato plural desde PHASE-44.11.B: una
    entrada por `request.key`, y "sin cotización" es un `QuoteError` con motivo,
    no un `None` sin explicación."""

    def __init__(self, price: Decimal | None, *, currency: str | None = None) -> None:
        self._price = price
        self._currency = currency

    async def quotes(self, requests: Sequence[QuoteRequest]) -> dict[str, Quote | QuoteError]:
        if self._price is None:
            return {
                r.key: QuoteError(reason="el proveedor no cubre este símbolo") for r in requests
            }
        return {
            r.key: Quote(
                price=self._price,
                prev_close=self._price - 5,
                currency=self._currency,
                as_of=datetime.now(UTC),
            )
            for r in requests
        }


def _override(price: Decimal | None, *, currency: str | None = None) -> None:
    app.dependency_overrides[get_fundamentals_adapter] = _FundAdapter
    app.dependency_overrides[get_price_adapter] = lambda: _PriceAdapter(price, currency=currency)


async def _setup(client: AsyncClient, token: str) -> str:
    resolved = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )
    sid = resolved.json()["id"]
    await client.post(
        "/investment/portfolio/lots",
        json={"security_id": sid, "trade_date": "2022-01-01", "quantity": "10", "price": "100"},
        headers=_auth(token),
    )
    return sid


async def test_summary_con_cotizacion(client: AsyncClient) -> None:
    token = await _register(client, "pr1@example.com")
    _override(Decimal("150"))
    await _setup(client, token)

    summary = await client.get("/investment/portfolio/summary", headers=_auth(token))
    assert summary.status_code == 200, summary.text
    data = summary.json()
    pos = data["positions"][0]
    assert pos["has_quote"] is True
    assert Decimal(pos["last_price"]) == Decimal(150)
    assert Decimal(pos["market_value"]) == Decimal(1500)
    assert Decimal(pos["unrealized_pnl"]) == Decimal(500)  # 1500 - 1000
    assert Decimal(pos["daily_change"]) == Decimal(50)  # 10*(150-145)
    assert pos["quote_stale"] is False
    assert data["quoted_count"] == 1
    assert Decimal(data["total_market_value"]) == Decimal(1500)
    assert Decimal(pos["weight_pct"]) == Decimal(1)


async def test_summary_sin_cotizacion_excluye_de_totales(client: AsyncClient) -> None:
    token = await _register(client, "pr2@example.com")
    _override(None)  # el proveedor no cubre / sin key
    await _setup(client, token)

    summary = await client.get("/investment/portfolio/summary", headers=_auth(token))
    data = summary.json()
    pos = data["positions"][0]
    assert pos["has_quote"] is False
    assert pos["market_value"] is None
    assert data["unquoted_count"] == 1
    assert Decimal(data["total_market_value"]) == Decimal(0)
    # `pricing_enabled` dejó de significar "hay FINNHUB_API_KEY" en PHASE-44.11:
    # el default es yfinance, que no pide credencial, así que el proveedor SÍ
    # está disponible aunque este símbolo concreto no traiga precio. Son dos
    # cosas distintas y la UI las cuenta distinto: "no hay proveedor" es un
    # aviso de configuración; "este valor no cotiza" es una posición excluida.
    assert data["pricing_enabled"] is True


async def test_pricing_disabled_solo_con_finnhub_sin_key(client: AsyncClient, monkeypatch) -> None:
    """El único caso en que el proveedor entero está apagado."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "price_provider", "finnhub")
    monkeypatch.setattr(settings, "finnhub_api_key", "")

    token = await _register(client, "pr4@example.com")
    _override(None)
    await _setup(client, token)

    data = (await client.get("/investment/portfolio/summary", headers=_auth(token))).json()
    assert data["pricing_enabled"] is False


async def test_refresh_manual(client: AsyncClient) -> None:
    token = await _register(client, "pr3@example.com")
    _override(Decimal("200"))
    await _setup(client, token)

    refresh = await client.post("/investment/pricing/refresh", json={}, headers=_auth(token))
    assert refresh.status_code == 200
    assert refresh.json()["refreshed"] == 1


async def test_divisa_del_proveedor_manda_y_la_discrepancia_se_marca(
    client: AsyncClient,
) -> None:
    """Regresión de D4 en el camino completo (adapter → refresh → summary).

    El catálogo dice USD (MCD/NYSE) y el proveedor devuelve GBP. Se persiste y
    se valora con la del PROVEEDOR —es quien emitió el precio— y la posición
    sale marcada. Silenciarlo es cómo un precio en peniques pasa por libras.
    """
    token = await _register(client, "pr5@example.com")
    _override(Decimal("150"), currency="GBP")
    await _setup(client, token)

    data = (await client.get("/investment/portfolio/summary", headers=_auth(token))).json()
    pos = data["positions"][0]

    assert pos["currency"] == "USD"  # el catálogo
    assert pos["quote_currency"] == "GBP"  # el proveedor
    assert pos["currency_mismatch"] is True
    assert Decimal(pos["market_value"]) == Decimal(1500)  # se valora igual, no se descarta


async def test_sin_discrepancia_no_hay_flag(client: AsyncClient) -> None:
    token = await _register(client, "pr6@example.com")
    _override(Decimal("150"), currency="USD")
    await _setup(client, token)

    data = (await client.get("/investment/portfolio/summary", headers=_auth(token))).json()
    assert data["positions"][0]["currency_mismatch"] is False
