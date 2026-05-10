"""Tests del módulo transfers (PHASE-19.3) y de saldos por cuenta (PHASE-19.4)."""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient


async def _setup_user_with_two_accounts(
    client: AsyncClient, email: str = "tr@example.com"
) -> tuple[str, str, str, str]:
    """Registra usuario, crea categoría, dos cuentas. Devuelve
    (token, category_id, account_a_id, account_b_id)."""
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    cat = await client.post(
        "/categories",
        json={"name": "Sin clasificar", "kind": "expense"},
        headers=headers,
    )
    acc_a = await client.post(
        "/accounts",
        json={"name": "Cuenta corriente", "type": "bank", "currency": "EUR"},
        headers=headers,
    )
    acc_b = await client.post(
        "/accounts",
        json={"name": "Broker", "type": "brokerage", "currency": "EUR"},
        headers=headers,
    )
    return token, cat.json()["id"], acc_a.json()["id"], acc_b.json()["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_tx(
    client: AsyncClient,
    token: str,
    *,
    account_id: str,
    amount: str,
    occurred_at: str,
    category_id: str | None = None,
    description: str | None = None,
) -> str:
    """Helper para crear una tx; devuelve su id."""
    payload: dict[str, object] = {
        "account_id": account_id,
        "amount": amount,
        "occurred_at": occurred_at,
    }
    if category_id is not None:
        payload["category_id"] = category_id
    if description is not None:
        payload["description"] = description
    r = await client.post("/transactions", json=payload, headers=_auth(token))
    assert r.status_code == 201
    return r.json()["id"]


async def test_link_two_transactions_as_transfer(client: AsyncClient) -> None:
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(
        client, "link@example.com"
    )
    out_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="500.00",
        occurred_at="2026-04-15T12:00:00Z",
        description="Traspaso a broker",
    )
    in_id = await _create_tx(
        client,
        token,
        account_id=acc_b,
        amount="500.00",
        occurred_at="2026-04-15T13:00:00Z",
        description="Ingreso desde cte",
    )

    r = await client.post(
        "/transfers/link",
        json={"out_transaction_id": out_id, "in_transaction_id": in_id},
        headers=_auth(token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["out_transaction_id"] == out_id
    assert body["in_transaction_id"] == in_id

    # GET /transfers ahora lista el par
    pairs = (await client.get("/transfers", headers=_auth(token))).json()
    assert len(pairs) == 1
    assert pairs[0]["amount"] == "500.00"

    # Las dos txs reflejan transfer_pair_id
    out_tx = (
        await client.get(f"/transactions/{out_id}", headers=_auth(token))
    ).json()
    assert out_tx["transfer_pair_id"] == in_id


async def test_link_rejects_same_account(client: AsyncClient) -> None:
    token, _cat, acc_a, _acc_b = await _setup_user_with_two_accounts(
        client, "samelinked@example.com"
    )
    out_id = await _create_tx(
        client, token, account_id=acc_a, amount="100", occurred_at="2026-04-15T12:00:00Z"
    )
    in_id = await _create_tx(
        client, token, account_id=acc_a, amount="100", occurred_at="2026-04-15T12:00:00Z"
    )
    r = await client.post(
        "/transfers/link",
        json={"out_transaction_id": out_id, "in_transaction_id": in_id},
        headers=_auth(token),
    )
    assert r.status_code == 400


async def test_link_rejects_different_amounts(client: AsyncClient) -> None:
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(
        client, "diffamount@example.com"
    )
    out_id = await _create_tx(
        client, token, account_id=acc_a, amount="100", occurred_at="2026-04-15T12:00:00Z"
    )
    in_id = await _create_tx(
        client, token, account_id=acc_b, amount="200", occurred_at="2026-04-15T12:00:00Z"
    )
    r = await client.post(
        "/transfers/link",
        json={"out_transaction_id": out_id, "in_transaction_id": in_id},
        headers=_auth(token),
    )
    assert r.status_code == 400


async def test_link_rejects_already_paired(client: AsyncClient) -> None:
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(
        client, "already@example.com"
    )
    out_id = await _create_tx(
        client, token, account_id=acc_a, amount="50", occurred_at="2026-04-15T12:00:00Z"
    )
    in_id = await _create_tx(
        client, token, account_id=acc_b, amount="50", occurred_at="2026-04-15T12:00:00Z"
    )
    other_in = await _create_tx(
        client, token, account_id=acc_b, amount="50", occurred_at="2026-04-15T15:00:00Z"
    )

    first = await client.post(
        "/transfers/link",
        json={"out_transaction_id": out_id, "in_transaction_id": in_id},
        headers=_auth(token),
    )
    assert first.status_code == 201

    second = await client.post(
        "/transfers/link",
        json={"out_transaction_id": out_id, "in_transaction_id": other_in},
        headers=_auth(token),
    )
    assert second.status_code == 409


async def test_unlink_breaks_pair(client: AsyncClient) -> None:
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(
        client, "unlink@example.com"
    )
    out_id = await _create_tx(
        client, token, account_id=acc_a, amount="80", occurred_at="2026-04-15T12:00:00Z"
    )
    in_id = await _create_tx(
        client, token, account_id=acc_b, amount="80", occurred_at="2026-04-15T12:00:00Z"
    )
    await client.post(
        "/transfers/link",
        json={"out_transaction_id": out_id, "in_transaction_id": in_id},
        headers=_auth(token),
    )

    r = await client.delete(f"/transfers/{out_id}", headers=_auth(token))
    assert r.status_code == 204

    out_tx = (
        await client.get(f"/transactions/{out_id}", headers=_auth(token))
    ).json()
    assert out_tx["transfer_pair_id"] is None
    in_tx = (
        await client.get(f"/transactions/{in_id}", headers=_auth(token))
    ).json()
    assert in_tx["transfer_pair_id"] is None


async def test_match_links_unambiguous_pair(client: AsyncClient) -> None:
    """Una salida en A + una entrada en B con mismo importe y fecha
    cercana se enlazan automáticamente."""
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(
        client, "match1@example.com"
    )
    # Para que el matcher pueda distinguir kind=expense vs income,
    # creamos una categoría income separada.
    income_cat = await client.post(
        "/categories",
        json={"name": "Ingreso interno", "kind": "income"},
        headers=_auth(token),
    )
    expense_cat = await client.post(
        "/categories",
        json={"name": "Salida interna", "kind": "expense"},
        headers=_auth(token),
    )

    await _create_tx(
        client,
        token,
        account_id=acc_a,
        category_id=expense_cat.json()["id"],
        amount="120.00",
        occurred_at="2026-04-15T10:00:00Z",
    )
    await _create_tx(
        client,
        token,
        account_id=acc_b,
        category_id=income_cat.json()["id"],
        amount="120.00",
        occurred_at="2026-04-15T11:30:00Z",
    )

    r = await client.post("/transfers/match", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["linked_count"] == 1
    assert body["pending_candidates"] == []


async def test_match_keeps_ambiguous_for_user(client: AsyncClient) -> None:
    """Si hay dos salidas y dos entradas idénticas, el matcher NO
    enlaza nada y deja los candidatos para revisión manual."""
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(
        client, "match2@example.com"
    )
    # Sin categoría — caen en "unknown" y el matcher las cruza por
    # fecha + importe + cuentas.
    await _create_tx(
        client, token, account_id=acc_a, amount="200", occurred_at="2026-04-10T10:00:00Z"
    )
    await _create_tx(
        client, token, account_id=acc_a, amount="200", occurred_at="2026-04-12T10:00:00Z"
    )
    await _create_tx(
        client, token, account_id=acc_b, amount="200", occurred_at="2026-04-10T11:00:00Z"
    )
    await _create_tx(
        client, token, account_id=acc_b, amount="200", occurred_at="2026-04-12T11:00:00Z"
    )

    r = await client.post("/transfers/match", headers=_auth(token))
    body = r.json()
    assert body["linked_count"] == 0
    # Ambos pares (A1↔B1 y A2↔B2) son ambiguos → 2 candidatos.
    assert len(body["pending_candidates"]) == 2


async def test_paired_tx_excluded_from_dashboard_summary(
    client: AsyncClient,
) -> None:
    """Una transferencia interna no infla `expenses` ni `income` del
    summary del dashboard una vez emparejada."""
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(
        client, "exclsum@example.com"
    )
    expense_cat = await client.post(
        "/categories",
        json={"name": "Salida interna", "kind": "expense"},
        headers=_auth(token),
    )
    income_cat = await client.post(
        "/categories",
        json={"name": "Entrada interna", "kind": "income"},
        headers=_auth(token),
    )
    out_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        category_id=expense_cat.json()["id"],
        amount="300.00",
        occurred_at="2026-04-15T10:00:00Z",
    )
    in_id = await _create_tx(
        client,
        token,
        account_id=acc_b,
        category_id=income_cat.json()["id"],
        amount="300.00",
        occurred_at="2026-04-15T11:00:00Z",
    )

    # Antes de emparejar, ambas entran en el cómputo.
    summary_before = (
        await client.get(
            "/dashboard/summary?currency=EUR", headers=_auth(token)
        )
    ).json()
    assert Decimal(summary_before["income"]) == Decimal("300.00")
    assert Decimal(summary_before["expenses"]) == Decimal("300.00")

    # Emparejar y volver a consultar.
    await client.post(
        "/transfers/link",
        json={"out_transaction_id": out_id, "in_transaction_id": in_id},
        headers=_auth(token),
    )
    summary_after = (
        await client.get(
            "/dashboard/summary?currency=EUR", headers=_auth(token)
        )
    ).json()
    assert Decimal(summary_after["income"]) == Decimal("0")
    assert Decimal(summary_after["expenses"]) == Decimal("0")
    assert Decimal(summary_after["balance"]) == Decimal("0")


async def test_user_isolation_in_transfers(client: AsyncClient) -> None:
    """Usuario B no puede enlazar txs de A ni ver sus pares."""
    token_a, _, acc_a1, acc_a2 = await _setup_user_with_two_accounts(
        client, "isoTrA@example.com"
    )
    token_b = (
        await client.post(
            "/auth/register",
            json={
                "email": "isoTrB@example.com",
                "password": "SecurePass123",
                "display_name": "B",
            },
        )
    ).json()["access_token"]

    out_a = await _create_tx(
        client, token_a, account_id=acc_a1, amount="50", occurred_at="2026-04-15T12:00:00Z"
    )
    in_a = await _create_tx(
        client, token_a, account_id=acc_a2, amount="50", occurred_at="2026-04-15T12:00:00Z"
    )

    # B no puede enlazar
    r = await client.post(
        "/transfers/link",
        json={"out_transaction_id": out_a, "in_transaction_id": in_a},
        headers=_auth(token_b),
    )
    assert r.status_code == 404

    # B no ve los pares de A
    pairs_b = (await client.get("/transfers", headers=_auth(token_b))).json()
    assert pairs_b == []


async def test_account_balances_endpoint(client: AsyncClient) -> None:
    """`/accounts/balances` devuelve saldo por cuenta + agregados de
    patrimonio. Income suma, expense resta. Opening balance se incluye."""
    token, _cat, _acc_a, _acc_b = await _setup_user_with_two_accounts(
        client, "bal@example.com"
    )
    # Crea una tercera cuenta con opening_balance distinto de 0.
    acc_c = await client.post(
        "/accounts",
        json={
            "name": "Ahorro",
            "type": "savings",
            "currency": "EUR",
            "opening_balance": "1000.00",
        },
        headers=_auth(token),
    )
    expense_cat = await client.post(
        "/categories",
        json={"name": "Gasto", "kind": "expense"},
        headers=_auth(token),
    )
    income_cat = await client.post(
        "/categories",
        json={"name": "Ingreso", "kind": "income"},
        headers=_auth(token),
    )

    # En _acc_a creamos un gasto y un ingreso netos (-50 + 200 = +150).
    await _create_tx(
        client,
        token,
        account_id=_acc_a,
        category_id=expense_cat.json()["id"],
        amount="50",
        occurred_at="2026-04-15T12:00:00Z",
    )
    await _create_tx(
        client,
        token,
        account_id=_acc_a,
        category_id=income_cat.json()["id"],
        amount="200",
        occurred_at="2026-04-16T12:00:00Z",
    )

    balances = (
        await client.get("/accounts/balances", headers=_auth(token))
    ).json()

    by_id = {b["account_id"]: b for b in balances["items"]}
    bal_a = by_id[_acc_a]
    assert Decimal(bal_a["movements_balance"]) == Decimal("150.00")
    assert Decimal(bal_a["current_balance"]) == Decimal("150.00")
    bal_c = by_id[acc_c.json()["id"]]
    assert Decimal(bal_c["opening_balance"]) == Decimal("1000.00")
    assert Decimal(bal_c["movements_balance"]) == Decimal("0")
    assert Decimal(bal_c["current_balance"]) == Decimal("1000.00")

    # Total assets: opening + movements de las tres asset accounts.
    expected_total = Decimal("0") + Decimal("0") + Decimal("1000") + Decimal("150")
    assert Decimal(balances["total_assets"]) == expected_total
    assert Decimal(balances["total_liabilities"]) == Decimal("0")
    assert Decimal(balances["net_worth"]) == expected_total
    assert balances["mixed_currencies"] is False
    assert balances["reference_currency"] == "EUR"


async def test_list_transactions_filters_by_account(client: AsyncClient) -> None:
    """`GET /transactions?account_id=X` devuelve sólo las de esa cuenta."""
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(
        client, "filter@example.com"
    )
    await _create_tx(
        client, token, account_id=acc_a, amount="10", occurred_at="2026-04-15T12:00:00Z"
    )
    await _create_tx(
        client, token, account_id=acc_b, amount="20", occurred_at="2026-04-15T12:00:00Z"
    )
    await _create_tx(
        client, token, account_id=acc_b, amount="30", occurred_at="2026-04-16T12:00:00Z"
    )

    r = await client.get(f"/transactions?account_id={acc_b}", headers=_auth(token))
    body = r.json()
    assert body["total"] == 2
    for item in body["items"]:
        assert item["account_id"] == acc_b
