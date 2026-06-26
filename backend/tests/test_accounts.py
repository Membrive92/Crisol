"""Tests del módulo accounts (PHASE-19.1)."""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient


async def _setup_user(client: AsyncClient, email: str = "acc@example.com") -> str:
    """Registra un usuario y devuelve el access token."""
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_list_empty(client: AsyncClient) -> None:
    """Sin cuentas declaradas, GET /accounts devuelve []."""
    token = await _setup_user(client, "empty@example.com")
    r = await client.get("/accounts", headers=_auth(token))
    assert r.status_code == 200
    assert r.json() == []


async def test_create_account_as_default(client: AsyncClient) -> None:
    """PHASE-32 — crear una cuenta como principal devuelve `is_default=true`."""
    token = await _setup_user(client, "isdefault@example.com")
    r = await client.post(
        "/accounts",
        json={"name": "BBVA", "type": "bank", "currency": "EUR", "is_default": True},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["is_default"] is True


async def test_only_one_default_account_per_user(client: AsyncClient) -> None:
    """PHASE-32 — marcar una cuenta como principal desmarca la anterior
    (única cuenta principal por usuario)."""
    token = await _setup_user(client, "onedefault@example.com")
    a = await client.post(
        "/accounts",
        json={"name": "BBVA", "type": "bank", "currency": "EUR", "is_default": True},
        headers=_auth(token),
    )
    a_id = a.json()["id"]
    b = await client.post(
        "/accounts",
        json={"name": "Santander", "type": "bank", "currency": "EUR"},
        headers=_auth(token),
    )
    b_id = b.json()["id"]
    assert b.json()["is_default"] is False

    # Marcar B como principal vía PUT.
    upd = await client.put(f"/accounts/{b_id}", json={"is_default": True}, headers=_auth(token))
    assert upd.status_code == 200, upd.text
    assert upd.json()["is_default"] is True

    # A ya no es la principal.
    accounts = (await client.get("/accounts", headers=_auth(token))).json()
    by_id = {x["id"]: x for x in accounts}
    assert by_id[a_id]["is_default"] is False
    assert by_id[b_id]["is_default"] is True


async def test_create_account(client: AsyncClient) -> None:
    token = await _setup_user(client, "create@example.com")
    r = await client.post(
        "/accounts",
        json={
            "name": "BBVA Cuenta corriente",
            "type": "bank",
            "currency": "EUR",
            "color": "#1976d2",
            "icon": "🏦",
            "opening_balance": "1500.00",
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "BBVA Cuenta corriente"
    assert body["type"] == "bank"
    assert body["nature"] == "asset"
    assert body["currency"] == "EUR"
    assert body["color"] == "#1976d2"
    assert body["icon"] == "🏦"
    assert body["opening_balance"] == "1500.00"
    assert body["is_archived"] is False


async def test_create_uppercases_currency(client: AsyncClient) -> None:
    token = await _setup_user(client, "currency@example.com")
    r = await client.post(
        "/accounts",
        json={"name": "USD Broker", "type": "brokerage", "currency": "usd"},
        headers=_auth(token),
    )
    assert r.status_code == 201
    assert r.json()["currency"] == "USD"


async def test_create_rejects_duplicate_name(client: AsyncClient) -> None:
    token = await _setup_user(client, "dupname@example.com")
    body = {"name": "Cuenta principal", "type": "bank"}
    first = await client.post("/accounts", json=body, headers=_auth(token))
    assert first.status_code == 201

    second = await client.post(
        "/accounts",
        json={"name": "cuenta PRINCIPAL", "type": "bank"},
        headers=_auth(token),
    )
    assert second.status_code == 409


async def test_create_liability_type_assigns_nature(
    client: AsyncClient,
) -> None:
    """Tipos `liability` (credit_card/loan/mortgage) se aceptan (PHASE-22)
    y reciben `nature=liability` automáticamente."""
    token = await _setup_user(client, "liability@example.com")
    r = await client.post(
        "/accounts",
        json={"name": "Visa", "type": "credit_card"},
        headers=_auth(token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["nature"] == "liability"
    assert body["type"] == "credit_card"


async def test_update_account(client: AsyncClient) -> None:
    token = await _setup_user(client, "upd@example.com")
    create = await client.post(
        "/accounts",
        json={"name": "Cuenta A", "type": "bank"},
        headers=_auth(token),
    )
    aid = create.json()["id"]

    upd = await client.put(
        f"/accounts/{aid}",
        json={"name": "Cuenta renombrada", "color": "#ef4444", "icon": "💰"},
        headers=_auth(token),
    )
    assert upd.status_code == 200
    body = upd.json()
    assert body["name"] == "Cuenta renombrada"
    assert body["color"] == "#ef4444"
    assert body["icon"] == "💰"


async def test_archive_account(client: AsyncClient) -> None:
    """`is_archived=true` oculta la cuenta del listado por defecto."""
    token = await _setup_user(client, "arch@example.com")
    create = await client.post(
        "/accounts",
        json={"name": "Vieja", "type": "bank"},
        headers=_auth(token),
    )
    aid = create.json()["id"]

    await client.put(
        f"/accounts/{aid}",
        json={"is_archived": True},
        headers=_auth(token),
    )

    listing = await client.get("/accounts", headers=_auth(token))
    assert all(a["id"] != aid for a in listing.json())

    listing_with_archived = await client.get(
        "/accounts?include_archived=true", headers=_auth(token)
    )
    assert any(a["id"] == aid for a in listing_with_archived.json())


async def test_delete_empty_account(client: AsyncClient) -> None:
    """Cuentas sin transacciones asociadas se pueden borrar."""
    token = await _setup_user(client, "delempty@example.com")
    create = await client.post(
        "/accounts",
        json={"name": "Borrable", "type": "bank"},
        headers=_auth(token),
    )
    aid = create.json()["id"]

    r = await client.delete(f"/accounts/{aid}", headers=_auth(token))
    assert r.status_code == 204

    after = await client.get(f"/accounts/{aid}", headers=_auth(token))
    assert after.status_code == 404


async def test_delete_account_with_transactions_returns_409(
    client: AsyncClient,
) -> None:
    """Si la cuenta tiene transacciones, DELETE devuelve 409 — el
    usuario debe archivar para conservar el histórico."""
    token = await _setup_user(client, "delfull@example.com")
    create = await client.post(
        "/accounts",
        json={"name": "Con datos", "type": "bank"},
        headers=_auth(token),
    )
    aid = create.json()["id"]

    await client.post(
        "/transactions",
        json={
            "account_id": aid,
            "amount": "10.00",
            "occurred_at": "2026-04-15T12:00:00Z",
        },
        headers=_auth(token),
    )

    r = await client.delete(f"/accounts/{aid}", headers=_auth(token))
    assert r.status_code == 409


async def test_user_isolation(client: AsyncClient) -> None:
    """Una cuenta del usuario A no es visible ni accesible para B."""
    token_a = await _setup_user(client, "isoA@example.com")
    token_b = await _setup_user(client, "isoB@example.com")

    create = await client.post(
        "/accounts",
        json={"name": "De A", "type": "bank"},
        headers=_auth(token_a),
    )
    aid = create.json()["id"]

    list_b = await client.get("/accounts", headers=_auth(token_b))
    assert all(a["id"] != aid for a in list_b.json())

    get_b = await client.get(f"/accounts/{aid}", headers=_auth(token_b))
    assert get_b.status_code == 404

    upd_b = await client.put(
        f"/accounts/{aid}",
        json={"name": "Hijack"},
        headers=_auth(token_b),
    )
    assert upd_b.status_code == 404

    del_b = await client.delete(f"/accounts/{aid}", headers=_auth(token_b))
    assert del_b.status_code == 404


async def test_transaction_requires_account_id(client: AsyncClient) -> None:
    """Sin `account_id` el POST /transactions falla con 422 (Pydantic)."""
    token = await _setup_user(client, "noacc@example.com")
    r = await client.post(
        "/transactions",
        json={
            "amount": "10.00",
            "occurred_at": "2026-04-15T12:00:00Z",
        },
        headers=_auth(token),
    )
    assert r.status_code == 422


async def test_transaction_with_foreign_account_id_returns_404(
    client: AsyncClient,
) -> None:
    """Si el `account_id` pertenece a otro usuario, 404 (no leak)."""
    token_a = await _setup_user(client, "ownerA@example.com")
    token_b = await _setup_user(client, "ownerB@example.com")

    create = await client.post(
        "/accounts",
        json={"name": "De A", "type": "bank"},
        headers=_auth(token_a),
    )
    aid_a = create.json()["id"]

    r = await client.post(
        "/transactions",
        json={
            "account_id": aid_a,
            "amount": "10.00",
            "occurred_at": "2026-04-15T12:00:00Z",
        },
        headers=_auth(token_b),
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PHASE-31.3 — tx sin categoría no contribuye al saldo (`else_=0`).
# ---------------------------------------------------------------------------


async def test_uncategorized_tx_does_not_affect_balance(
    client: AsyncClient,
) -> None:
    """Una tx sin `category_id` no cuenta al saldo. Antes el fallback
    `else_=Transaction.amount` la sumaba arbitrariamente — PHASE-31.3
    lo cambia a `else_=0`."""
    token = await _setup_user(client, "uncat-balance@example.com")
    acc = await client.post(
        "/accounts",
        json={"name": "Test", "type": "bank", "currency": "EUR"},
        headers=_auth(token),
    )
    aid = acc.json()["id"]

    # Crear una tx SIN categoría.
    tx = await client.post(
        "/transactions",
        json={
            "amount": "500.00",
            "currency": "EUR",
            "occurred_at": "2026-04-15T12:00:00Z",
            "account_id": aid,
        },
        headers=_auth(token),
    )
    assert tx.status_code == 201

    balances = await client.get("/accounts/balances", headers=_auth(token))
    by_id = {b["account_id"]: b for b in balances.json()["items"]}
    # La tx no contribuye al saldo hasta que tenga categoría.
    assert by_id[aid]["movements_balance"] == "0"


async def test_uncategorized_summary_endpoint(client: AsyncClient) -> None:
    """`GET /transactions/uncategorized-summary` devuelve conteo y total
    de tx sin categorizar para alimentar el banner UX."""
    token = await _setup_user(client, "uncat-summary@example.com")
    acc = await client.post(
        "/accounts",
        json={"name": "Test", "type": "bank", "currency": "EUR"},
        headers=_auth(token),
    )
    aid = acc.json()["id"]

    # Crear 3 tx sin categoría.
    for amount in ("10.00", "20.00", "30.00"):
        r = await client.post(
            "/transactions",
            json={
                "amount": amount,
                "currency": "EUR",
                "occurred_at": "2026-04-15T12:00:00Z",
                "account_id": aid,
            },
            headers=_auth(token),
        )
        assert r.status_code == 201

    summary = await client.get("/transactions/uncategorized-summary", headers=_auth(token))
    assert summary.status_code == 200
    body = summary.json()
    assert body["count"] == 3
    # 10 + 20 + 30
    assert body["total_amount"] == "60.00"
    assert body["currency"] == "EUR"


# ---------------------------------------------------------------------------
# PHASE-31.4 — brokerage/crypto fuera del patrimonio neto agregado.
# ---------------------------------------------------------------------------


async def test_brokerage_account_marked_unvalued(client: AsyncClient) -> None:
    """Una cuenta brokerage tiene `is_unvalued=true` en /accounts/balances."""
    token = await _setup_user(client, "brokerage-flag@example.com")
    r = await client.post(
        "/accounts",
        json={"name": "Broker", "type": "brokerage", "currency": "EUR"},
        headers=_auth(token),
    )
    assert r.status_code == 201

    balances = await client.get("/accounts/balances", headers=_auth(token))
    items = balances.json()["items"]
    assert len(items) == 1
    assert items[0]["is_unvalued"] is True


async def test_brokerage_account_excluded_from_net_worth(
    client: AsyncClient,
) -> None:
    """Una cuenta brokerage con opening_balance=10000 no suma a
    `total_assets`. Solo las cuentas valoradas (bank, savings, cash)
    cuentan al patrimonio neto agregado hasta que exista el módulo de
    inversión."""
    token = await _setup_user(client, "brokerage-aggregate@example.com")
    await client.post(
        "/accounts",
        json={
            "name": "Bank",
            "type": "bank",
            "currency": "EUR",
            "opening_balance": "5000.00",
        },
        headers=_auth(token),
    )
    await client.post(
        "/accounts",
        json={
            "name": "Broker",
            "type": "brokerage",
            "currency": "EUR",
            "opening_balance": "10000.00",
        },
        headers=_auth(token),
    )

    balances = await client.get("/accounts/balances", headers=_auth(token))
    body = balances.json()
    # Total assets = solo bank (5000), brokerage (10000) excluido.
    assert body["total_assets"] == "5000.00"
    assert body["net_worth"] == "5000.00"
    # Ambas cuentas siguen apareciendo en `items`.
    assert len(body["items"]) == 2


# ---------------------------------------------------------------------------
# PHASE-32 — la cuenta principal (is_default) refleja AHORRO NETO.
# ---------------------------------------------------------------------------


async def test_default_account_balance_excludes_internal_transfers(
    client: AsyncClient,
) -> None:
    """PHASE-32 — La cuenta principal (`is_default`) refleja ahorro neto: las
    transferencias internas (`is_transfer`) NO cuentan en su saldo. Una
    cuenta NO principal sí las cuenta (modo cash, PHASE-23.1)."""
    token = await _setup_user(client, "default-savings@example.com")

    cats = (await client.get("/categories", headers=_auth(token))).json()
    income = next(c for c in cats if c["kind"] == "income" and not c["is_transfer"])
    transfer_in = next(c for c in cats if c["kind"] == "income" and c["is_transfer"])

    main = await client.post(
        "/accounts",
        json={"name": "Principal", "type": "bank", "currency": "EUR", "is_default": True},
        headers=_auth(token),
    )
    main_id = main.json()["id"]
    other = await client.post(
        "/accounts",
        json={"name": "Otra", "type": "bank", "currency": "EUR"},
        headers=_auth(token),
    )
    other_id = other.json()["id"]

    # En cada cuenta: 100 de ingreso real + 500 de transferencia interna.
    for acc_id in (main_id, other_id):
        for amount, cat in (("100.00", income["id"]), ("500.00", transfer_in["id"])):
            r = await client.post(
                "/transactions",
                json={
                    "amount": amount,
                    "currency": "EUR",
                    "occurred_at": "2026-01-15T12:00:00Z",
                    "account_id": acc_id,
                    "category_id": cat,
                },
                headers=_auth(token),
            )
            assert r.status_code == 201, r.text

    by_id = {
        b["account_id"]: b
        for b in (await client.get("/accounts/balances", headers=_auth(token))).json()["items"]
    }
    # Principal: solo el ingreso real (100); la transferencia NO cuenta.
    assert Decimal(by_id[main_id]["movements_balance"]) == Decimal("100.00")
    # Otra: ingreso + transferencia (modo cash).
    assert Decimal(by_id[other_id]["movements_balance"]) == Decimal("600.00")


async def test_net_worth_unaffected_by_transfer_into_default_account(
    client: AsyncClient,
) -> None:
    """PHASE-32 HIGH#1 — una transferencia interna HACIA la cuenta principal
    NO debe cambiar el patrimonio neto agregado. La pata entrante está zerada
    en el DISPLAY de ahorro neto de la principal, pero el agregado usa el
    saldo CASH, así que se cancela con la pata saliente de la otra cuenta.
    Antes (bug), el net_worth encogía por el importe de la transferencia."""
    token = await _setup_user(client, "networth-transfer@example.com")

    cats = (await client.get("/categories", headers=_auth(token))).json()
    income = next(c for c in cats if c["kind"] == "income" and not c["is_transfer"])
    transfer_in = next(c for c in cats if c["kind"] == "income" and c["is_transfer"])
    transfer_out = next(c for c in cats if c["kind"] == "expense" and c["is_transfer"])

    main = await client.post(
        "/accounts",
        json={"name": "Principal", "type": "bank", "currency": "EUR", "is_default": True},
        headers=_auth(token),
    )
    main_id = main.json()["id"]
    other = await client.post(
        "/accounts",
        json={"name": "Otra", "type": "bank", "currency": "EUR"},
        headers=_auth(token),
    )
    other_id = other.json()["id"]

    async def _post(acc_id: str, amount: str, cat_id: str) -> None:
        r = await client.post(
            "/transactions",
            json={
                "amount": amount,
                "currency": "EUR",
                "occurred_at": "2026-01-15T12:00:00Z",
                "account_id": acc_id,
                "category_id": cat_id,
            },
            headers=_auth(token),
        )
        assert r.status_code == 201, r.text

    # Ahorro real en la principal: +100.
    await _post(main_id, "100.00", income["id"])
    # Transferencia interna de 500 "Otra" → "Principal": dos patas.
    await _post(main_id, "500.00", transfer_in["id"])  # +500 entra a la principal
    await _post(other_id, "500.00", transfer_out["id"])  # -500 sale de la otra

    bal = (await client.get("/accounts/balances", headers=_auth(token))).json()
    by_id = {b["account_id"]: b for b in bal["items"]}

    # DISPLAY: la principal muestra ahorro neto (100, sin la transferencia).
    assert Decimal(by_id[main_id]["movements_balance"]) == Decimal("100.00")
    # AGREGADO: net_worth = sólo el ahorro real (100). Las dos patas de la
    # transferencia (+500 principal cash, -500 otra) se cancelan.
    assert Decimal(bal["net_worth"]) == Decimal("100.00")
    assert Decimal(bal["total_assets"]) == Decimal("100.00")


async def test_liability_account_cannot_be_default_on_create(client: AsyncClient) -> None:
    """PHASE-32 HIGH#2 — una cuenta de pasivo no puede crearse como principal
    (su saldo es deuda, no ahorro; el carve-out de transferencias no aplica)."""
    token = await _setup_user(client, "liab-default-create@example.com")
    r = await client.post(
        "/accounts",
        json={"name": "Visa", "type": "credit_card", "currency": "EUR", "is_default": True},
        headers=_auth(token),
    )
    assert r.status_code == 400, r.text


async def test_liability_account_cannot_be_default_on_update(client: AsyncClient) -> None:
    """PHASE-32 HIGH#2 — marcar una cuenta de pasivo como principal vía PUT
    también se rechaza."""
    token = await _setup_user(client, "liab-default-update@example.com")
    cc = await client.post(
        "/accounts",
        json={"name": "Visa", "type": "credit_card", "currency": "EUR"},
        headers=_auth(token),
    )
    cc_id = cc.json()["id"]
    r = await client.put(f"/accounts/{cc_id}", json={"is_default": True}, headers=_auth(token))
    assert r.status_code == 400, r.text


async def test_default_asset_converted_to_liability_type_is_rejected(client: AsyncClient) -> None:
    """PHASE-32 fix-review — cambiar el `type` de una cuenta principal ASSET a
    un tipo de pasivo, SIN tocar `is_default` en el payload, se rechaza: no
    debe quedar `is_default=True` sobre un pasivo (gap del guard antiguo)."""
    token = await _setup_user(client, "default-to-liability@example.com")
    a = await client.post(
        "/accounts",
        json={"name": "Principal", "type": "bank", "currency": "EUR", "is_default": True},
        headers=_auth(token),
    )
    a_id = a.json()["id"]
    r = await client.put(f"/accounts/{a_id}", json={"type": "credit_card"}, headers=_auth(token))
    assert r.status_code == 400, r.text


async def test_archiving_default_account_clears_is_default(client: AsyncClient) -> None:
    """PHASE-32 (AUDIT MEDIUM#6) — archivar la cuenta principal limpia
    `is_default`: los formularios sólo cargan cuentas activas, así que dejar
    el flag colgando perdería la pre-selección en silencio."""
    token = await _setup_user(client, "archive-default@example.com")
    a = await client.post(
        "/accounts",
        json={"name": "Principal", "type": "bank", "currency": "EUR", "is_default": True},
        headers=_auth(token),
    )
    a_id = a.json()["id"]
    r = await client.put(f"/accounts/{a_id}", json={"is_archived": True}, headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["is_archived"] is True
    assert r.json()["is_default"] is False
