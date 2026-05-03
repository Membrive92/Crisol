"""Tests HTTP del router /currency/*."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.currency import repository


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed(test_engine, rows) -> None:  # type: ignore[no-untyped-def]
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    async with factory() as db:
        await repository.upsert_rates(db, rows)
        await db.commit()


async def test_rates_endpoint_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/currency/rates")
    assert r.status_code == 401


async def test_rates_endpoint_returns_seeded(client: AsyncClient, test_engine) -> None:  # type: ignore[no-untyped-def]
    token = await _register(client, "rates@test.com")
    await _seed(
        test_engine,
        [
            (date(2026, 4, 1), "EUR", "USD", Decimal("1.10"), "test"),
            (date(2026, 4, 1), "EUR", "GBP", Decimal("0.85"), "test"),
        ],
    )

    r = await client.get(
        "/currency/rates",
        params={"date": "2026-04-01"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["base"] == "EUR"
    assert data["rate_date"] == "2026-04-01"
    quotes = {row["quote"] for row in data["rates"]}
    assert quotes == {"USD", "GBP"}


async def test_convert_endpoint_returns_amount(client: AsyncClient, test_engine) -> None:  # type: ignore[no-untyped-def]
    token = await _register(client, "convert@test.com")
    await _seed(
        test_engine,
        [(date(2026, 4, 1), "EUR", "USD", Decimal("1.20"), "test")],
    )

    r = await client.get(
        "/currency/convert",
        params={
            "amount": "100",
            "from": "EUR",
            "to": "USD",
            "date": "2026-04-01",
        },
        headers=_auth(token),
    )
    assert r.status_code == 200
    data = r.json()
    assert Decimal(data["amount"]) == Decimal("120.00")
    assert data["fallback"] == "exact"


async def test_convert_endpoint_rejects_invalid_amount(client: AsyncClient) -> None:
    token = await _register(client, "invalid@test.com")
    r = await client.get(
        "/currency/convert",
        params={"amount": "not-a-number", "from": "EUR", "to": "USD"},
        headers=_auth(token),
    )
    assert r.status_code == 422


async def test_convert_endpoint_returns_missing_when_no_rate(
    client: AsyncClient,
) -> None:
    token = await _register(client, "missing@test.com")
    r = await client.get(
        "/currency/convert",
        params={
            "amount": "100",
            "from": "USD",
            "to": "EUR",
            "date": "2024-01-15",
        },
        headers=_auth(token),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["fallback"] == "missing"
    # Importe sin convertir cuando no hay tasa.
    assert Decimal(data["amount"]) == Decimal("100.00")
