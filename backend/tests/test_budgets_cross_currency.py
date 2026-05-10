"""Tests del flag `convert_other_currencies` en budgets (PHASE-16)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.currency.models import ExchangeRate


async def _setup_user(
    client: AsyncClient, email: str
) -> tuple[str, str, str]:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    token = r.json()["access_token"]
    cat = await client.post(
        "/categories",
        json={"name": "Comida", "kind": "expense"},
        headers={"Authorization": f"Bearer {token}"},
    )
    acc = await client.post(
        "/accounts",
        json={"name": "Cuenta principal", "type": "bank", "currency": "EUR"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, cat.json()["id"], acc.json()["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_rate(test_engine, *, rate_date: date, quote: str, rate: str) -> None:
    """Inserta una tasa EUR → quote para tests, evitando llamadas reales
    a frankfurter durante los tests."""
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        db.add(
            ExchangeRate(
                rate_date=rate_date,
                base="EUR",
                quote=quote,
                rate=Decimal(rate),
                source="test",
            )
        )
        await db.commit()


async def test_create_budget_with_cross_currency_flag(client: AsyncClient) -> None:
    """El flag se persiste y se devuelve en la respuesta."""
    token, cat_id, _ = await _setup_user(client, "ccb1@example.com")
    r = await client.post(
        "/budgets",
        json={
            "category_id": cat_id,
            "amount": "300.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
            "convert_other_currencies": True,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    assert r.json()["convert_other_currencies"] is True

    # Default sigue siendo False.
    r2 = await client.post(
        "/budgets",
        json={
            "amount": "1000.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
        },
        headers=_auth(token),
    )
    assert r2.json()["convert_other_currencies"] is False


async def test_status_without_flag_ignores_other_currencies(
    client: AsyncClient,
) -> None:
    """Sin flag, una tx en USD no contribuye a un budget EUR."""
    token, cat_id, account_id = await _setup_user(client, "ccb2@example.com")
    await client.post(
        "/budgets",
        json={
            "category_id": cat_id,
            "amount": "100.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
        },
        headers=_auth(token),
    )

    today_iso = date.today().isoformat()
    await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": cat_id,
            "amount": "50.00",
            "currency": "USD",  # no es EUR
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )

    r = await client.get(
        "/budgets/status", params={"currency": "EUR"}, headers=_auth(token)
    )
    item = r.json()["items"][0]
    assert float(item["spent_this_month"]) == 0.0
    assert item["unconvertible_count"] == 0  # legacy mode no cuenta


async def test_status_with_flag_sums_converted(client: AsyncClient, test_engine) -> None:
    """Con flag, USD se convierte a EUR usando la tasa del día."""
    token, cat_id, account_id = await _setup_user(client, "ccb3@example.com")
    await client.post(
        "/budgets",
        json={
            "category_id": cat_id,
            "amount": "100.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
            "convert_other_currencies": True,
        },
        headers=_auth(token),
    )

    today = date.today()
    today_iso = today.isoformat()
    # Tasa: 1 EUR = 1.10 USD (es decir, 1 USD = 1/1.10 EUR ≈ 0.909 EUR).
    # 50 USD ≈ 45.45 EUR.
    await _seed_rate(test_engine, rate_date=today, quote="USD", rate="1.10")

    await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": cat_id,
            "amount": "50.00",
            "currency": "USD",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )

    r = await client.get(
        "/budgets/status", params={"currency": "EUR"}, headers=_auth(token)
    )
    item = r.json()["items"][0]
    spent = float(item["spent_this_month"])
    # 50 / 1.10 = 45.4545... — toleramos algo de precisión decimal.
    assert 45.0 < spent < 46.0
    assert item["unconvertible_count"] == 0


async def test_status_with_flag_reports_unconvertible(
    client: AsyncClient,
) -> None:
    """Con flag, una tx en moneda exótica sin tasa se cuenta en
    unconvertible_count y NO se suma."""
    token, cat_id, account_id = await _setup_user(client, "ccb4@example.com")
    await client.post(
        "/budgets",
        json={
            "category_id": cat_id,
            "amount": "100.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
            "convert_other_currencies": True,
        },
        headers=_auth(token),
    )

    today_iso = date.today().isoformat()
    # Una tx en EUR (siempre convertible)
    await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": cat_id,
            "amount": "30.00",
            "currency": "EUR",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )
    # Una tx en una moneda inventada sin tasa.
    await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": cat_id,
            "amount": "999.00",
            "currency": "XYZ",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )

    r = await client.get(
        "/budgets/status", params={"currency": "EUR"}, headers=_auth(token)
    )
    item = r.json()["items"][0]
    assert float(item["spent_this_month"]) == 30.0  # solo la EUR
    assert item["unconvertible_count"] == 1


async def test_update_can_toggle_flag(client: AsyncClient) -> None:
    """PUT puede activar/desactivar el flag."""
    token, cat_id, _ = await _setup_user(client, "ccb5@example.com")
    r = await client.post(
        "/budgets",
        json={
            "category_id": cat_id,
            "amount": "100.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
        },
        headers=_auth(token),
    )
    bid = r.json()["id"]
    assert r.json()["convert_other_currencies"] is False

    r2 = await client.put(
        f"/budgets/{bid}",
        json={"convert_other_currencies": True},
        headers=_auth(token),
    )
    assert r2.json()["convert_other_currencies"] is True

    r3 = await client.put(
        f"/budgets/{bid}",
        json={"convert_other_currencies": False},
        headers=_auth(token),
    )
    assert r3.json()["convert_other_currencies"] is False


async def test_alert_respects_flag(client: AsyncClient, test_engine) -> None:
    """El alert proactivo (PHASE-14.5) usa el mismo flag que el status."""
    token, cat_id, account_id = await _setup_user(client, "ccb6@example.com")
    await client.post(
        "/budgets",
        json={
            "category_id": cat_id,
            "amount": "100.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
            "convert_other_currencies": True,
        },
        headers=_auth(token),
    )

    today = date.today()
    today_iso = today.isoformat()
    # 1 EUR = 1.10 USD → 100 USD ≈ 90.9 EUR (warning sobre 100).
    await _seed_rate(test_engine, rate_date=today, quote="USD", rate="1.10")

    r = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": cat_id,
            "amount": "100.00",
            "currency": "USD",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )
    alert = r.json()["budget_alert"]
    assert alert is not None
    assert alert["status"] == "warning"
    # ~91% de 100 EUR.
    assert 88 < alert["percent_used"] < 93
