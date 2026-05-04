"""Tests del soft-delete de transacciones (PHASE-10.1).

Cubre:
- DELETE mueve a papelera (no destruye).
- /trash lista soft-deleted ordenadas por deleted_at desc.
- restore vuelve a activa.
- purge sólo aplica a las que están en papelera.
- aislamiento entre usuarios.
- dashboard summary y top-expenses ignoran soft-deleted.
- imports dedup ignora soft-deleted.
"""

from __future__ import annotations

from httpx import AsyncClient


async def _setup_user(client: AsyncClient, email: str = "soft@example.com") -> tuple[str, str]:
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


async def _create_tx(
    client: AsyncClient,
    token: str,
    *,
    cat_id: str | None = None,
    amount: str = "10.00",
    when: str = "2026-04-15T12:00:00Z",
    description: str | None = None,
) -> str:
    body: dict[str, str | None] = {"amount": amount, "occurred_at": when}
    if cat_id is not None:
        body["category_id"] = cat_id
    if description is not None:
        body["description"] = description
    r = await client.post("/transactions", json=body, headers=_auth(token))
    assert r.status_code == 201
    return r.json()["id"]


async def test_delete_moves_to_trash_not_destructive(client: AsyncClient) -> None:
    token, cat_id = await _setup_user(client, "soft1@example.com")
    tx_id = await _create_tx(client, token, cat_id=cat_id)

    # DELETE devuelve 204 igual que antes.
    r = await client.delete(f"/transactions/{tx_id}", headers=_auth(token))
    assert r.status_code == 204

    # /transactions ya no la lista.
    r_list = await client.get("/transactions", headers=_auth(token))
    assert r_list.json()["total"] == 0

    # /transactions/{id} 404.
    r_get = await client.get(f"/transactions/{tx_id}", headers=_auth(token))
    assert r_get.status_code == 404

    # /transactions/trash sí — con deleted_at no NULL.
    r_trash = await client.get("/transactions/trash", headers=_auth(token))
    body = r_trash.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == tx_id
    assert body["items"][0]["deleted_at"] is not None


async def test_restore_returns_to_active(client: AsyncClient) -> None:
    token, cat_id = await _setup_user(client, "soft2@example.com")
    tx_id = await _create_tx(client, token, cat_id=cat_id)
    await client.delete(f"/transactions/{tx_id}", headers=_auth(token))

    r = await client.post(f"/transactions/{tx_id}/restore", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["deleted_at"] is None

    r_list = await client.get("/transactions", headers=_auth(token))
    assert r_list.json()["total"] == 1


async def test_restore_404_when_active(client: AsyncClient) -> None:
    """Restaurar una activa o inexistente devuelve 404, no no-op silencioso."""
    token, cat_id = await _setup_user(client, "soft3@example.com")
    tx_id = await _create_tx(client, token, cat_id=cat_id)

    r = await client.post(f"/transactions/{tx_id}/restore", headers=_auth(token))
    assert r.status_code == 404


async def test_purge_only_works_on_trashed(client: AsyncClient) -> None:
    token, cat_id = await _setup_user(client, "soft4@example.com")
    tx_id = await _create_tx(client, token, cat_id=cat_id)

    # Activa → purge debe ser 404 (forzar pasar por papelera primero).
    r_active = await client.delete(
        f"/transactions/{tx_id}/purge", headers=_auth(token)
    )
    assert r_active.status_code == 404

    # Soft-delete → ahora sí.
    await client.delete(f"/transactions/{tx_id}", headers=_auth(token))
    r_purge = await client.delete(
        f"/transactions/{tx_id}/purge", headers=_auth(token)
    )
    assert r_purge.status_code == 204

    # Ya no existe ni en papelera.
    r_trash = await client.get("/transactions/trash", headers=_auth(token))
    assert r_trash.json()["total"] == 0

    # Restore tampoco la encuentra.
    r_restore = await client.post(
        f"/transactions/{tx_id}/restore", headers=_auth(token)
    )
    assert r_restore.status_code == 404


async def test_trash_user_isolation(client: AsyncClient) -> None:
    """User A no puede listar/restaurar/purgar la papelera de User B."""
    token_a, cat_a = await _setup_user(client, "softA@example.com")
    token_b, _ = await _setup_user(client, "softB@example.com")

    tx_a = await _create_tx(client, token_a, cat_id=cat_a, description="A trashed")
    await client.delete(f"/transactions/{tx_a}", headers=_auth(token_a))

    # B no ve la papelera de A.
    r_b_trash = await client.get("/transactions/trash", headers=_auth(token_b))
    assert r_b_trash.json()["total"] == 0

    # B no puede restaurar la tx de A.
    r_b_restore = await client.post(
        f"/transactions/{tx_a}/restore", headers=_auth(token_b)
    )
    assert r_b_restore.status_code == 404

    # B no puede purgar la tx de A.
    r_b_purge = await client.delete(
        f"/transactions/{tx_a}/purge", headers=_auth(token_b)
    )
    assert r_b_purge.status_code == 404


async def test_trash_ordered_by_deleted_at_desc(client: AsyncClient) -> None:
    """La papelera devuelve los más recientes primero."""
    token, cat = await _setup_user(client, "softorder@example.com")
    tx_old = await _create_tx(client, token, cat_id=cat, description="vieja")
    tx_new = await _create_tx(client, token, cat_id=cat, description="nueva")

    await client.delete(f"/transactions/{tx_old}", headers=_auth(token))
    await client.delete(f"/transactions/{tx_new}", headers=_auth(token))

    body = (await client.get("/transactions/trash", headers=_auth(token))).json()
    assert body["total"] == 2
    # La última en borrarse va primero.
    assert body["items"][0]["id"] == tx_new
    assert body["items"][1]["id"] == tx_old


async def test_dashboard_summary_excludes_trashed(client: AsyncClient) -> None:
    """Una transacción trasheada no contribuye al summary del dashboard."""
    token, cat_id = await _setup_user(client, "softdash@example.com")
    tx_keep = await _create_tx(client, token, cat_id=cat_id, amount="100.00")
    tx_trash = await _create_tx(client, token, cat_id=cat_id, amount="999.00")

    # Antes de borrar: 2 transacciones, 1099 de gasto.
    r1 = await client.get(
        "/dashboard/summary", params={"currency": "EUR"}, headers=_auth(token)
    )
    assert r1.json()["transaction_count"] == 2
    assert float(r1.json()["expenses"]) == 1099.0

    await client.delete(f"/transactions/{tx_trash}", headers=_auth(token))

    # Después: la trasheada desaparece del summary.
    r2 = await client.get(
        "/dashboard/summary", params={"currency": "EUR"}, headers=_auth(token)
    )
    assert r2.json()["transaction_count"] == 1
    assert float(r2.json()["expenses"]) == 100.0
    # Sigue accesible vía papelera para la UI.
    r_trash = await client.get("/transactions/trash", headers=_auth(token))
    assert r_trash.json()["total"] == 1
    assert r_trash.json()["items"][0]["id"] == tx_trash
    # tx_keep no se ha tocado.
    assert (await client.get(f"/transactions/{tx_keep}", headers=_auth(token))).status_code == 200


async def test_top_expenses_excludes_trashed(client: AsyncClient) -> None:
    """El top de gastos del dashboard ignora soft-deleted."""
    token, cat_id = await _setup_user(client, "softtop@example.com")
    await _create_tx(client, token, cat_id=cat_id, amount="50.00", description="keep")
    tx_trash = await _create_tx(
        client, token, cat_id=cat_id, amount="500.00", description="trash"
    )
    await client.delete(f"/transactions/{tx_trash}", headers=_auth(token))

    r = await client.get(
        "/dashboard/top-expenses",
        params={"limit": 5, "currency": "EUR"},
        headers=_auth(token),
    )
    items = r.json()
    assert len(items) == 1
    assert items[0]["description"] == "keep"


async def test_imports_dedup_ignores_trashed(client: AsyncClient) -> None:
    """Importar un fichero cuya fila previa fue trasheada NO debe ser
    bloqueada por el dedup — el partial unique excluye soft-deleted.
    """
    import json

    token, _ = await _setup_user(client, "softimport@example.com")

    csv = b"date,amount,description\n2026-04-01,12.34,Coffee\n"
    column_mappings = json.dumps(
        {"amount": "amount", "occurred_at": "date", "description": "description"}
    )

    # Primer import.
    r1 = await client.post(
        "/imports",
        files={"file": ("a.csv", csv, "text/csv")},
        data={"column_mappings": column_mappings, "currency": "EUR"},
        headers=_auth(token),
    )
    assert r1.status_code == 201, r1.text
    assert r1.json()["rows_ok"] == 1, r1.text

    # Buscar la transacción y trashearla.
    txs = (await client.get("/transactions", headers=_auth(token))).json()["items"]
    tx_id = txs[0]["id"]
    await client.delete(f"/transactions/{tx_id}", headers=_auth(token))

    # Re-importar el mismo fichero — debe importar de nuevo (no dedup).
    r2 = await client.post(
        "/imports",
        files={"file": ("a.csv", csv, "text/csv")},
        data={"column_mappings": column_mappings, "currency": "EUR"},
        headers=_auth(token),
    )
    assert r2.status_code == 201, r2.text
    assert r2.json()["rows_ok"] == 1, (
        f"Soft-deleted no debería bloquear el dedup de imports — {r2.text}"
    )
