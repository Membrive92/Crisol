"""Tests de pause/resume/cancel para gastos fijos (PHASE-15.2,
renombrado en PHASE-17.1)."""

from __future__ import annotations

from datetime import date, timedelta

from httpx import AsyncClient


async def _setup_user(client: AsyncClient, email: str) -> tuple[str, str, str]:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    token = r.json()["access_token"]
    cat = await client.post(
        "/categories",
        json={"name": "Streaming", "kind": "expense"},
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


async def _create_pending_sub(
    client: AsyncClient, token: str, cat_id: str, account_id: str
) -> str:
    """Helper: crea 4 cargos mensuales y dispara scan → devuelve id
    de la pending creada."""
    today = date.today()
    for i in range(4):
        when = today - timedelta(days=30 * i)
        await client.post(
            "/transactions",
            json={
                "account_id": account_id,
                "category_id": cat_id,
                "amount": "12.99",
                "currency": "EUR",
                "occurred_at": f"{when.isoformat()}T12:00:00Z",
                "description": "NETFLIX.COM",
            },
            headers=_auth(token),
        )
    await client.post("/fixed-expenses/scan", headers=_auth(token))
    return (await client.get("/fixed-expenses", headers=_auth(token))).json()[0]["id"]


async def test_pause_only_from_confirmed(client: AsyncClient) -> None:
    """Sólo confirmed → paused. Desde pending → 409."""
    token, cat_id, account_id = await _setup_user(client, "pc1@example.com")
    sid = await _create_pending_sub(client, token, cat_id, account_id)

    # Pending → 409.
    r_pending = await client.post(
        f"/fixed-expenses/{sid}/pause", headers=_auth(token)
    )
    assert r_pending.status_code == 409

    # Confirmar primero.
    await client.post(f"/fixed-expenses/{sid}/confirm", headers=_auth(token))

    # Confirmed → pause OK.
    r = await client.post(f"/fixed-expenses/{sid}/pause", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["status"] == "paused"


async def test_resume_only_from_paused(client: AsyncClient) -> None:
    token, cat_id, account_id = await _setup_user(client, "pc2@example.com")
    sid = await _create_pending_sub(client, token, cat_id, account_id)
    await client.post(f"/fixed-expenses/{sid}/confirm", headers=_auth(token))

    # Confirmed → resume → 409 (no está paused).
    r_conf = await client.post(
        f"/fixed-expenses/{sid}/resume", headers=_auth(token)
    )
    assert r_conf.status_code == 409

    # Pause + resume.
    await client.post(f"/fixed-expenses/{sid}/pause", headers=_auth(token))
    r = await client.post(f"/fixed-expenses/{sid}/resume", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["status"] == "confirmed"


async def test_cancel_from_pending_confirmed_paused(client: AsyncClient) -> None:
    """cancel acepta desde cualquier estado activo (no dismissed)."""
    # Desde pending.
    token1, cat1, account1 = await _setup_user(client, "pc3a@example.com")
    sid1 = await _create_pending_sub(client, token1, cat1, account1)
    r1 = await client.post(f"/fixed-expenses/{sid1}/cancel", headers=_auth(token1))
    assert r1.status_code == 200
    assert r1.json()["status"] == "cancelled"

    # Desde confirmed.
    token2, cat2, account2 = await _setup_user(client, "pc3b@example.com")
    sid2 = await _create_pending_sub(client, token2, cat2, account2)
    await client.post(f"/fixed-expenses/{sid2}/confirm", headers=_auth(token2))
    r2 = await client.post(f"/fixed-expenses/{sid2}/cancel", headers=_auth(token2))
    assert r2.json()["status"] == "cancelled"

    # Desde paused.
    token3, cat3, account3 = await _setup_user(client, "pc3c@example.com")
    sid3 = await _create_pending_sub(client, token3, cat3, account3)
    await client.post(f"/fixed-expenses/{sid3}/confirm", headers=_auth(token3))
    await client.post(f"/fixed-expenses/{sid3}/pause", headers=_auth(token3))
    r3 = await client.post(f"/fixed-expenses/{sid3}/cancel", headers=_auth(token3))
    assert r3.json()["status"] == "cancelled"


async def test_cancel_blocked_from_dismissed(client: AsyncClient) -> None:
    """Una dismissed no se cancela — 409."""
    token, cat_id, account_id = await _setup_user(client, "pc4@example.com")
    sid = await _create_pending_sub(client, token, cat_id, account_id)
    await client.post(f"/fixed-expenses/{sid}/dismiss", headers=_auth(token))
    r = await client.post(f"/fixed-expenses/{sid}/cancel", headers=_auth(token))
    assert r.status_code == 409


async def test_paused_blocks_re_suggestion(client: AsyncClient) -> None:
    """Re-scan de una paused: la huella matchea → solo refresca, no
    crea nueva pending."""
    token, cat_id, account_id = await _setup_user(client, "pc5@example.com")
    sid = await _create_pending_sub(client, token, cat_id, account_id)
    await client.post(f"/fixed-expenses/{sid}/confirm", headers=_auth(token))
    await client.post(f"/fixed-expenses/{sid}/pause", headers=_auth(token))

    r = await client.post("/fixed-expenses/scan", headers=_auth(token))
    body = r.json()
    assert body["created"] == 0  # no duplica

    items = (await client.get("/fixed-expenses", headers=_auth(token))).json()
    assert len(items) == 1
    assert items[0]["status"] == "paused"  # status preservado
