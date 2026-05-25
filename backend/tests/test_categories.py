"""Tests del módulo categories."""

from __future__ import annotations

from httpx import AsyncClient


async def _register_and_get_token(client: AsyncClient, email: str = "cat@example.com") -> str:
    """Helper: registra, limpia el seed automático y devuelve token.

    PHASE-20: el register siembra ~18 categorías + ~100 reglas. Estos
    tests del módulo categories se centran en el CRUD básico y verifican
    contadores exactos, así que partimos de cero.
    """
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    rules = (await client.get("/category-rules", headers=h)).json()["items"]
    for rule in rules:
        await client.delete(f"/category-rules/{rule['id']}", headers=h)
    cats = (await client.get("/categories", headers=h)).json()
    for c in cats:
        await client.delete(f"/categories/{c['id']}", headers=h)
    return token


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


async def test_create_category_defaults_role_generic(client: AsyncClient) -> None:
    """PHASE-30.1 — sin especificar `role`, una categoría nueva nace GENERIC."""
    token = await _register_and_get_token(client, "role_default@example.com")
    r = await client.post(
        "/categories",
        json={"name": "Restaurantes", "kind": "expense"},
        headers=_auth(token),
    )
    assert r.status_code == 201
    assert r.json()["role"] == "GENERIC"


async def test_create_category_with_role_debt_interest(client: AsyncClient) -> None:
    """PHASE-30.1 — el caller puede crear DEBT_INTEREST custom y se persiste."""
    token = await _register_and_get_token(client, "role_di@example.com")
    r = await client.post(
        "/categories",
        json={
            "name": "Intereses préstamo personal",
            "kind": "expense",
            "role": "DEBT_INTEREST",
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    assert r.json()["role"] == "DEBT_INTEREST"


async def test_is_transfer_forces_role_transfer(client: AsyncClient) -> None:
    """PHASE-30.1 — `is_transfer=true` sin role explícito → role=TRANSFER."""
    token = await _register_and_get_token(client, "role_transfer@example.com")
    r = await client.post(
        "/categories",
        json={
            "name": "Transferencia auto",
            "kind": "expense",
            "is_transfer": True,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    assert r.json()["is_transfer"] is True
    assert r.json()["role"] == "TRANSFER"


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
