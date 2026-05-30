"""Tests del campo `budget_alert` en POST /transactions (PHASE-14.5)."""

from __future__ import annotations

from datetime import date

from httpx import AsyncClient


async def _setup_user(client: AsyncClient, email: str = "ba@example.com") -> tuple[str, str, str]:
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


async def test_no_budget_returns_no_alert(client: AsyncClient) -> None:
    token, cat_id, account_id = await _setup_user(client, "ba1@example.com")
    today_iso = date.today().isoformat()
    r = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": cat_id,
            "amount": "10.00",
            "currency": "EUR",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    assert r.json()["budget_alert"] is None


async def test_under_warning_threshold_no_alert(client: AsyncClient) -> None:
    """Spent < 80% del budget → status ok → no alert."""
    token, cat_id, account_id = await _setup_user(client, "ba2@example.com")
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
    r = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": cat_id,
            "amount": "10.00",
            "currency": "EUR",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )
    assert r.json()["budget_alert"] is None


async def test_warning_threshold_emits_alert(client: AsyncClient) -> None:
    """Spent ≥ 80% → warning alert con porcentaje correcto."""
    token, cat_id, account_id = await _setup_user(client, "ba3@example.com")
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
    r = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": cat_id,
            "amount": "85.00",
            "currency": "EUR",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )
    alert = r.json()["budget_alert"]
    assert alert is not None
    assert alert["status"] == "warning"
    assert alert["percent_used"] == 85.0
    assert alert["category_id"] == cat_id
    assert "85" in alert["next_due_label"]
    assert "Comida" in alert["next_due_label"]


async def test_over_threshold_emits_alert(client: AsyncClient) -> None:
    """Spent > 100% → over alert."""
    token, cat_id, account_id = await _setup_user(client, "ba4@example.com")
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
    r = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": cat_id,
            "amount": "120.00",
            "currency": "EUR",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )
    alert = r.json()["budget_alert"]
    assert alert is not None
    assert alert["status"] == "over"
    assert alert["percent_used"] == 120.0


async def test_global_budget_triggers_alert(client: AsyncClient) -> None:
    """Tx en una categoría sin budget propio dispara el budget global."""
    token, cat_id, account_id = await _setup_user(client, "ba5@example.com")
    await client.post(
        "/budgets",
        json={
            "amount": "100.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
        },
        headers=_auth(token),
    )

    today_iso = date.today().isoformat()
    r = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": cat_id,
            "amount": "90.00",
            "currency": "EUR",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )
    alert = r.json()["budget_alert"]
    assert alert is not None
    assert alert["category_id"] is None  # global
    assert alert["status"] == "warning"
    assert "Presupuesto global" in alert["next_due_label"]


async def test_falls_through_to_global_when_category_budget_ok(
    client: AsyncClient,
) -> None:
    """Si el budget de la categoría está OK pero el global en over,
    se emite la alert del global (el detector itera y devuelve el
    primero con warning/over, no el primer candidato)."""
    token, cat_id, account_id = await _setup_user(client, "ba6@example.com")
    # Categoría grande (no se dispara con la tx).
    await client.post(
        "/budgets",
        json={
            "category_id": cat_id,
            "amount": "1000.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
        },
        headers=_auth(token),
    )
    # Global pequeño (la tx lo dispara).
    await client.post(
        "/budgets",
        json={
            "amount": "50.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
        },
        headers=_auth(token),
    )

    today_iso = date.today().isoformat()
    r = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": cat_id,
            "amount": "60.00",
            "currency": "EUR",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )
    alert = r.json()["budget_alert"]
    assert alert is not None
    assert alert["category_id"] is None  # global
    assert alert["status"] == "over"
