"""Tests del módulo categories."""

from __future__ import annotations

from httpx import AsyncClient


async def _register_and_get_token(client: AsyncClient, email: str = "cat@example.com") -> str:
    """Helper: registra y devuelve access token."""
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_create_category(client: AsyncClient) -> None:
    token = await _register_and_get_token(client)
    r = await client.post(
        "/categories",
        json={"name": "Comida", "kind": "expense", "icon": "🍔", "color": "#FF5733"},
        headers=_auth(token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Comida"
    assert body["kind"] == "expense"


async def test_list_categories(client: AsyncClient) -> None:
    token = await _register_and_get_token(client)
    await client.post(
        "/categories", json={"name": "Salario", "kind": "income"}, headers=_auth(token)
    )
    await client.post(
        "/categories", json={"name": "Transporte", "kind": "expense"}, headers=_auth(token)
    )

    r = await client.get("/categories", headers=_auth(token))
    assert r.status_code == 200
    assert len(r.json()) == 2


async def test_update_category(client: AsyncClient) -> None:
    token = await _register_and_get_token(client)
    r = await client.post(
        "/categories", json={"name": "Old", "kind": "expense"}, headers=_auth(token)
    )
    cat_id = r.json()["id"]

    r2 = await client.put(f"/categories/{cat_id}", json={"name": "Updated"}, headers=_auth(token))
    assert r2.status_code == 200
    assert r2.json()["name"] == "Updated"


async def test_delete_category(client: AsyncClient) -> None:
    token = await _register_and_get_token(client)
    r = await client.post(
        "/categories", json={"name": "ToDelete", "kind": "expense"}, headers=_auth(token)
    )
    cat_id = r.json()["id"]

    r2 = await client.delete(f"/categories/{cat_id}", headers=_auth(token))
    assert r2.status_code == 204

    r3 = await client.get(f"/categories/{cat_id}", headers=_auth(token))
    assert r3.status_code == 404


async def test_category_user_isolation(client: AsyncClient) -> None:
    """User A no ve categorías de User B."""
    token_a = await _register_and_get_token(client, "catA@example.com")
    token_b = await _register_and_get_token(client, "catB@example.com")

    await client.post(
        "/categories", json={"name": "Solo A", "kind": "expense"}, headers=_auth(token_a)
    )
    await client.post(
        "/categories", json={"name": "Solo B", "kind": "income"}, headers=_auth(token_b)
    )

    cats_a = await client.get("/categories", headers=_auth(token_a))
    cats_b = await client.get("/categories", headers=_auth(token_b))

    assert len(cats_a.json()) == 1
    assert cats_a.json()[0]["name"] == "Solo A"
    assert len(cats_b.json()) == 1
    assert cats_b.json()[0]["name"] == "Solo B"
