"""Tests del audit-fix del módulo `personal_finance/accounts`
(amortización + saldos) — AUDIT-2026-06.

NOTA sobre el finding #1/#2 (coherencia de la última cuota): la propuesta
original era hacer que la última fila reportase `payment == interest +
principal` (ajuste de cuota final como un banco). Se DESCARTÓ porque
choca con un contrato deliberado y testeado de PHASE-24.3: el cuadro usa
cuotas iguales (`Σ payments == n × cuota`) para que
`extra_charges = total_to_pay − Σ payments` revele la comisión oculta que
cobra el banco (ver `test_debt.py::test_extra_charges_derived_from_total_to_pay`,
caso real BBVA: 9 × 100,08 = 900,72 → comisión 13,14 €). Cambiar la
última cuota alteraría `total_paid` y, por tanto, la comisión calculada
(13,14 → 13,09), que es incorrecto desde el punto de vista del usuario.
Por eso `amortization.build_schedule` conserva la convención de cuotas
iguales y el finding #1/#2 queda como mejora de presentación pendiente de
decisión de producto.

Sí se mantienen y se cubren aquí:

  #3 [low]  `interest_only_first_payment` se almacenaba pero NUNCA se
            aplicaba a `total_paid`/`total_interest`. FIX: ahora se
            incorpora a ambos (coherente con el docstring del schema y
            con la base de `extra_charges`).
  #4 [low]  Editar el importe de una cuota no recomputaba el split de la
            fila → `payment != interest + principal`. FIX: al editar
            `payment`, `principal = payment − interest` (override puntual).
  #5 [low]  `get_balances` sumaba patrimonio en monedas mezcladas sin
            convertir. FIX: modo `target_currency` que convierte cada
            saldo con la tasa de hoy y excluye cuentas sin tasa,
            manteniendo el modo crudo + flag como fallback.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.currency import repository as rates_repository

# ---------------------------------------------------------------------------
# Helpers HTTP (mismo patrón que test_accounts.py)
# ---------------------------------------------------------------------------


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _setup_user(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    return r.json()["access_token"]


async def _create_loan(
    client: AsyncClient,
    token: str,
    *,
    name: str,
    principal: str,
    apr: str,
    term: int,
    start: str = "2024-01-15",
    interest_only: str | None = None,
    total_to_pay: str | None = None,
) -> str:
    body: dict[str, object] = {
        "name": name,
        "type": "loan",
        "currency": "EUR",
        "opening_balance": principal,
        "apr": apr,
        "term_months": term,
        "start_date": start,
    }
    if interest_only is not None:
        body["interest_only_first_payment"] = interest_only
    if total_to_pay is not None:
        body["total_to_pay"] = total_to_pay
    r = await client.post("/accounts", json=body, headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# #3 — interest_only_first_payment se aplica a total_paid (DB real)
# ---------------------------------------------------------------------------


async def test_schedule_endpoint_interest_only_applied(client: AsyncClient) -> None:
    """Con `interest_only_first_payment`, `total_paid` lo incluye (antes se
    ignoraba) y `extra_charges` se deriva de forma coherente. No se asume
    la identidad de la última cuota (convención de cuotas iguales)."""
    token = await _setup_user(client, "amort-io@example.com")
    aid = await _create_loan(
        client,
        token,
        name="Prestamo IO",
        principal="15000.00",
        apr="0.0699",
        term=60,
        interest_only="87.38",
        total_to_pay="18000.00",
    )
    r = await client.get(f"/accounts/{aid}/amortization-schedule", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()

    rows = body["rows"]
    sum_payments = sum((Decimal(row["payment"]) for row in rows), Decimal("0"))
    io = Decimal(body["interest_only_first_payment"])
    assert io == Decimal("87.38")
    # finding #3: el primer pago sólo-intereses se incorpora a total_paid
    # (= Σ cuotas + interest_only), en vez de ignorarse como antes.
    assert Decimal(body["total_paid"]) == sum_payments + io
    # extra_charges derivado de la MISMA base que total_paid.
    assert Decimal(body["extra_charges"]) == Decimal(body["total_to_pay"]) - Decimal(
        body["total_paid"]
    )


# ---------------------------------------------------------------------------
# #4 — editar una cuota recomputa su split (DB real)
# ---------------------------------------------------------------------------


async def test_edit_installment_recomputes_split(client: AsyncClient) -> None:
    """Al editar el `payment` de una cuota, `principal = payment − interest`
    para que la fila siga cumpliendo `payment == interest + principal`."""
    token = await _setup_user(client, "amort-edit@example.com")
    aid = await _create_loan(
        client,
        token,
        name="Prestamo Editable",
        principal="15000.00",
        apr="0.0699",
        term=60,
    )
    r = await client.get(f"/accounts/{aid}/amortization-schedule", headers=_auth(token))
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    target = rows[0]
    inst_id = target["id"]
    interest = Decimal(target["interest"])

    # Subir la cuota en 50 € respecto a la original.
    new_payment = (Decimal(target["payment"]) + Decimal("50.00")).quantize(Decimal("0.01"))
    patch = await client.patch(
        f"/accounts/installments/{inst_id}",
        json={"payment": str(new_payment)},
        headers=_auth(token),
    )
    assert patch.status_code == 200, patch.text
    updated = patch.json()
    assert Decimal(updated["payment"]) == new_payment
    # El interés del mes se mantiene; el principal absorbe la diferencia.
    assert Decimal(updated["interest"]) == interest
    assert Decimal(updated["principal"]) == new_payment - interest
    # Identidad de la fila restaurada.
    assert Decimal(updated["payment"]) == Decimal(updated["interest"]) + Decimal(
        updated["principal"]
    )


# ---------------------------------------------------------------------------
# #5 — get_balances con target_currency (DB real)
# ---------------------------------------------------------------------------


async def test_balances_raw_mode_unchanged(client: AsyncClient) -> None:
    """Sin `target_currency`, /accounts/balances mantiene el modo crudo +
    `mixed_currencies` (no se rompen los consumidores existentes)."""
    token = await _setup_user(client, "bal-raw@example.com")
    await client.post(
        "/accounts",
        json={"name": "EUR acc", "type": "bank", "currency": "EUR", "opening_balance": "100.00"},
        headers=_auth(token),
    )
    await client.post(
        "/accounts",
        json={"name": "USD acc", "type": "bank", "currency": "USD", "opening_balance": "100.00"},
        headers=_auth(token),
    )
    r = await client.get("/accounts/balances", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    # Dos monedas activas distintas → suma cruda + flag.
    assert body["mixed_currencies"] is True
    # Suma cruda: 100 EUR + 100 USD = 200 (sin sentido, pero es el contrato
    # del modo crudo que la UI advierte con el flag).
    assert Decimal(body["total_assets"]) == Decimal("200.00")


async def test_balances_target_currency_homogenizes_and_excludes_unrated(
    client: AsyncClient,
) -> None:
    """Con `?target_currency=EUR`, los saldos se homogeneizan a esa moneda
    (`mixed_currencies=False`) y las cuentas cuya divisa no tiene tasa
    quedan EXCLUIDAS del agregado, en vez de sumar monedas crudas
    (finding #net-worth-mixed-currencies)."""
    token = await _setup_user(client, "bal-target@example.com")
    await client.post(
        "/accounts",
        json={"name": "EUR1", "type": "bank", "currency": "EUR", "opening_balance": "100.00"},
        headers=_auth(token),
    )
    await client.post(
        "/accounts",
        json={"name": "EUR2", "type": "bank", "currency": "EUR", "opening_balance": "50.00"},
        headers=_auth(token),
    )
    # USD sin tasa EUR↔USD sembrada en la DB de tests → inconvertible.
    await client.post(
        "/accounts",
        json={"name": "USD", "type": "bank", "currency": "USD", "opening_balance": "100.00"},
        headers=_auth(token),
    )
    r = await client.get("/accounts/balances?target_currency=EUR", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    # Homogeneizado al target → ya no hay mezcla.
    assert body["mixed_currencies"] is False
    # Sólo las dos cuentas EUR (100+50) entran; la USD sin tasa se excluye.
    assert Decimal(body["total_assets"]) == Decimal("150.00")
    # `items` muestra las 3 cuentas; la USD (sin tasa) se queda nativa.
    assert len(body["items"]) == 3


async def _seed_rates(test_engine, rows: list[tuple[date, str, str, str]]) -> None:  # type: ignore[no-untyped-def]
    """rows: (rate_date, base, quote, rate_string). Siembra directo en
    `exchange_rates` para no depender de frankfurter en CI."""
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    async with factory() as db:
        await rates_repository.upsert_rates(
            db,
            [(d, base, quote, Decimal(rate), "test") for d, base, quote, rate in rows],
        )
        await db.commit()


async def test_balances_target_currency_converts_each_item(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
) -> None:
    """AUDIT-2026-06 — En modo convertido, CADA item de
    `/accounts/balances` se reexpresa en la divisa destino (no sólo los
    agregados). Antes los items se quedaban nativos, así que la DebtList
    y los tiles del hero salían en divisa distinta a los KPIs/charts de la
    misma pantalla (findings deuda #2 / integración #7)."""
    token = await _setup_user(client, "bal-item-convert@example.com")
    await client.post(
        "/accounts",
        json={"name": "EUR", "type": "bank", "currency": "EUR", "opening_balance": "100.00"},
        headers=_auth(token),
    )
    await client.post(
        "/accounts",
        json={"name": "USD", "type": "bank", "currency": "USD", "opening_balance": "110.00"},
        headers=_auth(token),
    )
    # 1 EUR = 1.10 USD (hoy) → 110 USD = 100 EUR.
    await _seed_rates(test_engine, [(date.today(), "EUR", "USD", "1.10")])

    r = await client.get("/accounts/balances?target_currency=EUR", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    items = {it["name"]: it for it in body["items"]}
    # El item USD ahora se reporta en EUR con el saldo convertido.
    assert items["USD"]["currency"] == "EUR"
    assert Decimal(items["USD"]["current_balance"]) == Decimal("100.00")
    # El item EUR (== target) no cambia.
    assert items["EUR"]["currency"] == "EUR"
    assert Decimal(items["EUR"]["current_balance"]) == Decimal("100.00")
    # Agregado homogéneo: 100 (EUR) + 100 (USD→EUR) = 200.
    assert Decimal(body["total_assets"]) == Decimal("200.00")
    assert body["mixed_currencies"] is False
