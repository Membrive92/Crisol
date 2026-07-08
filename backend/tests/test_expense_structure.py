"""Tests de gasto estructural vs puntual + tasa de ahorro dual (PHASE-37.3).

Tres capas:
1. Unit puro sobre la regla 3 (`classify_recurring_categories`) — sin BD.
2. Integración vía API del endpoint `/analytics/expense-structure`.
3. `seed_structural_category_ids` con sesión directa (reglas 1 y 2).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.personal_finance.analytics.recurrence import classify_recurring_categories
from app.modules.personal_finance.analytics.repository import seed_structural_category_ids
from app.modules.personal_finance.fixed_expenses.models import FixedExpense, FixedExpenseStatus

_UNSET: Any = object()


# ─────────────────────────────────────────────────────────────────────
# 1. Unit puro — regla 3 (recurrencia por importe estable)
# ─────────────────────────────────────────────────────────────────────


def test_recurrence_stable_category_is_recurring() -> None:
    cat = uuid.uuid4()
    # 5 meses con importe casi idéntico (dentro de ±40%).
    totals = {cat: [Decimal("100"), Decimal("110"), Decimal("95"), Decimal("105"), Decimal("100")]}
    assert classify_recurring_categories(totals) == {cat}


def test_recurrence_single_large_is_not_recurring() -> None:
    cat = uuid.uuid4()
    # Un único mes (gasto puntual grande) no recurre.
    assert classify_recurring_categories({cat: [Decimal("3000")]}) == set()


def test_recurrence_below_min_months_is_not_recurring() -> None:
    cat = uuid.uuid4()
    # 3 meses (< N=4) no basta aunque sean estables.
    totals = {cat: [Decimal("50"), Decimal("50"), Decimal("50")]}
    assert classify_recurring_categories(totals) == set()


def test_recurrence_volatile_amounts_not_recurring() -> None:
    cat = uuid.uuid4()
    # 5 meses de actividad pero importes dispares: la mediana (50) deja
    # fuera de banda a los picos, y quedan < N=4 meses en banda.
    totals = {cat: [Decimal("10"), Decimal("50"), Decimal("500"), Decimal("5"), Decimal("300")]}
    assert classify_recurring_categories(totals) == set()


def test_recurrence_median_resists_one_outlier() -> None:
    cat = uuid.uuid4()
    # 4 meses estables (~100) + 1 outlier: la mediana sigue en 100 y los
    # 4 estables quedan en banda → recurrente.
    totals = {cat: [Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100"), Decimal("900")]}
    assert classify_recurring_categories(totals) == {cat}


# ─────────────────────────────────────────────────────────────────────
# Helpers de integración
# ─────────────────────────────────────────────────────────────────────


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Exp"},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["access_token"])


async def _create_account(client: AsyncClient, token: str) -> str:
    r = await client.post(
        "/accounts",
        json={"name": "BBVA", "type": "bank", "currency": "EUR", "opening_balance": "0.00"},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _create_category(
    client: AsyncClient,
    token: str,
    *,
    name: str,
    kind: str = "expense",
    role: str = "GENERIC",
) -> dict[str, Any]:
    r = await client.post(
        "/categories",
        json={"name": name, "kind": kind, "role": role},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


async def _post_tx(
    client: AsyncClient,
    token: str,
    *,
    account_id: str,
    amount: str,
    flow: str,
    when: str,
    category_id: str | None = None,
    is_exceptional: Any = _UNSET,
) -> str:
    payload: dict[str, Any] = {
        "account_id": account_id,
        "amount": amount,
        "currency": "EUR",
        "occurred_at": when,
        "flow": flow,
    }
    if category_id is not None:
        payload["category_id"] = category_id
    if is_exceptional is not _UNSET:
        payload["is_exceptional"] = is_exceptional
    r = await client.post("/transactions", json=payload, headers=_auth(token))
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def _june_query() -> str:
    # Rango = junio 2026. La ventana de recurrencia queda ene–jun 2026.
    return "?currency=EUR&date_from=2026-06-01T00:00:00Z&date_to=2026-06-30T23:59:59Z"


async def _expense_structure(client: AsyncClient, token: str) -> dict[str, Any]:
    r = await client.get(f"/analytics/expense-structure{_june_query()}", headers=_auth(token))
    assert r.status_code == 200, r.text
    return dict(r.json())


# ─────────────────────────────────────────────────────────────────────
# 2. Integración — endpoint
# ─────────────────────────────────────────────────────────────────────


async def test_split_recurring_vs_oneoff_and_invariant(client: AsyncClient) -> None:
    """Categoría recurrente (6 meses) → estructural; one-off → puntual;
    estructural + puntual == gasto total; tasas de ahorro dual."""
    token = await _register(client, "exp_split@example.com")
    acc = await _create_account(client, token)
    market = await _create_category(client, token, name="Supermercado")
    dentist = await _create_category(client, token, name="Dentista")

    # Supermercado ~100 € cada mes ene–jun → recurrente (estructural).
    for month in range(1, 7):
        await _post_tx(
            client, token, account_id=acc, amount="100.00", flow="OUT",
            when=f"2026-0{month}-15T12:00:00Z", category_id=market["id"],
        )
    # Dentista 500 € sólo en junio → puntual.
    await _post_tx(
        client, token, account_id=acc, amount="500.00", flow="OUT",
        when="2026-06-20T12:00:00Z", category_id=dentist["id"],
    )
    # Ingreso de junio para las tasas de ahorro.
    await _post_tx(
        client, token, account_id=acc, amount="2000.00", flow="IN",
        when="2026-06-01T09:00:00Z",
    )

    body = await _expense_structure(client, token)
    assert Decimal(body["structural_total"]) == Decimal("100.00")
    assert Decimal(body["exceptional_total"]) == Decimal("500.00")
    # Invariante: estructural + puntual == gasto total del rango.
    assert Decimal(body["structural_total"]) + Decimal(body["exceptional_total"]) == Decimal(
        "600.00"
    )
    # Media mensual estructural sobre ene–jun: 100 €/mes.
    assert Decimal(body["structural_monthly_avg"]) == Decimal("100.00")
    assert body["savings_rate_gross"] == pytest.approx(0.7)
    assert body["savings_rate_structural"] == pytest.approx(0.95)
    # El puntual asoma en las listas.
    assert len(body["top_exceptional"]) == 1
    assert Decimal(body["top_exceptional"][0]["amount"]) == Decimal("500.00")
    assert body["exceptional_by_category"][0]["category_name"] == "Dentista"


async def test_debt_category_is_structural(client: AsyncClient) -> None:
    """Una categoría con rol de deuda es estructural aunque sólo tenga
    un mes de actividad (regla 2, no depende de recurrencia)."""
    token = await _register(client, "exp_debt@example.com")
    acc = await _create_account(client, token)
    loan = await _create_category(client, token, name="Cuota préstamo", role="DEBT_PAYMENT")
    await _post_tx(
        client, token, account_id=acc, amount="200.00", flow="OUT",
        when="2026-06-10T12:00:00Z", category_id=loan["id"],
    )
    body = await _expense_structure(client, token)
    assert Decimal(body["structural_total"]) == Decimal("200.00")
    assert Decimal(body["exceptional_total"]) == Decimal("0.00")


async def test_override_true_forces_exceptional(client: AsyncClient) -> None:
    """`is_exceptional=true` gana sobre la heurística: una tx en categoría
    de deuda (estructural) marcada puntual cuenta como puntual."""
    token = await _register(client, "exp_ovr_true@example.com")
    acc = await _create_account(client, token)
    loan = await _create_category(client, token, name="Cuota préstamo", role="DEBT_PAYMENT")
    await _post_tx(
        client, token, account_id=acc, amount="200.00", flow="OUT",
        when="2026-06-10T12:00:00Z", category_id=loan["id"], is_exceptional=True,
    )
    body = await _expense_structure(client, token)
    assert Decimal(body["structural_total"]) == Decimal("0.00")
    assert Decimal(body["exceptional_total"]) == Decimal("200.00")


async def test_override_false_forces_structural(client: AsyncClient) -> None:
    """`is_exceptional=false` gana: un one-off marcado estructural cuenta
    como estructural pese a no recurrir."""
    token = await _register(client, "exp_ovr_false@example.com")
    acc = await _create_account(client, token)
    misc = await _create_category(client, token, name="Reforma")
    await _post_tx(
        client, token, account_id=acc, amount="800.00", flow="OUT",
        when="2026-06-10T12:00:00Z", category_id=misc["id"], is_exceptional=False,
    )
    body = await _expense_structure(client, token)
    assert Decimal(body["structural_total"]) == Decimal("800.00")
    assert Decimal(body["exceptional_total"]) == Decimal("0.00")


async def test_transfers_excluded_from_both_totals(client: AsyncClient) -> None:
    """Un movimiento TRANSFER_OUT no cuenta ni en estructural ni en puntual."""
    token = await _register(client, "exp_transfer@example.com")
    acc = await _create_account(client, token)
    misc = await _create_category(client, token, name="Varios")
    await _post_tx(
        client, token, account_id=acc, amount="300.00", flow="OUT",
        when="2026-06-05T12:00:00Z", category_id=misc["id"],
    )
    # Transferencia interna (no cashflow).
    await _post_tx(
        client, token, account_id=acc, amount="1000.00", flow="TRANSFER_OUT",
        when="2026-06-06T12:00:00Z",
    )
    body = await _expense_structure(client, token)
    total = Decimal(body["structural_total"]) + Decimal(body["exceptional_total"])
    assert total == Decimal("300.00")  # la transferencia no suma


async def test_savings_rate_none_without_income(client: AsyncClient) -> None:
    """Sin ingresos en el rango, ambas tasas de ahorro son None (no 0)."""
    token = await _register(client, "exp_noincome@example.com")
    acc = await _create_account(client, token)
    misc = await _create_category(client, token, name="Varios")
    await _post_tx(
        client, token, account_id=acc, amount="120.00", flow="OUT",
        when="2026-06-05T12:00:00Z", category_id=misc["id"],
    )
    body = await _expense_structure(client, token)
    assert body["savings_rate_gross"] is None
    assert body["savings_rate_structural"] is None


# ─────────────────────────────────────────────────────────────────────
# 3. Sesión directa — seed (reglas 1 y 2)
# ─────────────────────────────────────────────────────────────────────


async def test_seed_structural_ids_rules_1_and_2(
    client: AsyncClient,
    test_engine: Any,
) -> None:
    """`seed_structural_category_ids`: incluye la categoría de un
    fixed_expense CONFIRMADO (regla 1) y la de rol deuda (regla 2), y
    EXCLUYE la de un fixed_expense sólo pendiente."""
    token = await _register(client, "exp_seed@example.com")
    gym = await _create_category(client, token, name="Gimnasio")
    loan = await _create_category(client, token, name="Cuota", role="DEBT_PAYMENT")
    pending = await _create_category(client, token, name="Sugerido")
    user_id = uuid.UUID(gym["user_id"])

    sm = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with sm() as session:
        session.add(
            FixedExpense(
                user_id=user_id, merchant="GYM", raw_description="GYM CUOTA",
                amount=Decimal("30.00"), currency="EUR", cadence_days=30,
                next_due=date(2026, 8, 1), status=FixedExpenseStatus.CONFIRMED,
                category_id=uuid.UUID(gym["id"]), first_seen_at=date(2026, 1, 1),
                last_seen_at=date(2026, 7, 1), occurrence_count=6, confidence=0.9,
            )
        )
        session.add(
            FixedExpense(
                user_id=user_id, merchant="OTRO", raw_description="OTRO",
                amount=Decimal("10.00"), currency="EUR", cadence_days=30,
                next_due=date(2026, 8, 1), status=FixedExpenseStatus.PENDING,
                category_id=uuid.UUID(pending["id"]), first_seen_at=date(2026, 1, 1),
                last_seen_at=date(2026, 7, 1), occurrence_count=2, confidence=0.4,
            )
        )
        await session.commit()
        ids = await seed_structural_category_ids(session, user_id)

    assert uuid.UUID(gym["id"]) in ids  # regla 1 (fixed_expense confirmado)
    assert uuid.UUID(loan["id"]) in ids  # regla 2 (rol deuda)
    assert uuid.UUID(pending["id"]) not in ids  # pendiente → no cuenta
