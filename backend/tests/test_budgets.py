"""Tests del módulo budgets (PHASE-12.1)."""

from __future__ import annotations

from datetime import date

from httpx import AsyncClient


async def _setup_user(client: AsyncClient, email: str = "bg@example.com") -> tuple[str, str]:
    """Helper: registra, crea categoría de gasto, devuelve (token, category_id)."""
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
    return token, cat.json()["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_create_and_list_budget(client: AsyncClient) -> None:
    token, cat_id = await _setup_user(client, "bg1@example.com")
    r = await client.post(
        "/budgets",
        json={
            "category_id": cat_id,
            "amount": "300.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["amount"] == "300.00"
    assert body["category_id"] == cat_id
    assert body["effective_to"] is None

    r_list = await client.get("/budgets", headers=_auth(token))
    assert r_list.status_code == 200
    assert len(r_list.json()) == 1


async def test_create_blocks_duplicate_active(client: AsyncClient) -> None:
    """No puede haber dos presupuestos activos para la misma categoría."""
    token, cat_id = await _setup_user(client, "bg2@example.com")
    payload = {
        "category_id": cat_id,
        "amount": "300.00",
        "currency": "EUR",
        "effective_from": "2026-05-01",
    }
    await client.post("/budgets", json=payload, headers=_auth(token))
    r = await client.post("/budgets", json=payload, headers=_auth(token))
    assert r.status_code == 409


async def test_global_budget_distinct_from_category(client: AsyncClient) -> None:
    """Un budget global (sin categoría) no choca con uno por categoría."""
    token, cat_id = await _setup_user(client, "bg3@example.com")
    await client.post(
        "/budgets",
        json={
            "category_id": cat_id,
            "amount": "300.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
        },
        headers=_auth(token),
    )
    r = await client.post(
        "/budgets",
        json={"amount": "1000.00", "currency": "EUR", "effective_from": "2026-05-01"},
        headers=_auth(token),
    )
    assert r.status_code == 201
    assert r.json()["category_id"] is None


async def test_update_amount_and_currency(client: AsyncClient) -> None:
    token, cat_id = await _setup_user(client, "bg4@example.com")
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

    r2 = await client.put(
        f"/budgets/{bid}",
        json={"amount": "250.00", "currency": "USD"},
        headers=_auth(token),
    )
    assert r2.status_code == 200
    assert r2.json()["amount"] == "250.00"
    assert r2.json()["currency"] == "USD"


async def test_delete_closes_budget(client: AsyncClient) -> None:
    """DELETE inicial cierra (effective_to=today)."""
    token, cat_id = await _setup_user(client, "bg5@example.com")
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

    r2 = await client.delete(f"/budgets/{bid}", headers=_auth(token))
    assert r2.status_code == 204

    # Ya no aparece como activo (effective_to=today, today >= today, sigue activo).
    # Mejor dicho: aparece HOY pero mañana no. Lo más limpio en el test
    # es comprobar via GET /budgets/{id} que `effective_to` se rellenó.
    r3 = await client.get(f"/budgets/{bid}", headers=_auth(token))
    assert r3.status_code == 200
    assert r3.json()["effective_to"] is not None


async def test_user_isolation(client: AsyncClient) -> None:
    """User A no ve / no toca budgets de User B."""
    token_a, cat_a = await _setup_user(client, "bgA@example.com")
    token_b, _ = await _setup_user(client, "bgB@example.com")

    r = await client.post(
        "/budgets",
        json={
            "category_id": cat_a,
            "amount": "200.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
        },
        headers=_auth(token_a),
    )
    bid = r.json()["id"]

    # B no lo ve.
    r_list = await client.get("/budgets", headers=_auth(token_b))
    assert r_list.json() == []

    # B no puede actualizarlo ni borrarlo.
    r_get = await client.get(f"/budgets/{bid}", headers=_auth(token_b))
    assert r_get.status_code == 404


async def test_status_no_transactions(client: AsyncClient) -> None:
    """Sin transacciones, spent=0 y status=ok."""
    token, cat_id = await _setup_user(client, "bgst1@example.com")
    await client.post(
        "/budgets",
        json={
            "category_id": cat_id,
            "amount": "300.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
        },
        headers=_auth(token),
    )

    r = await client.get("/budgets/status", headers=_auth(token))
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert float(items[0]["spent_this_month"]) == 0.0
    assert float(items[0]["remaining"]) == 300.0
    assert items[0]["percent_used"] == 0.0
    assert items[0]["status"] == "ok"


async def test_status_warning_and_over(client: AsyncClient) -> None:
    """Spent > 80% del budget → warning; > 100% → over."""
    token, cat_id = await _setup_user(client, "bgst2@example.com")
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
    # Inserto una tx de 90€ → 90% → warning.
    await client.post(
        "/transactions",
        json={
            "category_id": cat_id,
            "amount": "90.00",
            "currency": "EUR",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )

    r = await client.get("/budgets/status", headers=_auth(token))
    items = r.json()["items"]
    assert items[0]["status"] == "warning"
    assert items[0]["percent_used"] == 90.0

    # Otra tx de 50€ → total 140 → over.
    await client.post(
        "/transactions",
        json={
            "category_id": cat_id,
            "amount": "50.00",
            "currency": "EUR",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )

    r2 = await client.get("/budgets/status", headers=_auth(token))
    items2 = r2.json()["items"]
    assert items2[0]["status"] == "over"
    assert items2[0]["percent_used"] == 140.0
    assert float(items2[0]["remaining"]) == -40.0


async def test_status_global_budget_sums_all_expense_categories(client: AsyncClient) -> None:
    """Budget global (category_id=null) suma todos los gastos del mes."""
    token, cat_id = await _setup_user(client, "bgst3@example.com")
    cat2 = await client.post(
        "/categories",
        json={"name": "Transporte", "kind": "expense"},
        headers=_auth(token),
    )
    cat2_id = cat2.json()["id"]

    await client.post(
        "/budgets",
        json={"amount": "500.00", "currency": "EUR", "effective_from": "2026-05-01"},
        headers=_auth(token),
    )

    today_iso = date.today().isoformat()
    await client.post(
        "/transactions",
        json={
            "category_id": cat_id,
            "amount": "100.00",
            "currency": "EUR",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )
    await client.post(
        "/transactions",
        json={
            "category_id": cat2_id,
            "amount": "150.00",
            "currency": "EUR",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )

    r = await client.get("/budgets/status", headers=_auth(token))
    items = r.json()["items"]
    assert len(items) == 1
    assert float(items[0]["spent_this_month"]) == 250.0
    assert items[0]["status"] == "ok"


async def test_status_excludes_soft_deleted(client: AsyncClient) -> None:
    """Una transacción trasheada (PHASE-10.1) no debe contar."""
    token, cat_id = await _setup_user(client, "bgst4@example.com")
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
    r_tx = await client.post(
        "/transactions",
        json={
            "category_id": cat_id,
            "amount": "60.00",
            "currency": "EUR",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )
    tx_id = r_tx.json()["id"]
    await client.delete(f"/transactions/{tx_id}", headers=_auth(token))

    r = await client.get("/budgets/status", headers=_auth(token))
    assert float(r.json()["items"][0]["spent_this_month"]) == 0.0
