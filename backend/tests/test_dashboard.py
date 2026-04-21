"""Tests del módulo dashboard.

Cubre: agregaciones básicas, filtros por fecha/moneda, bucket "Sin
categoría", aislamiento multi-usuario, top-expenses.
"""

from __future__ import annotations

from httpx import AsyncClient


async def _register(client: AsyncClient, email: str) -> str:
    """Registra un usuario y devuelve su access_token."""
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _make_category(
    client: AsyncClient, token: str, *, name: str, kind: str
) -> str:
    r = await client.post(
        "/categories",
        json={"name": name, "kind": kind},
        headers=_auth(token),
    )
    return r.json()["id"]


async def _make_tx(
    client: AsyncClient,
    token: str,
    *,
    amount: str,
    occurred_at: str,
    category_id: str | None = None,
    currency: str = "USD",
    description: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "amount": amount,
        "currency": currency,
        "occurred_at": occurred_at,
    }
    if category_id is not None:
        payload["category_id"] = category_id
    if description is not None:
        payload["description"] = description
    r = await client.post("/transactions", json=payload, headers=_auth(token))
    assert r.status_code == 201, r.text


# ---------- /dashboard/summary ----------


async def test_summary_zero_when_no_transactions(client: AsyncClient) -> None:
    token = await _register(client, "dash-empty@example.com")

    r = await client.get("/dashboard/summary", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["income"] == "0"
    assert body["expenses"] == "0"
    assert body["balance"] == "0"
    assert body["transaction_count"] == 0
    assert body["currency"] == "USD"


async def test_summary_aggregates_income_expenses_and_balance(client: AsyncClient) -> None:
    token = await _register(client, "dash-sum@example.com")
    income_cat = await _make_category(client, token, name="Salario", kind="income")
    expense_cat = await _make_category(client, token, name="Comida", kind="expense")

    await _make_tx(
        client, token, amount="1000.00", occurred_at="2026-04-01T10:00:00Z",
        category_id=income_cat,
    )
    await _make_tx(
        client, token, amount="150.50", occurred_at="2026-04-02T10:00:00Z",
        category_id=expense_cat,
    )
    await _make_tx(
        client, token, amount="49.50", occurred_at="2026-04-03T10:00:00Z",
        category_id=expense_cat,
    )

    r = await client.get("/dashboard/summary", headers=_auth(token))
    body = r.json()
    assert body["income"] == "1000.00"
    assert body["expenses"] == "200.00"
    assert body["balance"] == "800.00"
    assert body["transaction_count"] == 3


async def test_summary_filters_by_currency(client: AsyncClient) -> None:
    token = await _register(client, "dash-cur@example.com")
    cat = await _make_category(client, token, name="Salario", kind="income")

    await _make_tx(
        client, token, amount="100.00", occurred_at="2026-04-01T10:00:00Z",
        category_id=cat, currency="USD",
    )
    await _make_tx(
        client, token, amount="200.00", occurred_at="2026-04-01T10:00:00Z",
        category_id=cat, currency="EUR",
    )

    r_usd = await client.get("/dashboard/summary", headers=_auth(token))
    r_eur = await client.get("/dashboard/summary?currency=EUR", headers=_auth(token))

    assert r_usd.json()["income"] == "100.00"
    assert r_eur.json()["income"] == "200.00"


async def test_summary_filters_by_date_range(client: AsyncClient) -> None:
    token = await _register(client, "dash-date@example.com")
    cat = await _make_category(client, token, name="Comida", kind="expense")

    await _make_tx(
        client, token, amount="10.00", occurred_at="2026-01-15T10:00:00Z",
        category_id=cat,
    )
    await _make_tx(
        client, token, amount="20.00", occurred_at="2026-06-15T10:00:00Z",
        category_id=cat,
    )

    r = await client.get(
        "/dashboard/summary",
        params={"date_from": "2026-06-01T00:00:00Z"},
        headers=_auth(token),
    )
    assert r.json()["expenses"] == "20.00"
    assert r.json()["transaction_count"] == 1


async def test_summary_counts_uncategorized_but_not_in_income_expense(
    client: AsyncClient,
) -> None:
    """Transacciones sin categoría cuentan en total, no en income/expenses."""
    token = await _register(client, "dash-uncat@example.com")
    income_cat = await _make_category(client, token, name="Salario", kind="income")

    await _make_tx(
        client, token, amount="500.00", occurred_at="2026-04-01T10:00:00Z",
        category_id=income_cat,
    )
    await _make_tx(
        client, token, amount="50.00", occurred_at="2026-04-02T10:00:00Z",
        category_id=None,
    )

    r = await client.get("/dashboard/summary", headers=_auth(token))
    body = r.json()
    assert body["income"] == "500.00"
    assert body["expenses"] == "0"
    assert body["balance"] == "500.00"
    assert body["transaction_count"] == 2


# ---------- /dashboard/by-category ----------


async def test_by_category_includes_uncategorized_bucket(client: AsyncClient) -> None:
    token = await _register(client, "dash-cat@example.com")
    food = await _make_category(client, token, name="Comida", kind="expense")
    transport = await _make_category(client, token, name="Transporte", kind="expense")

    await _make_tx(
        client, token, amount="30.00", occurred_at="2026-04-01T10:00:00Z",
        category_id=food,
    )
    await _make_tx(
        client, token, amount="20.00", occurred_at="2026-04-02T10:00:00Z",
        category_id=food,
    )
    await _make_tx(
        client, token, amount="15.00", occurred_at="2026-04-03T10:00:00Z",
        category_id=transport,
    )
    await _make_tx(
        client, token, amount="5.00", occurred_at="2026-04-04T10:00:00Z",
        category_id=None,
    )

    r = await client.get("/dashboard/by-category", headers=_auth(token))
    items = r.json()
    assert len(items) == 3

    by_name = {i["category_name"]: i for i in items}
    assert by_name["Comida"]["total"] == "50.00"
    assert by_name["Comida"]["count"] == 2
    assert by_name["Transporte"]["total"] == "15.00"
    assert by_name["Sin categoría"]["total"] == "5.00"
    assert by_name["Sin categoría"]["category_id"] is None
    assert by_name["Sin categoría"]["category_kind"] is None


async def test_by_category_filter_by_kind_excludes_uncategorized(
    client: AsyncClient,
) -> None:
    token = await _register(client, "dash-kind@example.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")
    income = await _make_category(client, token, name="Ingreso", kind="income")

    await _make_tx(
        client, token, amount="10.00", occurred_at="2026-04-01T10:00:00Z",
        category_id=expense,
    )
    await _make_tx(
        client, token, amount="100.00", occurred_at="2026-04-01T10:00:00Z",
        category_id=income,
    )
    await _make_tx(
        client, token, amount="50.00", occurred_at="2026-04-01T10:00:00Z",
        category_id=None,
    )

    r = await client.get(
        "/dashboard/by-category", params={"kind": "expense"}, headers=_auth(token)
    )
    items = r.json()
    assert len(items) == 1
    assert items[0]["category_name"] == "Gasto"


# ---------- /dashboard/by-month ----------


async def test_by_month_returns_12_buckets_with_zero_fill(client: AsyncClient) -> None:
    token = await _register(client, "dash-month@example.com")
    income = await _make_category(client, token, name="Salario", kind="income")
    expense = await _make_category(client, token, name="Comida", kind="expense")

    await _make_tx(
        client, token, amount="1000.00", occurred_at="2026-03-15T10:00:00Z",
        category_id=income,
    )
    await _make_tx(
        client, token, amount="200.00", occurred_at="2026-03-20T10:00:00Z",
        category_id=expense,
    )
    await _make_tx(
        client, token, amount="2000.00", occurred_at="2026-07-15T10:00:00Z",
        category_id=income,
    )

    r = await client.get("/dashboard/by-month?year=2026", headers=_auth(token))
    buckets = r.json()
    assert len(buckets) == 12

    by_month = {b["month"]: b for b in buckets}
    assert by_month["2026-03"]["income"] == "1000.00"
    assert by_month["2026-03"]["expenses"] == "200.00"
    assert by_month["2026-03"]["balance"] == "800.00"
    assert by_month["2026-07"]["income"] == "2000.00"
    assert by_month["2026-07"]["expenses"] == "0"
    assert by_month["2026-01"]["income"] == "0"
    assert by_month["2026-12"]["balance"] == "0"


async def test_by_month_ignores_other_years(client: AsyncClient) -> None:
    token = await _register(client, "dash-year@example.com")
    cat = await _make_category(client, token, name="Salario", kind="income")

    await _make_tx(
        client, token, amount="500.00", occurred_at="2025-06-15T10:00:00Z",
        category_id=cat,
    )
    await _make_tx(
        client, token, amount="1000.00", occurred_at="2026-06-15T10:00:00Z",
        category_id=cat,
    )

    r = await client.get("/dashboard/by-month?year=2026", headers=_auth(token))
    buckets = {b["month"]: b for b in r.json()}
    assert buckets["2026-06"]["income"] == "1000.00"


# ---------- /dashboard/top-expenses ----------


async def test_top_expenses_sorted_desc_respecting_limit(client: AsyncClient) -> None:
    token = await _register(client, "dash-top@example.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")

    amounts = ["10.00", "500.00", "50.00", "100.00", "5.00"]
    for idx, amount in enumerate(amounts):
        await _make_tx(
            client, token, amount=amount, occurred_at=f"2026-04-{10 + idx}T10:00:00Z",
            category_id=expense, description=f"Gasto {amount}",
        )

    r = await client.get(
        "/dashboard/top-expenses", params={"limit": 3}, headers=_auth(token)
    )
    items = r.json()
    assert len(items) == 3
    assert [i["amount"] for i in items] == ["500.00", "100.00", "50.00"]


async def test_top_expenses_excludes_income_and_uncategorized(client: AsyncClient) -> None:
    token = await _register(client, "dash-topx@example.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")
    income = await _make_category(client, token, name="Ingreso", kind="income")

    await _make_tx(
        client, token, amount="999.00", occurred_at="2026-04-01T10:00:00Z",
        category_id=income, description="Income 999 (should NOT appear)",
    )
    await _make_tx(
        client, token, amount="888.00", occurred_at="2026-04-02T10:00:00Z",
        category_id=None, description="Uncategorized 888 (should NOT appear)",
    )
    await _make_tx(
        client, token, amount="10.00", occurred_at="2026-04-03T10:00:00Z",
        category_id=expense, description="Real expense",
    )

    r = await client.get("/dashboard/top-expenses", headers=_auth(token))
    items = r.json()
    assert len(items) == 1
    assert items[0]["description"] == "Real expense"


# ---------- Isolation ----------


async def test_dashboard_user_isolation(client: AsyncClient) -> None:
    """Usuario A no ve agregados de usuario B en ningún endpoint."""
    token_a = await _register(client, "dashA@example.com")
    token_b = await _register(client, "dashB@example.com")

    exp_a = await _make_category(client, token_a, name="GastoA", kind="expense")
    exp_b = await _make_category(client, token_b, name="GastoB", kind="expense")

    await _make_tx(
        client, token_a, amount="100.00", occurred_at="2026-04-01T10:00:00Z",
        category_id=exp_a, description="A only",
    )
    await _make_tx(
        client, token_b, amount="999.00", occurred_at="2026-04-01T10:00:00Z",
        category_id=exp_b, description="B only",
    )

    summary_a = (await client.get("/dashboard/summary", headers=_auth(token_a))).json()
    summary_b = (await client.get("/dashboard/summary", headers=_auth(token_b))).json()
    assert summary_a["expenses"] == "100.00"
    assert summary_b["expenses"] == "999.00"

    by_cat_a = (await client.get("/dashboard/by-category", headers=_auth(token_a))).json()
    by_cat_b = (await client.get("/dashboard/by-category", headers=_auth(token_b))).json()
    names_a = {i["category_name"] for i in by_cat_a}
    names_b = {i["category_name"] for i in by_cat_b}
    assert "GastoA" in names_a and "GastoB" not in names_a
    assert "GastoB" in names_b and "GastoA" not in names_b

    top_a = (await client.get("/dashboard/top-expenses", headers=_auth(token_a))).json()
    top_b = (await client.get("/dashboard/top-expenses", headers=_auth(token_b))).json()
    assert len(top_a) == 1 and top_a[0]["description"] == "A only"
    assert len(top_b) == 1 and top_b[0]["description"] == "B only"


async def test_dashboard_requires_auth(client: AsyncClient) -> None:
    for path in ("/dashboard/summary", "/dashboard/by-category", "/dashboard/by-month", "/dashboard/top-expenses"):
        r = await client.get(path)
        assert r.status_code == 401, path
