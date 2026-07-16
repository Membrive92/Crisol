"""Tests de la serie temporal de patrimonio (PHASE-37.1)."""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Pos"},
    )
    return str(r.json()["access_token"])


async def _create_account(
    client: AsyncClient,
    token: str,
    *,
    name: str,
    type: str,
    opening_balance: str,
) -> str:
    r = await client.post(
        "/accounts",
        json={
            "name": name,
            "type": type,
            "currency": "EUR",
            "opening_balance": opening_balance,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _post_tx(
    client: AsyncClient,
    token: str,
    *,
    account_id: str,
    amount: str,
    flow: str,
    when: str,
) -> None:
    r = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "amount": amount,
            "currency": "EUR",
            "occurred_at": when,
            "flow": flow,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text


async def test_position_history_empty_user(client: AsyncClient) -> None:
    token = await _register(client, "pos_empty@example.com")
    r = await client.get("/accounts/position-history", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["points"] == []
    assert body["delta_period"] is None


async def test_position_history_last_point_matches_balances(client: AsyncClient) -> None:
    """Invariante crítico: el último punto histórico == el agregado actual de
    /accounts/balances (con cuentas sin cuadro, ambas fuentes son por
    movimientos y deben coincidir al céntimo)."""
    token = await _register(client, "pos_invariant@example.com")
    bank = await _create_account(
        client, token, name="BBVA", type="bank", opening_balance="1000.00"
    )
    card = await _create_account(
        client, token, name="Visa", type="credit_card", opening_balance="0.00"
    )
    # Todo en meses CERRADOS (hasta jun-2026) para que el último punto (jun)
    # contenga todos los movimientos, igual que el saldo all-time de balances.
    await _post_tx(client, token, account_id=bank, amount="500.00", flow="IN", when="2026-03-10T12:00:00Z")
    await _post_tx(client, token, account_id=bank, amount="200.00", flow="OUT", when="2026-04-12T12:00:00Z")
    await _post_tx(client, token, account_id=card, amount="300.00", flow="OUT", when="2026-05-08T12:00:00Z")

    balances = (await client.get("/accounts/balances", headers=_auth(token))).json()
    pos = (
        await client.get("/accounts/position-history?months_back=6", headers=_auth(token))
    ).json()

    assert len(pos["points"]) == 6
    last = pos["points"][-1]
    assert Decimal(last["total_assets"]) == Decimal(balances["total_assets"])
    assert Decimal(last["total_liabilities"]) == Decimal(balances["total_liabilities"])
    assert Decimal(last["net_worth"]) == Decimal(balances["net_worth"])
    # Sanity de los valores esperados.
    assert Decimal(last["total_assets"]) == Decimal("1300.00")
    assert Decimal(last["total_liabilities"]) == Decimal("300.00")
    assert Decimal(last["net_worth"]) == Decimal("1000.00")


async def test_position_history_delta_period(client: AsyncClient) -> None:
    """Δ del periodo = neto último − neto primer punto de la ventana."""
    token = await _register(client, "pos_delta@example.com")
    bank = await _create_account(
        client, token, name="BBVA", type="bank", opening_balance="1000.00"
    )
    # Un ingreso en un mes intermedio: el neto sube entre el primer y último punto.
    await _post_tx(client, token, account_id=bank, amount="400.00", flow="IN", when="2026-04-10T12:00:00Z")

    pos = (
        await client.get("/accounts/position-history?months_back=6", headers=_auth(token))
    ).json()
    points = pos["points"]
    assert len(points) == 6
    # El primer punto (antes del ingreso) neto 1000; el último 1400.
    assert Decimal(points[0]["net_worth"]) == Decimal("1000.00")
    assert Decimal(points[-1]["net_worth"]) == Decimal("1400.00")
    assert Decimal(pos["delta_period"]) == Decimal("400.00")
    assert pos["delta_period_pct"] == 40.0


async def test_position_history_excludes_brokerage(client: AsyncClient) -> None:
    """Las cuentas no valoradas (brokerage/crypto) no entran en la serie."""
    token = await _register(client, "pos_broker@example.com")
    await _create_account(client, token, name="BBVA", type="bank", opening_balance="1000.00")
    await _create_account(client, token, name="IBKR", type="brokerage", opening_balance="5000.00")
    pos = (
        await client.get("/accounts/position-history?months_back=3", headers=_auth(token))
    ).json()
    # El patrimonio refleja solo el banco (1000), no el brokerage (5000).
    assert Decimal(pos["points"][-1]["total_assets"]) == Decimal("1000.00")


# ── /accounts/position-as-of (PHASE-41) ──────────────────────────────────────


async def test_position_as_of_reflects_range_end_not_today(client: AsyncClient) -> None:
    """El patrimonio A FECHA de fin de rango ignora movimientos POSTERIORES a
    `date_to` (es una foto del período, no de hoy) y el Δ cuenta solo los
    movimientos DENTRO de `[date_from, date_to]`."""
    token = await _register(client, "asof_end@example.com")
    bank = await _create_account(
        client, token, name="BBVA", type="bank", opening_balance="1000.00"
    )
    await _post_tx(client, token, account_id=bank, amount="400.00", flow="IN", when="2026-04-10T12:00:00Z")
    # Movimiento POSTERIOR al rango: no debe entrar en la foto a fecha.
    await _post_tx(client, token, account_id=bank, amount="100.00", flow="OUT", when="2026-06-20T12:00:00Z")

    r = await client.get(
        "/accounts/position-as-of",
        params={"date_from": "2026-04-01T00:00:00Z", "date_to": "2026-04-30T23:59:59Z"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Foto a 30-abr: 1000 + 400 = 1400 (el cargo de junio queda fuera).
    assert Decimal(body["total_assets"]) == Decimal("1400.00")
    assert Decimal(body["total_liabilities"]) == Decimal("0.00")
    assert Decimal(body["net_worth"]) == Decimal("1400.00")
    # Δ del rango = solo el ingreso de abril.
    assert Decimal(body["delta_assets"]) == Decimal("400.00")
    assert Decimal(body["delta_net_worth"]) == Decimal("400.00")
    # Prueba de que NO es la foto de hoy (hoy el neto sería 1300).
    assert Decimal(body["net_worth"]) != Decimal("1300.00")


async def test_position_as_of_delta_excludes_movements_before_range(client: AsyncClient) -> None:
    """Un movimiento ANTERIOR a `date_from` entra en la base (valor a fecha)
    pero NO en el Δ del rango."""
    token = await _register(client, "asof_before@example.com")
    bank = await _create_account(
        client, token, name="BBVA", type="bank", opening_balance="1000.00"
    )
    await _post_tx(client, token, account_id=bank, amount="200.00", flow="IN", when="2026-03-05T12:00:00Z")
    await _post_tx(client, token, account_id=bank, amount="500.00", flow="IN", when="2026-05-15T12:00:00Z")

    r = await client.get(
        "/accounts/position-as-of",
        params={"date_from": "2026-05-01T00:00:00Z", "date_to": "2026-05-31T23:59:59Z"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Valor a 31-may = 1000 + 200 (marzo) + 500 (mayo) = 1700.
    assert Decimal(body["net_worth"]) == Decimal("1700.00")
    # Δ de mayo = solo el ingreso de mayo (el de marzo queda en la base).
    assert Decimal(body["delta_net_worth"]) == Decimal("500.00")
