"""Tests de la auditoría del módulo transactions.

Cubre dos defectos cerrados:

1. (high) create/update_transaction asignaban `category_id` sin validar
   que la categoría pertenece al usuario → fuga multi-tenant + posible
   corrupción del saldo al heredar `kind`/`is_transfer` ajenos.
2. (low) `converted_amount` per-row se devolvía con la precisión cruda
   de SQL (8 decimales) → la suma de filas mostradas no cuadraba con un
   total cuantizado a céntimos.

No tocan ficheros de test existentes (fichero nuevo, por requisito de la
auditoría).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.currency import repository as rates_repository
from app.modules.currency.exceptions import FrankfurterUnavailableError


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client: AsyncClient, email: str) -> tuple[str, str]:
    """Registra un usuario y le crea una cuenta. Devuelve (token, account_id)."""
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    token = r.json()["access_token"]
    acc = await client.post(
        "/accounts",
        json={"name": "Cuenta principal", "type": "bank", "currency": "EUR"},
        headers=_auth(token),
    )
    return token, acc.json()["id"]


async def _make_category(client: AsyncClient, token: str, *, name: str, kind: str) -> str:
    r = await client.post(
        "/categories",
        json={"name": name, "kind": kind},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------- Fix #1: aislamiento multi-tenant de category_id ----------


async def test_create_transaction_rejects_foreign_category(client: AsyncClient) -> None:
    """Usuario A NO puede crear una tx referenciando la categoría de B.

    Espera 400 (mismo código/mensaje que category_rules y receipts), no
    201 — antes de la auditoría se persistía sin comprobar pertenencia.
    """
    token_b, _acc_b = await _register(client, "audit_owner_b@example.com")
    cat_b = await _make_category(client, token_b, name="Privada de B", kind="expense")

    token_a, acc_a = await _register(client, "audit_attacker_a@example.com")
    r = await client.post(
        "/transactions",
        json={
            "account_id": acc_a,
            "category_id": cat_b,  # categoría de OTRO usuario
            "amount": "10.00",
            "currency": "EUR",
            "occurred_at": "2026-04-15T12:00:00Z",
        },
        headers=_auth(token_a),
    )
    assert r.status_code == 400, r.text
    assert "category_id" in r.json()["detail"]


async def test_update_transaction_rejects_foreign_category(client: AsyncClient) -> None:
    """Usuario A NO puede reasignar su tx a la categoría de B vía PUT."""
    token_b, _acc_b = await _register(client, "audit_owner_b2@example.com")
    cat_b = await _make_category(client, token_b, name="Privada de B", kind="expense")

    token_a, acc_a = await _register(client, "audit_attacker_a2@example.com")
    cat_a = await _make_category(client, token_a, name="Propia de A", kind="expense")
    created = await client.post(
        "/transactions",
        json={
            "account_id": acc_a,
            "category_id": cat_a,
            "amount": "10.00",
            "currency": "EUR",
            "occurred_at": "2026-04-15T12:00:00Z",
        },
        headers=_auth(token_a),
    )
    assert created.status_code == 201, created.text
    tx_id = created.json()["id"]

    r = await client.put(
        f"/transactions/{tx_id}",
        json={"category_id": cat_b},  # categoría de OTRO usuario
        headers=_auth(token_a),
    )
    assert r.status_code == 400, r.text
    assert "category_id" in r.json()["detail"]

    # La tx conserva su categoría original (no se reasignó).
    after = await client.get(f"/transactions/{tx_id}", headers=_auth(token_a))
    assert after.json()["category_id"] == cat_a


async def test_create_transaction_accepts_own_category(client: AsyncClient) -> None:
    """Regresión: la categoría propia sigue funcionando (201)."""
    token, acc = await _register(client, "audit_owncat@example.com")
    cat = await _make_category(client, token, name="Mía", kind="expense")
    r = await client.post(
        "/transactions",
        json={
            "account_id": acc,
            "category_id": cat,
            "amount": "10.00",
            "currency": "EUR",
            "occurred_at": "2026-04-15T12:00:00Z",
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["category_id"] == cat


async def test_create_transaction_without_category_still_allowed(client: AsyncClient) -> None:
    """Regresión: una tx sin categoría sigue siendo válida (la validación
    de pertenencia sólo aplica cuando category_id no es NULL)."""
    token, acc = await _register(client, "audit_nocat@example.com")
    r = await client.post(
        "/transactions",
        json={
            "account_id": acc,
            "amount": "10.00",
            "currency": "EUR",
            "occurred_at": "2026-04-15T12:00:00Z",
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["category_id"] is None


# ---------- Fix #2: cuantización per-row de converted_amount ----------


async def _seed_rates(test_engine, rows: list[tuple[date, str, str, str]]) -> None:  # type: ignore[no-untyped-def]
    """rows: list of (rate_date, base, quote, rate_string)."""
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    async with factory() as db:
        await rates_repository.upsert_rates(
            db,
            [(d, base, quote, Decimal(rate), "test") for d, base, quote, rate in rows],
        )
        await db.commit()


@pytest_asyncio.fixture(autouse=True)
async def _mock_frankfurter():
    """Bloquea el fetch real a frankfurter: las tasas vienen sólo de los
    seeds explícitos, sin depender de red ni de la fecha real del CI."""
    with patch(
        "app.modules.currency.client.fetch_rates",
        new_callable=AsyncMock,
        side_effect=FrankfurterUnavailableError("test offline"),
    ):
        yield


async def test_converted_amount_is_quantized_to_cents(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
) -> None:
    """`converted_amount` per-row se devuelve con 2 decimales y la suma de
    filas cuadra con el total esperado a céntimos.

    100 USD @ 0.9123 (EUR→USD) → 100 / 0.9123 = 109.6131...€ cruda;
    debe llegar redondeada a 109.61 €. Una segunda fila de 50 USD →
    54.81 €. Suma de filas = 164.42 €, sin colas de 8 decimales.
    """
    token, account_id = await _register(client, "audit_quant@example.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")

    for amount, when in (("100", "2026-02-15T12:00:00Z"), ("50", "2026-02-15T12:00:00Z")):
        r = await client.post(
            "/transactions",
            json={
                "account_id": account_id,
                "category_id": expense,
                "amount": amount,
                "currency": "USD",
                "occurred_at": when,
            },
            headers=_auth(token),
        )
        assert r.status_code == 201, r.text

    # EUR→USD = 0.9123 ese día (tasa "fea" para forzar decimales no triviales).
    await _seed_rates(test_engine, [(date(2026, 2, 15), "EUR", "USD", "0.9123")])

    r = await client.get(
        "/transactions",
        params={"target_currency": "EUR"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 2

    converted = [Decimal(it["converted_amount"]) for it in items]
    # Cada fila tiene exactamente 2 decimales (la cuantización aplicó) y la
    # moneda destino es la solicitada.
    for it, value in zip(items, converted, strict=True):
        assert value.as_tuple().exponent == -2, it["converted_amount"]
        assert it["converted_currency"] == "EUR"

    # Valores esperados redondeados a céntimos (ROUND_HALF_EVEN, default Decimal).
    # 100 / 0.9123 = 109.6131...  → 109.61 ; 50 / 0.9123 = 54.8065... → 54.81
    assert sorted(converted) == [Decimal("54.81"), Decimal("109.61")]
    # La suma de las filas mostradas cuadra a céntimos.
    assert sum(converted) == Decimal("164.42")
