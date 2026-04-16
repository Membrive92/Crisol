"""Tests del módulo transactions."""

from __future__ import annotations

from httpx import AsyncClient


async def _setup_user(client: AsyncClient, email: str = "tx@example.com") -> tuple[str, str]:
    """Helper: registra, crea categoría, devuelve (token, category_id)."""
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    token = r.json()["access_token"]
    cat = await client.post(
        "/categories",
        json={"name": "General", "kind": "expense"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, cat.json()["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_create_transaction(client: AsyncClient) -> None:
    token, cat_id = await _setup_user(client)
    r = await client.post(
        "/transactions",
        json={
            "category_id": cat_id,
            "amount": "25.50",
            "currency": "EUR",
            "occurred_at": "2026-04-15T12:00:00Z",
            "description": "Almuerzo",
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["amount"] == "25.50"
    assert body["description"] == "Almuerzo"
    assert body["source"] == "manual"


async def test_list_transactions(client: AsyncClient) -> None:
    token, cat_id = await _setup_user(client, "txlist@example.com")
    for i in range(3):
        await client.post(
            "/transactions",
            json={
                "category_id": cat_id,
                "amount": f"{10 + i}.00",
                "occurred_at": f"2026-04-{15 + i}T12:00:00Z",
            },
            headers=_auth(token),
        )

    r = await client.get("/transactions", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


async def test_filter_by_date(client: AsyncClient) -> None:
    token, _cat_id = await _setup_user(client, "txdate@example.com")
    await client.post(
        "/transactions",
        json={"amount": "10.00", "occurred_at": "2026-01-15T12:00:00Z"},
        headers=_auth(token),
    )
    await client.post(
        "/transactions",
        json={"amount": "20.00", "occurred_at": "2026-06-15T12:00:00Z"},
        headers=_auth(token),
    )

    r = await client.get(
        "/transactions",
        params={"date_from": "2026-06-01T00:00:00Z"},
        headers=_auth(token),
    )
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["amount"] == "20.00"


async def test_filter_by_search(client: AsyncClient) -> None:
    token, _ = await _setup_user(client, "txsearch@example.com")
    await client.post(
        "/transactions",
        json={"amount": "5.00", "occurred_at": "2026-04-15T12:00:00Z", "description": "Café"},
        headers=_auth(token),
    )
    await client.post(
        "/transactions",
        json={"amount": "50.00", "occurred_at": "2026-04-15T12:00:00Z", "description": "Gasolina"},
        headers=_auth(token),
    )

    r = await client.get("/transactions", params={"search": "café"}, headers=_auth(token))
    assert r.json()["total"] == 1


async def test_update_transaction(client: AsyncClient) -> None:
    token, _cat_id = await _setup_user(client, "txupdate@example.com")
    r = await client.post(
        "/transactions",
        json={"amount": "100.00", "occurred_at": "2026-04-15T12:00:00Z"},
        headers=_auth(token),
    )
    tx_id = r.json()["id"]

    r2 = await client.put(
        f"/transactions/{tx_id}",
        json={"amount": "150.00", "description": "Corregido"},
        headers=_auth(token),
    )
    assert r2.status_code == 200
    assert r2.json()["amount"] == "150.00"
    assert r2.json()["description"] == "Corregido"


async def test_delete_transaction(client: AsyncClient) -> None:
    token, _ = await _setup_user(client, "txdelete@example.com")
    r = await client.post(
        "/transactions",
        json={"amount": "10.00", "occurred_at": "2026-04-15T12:00:00Z"},
        headers=_auth(token),
    )
    tx_id = r.json()["id"]

    assert (await client.delete(f"/transactions/{tx_id}", headers=_auth(token))).status_code == 204
    assert (await client.get(f"/transactions/{tx_id}", headers=_auth(token))).status_code == 404


async def test_transaction_user_isolation(client: AsyncClient) -> None:
    """User A no ve transacciones de User B."""
    token_a, _ = await _setup_user(client, "txA@example.com")
    token_b, _ = await _setup_user(client, "txB@example.com")

    await client.post(
        "/transactions",
        json={"amount": "10.00", "occurred_at": "2026-04-15T12:00:00Z", "description": "A only"},
        headers=_auth(token_a),
    )
    await client.post(
        "/transactions",
        json={"amount": "20.00", "occurred_at": "2026-04-15T12:00:00Z", "description": "B only"},
        headers=_auth(token_b),
    )

    r_a = await client.get("/transactions", headers=_auth(token_a))
    r_b = await client.get("/transactions", headers=_auth(token_b))

    assert r_a.json()["total"] == 1
    assert r_a.json()["items"][0]["description"] == "A only"
    assert r_b.json()["total"] == 1
    assert r_b.json()["items"][0]["description"] == "B only"
