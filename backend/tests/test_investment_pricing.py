"""Tests de precios / summary (PHASE-44.7).

Con un `PriceAdapter` mockeado (sin Finnhub key): con cotización y sin ella.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from httpx import AsyncClient

from app.main import app
from app.modules.investment.fundamentals.adapters.base import SecurityIdentity
from app.modules.investment.fundamentals.adapters.factory import get_fundamentals_adapter
from app.modules.investment.pricing.adapters.base import Quote
from app.modules.investment.pricing.adapters.factory import get_price_adapter


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
    def __init__(self, price: Decimal | None) -> None:
        self._price = price

    async def quote(self, ticker: str) -> Quote | None:
        if self._price is None:
            return None
        return Quote(price=self._price, prev_close=self._price - 5, as_of=datetime.now(UTC))


def _override(price: Decimal | None) -> None:
    app.dependency_overrides[get_fundamentals_adapter] = _FundAdapter
    app.dependency_overrides[get_price_adapter] = lambda: _PriceAdapter(price)


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
    assert data["pricing_enabled"] is False  # no hay FINNHUB_API_KEY en tests


async def test_refresh_manual(client: AsyncClient) -> None:
    token = await _register(client, "pr3@example.com")
    _override(Decimal("200"))
    await _setup(client, token)

    refresh = await client.post("/investment/pricing/refresh", json={}, headers=_auth(token))
    assert refresh.status_code == 200
    assert refresh.json()["refreshed"] == 1
