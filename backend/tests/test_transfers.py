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
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(client, "link@example.com")
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
    out_tx = (await client.get(f"/transactions/{out_id}", headers=_auth(token))).json()
    assert out_tx["transfer_pair_id"] == in_id


async def test_soft_delete_unlinks_transfer_pair(client: AsyncClient) -> None:
    """AUDIT-2026-05 — al trashear una pata del par, la pareja se
    desvincula (no queda apuntando a una fila borrada: invisible en
    /transfers pero excluida del cashflow)."""
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(
        client, "softdel_pair@example.com"
    )
    out_id = await _create_tx(
        client, token, account_id=acc_a, amount="300.00", occurred_at="2026-04-15T12:00:00Z"
    )
    in_id = await _create_tx(
        client, token, account_id=acc_b, amount="300.00", occurred_at="2026-04-15T13:00:00Z"
    )
    link = await client.post(
        "/transfers/link",
        json={"out_transaction_id": out_id, "in_transaction_id": in_id},
        headers=_auth(token),
    )
    assert link.status_code == 201

    # Soft-delete (papelera) de la pata de salida.
    delete = await client.delete(f"/transactions/{out_id}", headers=_auth(token))
    assert delete.status_code in (200, 204), delete.text

    # El par ya no aparece y la pareja superviviente quedó desvinculada.
    pairs = (await client.get("/transfers", headers=_auth(token))).json()
    assert pairs == []
    in_tx = (await client.get(f"/transactions/{in_id}", headers=_auth(token))).json()
    assert in_tx["transfer_pair_id"] is None


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
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(client, "already@example.com")
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
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(client, "unlink@example.com")
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

    out_tx = (await client.get(f"/transactions/{out_id}", headers=_auth(token))).json()
    assert out_tx["transfer_pair_id"] is None
    in_tx = (await client.get(f"/transactions/{in_id}", headers=_auth(token))).json()
    assert in_tx["transfer_pair_id"] is None


async def test_match_links_unambiguous_pair(client: AsyncClient) -> None:
    """Una salida en A + una entrada en B con mismo importe y fecha
    cercana se enlazan automáticamente."""
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(client, "match1@example.com")
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
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(client, "match2@example.com")
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
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(client, "exclsum@example.com")
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
        await client.get("/dashboard/summary?currency=EUR", headers=_auth(token))
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
        await client.get("/dashboard/summary?currency=EUR", headers=_auth(token))
    ).json()
    assert Decimal(summary_after["income"]) == Decimal("0")
    assert Decimal(summary_after["expenses"]) == Decimal("0")
    assert Decimal(summary_after["balance"]) == Decimal("0")


async def test_user_isolation_in_transfers(client: AsyncClient) -> None:
    """Usuario B no puede enlazar txs de A ni ver sus pares."""
    token_a, _, acc_a1, acc_a2 = await _setup_user_with_two_accounts(client, "isoTrA@example.com")
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
    token, _cat, _acc_a, _acc_b = await _setup_user_with_two_accounts(client, "bal@example.com")
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

    balances = (await client.get("/accounts/balances", headers=_auth(token))).json()

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
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(client, "filter@example.com")
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


# ---------------------------------------------------------------------------
# PHASE-23.1 — Category.is_transfer + suspects + mark + from-source
# ---------------------------------------------------------------------------


async def test_suspects_only_returns_unmatched_with_transfer_in_description(
    client: AsyncClient,
) -> None:
    """`GET /transfers/suspects` devuelve SÓLO txs activas, sin pareja,
    no categorizadas con is_transfer=true, cuya descripción contiene
    "transfer" (case insensitive)."""
    token, cat, acc_a, _acc_b = await _setup_user_with_two_accounts(client, "suspects@example.com")
    yes_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="100.00",
        occurred_at="2026-04-15T12:00:00Z",
        category_id=cat,
        description="TRANSFERENCIA REALIZADA",
    )
    await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="50.00",
        occurred_at="2026-04-15T12:00:00Z",
        category_id=cat,
        description="Compra supermercado",
    )

    r = await client.get("/transfers/suspects", headers=_auth(token))
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["transaction_id"] == yes_id
    assert items[0]["description"] == "TRANSFERENCIA REALIZADA"


async def test_suspects_detects_spanish_bank_terms(client: AsyncClient) -> None:
    """P1 (transfers-ux) — el descubrimiento cubre términos de banca
    española (BIZUM, TRASPASO), no sólo el inglés "transfer". Antes esos
    movimientos — los más frecuentes — quedaban invisibles a /transfers."""
    token, cat, acc_a, _acc_b = await _setup_user_with_two_accounts(
        client, "suspects-es@example.com"
    )
    bizum_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="20.00",
        occurred_at="2026-04-15T12:00:00Z",
        category_id=cat,
        description="BIZUM A JOSE",
    )
    traspaso_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="500.00",
        occurred_at="2026-04-16T12:00:00Z",
        category_id=cat,
        description="TRASPASO ENTRE CUENTAS",
    )
    # Un gasto normal NO debe aparecer (evita inundar la bandeja).
    await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="9.00",
        occurred_at="2026-04-17T12:00:00Z",
        category_id=cat,
        description="MERCADONA TORRE PACHECO",
    )

    r = await client.get("/transfers/suspects", headers=_auth(token))
    assert r.status_code == 200
    items = r.json()
    ids = {it["transaction_id"] for it in items}
    descs = {it["description"] for it in items}
    assert bizum_id in ids
    assert traspaso_id in ids
    assert "MERCADONA TORRE PACHECO" not in descs


async def test_mark_uses_seed_transfer_category_with_correct_kind(
    client: AsyncClient,
) -> None:
    """Marcar una tx con descripción "REALIZADA" (saliente) usa una
    categoría is_transfer=true + kind=EXPENSE. El seed crea
    "Transferencias" en el registro del usuario; al marcar, la
    asignamos sin crear duplicado."""
    token, _cat, acc_a, _acc_b = await _setup_user_with_two_accounts(
        client, "mark-create@example.com"
    )
    tx_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="200.00",
        occurred_at="2026-04-15T12:00:00Z",
        description="TRANSFERENCIA enviada",
    )

    r = await client.post(
        "/transfers/mark",
        json={"transaction_id": tx_id},
        headers=_auth(token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["transaction_id"] == tx_id

    cats = await client.get("/categories", headers=_auth(token))
    transfer_cats = [c for c in cats.json() if c["is_transfer"]]
    # El seed crea "Transferencias" (expense, is_transfer=true). La
    # asignación reutiliza esa categoría, no crea duplicado.
    expense_transfer = [c for c in transfer_cats if c["kind"] == "expense"]
    assert len(expense_transfer) == 1
    assert body["category_id"] == expense_transfer[0]["id"]

    # La tx ya no aparece como sospechosa
    r2 = await client.get("/transfers/suspects", headers=_auth(token))
    assert r2.json() == []


async def test_mark_infers_income_kind_from_recibida_description(
    client: AsyncClient,
) -> None:
    """Una tx con "RECIBIDA" en descripción se marca con kind=INCOME.
    Tras PHASE-31.1 el seed trae "Transferencia a favor" (INCOME,
    is_transfer) lista — `get_or_create_default_transfer_category`
    devuelve esa en lugar de crear "Transferencia interna (entrada)".
    Lo importante es que la asignación preserva +amount al saldo
    (asset+income → +amount), no el nombre exacto.
    """
    token, _cat, acc_a, _acc_b = await _setup_user_with_two_accounts(
        client, "mark-incoming@example.com"
    )
    tx_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="300.00",
        occurred_at="2026-04-15T12:00:00Z",
        description="TRANSFERENCIA RECIBIDA DE Jose",
    )
    r = await client.post(
        "/transfers/mark",
        json={"transaction_id": tx_id},
        headers=_auth(token),
    )
    assert r.status_code == 201
    # La categoría asignada debe ser is_transfer=true + INCOME, sin
    # importar si la creó el seed (PHASE-31.1) o el helper legacy.
    body = r.json()
    cats_all = await client.get("/categories", headers=_auth(token))
    target_cat = next(c for c in cats_all.json() if c["id"] == body["category_id"])
    assert target_cat["kind"] == "income"
    assert target_cat["is_transfer"] is True

    cats = await client.get("/categories", headers=_auth(token))
    income_transfer = [c for c in cats.json() if c["is_transfer"] and c["kind"] == "income"]
    assert len(income_transfer) == 1


async def test_mark_409_when_tx_already_paired(client: AsyncClient) -> None:
    """No se puede marcar una tx que ya forma parte de un par."""
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(
        client, "mark-paired@example.com"
    )
    out_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="400.00",
        occurred_at="2026-04-15T12:00:00Z",
        description="transfer out",
    )
    in_id = await _create_tx(
        client,
        token,
        account_id=acc_b,
        amount="400.00",
        occurred_at="2026-04-15T12:00:00Z",
        description="transfer in",
    )
    link = await client.post(
        "/transfers/link",
        json={"out_transaction_id": out_id, "in_transaction_id": in_id},
        headers=_auth(token),
    )
    assert link.status_code == 201

    r = await client.post(
        "/transfers/mark",
        json={"transaction_id": out_id},
        headers=_auth(token),
    )
    assert r.status_code == 409


async def test_mark_excludes_tx_from_dashboard_cashflow_preserves_balance(
    client: AsyncClient,
) -> None:
    """Marcar como transferencia (PHASE-23.1):
    - Saca la tx del cashflow agregado (expenses=0).
    - **Conserva** el signo en el saldo de la cuenta (-500 en ASSET).
    """
    token, expense_cat, acc_a, _acc_b = await _setup_user_with_two_accounts(
        client, "mark-balance@example.com"
    )
    await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="500.00",
        occurred_at="2026-04-15T12:00:00Z",
        category_id=expense_cat,
        description="TRANSFER realizada",
    )
    r1 = await client.get("/dashboard/summary?currency=EUR", headers=_auth(token))
    assert Decimal(r1.json()["expenses"]) == Decimal("500.00")

    # Get the actual tx_id from the list
    tx_list = await client.get(f"/transactions?account_id={acc_a}", headers=_auth(token))
    tx_id = tx_list.json()["items"][0]["id"]

    await client.post(
        "/transfers/mark",
        json={"transaction_id": tx_id},
        headers=_auth(token),
    )
    # Cashflow ya no la cuenta
    r2 = await client.get("/dashboard/summary?currency=EUR", headers=_auth(token))
    assert Decimal(r2.json()["expenses"]) == Decimal("0.00")

    # Saldo SÍ refleja el movimiento: -500 (asset + expense kind)
    balances = await client.get("/accounts/balances", headers=_auth(token))
    acc_a_balance = next(b for b in balances.json()["items"] if b["account_id"] == acc_a)
    assert Decimal(acc_a_balance["movements_balance"]) == Decimal("-500.00")


async def test_matcher_skips_is_transfer_categorized_txs(
    client: AsyncClient,
) -> None:
    """El matcher heurístico ignora txs ya marcadas como transferencia
    (categoría is_transfer=true) — no necesitan emparejarse."""
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(
        client, "matcher-skip@example.com"
    )
    out_cat = await client.post(
        "/categories",
        json={"name": "TrOut", "kind": "expense", "is_transfer": True},
        headers=_auth(token),
    )
    in_cat = await client.post(
        "/categories",
        json={"name": "TrIn", "kind": "income", "is_transfer": True},
        headers=_auth(token),
    )
    await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="600.00",
        occurred_at="2026-04-15T12:00:00Z",
        category_id=out_cat.json()["id"],
    )
    await _create_tx(
        client,
        token,
        account_id=acc_b,
        amount="600.00",
        occurred_at="2026-04-15T12:00:00Z",
        category_id=in_cat.json()["id"],
    )

    r = await client.post("/transfers/match", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["linked_count"] == 0
    assert r.json()["pending_candidates"] == []


async def test_from_source_creates_counterpart_and_pairs(
    client: AsyncClient,
) -> None:
    """`POST /transfers/from-source` convierte una tx existente en una
    transferencia interna:
    - Crea contraparte en la cuenta opuesta del par ordenante/beneficiaria.
    - Misma cantidad/moneda/fecha.
    - Empareja ambas vía transfer_pair_id.
    - Ambas cuentas reflejan el movimiento en sus saldos.
    - Ambas fuera del cashflow agregado.
    """
    token, expense_cat, acc_a, acc_b = await _setup_user_with_two_accounts(
        client, "fromsource@example.com"
    )
    source_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="1000.00",
        occurred_at="2026-04-15T12:00:00Z",
        category_id=expense_cat,
        description="Traspaso a broker",
    )

    r = await client.post(
        "/transfers/from-source",
        json={
            "source_transaction_id": source_id,
            "originating_account_id": acc_a,
            "beneficiary_account_id": acc_b,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    pair = r.json()
    assert pair["amount"] == "1000.00"
    assert pair["currency"] == "EUR"
    assert pair["out_account_id"] == acc_a
    assert pair["in_account_id"] == acc_b

    # Saldos: A -1000, B +1000
    balances = await client.get("/accounts/balances", headers=_auth(token))
    by_id = {b["account_id"]: b for b in balances.json()["items"]}
    assert Decimal(by_id[acc_a]["movements_balance"]) == Decimal("-1000.00")
    assert Decimal(by_id[acc_b]["movements_balance"]) == Decimal("1000.00")

    # Cashflow: cero (par emparejado excluido)
    summary = await client.get("/dashboard/summary?currency=EUR", headers=_auth(token))
    assert Decimal(summary.json()["expenses"]) == Decimal("0.00")
    assert Decimal(summary.json()["income"]) == Decimal("0.00")


async def test_update_paired_tx_protects_invariants(client: AsyncClient) -> None:
    """P8 (transfers-ux) — editar el importe / moneda / cuenta de una pata
    emparejada se rechaza con 409 (descuadraría el par). Editar la
    descripción sí se permite."""
    token, expense_cat, acc_a, acc_b = await _setup_user_with_two_accounts(
        client, "p8-edit@example.com"
    )
    source_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="1000.00",
        occurred_at="2026-04-15T12:00:00Z",
        category_id=expense_cat,
        description="Traspaso",
    )
    r = await client.post(
        "/transfers/from-source",
        json={
            "source_transaction_id": source_id,
            "originating_account_id": acc_a,
            "beneficiary_account_id": acc_b,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text

    # Cambiar importe → 409.
    r_amount = await client.put(
        f"/transactions/{source_id}", json={"amount": "999.00"}, headers=_auth(token)
    )
    assert r_amount.status_code == 409

    # Cambiar cuenta → 409.
    r_acc = await client.put(
        f"/transactions/{source_id}", json={"account_id": acc_b}, headers=_auth(token)
    )
    assert r_acc.status_code == 409

    # Cambiar descripción → 200 (no rompe el par).
    r_desc = await client.put(
        f"/transactions/{source_id}",
        json={"description": "Traspaso (corregido)"},
        headers=_auth(token),
    )
    assert r_desc.status_code == 200, r_desc.text
    assert r_desc.json()["description"] == "Traspaso (corregido)"


async def test_from_source_400_same_account(client: AsyncClient) -> None:
    """No se puede convertir si ordenante y beneficiaria son iguales."""
    token, _cat, acc_a, _acc_b = await _setup_user_with_two_accounts(
        client, "fromsource-same@example.com"
    )
    source_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="50.00",
        occurred_at="2026-04-15T12:00:00Z",
    )
    r = await client.post(
        "/transfers/from-source",
        json={
            "source_transaction_id": source_id,
            "originating_account_id": acc_a,
            "beneficiary_account_id": acc_a,
        },
        headers=_auth(token),
    )
    assert r.status_code == 400


async def test_from_source_400_different_currency(client: AsyncClient) -> None:
    """Cross-currency aún no soportado — debe rechazarse."""
    token, _cat, acc_a, _acc_b = await _setup_user_with_two_accounts(
        client, "fromsource-fx@example.com"
    )
    # Tercera cuenta en USD
    headers = _auth(token)
    usd_acc = await client.post(
        "/accounts",
        json={"name": "Broker USD", "type": "brokerage", "currency": "USD"},
        headers=headers,
    )
    source_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="100.00",
        occurred_at="2026-04-15T12:00:00Z",
    )
    r = await client.post(
        "/transfers/from-source",
        json={
            "source_transaction_id": source_id,
            "originating_account_id": acc_a,
            "beneficiary_account_id": usd_acc.json()["id"],
        },
        headers=headers,
    )
    assert r.status_code == 400


async def test_from_source_400_when_source_not_in_pair(client: AsyncClient) -> None:
    """Si la tx origen no pertenece a ni ordenante ni beneficiaria,
    devuelve 400 — el usuario eligió un par incompatible con la tx
    que está convirtiendo (no se puede crear ambos lados desde cero
    en este endpoint)."""
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(
        client, "fromsource-notinpair@example.com"
    )
    # Tercera cuenta para usarla como ordenante en el body, pero la tx
    # vive en acc_a — debería ser 400.
    headers = _auth(token)
    third_acc = await client.post(
        "/accounts",
        json={"name": "Otra EUR", "type": "savings", "currency": "EUR"},
        headers=headers,
    )
    third_id = third_acc.json()["id"]
    source_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="50.00",
        occurred_at="2026-04-15T12:00:00Z",
    )
    r = await client.post(
        "/transfers/from-source",
        json={
            "source_transaction_id": source_id,
            "originating_account_id": third_id,
            "beneficiary_account_id": acc_b,
        },
        headers=headers,
    )
    assert r.status_code == 400


async def test_from_source_incoming_overrides_wrong_category(
    client: AsyncClient,
) -> None:
    """Caso del bug original: la tx vive en BBVA (acc_a) y fue
    importada con categoría EXPENSE ("Transferencias (Gasto)") aunque
    en realidad era un ABONO. Al convertirla marcando acc_a como
    BENEFICIARIA, el sistema fuerza la categoría origen a INCOME y
    los saldos quedan: ordenante -1000, beneficiaria +1000."""
    token, expense_cat, acc_a, acc_b = await _setup_user_with_two_accounts(
        client, "fromsource-incoming@example.com"
    )
    # Tx en BBVA con categoría EXPENSE mal asignada (caso post-import).
    source_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="1000.00",
        occurred_at="2026-02-02T12:00:00Z",
        category_id=expense_cat,
        description="TRANSFERENCIA RECIBIDA Ws",
    )

    r = await client.post(
        "/transfers/from-source",
        json={
            "source_transaction_id": source_id,
            # acc_a (donde vive la tx) es BENEFICIARIA: el dinero ENTRÓ.
            "originating_account_id": acc_b,
            "beneficiary_account_id": acc_a,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    pair = r.json()
    assert pair["out_account_id"] == acc_b
    assert pair["in_account_id"] == acc_a

    balances = await client.get("/accounts/balances", headers=_auth(token))
    by_id = {b["account_id"]: b for b in balances.json()["items"]}
    # BBVA gana 1000 (beneficiaria), no pierde 1000 — éste es el fix.
    assert Decimal(by_id[acc_a]["movements_balance"]) == Decimal("1000.00")
    assert Decimal(by_id[acc_b]["movements_balance"]) == Decimal("-1000.00")


# ---------------------------------------------------------------------------
# PHASE-24 — convertir tx en operación financiada (deuda con plan de pago)
# ---------------------------------------------------------------------------


async def test_from_source_debt_creates_new_liability_and_pairs(
    client: AsyncClient,
) -> None:
    """`POST /transfers/from-source-debt` con `new_liability` crea la
    cuenta de deuda al vuelo + contraparte + empareja.

    Fix activo-fantasma: la pata-ACTIVO del par (el "abono" en BBVA) es
    dinero PRESTADO, no ahorro disponible, así que aporta 0 al saldo del
    activo y a `total_assets`. La pata-PASIVO sí eleva la deuda. Cashflow
    agregado: 0 (par excluido).
    """
    token, _expense_cat, acc_a, _acc_b = await _setup_user_with_two_accounts(
        client, "debt-new@example.com"
    )
    # Categoría INCOME (el extracto del banco abona el importe). NO es
    # is_transfer a propósito: el fix debe excluir la pata-activo por la
    # señal "pareja=liability", no por la categoría.
    income_cat = await client.post(
        "/categories",
        json={"name": "Op. financiada (abono)", "kind": "income"},
        headers=_auth(token),
    )
    # +824.77€ "abono" de operación financiada en BBVA (asset)
    source_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="824.77",
        occurred_at="2026-04-15T12:00:00Z",
        category_id=income_cat.json()["id"],
        description="OPERACION FINANCIADA CON TARJETA",
    )

    r = await client.post(
        "/transfers/from-source-debt",
        json={
            "source_transaction_id": source_id,
            "new_liability": {
                "name": "Tarjeta financiada BBVA",
                "type": "credit_card",
                "currency": "EUR",
                "color": "#ef4444",
                "icon": "💳",
            },
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    pair = r.json()
    assert pair["amount"] == "824.77"
    assert pair["currency"] == "EUR"

    # La nueva cuenta liability existe con nature=liability
    accs = await client.get("/accounts?include_archived=false", headers=_auth(token))
    new_acc = next(a for a in accs.json() if a["name"] == "Tarjeta financiada BBVA")
    assert new_acc["nature"] == "liability"
    assert new_acc["type"] == "credit_card"

    # Balances: la pata-activo del par de deuda NO infla el activo (0),
    # pero la deuda sí sube (+824.77). total_assets excluye el fantasma y
    # net_worth refleja la deuda completa (-824.77, sin compensar).
    balances = await client.get("/accounts/balances", headers=_auth(token))
    body = balances.json()
    by_id = {b["account_id"]: b for b in body["items"]}
    assert Decimal(by_id[acc_a]["movements_balance"]) == Decimal("0.00")
    assert Decimal(by_id[new_acc["id"]]["movements_balance"]) == Decimal("824.77")
    assert Decimal(body["total_assets"]) == Decimal("0.00")
    assert Decimal(body["total_liabilities"]) == Decimal("824.77")
    assert Decimal(body["net_worth"]) == Decimal("-824.77")

    # Cashflow agregado: cero (par emparejado excluido)
    summary = await client.get("/dashboard/summary?currency=EUR", headers=_auth(token))
    assert Decimal(summary.json()["expenses"]) == Decimal("0.00")
    assert Decimal(summary.json()["income"]) == Decimal("0.00")


async def test_from_source_debt_uses_existing_liability(
    client: AsyncClient,
) -> None:
    """Si la liability ya existe, la usa sin crear nada nuevo."""
    token, expense_cat, acc_a, _acc_b = await _setup_user_with_two_accounts(
        client, "debt-existing@example.com"
    )
    headers = _auth(token)
    liability = await client.post(
        "/accounts",
        json={
            "name": "Tarjeta",
            "type": "credit_card",
            "currency": "EUR",
        },
        headers=headers,
    )
    liability_id = liability.json()["id"]
    source_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="500.00",
        occurred_at="2026-04-15T12:00:00Z",
        category_id=expense_cat,
        description="OPERACION FINANCIADA",
    )
    r = await client.post(
        "/transfers/from-source-debt",
        json={
            "source_transaction_id": source_id,
            "destination_account_id": liability_id,
        },
        headers=headers,
    )
    assert r.status_code == 201
    # No se ha creado una segunda cuenta — sigue habiendo sólo las
    # iniciales del test + la liability creada manualmente.
    accs = await client.get("/accounts", headers=headers)
    liabilities = [a for a in accs.json() if a["nature"] == "liability"]
    assert len(liabilities) == 1

    # El fix es agnóstico al kind del origen: aquí la tx origen es un
    # GASTO (-500) en el activo. Tras convertirla a deuda, la pata-activo
    # se anula igual (no resta del activo) y la deuda sube +500.
    balances = await client.get("/accounts/balances", headers=headers)
    body = balances.json()
    by_id = {b["account_id"]: b for b in body["items"]}
    assert Decimal(by_id[acc_a]["movements_balance"]) == Decimal("0.00")
    assert Decimal(by_id[liability_id]["movements_balance"]) == Decimal("500.00")
    assert Decimal(body["total_liabilities"]) == Decimal("500.00")
    assert Decimal(body["net_worth"]) == Decimal("-500.00")


async def test_list_transactions_flags_is_debt_pair(client: AsyncClient) -> None:
    """El listado expone `is_debt_pair=True` en AMBAS patas de un par de
    conversión a deuda (activo↔pasivo) y `False` en transferencias
    internas (activo↔activo) y movimientos normales. La UI usa la señal
    para el badge "Deuda" y para pintar el importe en neutro (coherente
    con el fix activo-fantasma: la pata-activo aporta 0 al patrimonio).
    """
    token, expense_cat, acc_a, acc_b = await _setup_user_with_two_accounts(
        client, "debtflag@example.com"
    )

    # 1) Movimiento normal (sin par) → is_debt_pair False.
    normal_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="10.00",
        occurred_at="2026-04-10T12:00:00Z",
        category_id=expense_cat,
        description="Compra normal",
    )

    # 2) Transferencia interna activo↔activo (200) → False en ambas patas.
    transfer_src = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="200.00",
        occurred_at="2026-04-11T12:00:00Z",
        category_id=expense_cat,
        description="Traspaso a broker",
    )
    rt = await client.post(
        "/transfers/from-source",
        json={
            "source_transaction_id": transfer_src,
            "originating_account_id": acc_a,
            "beneficiary_account_id": acc_b,
        },
        headers=_auth(token),
    )
    assert rt.status_code == 201, rt.text

    # 3) Conversión a deuda activo↔pasivo (824.77) → True en ambas patas.
    income_cat = await client.post(
        "/categories",
        json={"name": "Abono financiado", "kind": "income"},
        headers=_auth(token),
    )
    debt_src = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="824.77",
        occurred_at="2026-04-12T12:00:00Z",
        category_id=income_cat.json()["id"],
        description="OPERACION FINANCIADA",
    )
    rd = await client.post(
        "/transfers/from-source-debt",
        json={
            "source_transaction_id": debt_src,
            "new_liability": {
                "name": "Tarjeta financiada",
                "type": "credit_card",
                "currency": "EUR",
            },
        },
        headers=_auth(token),
    )
    assert rd.status_code == 201, rd.text

    # 4) Cargo normal SIN par en una cuenta liability (tarjeta) → False.
    #    Regresión: el flag exige emparejamiento, no basta con que la
    #    cuenta sea liability (un cargo suelto en tarjeta NO es deuda
    #    contraída vía conversión).
    card = await client.post(
        "/accounts",
        json={"name": "Visa", "type": "credit_card", "currency": "EUR"},
        headers=_auth(token),
    )
    card_charge_id = await _create_tx(
        client,
        token,
        account_id=card.json()["id"],
        amount="33.00",
        occurred_at="2026-04-13T12:00:00Z",
        category_id=expense_cat,
        description="Cargo suelto en tarjeta",
    )

    lst = await client.get("/transactions?limit=200", headers=_auth(token))
    assert lst.status_code == 200, lst.text
    items = lst.json()["items"]
    by_id = {t["id"]: t for t in items}

    # Normal (en activo, sin par) → False
    assert by_id[normal_id]["is_debt_pair"] is False
    # Cargo suelto en liability (sin par) → False
    assert by_id[card_charge_id]["transfer_pair_id"] is None
    assert by_id[card_charge_id]["is_debt_pair"] is False

    # Las dos patas de la transferencia interna (importe 200) → False
    transfer_legs = [t for t in items if t["amount"] == "200.00"]
    assert len(transfer_legs) == 2
    assert all(t["transfer_pair_id"] is not None for t in transfer_legs)
    assert all(t["is_debt_pair"] is False for t in transfer_legs)

    # Las dos patas de la deuda (importe 824.77) → True
    debt_legs = [t for t in items if t["amount"] == "824.77"]
    assert len(debt_legs) == 2
    assert all(t["transfer_pair_id"] is not None for t in debt_legs)
    assert all(t["is_debt_pair"] is True for t in debt_legs)


async def test_from_source_debt_400_when_destination_is_asset(
    client: AsyncClient,
) -> None:
    """Si `destination_account_id` apunta a una cuenta asset, rechaza
    con 400 (sólo liabilities valen para registrar deuda)."""
    token, _cat, acc_a, acc_b = await _setup_user_with_two_accounts(
        client, "debt-asset-dest@example.com"
    )
    source_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="100.00",
        occurred_at="2026-04-15T12:00:00Z",
    )
    r = await client.post(
        "/transfers/from-source-debt",
        json={
            "source_transaction_id": source_id,
            "destination_account_id": acc_b,  # asset, no liability
        },
        headers=_auth(token),
    )
    assert r.status_code == 400


async def test_from_source_debt_400_when_both_or_neither_provided(
    client: AsyncClient,
) -> None:
    """Exactamente uno entre `destination_account_id` y `new_liability`
    debe venir."""
    token, _cat, acc_a, _acc_b = await _setup_user_with_two_accounts(client, "debt-xor@example.com")
    source_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="100.00",
        occurred_at="2026-04-15T12:00:00Z",
    )
    headers = _auth(token)
    # Ninguno
    r1 = await client.post(
        "/transfers/from-source-debt",
        json={"source_transaction_id": source_id},
        headers=headers,
    )
    assert r1.status_code == 400


async def test_from_source_debt_400_when_new_liability_type_is_asset(
    client: AsyncClient,
) -> None:
    """`new_liability.type` debe ser credit_card/loan/mortgage. Si
    viene un asset type (ej. 'bank'), rechaza con 400."""
    token, _cat, acc_a, _acc_b = await _setup_user_with_two_accounts(
        client, "debt-bad-type@example.com"
    )
    source_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="100.00",
        occurred_at="2026-04-15T12:00:00Z",
    )
    r = await client.post(
        "/transfers/from-source-debt",
        json={
            "source_transaction_id": source_id,
            "new_liability": {
                "name": "X",
                "type": "bank",  # asset, no liability
                "currency": "EUR",
            },
        },
        headers=_auth(token),
    )
    assert r.status_code == 400


async def test_from_source_debt_persists_amortization_fields_for_loan(
    client: AsyncClient,
) -> None:
    """Si `new_liability.type=loan` y trae apr/term/start, la cuenta
    creada los persiste para que el cuadro de amortización los use."""
    token, _cat, acc_a, _acc_b = await _setup_user_with_two_accounts(
        client, "debt-loan@example.com"
    )
    source_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="10000.00",
        occurred_at="2026-04-15T12:00:00Z",
    )
    r = await client.post(
        "/transfers/from-source-debt",
        json={
            "source_transaction_id": source_id,
            "new_liability": {
                "name": "Préstamo coche",
                "type": "loan",
                "currency": "EUR",
                "apr": "0.0590",
                "term_months": 60,
                "start_date": "2026-04-15",
            },
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    accs = await client.get("/accounts", headers=_auth(token))
    loan = next(a for a in accs.json() if a["name"] == "Préstamo coche")
    assert loan["type"] == "loan"
    assert loan["apr"] == "0.0590"
    assert loan["term_months"] == 60
    assert loan["start_date"] == "2026-04-15"


# ---------------------------------------------------------------------------
# PHASE-31.2 — UI bulk-fix de transferencias mal direccionadas.
# ---------------------------------------------------------------------------


async def _seed_user_with_two_transfer_cats(
    client: AsyncClient, email: str
) -> tuple[str, dict[str, str], dict[str, str], str, str]:
    """Helper: registra un usuario con seed (que ya trae las dos
    categorías is_transfer tras PHASE-31.1) y crea dos cuentas bank
    EUR. Devuelve (token, expense_cat, income_cat, acc_a, acc_b)."""
    token, _expense_cat, acc_a, acc_b = await _setup_user_with_two_accounts(client, email)
    cats = (await client.get("/categories", headers=_auth(token))).json()
    transfer_cats = [c for c in cats if c["is_transfer"]]
    expense_cat = next(c for c in transfer_cats if c["kind"] == "expense")
    income_cat = next(c for c in transfer_cats if c["kind"] == "income")
    return token, expense_cat, income_cat, acc_a, acc_b


async def test_misclassified_detects_recibida_in_expense_category(
    client: AsyncClient,
) -> None:
    """Tx "RECIBIDA" asignada a categoría EXPENSE 'Transferencias'
    aparece en /transfers/misclassified con suggested_kind=income."""
    token, expense_cat, _income_cat, acc_a, _acc_b = await _seed_user_with_two_transfer_cats(
        client, "misclassified-recibida@example.com"
    )
    src_id = await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="500.00",
        occurred_at="2026-04-15T12:00:00Z",
        category_id=expense_cat["id"],
        description="TRANSFERENCIA RECIBIDA DE Jose",
    )
    r = await client.get("/transfers/misclassified", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["transaction_id"] == src_id
    assert body[0]["current_category_kind"] == "expense"
    assert body[0]["suggested_kind"] == "income"


async def test_misclassified_excludes_ambiguous_descriptions(
    client: AsyncClient,
) -> None:
    """Texto que matchea ambos lados o ninguno NO aparece."""
    token, expense_cat, _income_cat, acc_a, _acc_b = await _seed_user_with_two_transfer_cats(
        client, "misclassified-ambiguous@example.com"
    )
    await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="100.00",
        occurred_at="2026-04-15T12:00:00Z",
        category_id=expense_cat["id"],
        description="TRANSFERENCIA REALIZADA Y RECIBIDA",
    )
    await _create_tx(
        client,
        token,
        account_id=acc_a,
        amount="200.00",
        occurred_at="2026-04-15T12:00:00Z",
        category_id=expense_cat["id"],
        description="Movimiento sin contexto claro",
    )
    r = await client.get("/transfers/misclassified", headers=_auth(token))
    assert r.json() == []


async def test_reclassify_bulk_moves_to_opposite_kind(
    client: AsyncClient,
) -> None:
    """Sin target_category_id, las tx flipean al kind opuesto
    (EXPENSE → INCOME) usando las categorías is_transfer existentes."""
    token, expense_cat, income_cat, acc_a, _acc_b = await _seed_user_with_two_transfer_cats(
        client, "reclassify-bulk-flip@example.com"
    )
    ids = []
    for i in range(3):
        ids.append(
            await _create_tx(
                client,
                token,
                account_id=acc_a,
                amount=f"{100 + i}.00",
                occurred_at="2026-04-15T12:00:00Z",
                category_id=expense_cat["id"],
                description=f"TRANSFERENCIA RECIBIDA DE X{i}",
            )
        )
    r = await client.post(
        "/transfers/reclassify-bulk",
        json={"transaction_ids": ids},
        headers=_auth(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["reclassified"] == 3
    assert body["errors"] == []
    for tx_id in ids:
        tx = await client.get(f"/transactions/{tx_id}", headers=_auth(token))
        assert tx.json()["category_id"] == income_cat["id"]
