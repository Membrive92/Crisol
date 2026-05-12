"""Tests del módulo deuda (PHASE-22): cuentas liability, signo invertido
del saldo, cuadro de amortización y salud financiera.
"""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_account(
    client: AsyncClient, token: str, **fields: object
) -> dict[str, object]:
    """Crea una cuenta. Acepta cualquier campo del schema."""
    r = await client.post("/accounts", json=fields, headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()


# ─────────────────────────────────────────────────────────────────────
# PHASE-22.1: liability como ciudadano de primera clase
# ─────────────────────────────────────────────────────────────────────


async def test_create_credit_card_account(client: AsyncClient) -> None:
    """Tipos `liability` ya son creables; nature se asigna a 'liability'."""
    token = await _register(client, "cc@example.com")
    acc = await _create_account(
        client, token, name="Visa", type="credit_card", currency="EUR"
    )
    assert acc["type"] == "credit_card"
    assert acc["nature"] == "liability"


async def test_create_mortgage_with_amortization_fields(client: AsyncClient) -> None:
    """Una hipoteca acepta apr/term_months/start_date."""
    token = await _register(client, "mortgage@example.com")
    acc = await _create_account(
        client,
        token,
        name="Hipoteca Sabadell",
        type="mortgage",
        currency="EUR",
        opening_balance="180000.00",
        apr="0.035",
        term_months=360,
        start_date="2026-01-01",
    )
    assert acc["nature"] == "liability"
    assert Decimal(acc["apr"]) == Decimal("0.0350")
    assert acc["term_months"] == 360


async def test_amortization_fields_ignored_for_non_loan_types(
    client: AsyncClient,
) -> None:
    """Crear una tarjeta con apr/term — los acepta pero el backend los
    descarta porque sólo aplican a loan/mortgage."""
    token = await _register(client, "cc_amort@example.com")
    acc = await _create_account(
        client,
        token,
        name="Tarjeta APR",
        type="credit_card",
        currency="EUR",
        apr="0.18",
        term_months=12,
        start_date="2026-01-01",
    )
    assert acc["apr"] is None
    assert acc["term_months"] is None
    assert acc["start_date"] is None


async def test_balance_inverted_for_liability(client: AsyncClient) -> None:
    """Una compra (expense) en una cuenta liability SUMA al saldo;
    un pago (transfer entrante = income) RESTA."""
    token = await _register(client, "balsign@example.com")
    # Categoría general para las txs.
    cat = await client.post(
        "/categories",
        json={"name": "Compra cualquiera", "kind": "expense"},
        headers=_auth(token),
    )
    expense_cat_id = cat.json()["id"]
    income_cat = await client.post(
        "/categories",
        json={"name": "Pago entrante", "kind": "income"},
        headers=_auth(token),
    )
    income_cat_id = income_cat.json()["id"]

    cte = await _create_account(
        client, token, name="Cte", type="bank", currency="EUR",
        opening_balance="1000",
    )
    visa = await _create_account(
        client, token, name="Visa", type="credit_card", currency="EUR",
    )

    # Compra de 30€ con la tarjeta → expense en Visa.
    await client.post(
        "/transactions",
        json={
            "account_id": visa["id"],
            "category_id": expense_cat_id,
            "amount": "30.00",
            "occurred_at": "2026-04-15T12:00:00Z",
            "description": "Compra",
        },
        headers=_auth(token),
    )
    # Pago entrante de 30€ desde Visa (simulado como income en Visa).
    await client.post(
        "/transactions",
        json={
            "account_id": visa["id"],
            "category_id": income_cat_id,
            "amount": "20.00",
            "occurred_at": "2026-04-20T12:00:00Z",
            "description": "Pago",
        },
        headers=_auth(token),
    )

    balances = (
        await client.get("/accounts/balances", headers=_auth(token))
    ).json()
    by_id = {b["account_id"]: b for b in balances["items"]}

    # Visa: 0 (opening) + 30 (compra suma deuda) − 20 (pago resta deuda) = 10
    assert Decimal(by_id[visa["id"]]["current_balance"]) == Decimal("10.00")
    # Net worth = assets − liabilities = 1000 − 10 = 990
    assert Decimal(balances["net_worth"]) == Decimal("990.00")
    assert Decimal(balances["total_liabilities"]) == Decimal("10.00")


# ─────────────────────────────────────────────────────────────────────
# PHASE-22.3: cuadro de amortización
# ─────────────────────────────────────────────────────────────────────


async def test_amortization_schedule_basic(client: AsyncClient) -> None:
    """Hipoteca 100k al 5% a 10 años (120 meses) — verifica la cuota
    teórica conocida y que el saldo final cierra a 0.
    """
    token = await _register(client, "amort1@example.com")
    acc = await _create_account(
        client,
        token,
        name="Hipoteca",
        type="mortgage",
        currency="EUR",
        opening_balance="100000.00",
        apr="0.05",
        term_months=120,
        start_date="2026-01-01",
    )
    r = await client.get(
        f"/accounts/{acc['id']}/amortization-schedule", headers=_auth(token)
    )
    assert r.status_code == 200
    body = r.json()
    # Cuota francesa para 100k al 5% en 10 años ≈ 1060.66 €/mes.
    monthly = Decimal(body["monthly_payment"])
    assert Decimal("1059") < monthly < Decimal("1062")
    # 120 filas + el saldo final exactamente 0.
    assert len(body["rows"]) == 120
    assert Decimal(body["rows"][-1]["remaining_balance"]) == Decimal("0.00")


async def test_amortization_schedule_rejects_credit_card(client: AsyncClient) -> None:
    """Tarjetas no usan cuadro fijo; 400."""
    token = await _register(client, "amort_cc@example.com")
    acc = await _create_account(
        client, token, name="Visa", type="credit_card", currency="EUR",
    )
    r = await client.get(
        f"/accounts/{acc['id']}/amortization-schedule", headers=_auth(token)
    )
    assert r.status_code == 400


async def test_amortization_schedule_rejects_without_fields(client: AsyncClient) -> None:
    """Mortgage sin apr/term/start_date → 400."""
    token = await _register(client, "amort_missing@example.com")
    acc = await _create_account(
        client, token, name="Hipoteca", type="mortgage", currency="EUR",
        opening_balance="180000",
    )
    r = await client.get(
        f"/accounts/{acc['id']}/amortization-schedule", headers=_auth(token)
    )
    assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────────
# PHASE-22.4: salud financiera
# ─────────────────────────────────────────────────────────────────────


async def test_debt_health_empty_user(client: AsyncClient) -> None:
    """Sin cuentas, todos los KPIs en 0 / unknown."""
    token = await _register(client, "dh_empty@example.com")
    r = await client.get("/accounts/debt-health", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert Decimal(body["total_liabilities"]) == Decimal("0")
    assert Decimal(body["total_assets"]) == Decimal("0")
    assert body["dti_status"] == "unknown"
    assert body["dti_ratio"] is None
    assert body["time_to_payoff_months"] is None


async def test_debt_health_basic_kpis(client: AsyncClient) -> None:
    """Patrimonio + cuota + APR medio se computan correctamente."""
    token = await _register(client, "dh_basic@example.com")
    await _create_account(
        client, token, name="Cte", type="bank", currency="EUR",
        opening_balance="20000",
    )
    await _create_account(
        client,
        token,
        name="Hipoteca",
        type="mortgage",
        currency="EUR",
        opening_balance="100000",
        apr="0.04",
        term_months=240,
        start_date="2026-01-01",
    )
    r = await client.get("/accounts/debt-health", headers=_auth(token))
    body = r.json()
    assert Decimal(body["total_assets"]) == Decimal("20000.00")
    assert Decimal(body["total_liabilities"]) == Decimal("100000.00")
    assert Decimal(body["net_worth"]) == Decimal("-80000.00")
    # weighted_apr con una sola liability = APR de esa liability.
    assert body["weighted_apr"] is not None
    assert abs(body["weighted_apr"] - 0.04) < 1e-6
    # Cuota teórica 100k al 4% en 240m ≈ 606 €/mes.
    monthly = Decimal(body["monthly_debt_payment"])
    assert Decimal("600") < monthly < Decimal("615")
