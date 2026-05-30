"""Tests del módulo transactions."""

from __future__ import annotations

from httpx import AsyncClient


async def _setup_user(client: AsyncClient, email: str = "tx@example.com") -> tuple[str, str, str]:
    """Helper: registra, crea categoría y cuenta, devuelve
    (token, category_id, account_id)."""
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
    acc = await client.post(
        "/accounts",
        json={"name": "Cuenta principal", "type": "bank", "currency": "EUR"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, cat.json()["id"], acc.json()["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_create_transaction(client: AsyncClient) -> None:
    token, cat_id, account_id = await _setup_user(client)
    r = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
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
    token, cat_id, account_id = await _setup_user(client, "txlist@example.com")
    for i in range(3):
        await client.post(
            "/transactions",
            json={
                "account_id": account_id,
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
    token, _cat_id, account_id = await _setup_user(client, "txdate@example.com")
    await client.post(
        "/transactions",
        json={"account_id": account_id, "amount": "10.00", "occurred_at": "2026-01-15T12:00:00Z"},
        headers=_auth(token),
    )
    await client.post(
        "/transactions",
        json={"account_id": account_id, "amount": "20.00", "occurred_at": "2026-06-15T12:00:00Z"},
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
    token, _, account_id = await _setup_user(client, "txsearch@example.com")
    await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "amount": "5.00",
            "occurred_at": "2026-04-15T12:00:00Z",
            "description": "Café",
        },
        headers=_auth(token),
    )
    await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "amount": "50.00",
            "occurred_at": "2026-04-15T12:00:00Z",
            "description": "Gasolina",
        },
        headers=_auth(token),
    )

    r = await client.get("/transactions", params={"search": "café"}, headers=_auth(token))
    assert r.json()["total"] == 1


async def test_update_transaction(client: AsyncClient) -> None:
    token, _cat_id, account_id = await _setup_user(client, "txupdate@example.com")
    r = await client.post(
        "/transactions",
        json={"account_id": account_id, "amount": "100.00", "occurred_at": "2026-04-15T12:00:00Z"},
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
    token, _, account_id = await _setup_user(client, "txdelete@example.com")
    r = await client.post(
        "/transactions",
        json={"account_id": account_id, "amount": "10.00", "occurred_at": "2026-04-15T12:00:00Z"},
        headers=_auth(token),
    )
    tx_id = r.json()["id"]

    assert (await client.delete(f"/transactions/{tx_id}", headers=_auth(token))).status_code == 204
    assert (await client.get(f"/transactions/{tx_id}", headers=_auth(token))).status_code == 404


async def test_transaction_user_isolation(client: AsyncClient) -> None:
    """User A no ve transacciones de User B."""
    token_a, _, account_a = await _setup_user(client, "txA@example.com")
    token_b, _, account_b = await _setup_user(client, "txB@example.com")

    await client.post(
        "/transactions",
        json={
            "account_id": account_a,
            "amount": "10.00",
            "occurred_at": "2026-04-15T12:00:00Z",
            "description": "A only",
        },
        headers=_auth(token_a),
    )
    await client.post(
        "/transactions",
        json={
            "account_id": account_b,
            "amount": "20.00",
            "occurred_at": "2026-04-15T12:00:00Z",
            "description": "B only",
        },
        headers=_auth(token_b),
    )

    r_a = await client.get("/transactions", headers=_auth(token_a))
    r_b = await client.get("/transactions", headers=_auth(token_b))

    assert r_a.json()["total"] == 1
    assert r_a.json()["items"][0]["description"] == "A only"
    assert r_b.json()["total"] == 1
    assert r_b.json()["items"][0]["description"] == "B only"


# ─────────────────────────────────────────────────────────────────────────────
# Bulk soft-delete (DELETE /transactions con filtros)
# ─────────────────────────────────────────────────────────────────────────────


async def test_bulk_delete_without_filters_moves_all_to_trash(
    client: AsyncClient,
) -> None:
    token, cat_id, account_id = await _setup_user(client, "bulk@example.com")
    for i in range(3):
        await client.post(
            "/transactions",
            json={
                "account_id": account_id,
                "category_id": cat_id,
                "amount": f"{10 + i}.00",
                "occurred_at": f"2026-04-{15 + i}T12:00:00Z",
            },
            headers=_auth(token),
        )

    r = await client.delete("/transactions", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted_count": 3}

    # Lista activa vacía, papelera con las 3.
    active = await client.get("/transactions", headers=_auth(token))
    trash = await client.get("/transactions/trash", headers=_auth(token))
    assert active.json()["total"] == 0
    assert trash.json()["total"] == 3


async def test_bulk_delete_with_category_filter_only_deletes_matching(
    client: AsyncClient,
) -> None:
    token, cat_a, account_id = await _setup_user(client, "bulkfilter@example.com")
    cat_b = (
        await client.post(
            "/categories",
            json={"name": "Otra", "kind": "expense"},
            headers=_auth(token),
        )
    ).json()["id"]

    # 2 en cat_a, 1 en cat_b.
    for cat in (cat_a, cat_a, cat_b):
        await client.post(
            "/transactions",
            json={
                "account_id": account_id,
                "category_id": cat,
                "amount": "10.00",
                "occurred_at": "2026-04-15T12:00:00Z",
            },
            headers=_auth(token),
        )

    r = await client.delete(f"/transactions?category_id={cat_a}", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["deleted_count"] == 2

    active = await client.get("/transactions", headers=_auth(token))
    assert active.json()["total"] == 1
    assert active.json()["items"][0]["category_id"] == cat_b


async def test_bulk_delete_isolates_by_user(client: AsyncClient) -> None:
    """A no debe poder borrar las transacciones de B."""
    token_a, _, _ = await _setup_user(client, "bulkA@example.com")
    token_b, _, account_b = await _setup_user(client, "bulkB@example.com")
    await client.post(
        "/transactions",
        json={
            "account_id": account_b,
            "amount": "10.00",
            "occurred_at": "2026-04-15T12:00:00Z",
            "description": "B",
        },
        headers=_auth(token_b),
    )

    r = await client.delete("/transactions", headers=_auth(token_a))
    assert r.status_code == 200
    assert r.json()["deleted_count"] == 0

    # B sigue viendo la suya.
    list_b = await client.get("/transactions", headers=_auth(token_b))
    assert list_b.json()["total"] == 1


async def test_bulk_delete_does_not_affect_already_trashed(
    client: AsyncClient,
) -> None:
    """Si ya está en papelera no se "re-borra" — el filtro `active=true`
    asegura idempotencia."""
    token, cat_id, account_id = await _setup_user(client, "bulkidem@example.com")
    tx_id = (
        await client.post(
            "/transactions",
            json={
                "account_id": account_id,
                "category_id": cat_id,
                "amount": "10.00",
                "occurred_at": "2026-04-15T12:00:00Z",
            },
            headers=_auth(token),
        )
    ).json()["id"]
    await client.delete(f"/transactions/{tx_id}", headers=_auth(token))

    r = await client.delete("/transactions", headers=_auth(token))
    assert r.json()["deleted_count"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Bulk restore + bulk purge sobre papelera
# ─────────────────────────────────────────────────────────────────────────────


async def _seed_trashed(
    client: AsyncClient, token: str, cat_id: str, account_id: str, n: int
) -> None:
    for i in range(n):
        tx_id = (
            await client.post(
                "/transactions",
                json={
                    "account_id": account_id,
                    "category_id": cat_id,
                    "amount": f"{10 + i}.00",
                    "occurred_at": f"2026-04-{15 + i}T12:00:00Z",
                },
                headers=_auth(token),
            )
        ).json()["id"]
        await client.delete(f"/transactions/{tx_id}", headers=_auth(token))


async def test_bulk_restore_trash_brings_all_back_to_active(
    client: AsyncClient,
) -> None:
    token, cat_id, account_id = await _setup_user(client, "bulkrestore@example.com")
    await _seed_trashed(client, token, cat_id, account_id, 3)
    assert (await client.get("/transactions/trash", headers=_auth(token))).json()["total"] == 3

    r = await client.post("/transactions/trash/restore", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json() == {"restored_count": 3}

    active = await client.get("/transactions", headers=_auth(token))
    trash = await client.get("/transactions/trash", headers=_auth(token))
    assert active.json()["total"] == 3
    assert trash.json()["total"] == 0


async def test_bulk_restore_trash_empty_returns_zero(client: AsyncClient) -> None:
    token, _, _ = await _setup_user(client, "bulkrestoreempty@example.com")
    r = await client.post("/transactions/trash/restore", headers=_auth(token))
    assert r.json() == {"restored_count": 0}


async def test_bulk_purge_trash_deletes_all_permanently(client: AsyncClient) -> None:
    token, cat_id, account_id = await _setup_user(client, "bulkpurge@example.com")
    await _seed_trashed(client, token, cat_id, account_id, 3)

    r = await client.delete("/transactions/trash", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json() == {"purged_count": 3}

    trash = await client.get("/transactions/trash", headers=_auth(token))
    assert trash.json()["total"] == 0

    # No las deja como activas tampoco — desaparecidas para siempre.
    active = await client.get("/transactions", headers=_auth(token))
    assert active.json()["total"] == 0


async def test_bulk_purge_trash_does_not_touch_active_transactions(
    client: AsyncClient,
) -> None:
    """Las activas no se ven afectadas — sólo borra lo que está en papelera."""
    token, cat_id, account_id = await _setup_user(client, "bulkpurgesafe@example.com")
    # 2 activas + 2 en papelera
    for i in range(2):
        await client.post(
            "/transactions",
            json={
                "account_id": account_id,
                "category_id": cat_id,
                "amount": f"{20 + i}.00",
                "occurred_at": f"2026-04-{10 + i}T12:00:00Z",
            },
            headers=_auth(token),
        )
    await _seed_trashed(client, token, cat_id, account_id, 2)

    r = await client.delete("/transactions/trash", headers=_auth(token))
    assert r.json()["purged_count"] == 2

    active = await client.get("/transactions", headers=_auth(token))
    assert active.json()["total"] == 2


async def test_bulk_trash_endpoints_isolate_by_user(client: AsyncClient) -> None:
    """A no debe poder restaurar/purgar la papelera de B."""
    token_a, _cat_a, _account_a = await _setup_user(client, "bulktrashA@example.com")
    token_b, cat_b, account_b = await _setup_user(client, "bulktrashB@example.com")
    await _seed_trashed(client, token_b, cat_b, account_b, 2)

    r_restore = await client.post("/transactions/trash/restore", headers=_auth(token_a))
    r_purge = await client.delete("/transactions/trash", headers=_auth(token_a))
    assert r_restore.json()["restored_count"] == 0
    assert r_purge.json()["purged_count"] == 0

    # B sigue teniendo sus 2 en papelera.
    trash_b = await client.get("/transactions/trash", headers=_auth(token_b))
    assert trash_b.json()["total"] == 2
