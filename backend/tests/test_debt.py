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


async def test_amortization_fields_accepted_for_credit_card(
    client: AsyncClient,
) -> None:
    """PHASE-24.2: las tarjetas también aceptan apr/term/start —
    necesario para tarjetas financiadas con plan fijo. Cuentas asset
    siguen ignorando estos campos."""
    token = await _register(client, "cc_amort@example.com")
    card = await _create_account(
        client,
        token,
        name="Tarjeta APR",
        type="credit_card",
        currency="EUR",
        apr="0.18",
        term_months=12,
        start_date="2026-01-01",
    )
    assert card["apr"] == "0.1800"
    assert card["term_months"] == 12
    assert card["start_date"] == "2026-01-01"
    # Cuenta asset (bank) sigue descartando los campos del cuadro.
    bank = await _create_account(
        client, token, name="Cte", type="bank", currency="EUR",
        apr="0.10", term_months=6, start_date="2026-01-01",
    )
    assert bank["apr"] is None
    assert bank["term_months"] is None
    assert bank["start_date"] is None


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


async def test_interest_paid_ytd_uses_role_not_category_name(
    client: AsyncClient,
) -> None:
    """PHASE-30.1 — `interest_paid_ytd` filtra por `role=DEBT_INTEREST`,
    no por nombres hardcoded. Una categoría con nombre arbitrario pero
    `role=DEBT_INTEREST` debe contar; una con nombre "Intereses" pero
    `role=GENERIC` debe ser ignorada (no es interés de deuda real).
    """
    token = await _register(client, "interest_role@example.com")
    cte = await _create_account(
        client, token, name="Cte", type="bank", currency="EUR",
        opening_balance="5000",
    )

    # Categoría custom marcada DEBT_INTEREST — debe contar.
    cat_di = await client.post(
        "/categories",
        json={
            "name": "Comisiones leasing coche",
            "kind": "expense",
            "role": "DEBT_INTEREST",
        },
        headers=_auth(token),
    )
    assert cat_di.status_code == 201
    di_cat_id = cat_di.json()["id"]

    # Categoría con nombre engañoso pero role GENERIC — NO debe contar.
    cat_generic = await client.post(
        "/categories",
        json={
            "name": "Intereses (cuenta remunerada)",
            "kind": "expense",
        },
        headers=_auth(token),
    )
    assert cat_generic.status_code == 201
    generic_id = cat_generic.json()["id"]
    assert cat_generic.json()["role"] == "GENERIC"

    # 50€ en la custom DEBT_INTEREST + 999€ en la GENERIC con nombre
    # "Intereses". Solo la primera debe sumar al KPI.
    from datetime import UTC, datetime
    year_now = datetime.now(UTC).year
    await client.post(
        "/transactions",
        json={
            "account_id": cte["id"],
            "category_id": di_cat_id,
            "amount": "50.00",
            "occurred_at": f"{year_now}-03-15T12:00:00Z",
            "description": "Comisión leasing",
        },
        headers=_auth(token),
    )
    await client.post(
        "/transactions",
        json={
            "account_id": cte["id"],
            "category_id": generic_id,
            "amount": "999.00",
            "occurred_at": f"{year_now}-03-15T12:00:00Z",
            "description": "Cargo no de deuda",
        },
        headers=_auth(token),
    )

    r = await client.get("/accounts/debt-health", headers=_auth(token))
    body = r.json()
    assert Decimal(body["interest_paid_ytd"]) == Decimal("50.00")


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


# ─────────────────────────────────────────────────────────────────────
# PHASE-22.1: serie temporal histórico + proyección
# ─────────────────────────────────────────────────────────────────────


async def test_debt_history_empty_user(client: AsyncClient) -> None:
    """Sin liabilities, items vacío y currency por defecto."""
    token = await _register(client, "dhist_empty@example.com")
    r = await client.get("/accounts/debt-history", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["months_historical"] == 0
    assert body["months_projected"] == 0


async def test_debt_history_no_liabilities_only_assets(
    client: AsyncClient,
) -> None:
    """Sólo activos = items vacío, pero reference_currency es la primera."""
    token = await _register(client, "dhist_assets@example.com")
    await _create_account(
        client, token, name="Cte", type="bank", currency="EUR",
        opening_balance="5000",
    )
    r = await client.get("/accounts/debt-history", headers=_auth(token))
    body = r.json()
    assert body["items"] == []
    assert body["reference_currency"] == "EUR"


async def test_debt_history_returns_historical_and_projected_points(
    client: AsyncClient,
) -> None:
    """Una hipoteca → genera el rango completo."""
    token = await _register(client, "dhist_full@example.com")
    await _create_account(
        client,
        token,
        name="Hipoteca",
        type="mortgage",
        currency="EUR",
        opening_balance="100000",
        apr="0.035",
        term_months=240,
        start_date="2026-01-01",
    )
    r = await client.get(
        "/accounts/debt-history?months_back=6&months_ahead=6",
        headers=_auth(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["months_historical"] == 6
    assert body["months_projected"] == 6
    assert len(body["items"]) == 12
    # Histórico primero, proyección después, en orden cronológico.
    kinds = [it["kind"] for it in body["items"]]
    assert kinds[:6] == ["historical"] * 6
    assert kinds[6:] == ["projected"] * 6
    # La proyección reduce la deuda total mes a mes (cuota francesa
    # siempre amortiza algo de principal).
    projected_debts = [Decimal(it["total_debt"]) for it in body["items"][6:]]
    for prev, curr in zip(projected_debts, projected_debts[1:]):
        assert curr <= prev


async def test_debt_history_months_ahead_zero_disables_projection(
    client: AsyncClient,
) -> None:
    """`months_ahead=0` → sólo histórico."""
    token = await _register(client, "dhist_no_proj@example.com")
    await _create_account(
        client, token, name="Visa", type="credit_card", currency="EUR",
    )
    r = await client.get(
        "/accounts/debt-history?months_back=3&months_ahead=0",
        headers=_auth(token),
    )
    body = r.json()
    assert body["months_projected"] == 0
    assert all(it["kind"] == "historical" for it in body["items"])


# ─────────────────────────────────────────────────────────────────────
# PHASE-24.1: cuotas persistidas editables + estado de pago
# ─────────────────────────────────────────────────────────────────────


async def test_create_loan_persists_installments(client: AsyncClient) -> None:
    """Crear una loan con apr/term/start/opening_balance genera las
    cuotas automáticamente. El endpoint de amortización las devuelve
    con `id` (persistidas) y `paid_at=None`."""
    token = await _register(client, "phase241-create@example.com")
    loan = await _create_account(
        client,
        token,
        name="Coche",
        type="loan",
        currency="EUR",
        opening_balance="10000.00",
        apr="0.0590",
        term_months=12,
        start_date="2026-01-01",
    )
    r = await client.get(
        f"/accounts/{loan['id']}/amortization-schedule", headers=_auth(token)
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["rows"]) == 12
    for row in body["rows"]:
        assert row["id"] is not None
        assert row["paid_at"] is None
    # Suma de principal en todas las cuotas == principal total
    total_principal = sum(Decimal(r["principal"]) for r in body["rows"])
    assert total_principal == Decimal("10000.00")


async def test_patch_installment_overrides_amount_and_date(
    client: AsyncClient,
) -> None:
    """PATCH cambia importe y fecha de UNA cuota sin recomputar las
    siguientes."""
    token = await _register(client, "phase241-patch@example.com")
    loan = await _create_account(
        client, token, name="L", type="loan", currency="EUR",
        opening_balance="1200.00", apr="0.0500", term_months=6,
        start_date="2026-01-01",
    )
    sched = await client.get(
        f"/accounts/{loan['id']}/amortization-schedule",
        headers=_auth(token),
    )
    third = sched.json()["rows"][2]
    third_id = third["id"]
    third_original_payment = Decimal(third["payment"])
    fourth_original_payment = Decimal(sched.json()["rows"][3]["payment"])

    r = await client.patch(
        f"/accounts/installments/{third_id}",
        json={"payment": "999.99", "due_date": "2026-04-05"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["payment"] == "999.99"
    assert r.json()["due_date"] == "2026-04-05"

    sched2 = await client.get(
        f"/accounts/{loan['id']}/amortization-schedule",
        headers=_auth(token),
    )
    # La 4ª cuota mantiene el importe original (sin recomputar)
    assert Decimal(sched2.json()["rows"][3]["payment"]) == fourth_original_payment
    # La 3ª refleja el override
    assert Decimal(sched2.json()["rows"][2]["payment"]) == Decimal("999.99")
    # El sanity check: el original no era 999.99
    assert third_original_payment != Decimal("999.99")


async def test_pay_and_unpay_installment(client: AsyncClient) -> None:
    """POST /pay marca la cuota; DELETE /pay la revierte. Soporta link
    opcional con una tx."""
    token = await _register(client, "phase241-pay@example.com")
    loan = await _create_account(
        client, token, name="L", type="loan", currency="EUR",
        opening_balance="600.00", apr="0.0", term_months=3,
        start_date="2026-01-01",
    )
    sched = await client.get(
        f"/accounts/{loan['id']}/amortization-schedule",
        headers=_auth(token),
    )
    first_id = sched.json()["rows"][0]["id"]

    # Marcar como pagada (sin tx)
    r = await client.post(
        f"/accounts/installments/{first_id}/pay",
        json={},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["paid_at"] is not None

    # Desmarcar
    r2 = await client.delete(
        f"/accounts/installments/{first_id}/pay",
        headers=_auth(token),
    )
    assert r2.status_code == 200
    assert r2.json()["paid_at"] is None


async def test_create_credit_card_with_amortization_persists_installments(
    client: AsyncClient,
) -> None:
    """PHASE-24.2: las tarjetas financiadas (`credit_card` + apr +
    plazo + fecha) generan cuotas igual que los préstamos."""
    token = await _register(client, "phase242-card-amort@example.com")
    card = await _create_account(
        client,
        token,
        name="Tarjeta financiada BBVA",
        type="credit_card",
        currency="EUR",
        opening_balance="824.77",
        apr="0.0795",
        tae="0.0824",
        term_months=12,
        start_date="2026-01-07",
    )
    assert card["tae"] == "0.0824"
    r = await client.get(
        f"/accounts/{card['id']}/amortization-schedule", headers=_auth(token)
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["rows"]) == 12
    assert body["principal"] == "824.77"


async def test_account_tae_is_persisted_and_returned(
    client: AsyncClient,
) -> None:
    """TAE es informativa pero debe persistirse y devolverse intacta."""
    token = await _register(client, "phase242-tae@example.com")
    loan = await _create_account(
        client, token, name="L", type="loan", currency="EUR",
        opening_balance="1000.00", apr="0.0500", tae="0.0512",
        term_months=12, start_date="2026-01-01",
    )
    assert loan["apr"] == "0.0500"
    assert loan["tae"] == "0.0512"
    # PATCH también acepta tae
    r = await client.put(
        f"/accounts/{loan['id']}",
        json={"tae": "0.0600"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["tae"] == "0.0600"


async def test_extra_charges_derived_from_total_to_pay(
    client: AsyncClient,
) -> None:
    """PHASE-24.3 — Caso BBVA financiación con comisión oculta:
    capital 824,77€, TIN 21,6%, 9 cuotas. Cuadro francés da
    cuota 100,08€ → total teórico 900,72€. Si declaras
    `total_to_pay=913,86€`, `extra_charges` debe ser 13,14€ (la
    comisión que el banco no desglosa pero sí cobra)."""
    token = await _register(client, "phase243-charges@example.com")
    loan = await _create_account(
        client,
        token,
        name="Compra financiada BBVA",
        type="credit_card",
        currency="EUR",
        opening_balance="824.77",
        apr="0.2160",
        tae="0.2412",
        term_months=9,
        start_date="2026-02-05",
        total_to_pay="913.86",
        interest_only_first_payment="0.00",
    )
    assert loan["total_to_pay"] == "913.86"
    assert loan["interest_only_first_payment"] == "0.00"

    r = await client.get(
        f"/accounts/{loan['id']}/amortization-schedule",
        headers=_auth(token),
    )
    body = r.json()
    assert body["total_to_pay"] == "913.86"
    # Σ cuotas teórico
    cuotas_sum = Decimal(body["total_paid"])
    assert cuotas_sum == Decimal("900.72"), f"got {cuotas_sum}"
    # extra_charges debe revelar la comisión oculta
    assert Decimal(body["extra_charges"]) == Decimal("13.14")


async def test_extra_charges_null_when_total_to_pay_not_set(
    client: AsyncClient,
) -> None:
    """Sin `total_to_pay`, `extra_charges` es null — no inventamos
    cargos."""
    token = await _register(client, "phase243-no-total@example.com")
    loan = await _create_account(
        client, token, name="L", type="loan", currency="EUR",
        opening_balance="1000.00", apr="0.0500", term_months=12,
        start_date="2026-01-01",
    )
    r = await client.get(
        f"/accounts/{loan['id']}/amortization-schedule",
        headers=_auth(token),
    )
    body = r.json()
    assert body["total_to_pay"] is None
    assert body["extra_charges"] is None


async def test_installment_isolation_between_users(client: AsyncClient) -> None:
    """Un usuario no puede tocar cuotas de otro — 404 por aislamiento."""
    token_a = await _register(client, "phase241-iso-a@example.com")
    token_b = await _register(client, "phase241-iso-b@example.com")
    loan_a = await _create_account(
        client, token_a, name="L", type="loan", currency="EUR",
        opening_balance="600.00", apr="0.0", term_months=3,
        start_date="2026-01-01",
    )
    sched = await client.get(
        f"/accounts/{loan_a['id']}/amortization-schedule",
        headers=_auth(token_a),
    )
    inst_id = sched.json()["rows"][0]["id"]

    # User B intenta marcar cuota de user A → 404 (sin filtración)
    r = await client.post(
        f"/accounts/installments/{inst_id}/pay",
        json={},
        headers=_auth(token_b),
    )
    assert r.status_code == 404
