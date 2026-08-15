"""PHASE-45 — "Es una amortización": enlazar un cargo del banco con su deuda.

Cubre los dos mecanismos (cuadro de cuotas vs. movimiento contrario), la
decisión explícita de si cuenta como gasto, el previsualizador `dry_run`, la
idempotencia, el deshacer y el aislamiento entre usuarios.

La distinción que más importa aquí, y por la que hay asserts exactos: con
cuadro la deuda baja por el CAPITAL de las cuotas cubiertas, no por lo pagado
(los intereses no amortizan); sin cuadro baja por el importe entero.
"""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient

from app.modules.personal_finance.debt.installments_model import LiabilityInstallment
from app.modules.personal_finance.debt.installments_repository import (
    plan_installments_covering_principal,
)


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    return str(r.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_account(client: AsyncClient, token: str, **fields: object) -> dict[str, object]:
    r = await client.post("/accounts", json=fields, headers=_auth(token))
    assert r.status_code == 201, r.text
    return dict(r.json())


async def _create_tx(
    client: AsyncClient,
    token: str,
    *,
    account_id: str,
    amount: str,
    occurred_at: str = "2026-07-08T00:00:00Z",
    flow: str = "TRANSFER_OUT",
    description: str = "Adeudo mensual de tarjeta",
) -> str:
    payload: dict[str, object] = {
        "account_id": account_id,
        "amount": amount,
        "occurred_at": occurred_at,
        "description": description,
        "flow": flow,
    }
    r = await client.post("/transactions", json=payload, headers=_auth(token))
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _balance(client: AsyncClient, token: str, account_id: str) -> Decimal:
    items = (await client.get("/accounts/balances", headers=_auth(token))).json()["items"]
    return Decimal(next(b for b in items if b["account_id"] == account_id)["current_balance"])


async def _amortize(
    client: AsyncClient,
    token: str,
    *,
    source_id: str,
    liability_id: str,
    counts_as_expense: bool | None = None,
    dry_run: bool = False,
) -> tuple[int, dict[str, object]]:
    payload: dict[str, object] = {
        "source_transaction_id": source_id,
        "liability_account_id": liability_id,
        "dry_run": dry_run,
    }
    if counts_as_expense is not None:
        payload["counts_as_expense"] = counts_as_expense
    r = await client.post("/transfers/amortization", json=payload, headers=_auth(token))
    body = r.json() if r.content else {}
    return r.status_code, dict(body) if isinstance(body, dict) else {}


async def _setup_card(client: AsyncClient, email: str) -> tuple[str, str, str]:
    """Usuario + cuenta corriente + tarjeta SIN cuadro. (token, bank, card)."""
    token = await _register(client, email)
    bank = await _create_account(client, token, name="BBVA", type="bank", currency="EUR")
    card = await _create_account(
        client, token, name="Tarjeta BBVA", type="credit_card", currency="EUR"
    )
    return token, str(bank["id"]), str(card["id"])


async def _setup_loan(client: AsyncClient, email: str) -> tuple[str, str, str]:
    """Usuario + cuenta corriente + préstamo CON cuadro. (token, bank, loan)."""
    token = await _register(client, email)
    bank = await _create_account(client, token, name="BBVA", type="bank", currency="EUR")
    loan = await _create_account(
        client,
        token,
        name="Prestamo coche",
        type="loan",
        currency="EUR",
        opening_balance="10000.00",
        apr="0.0590",
        term_months=12,
        start_date="2026-01-01",
    )
    return token, str(bank["id"]), str(loan["id"])


# ── El planificador puro ────────────────────────────────────────────────


def test_el_plan_de_cuotas_para_por_la_primera_que_no_cabe() -> None:
    rows = [
        LiabilityInstallment(installment_index=1, principal=Decimal("100"), paid_at=None),
        LiabilityInstallment(installment_index=2, principal=Decimal("100"), paid_at=None),
        LiabilityInstallment(installment_index=3, principal=Decimal("100"), paid_at=None),
    ]
    assert len(plan_installments_covering_principal(rows, Decimal("250"))) == 2
    # Un céntimo de holgura: 199,99 cubre dos cuotas de 100 (redondeo del banco).
    assert len(plan_installments_covering_principal(rows, Decimal("199.99"))) == 2
    # Por debajo de la primera pendiente no cubre NINGUNA: el saldo no baja.
    assert plan_installments_covering_principal(rows, Decimal("50")) == []


def test_el_plan_salta_las_cuotas_ya_pagadas() -> None:
    from datetime import UTC, datetime

    rows = [
        LiabilityInstallment(
            installment_index=1, principal=Decimal("100"), paid_at=datetime(2026, 1, 1, tzinfo=UTC)
        ),
        LiabilityInstallment(installment_index=2, principal=Decimal("100"), paid_at=None),
    ]
    plan = plan_installments_covering_principal(rows, Decimal("100"))
    assert [i.installment_index for i in plan] == [2]


# ── Modo movimiento (tarjeta sin cuadro) ────────────────────────────────


async def test_amortizacion_sin_cuadro_baja_la_deuda_por_el_importe(client: AsyncClient) -> None:
    token, bank, card = await _setup_card(client, "amort-mov@example.com")
    # La tarjeta arrastra 1.000 € de deuda por una compra registrada.
    await _create_tx(
        client, token, account_id=card, amount="1000.00", flow="OUT", description="Compra"
    )
    assert await _balance(client, token, card) == Decimal("1000.00")

    source = await _create_tx(client, token, account_id=bank, amount="400.00")
    status, body = await _amortize(
        client, token, source_id=source, liability_id=card, counts_as_expense=False
    )
    assert status == 200, body
    assert body["mode"] == "movement"
    assert Decimal(str(body["outstanding_before"])) == Decimal("1000.00")
    assert Decimal(str(body["outstanding_after"])) == Decimal("600.00")
    assert body["paired"] is True
    assert await _balance(client, token, card) == Decimal("600.00")


async def test_amortizacion_como_gasto_no_empareja(client: AsyncClient) -> None:
    """La pata del banco queda `OUT` y SIN emparejar a propósito.

    `budgets` y las queries de gasto del módulo de deuda filtran
    `transfer_pair_id IS NULL`, así que emparejar una pata declarada como gasto
    la borraría de las dos — lo contrario de lo que el usuario pidió.
    """
    token, bank, card = await _setup_card(client, "amort-gasto@example.com")
    await _create_tx(
        client, token, account_id=card, amount="1000.00", flow="OUT", description="Compra"
    )
    source = await _create_tx(client, token, account_id=bank, amount="400.00")

    status, body = await _amortize(
        client, token, source_id=source, liability_id=card, counts_as_expense=True
    )
    assert status == 200, body
    assert body["paired"] is False
    assert await _balance(client, token, card) == Decimal("600.00")

    detail = (await client.get(f"/transactions/{source}", headers=_auth(token))).json()
    assert detail["flow"] == "OUT"
    assert detail["transfer_pair_id"] is None


async def test_la_sugerencia_depende_de_si_la_tarjeta_tiene_compras(client: AsyncClient) -> None:
    token, bank, card = await _setup_card(client, "amort-sugerencia@example.com")
    source = await _create_tx(client, token, account_id=bank, amount="400.00")

    # Sin compras registradas: el cargo es el único rastro del gasto → sí cuenta.
    _, sin_compras = await _amortize(
        client, token, source_id=source, liability_id=card, dry_run=True
    )
    assert sin_compras["suggested_counts_as_expense"] is True
    assert "ninguna compra registrada" in str(sin_compras["suggestion_reason"])

    # Con compras registradas: ésas ya cuentan → contar la liquidación doblaría.
    await _create_tx(
        client, token, account_id=card, amount="50.00", flow="OUT", description="Consum"
    )
    _, con_compras = await _amortize(
        client, token, source_id=source, liability_id=card, dry_run=True
    )
    assert con_compras["suggested_counts_as_expense"] is False
    assert "dos veces" in str(con_compras["suggestion_reason"])


# ── Modo cuadro (préstamo) ──────────────────────────────────────────────


async def test_con_cuadro_la_deuda_baja_por_el_capital_no_por_lo_pagado(
    client: AsyncClient,
) -> None:
    token, bank, loan = await _setup_loan(client, "amort-cuadro@example.com")
    rows = (
        await client.get(f"/accounts/{loan}/amortization-schedule", headers=_auth(token))
    ).json()["rows"]
    first = rows[0]
    payment = Decimal(first["payment"])
    principal = Decimal(first["principal"])
    interest = Decimal(first["interest"])
    # Sanity: la cuota tiene interés, si no el test no probaría la distinción.
    assert interest > 0

    source = await _create_tx(
        client,
        token,
        account_id=bank,
        amount=f"{payment}",
        flow="OUT",
        description="Cargo por amortizacion de prestamo",
    )
    before = await _balance(client, token, loan)
    status, body = await _amortize(
        client, token, source_id=source, liability_id=loan, counts_as_expense=True
    )
    assert status == 200, body
    assert body["mode"] == "schedule"
    assert body["installments_marked"] == 1
    assert Decimal(str(body["principal_covered"])) == principal
    # Lo que NO amortiza (el interés) se declara en vez de esconderse.
    assert Decimal(str(body["principal_uncovered"])) == payment - principal
    assert await _balance(client, token, loan) == before - principal


async def test_un_pago_que_no_cubre_una_cuota_no_baja_la_deuda_y_lo_dice(
    client: AsyncClient,
) -> None:
    token, bank, loan = await _setup_loan(client, "amort-parcial@example.com")
    source = await _create_tx(client, token, account_id=bank, amount="10.00", flow="OUT")
    before = await _balance(client, token, loan)

    status, body = await _amortize(
        client, token, source_id=source, liability_id=loan, counts_as_expense=True
    )
    assert status == 200, body
    assert body["installments_marked"] == 0
    assert Decimal(str(body["principal_covered"])) == Decimal("0")
    assert Decimal(str(body["principal_uncovered"])) == Decimal("10.00")
    assert Decimal(str(body["outstanding_after"])) == before
    assert await _balance(client, token, loan) == before


async def test_con_cuadro_no_se_crea_ningun_movimiento_en_la_deuda(
    client: AsyncClient,
) -> None:
    """Manda el cuadro: una pata sería invisible para el saldo y ruido en la
    lista de movimientos de la cuenta."""
    token, bank, loan = await _setup_loan(client, "amort-sin-pata@example.com")
    rows = (
        await client.get(f"/accounts/{loan}/amortization-schedule", headers=_auth(token))
    ).json()["rows"]
    source = await _create_tx(client, token, account_id=bank, amount=rows[0]["payment"], flow="OUT")
    _, body = await _amortize(
        client, token, source_id=source, liability_id=loan, counts_as_expense=True
    )
    assert body["counterpart_transaction_id"] is None

    listed = (await client.get(f"/transactions?account_id={loan}", headers=_auth(token))).json()
    assert listed["total"] == 0


# ── dry_run ─────────────────────────────────────────────────────────────


async def test_dry_run_no_escribe_nada_y_predice_lo_que_pasa(client: AsyncClient) -> None:
    token, bank, card = await _setup_card(client, "amort-dryrun@example.com")
    await _create_tx(
        client, token, account_id=card, amount="1000.00", flow="OUT", description="Compra"
    )
    source = await _create_tx(client, token, account_id=bank, amount="400.00")

    _, preview = await _amortize(client, token, source_id=source, liability_id=card, dry_run=True)
    assert preview["dry_run"] is True
    assert await _balance(client, token, card) == Decimal("1000.00")

    _, applied = await _amortize(
        client, token, source_id=source, liability_id=card, counts_as_expense=False
    )
    # La previsión y el resultado salen de la misma cuenta: coinciden.
    assert applied["outstanding_after"] == preview["outstanding_after"]
    assert applied["principal_covered"] == preview["principal_covered"]
    assert applied["installments_marked"] == preview["installments_marked"]


async def test_aplicar_sin_declarar_si_es_gasto_es_400(client: AsyncClient) -> None:
    token, bank, card = await _setup_card(client, "amort-sin-declarar@example.com")
    source = await _create_tx(client, token, account_id=bank, amount="400.00")
    status, body = await _amortize(client, token, source_id=source, liability_id=card)
    assert status == 400, body
    assert "counts_as_expense" in str(body["detail"])


# ── Guardarraíles ───────────────────────────────────────────────────────


async def test_registrar_dos_veces_es_409(client: AsyncClient) -> None:
    token, bank, card = await _setup_card(client, "amort-doble@example.com")
    source = await _create_tx(client, token, account_id=bank, amount="400.00")
    first, _ = await _amortize(
        client, token, source_id=source, liability_id=card, counts_as_expense=True
    )
    assert first == 200
    second, body = await _amortize(
        client, token, source_id=source, liability_id=card, counts_as_expense=True
    )
    assert second == 409, body
    assert "ya está registrada" in str(body["detail"])


async def test_una_tx_emparejada_es_409(client: AsyncClient) -> None:
    """El par ya mueve el dinero a la otra cuenta; amortizar además bajaría la
    deuda dos veces por el mismo pago."""
    token, bank, card = await _setup_card(client, "amort-emparejada@example.com")
    out_tx = await _create_tx(client, token, account_id=bank, amount="400.00")
    in_tx = await _create_tx(client, token, account_id=card, amount="400.00", flow="TRANSFER_IN")
    linked = await client.post(
        "/transfers/link",
        json={"out_transaction_id": out_tx, "in_transaction_id": in_tx},
        headers=_auth(token),
    )
    assert linked.status_code == 201, linked.text

    status, body = await _amortize(
        client, token, source_id=out_tx, liability_id=card, counts_as_expense=True
    )
    assert status == 409, body
    assert "transferencia" in str(body["detail"])


async def test_un_ingreso_no_puede_amortizar(client: AsyncClient) -> None:
    token, bank, card = await _setup_card(client, "amort-ingreso@example.com")
    source = await _create_tx(client, token, account_id=bank, amount="400.00", flow="IN")
    status, body = await _amortize(
        client, token, source_id=source, liability_id=card, counts_as_expense=True
    )
    assert status == 400, body


async def test_la_cuenta_destino_debe_ser_de_deuda(client: AsyncClient) -> None:
    token, bank, _card = await _setup_card(client, "amort-destino@example.com")
    otra = await _create_account(client, token, name="Wise", type="bank", currency="EUR")
    source = await _create_tx(client, token, account_id=bank, amount="400.00")
    status, body = await _amortize(
        client, token, source_id=source, liability_id=str(otra["id"]), counts_as_expense=True
    )
    assert status == 400, body


async def test_cross_currency_es_400(client: AsyncClient) -> None:
    token, bank, _card = await _setup_card(client, "amort-divisa@example.com")
    usd_card = await _create_account(
        client, token, name="Tarjeta USD", type="credit_card", currency="USD"
    )
    source = await _create_tx(client, token, account_id=bank, amount="400.00")
    status, body = await _amortize(
        client,
        token,
        source_id=source,
        liability_id=str(usd_card["id"]),
        counts_as_expense=True,
    )
    assert status == 400, body


async def test_aislamiento_entre_usuarios(client: AsyncClient) -> None:
    token_a, bank_a, card_a = await _setup_card(client, "amort-a@example.com")
    source = await _create_tx(client, token_a, account_id=bank_a, amount="400.00")
    token_b = await _register(client, "amort-b@example.com")

    status, _ = await _amortize(
        client, token_b, source_id=source, liability_id=card_a, counts_as_expense=True
    )
    assert status == 404


# ── Consultar y deshacer ────────────────────────────────────────────────


async def test_consultar_el_registro_y_deshacerlo(client: AsyncClient) -> None:
    token, bank, card = await _setup_card(client, "amort-undo@example.com")
    await _create_tx(
        client, token, account_id=card, amount="1000.00", flow="OUT", description="Compra"
    )
    source = await _create_tx(client, token, account_id=bank, amount="400.00")

    # Antes de registrar: 404 (estado normal, no error de la pantalla).
    missing = await client.get(f"/transfers/amortization/{source}", headers=_auth(token))
    assert missing.status_code == 404

    await _amortize(client, token, source_id=source, liability_id=card, counts_as_expense=False)
    described = await client.get(f"/transfers/amortization/{source}", headers=_auth(token))
    assert described.status_code == 200, described.text
    state = described.json()
    assert state["liability_account_id"] == card
    assert state["mode"] == "movement"
    assert Decimal(state["outstanding_before"]) == Decimal("1000.00")
    assert Decimal(state["outstanding_after"]) == Decimal("600.00")

    undone = await client.delete(f"/transfers/amortization/{source}", headers=_auth(token))
    assert undone.status_code == 204, undone.text
    assert await _balance(client, token, card) == Decimal("1000.00")
    assert (
        await client.get(f"/transfers/amortization/{source}", headers=_auth(token))
    ).status_code == 404


async def test_deshacer_con_cuadro_desmarca_las_cuotas(client: AsyncClient) -> None:
    token, bank, loan = await _setup_loan(client, "amort-undo-cuadro@example.com")
    rows = (
        await client.get(f"/accounts/{loan}/amortization-schedule", headers=_auth(token))
    ).json()["rows"]
    source = await _create_tx(client, token, account_id=bank, amount=rows[0]["payment"], flow="OUT")
    before = await _balance(client, token, loan)
    await _amortize(client, token, source_id=source, liability_id=loan, counts_as_expense=True)
    assert await _balance(client, token, loan) < before

    undone = await client.delete(f"/transfers/amortization/{source}", headers=_auth(token))
    assert undone.status_code == 204, undone.text
    assert await _balance(client, token, loan) == before
    after_rows = (
        await client.get(f"/accounts/{loan}/amortization-schedule", headers=_auth(token))
    ).json()["rows"]
    assert all(r["paid_at"] is None for r in after_rows)


async def test_deshacer_algo_no_registrado_es_404(client: AsyncClient) -> None:
    token, bank, _card = await _setup_card(client, "amort-undo-404@example.com")
    source = await _create_tx(client, token, account_id=bank, amount="400.00")
    r = await client.delete(f"/transfers/amortization/{source}", headers=_auth(token))
    assert r.status_code == 404
