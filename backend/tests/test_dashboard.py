"""Tests del módulo dashboard.

Cubre: agregaciones básicas, filtros por fecha/moneda, bucket "Sin
categoría", aislamiento multi-usuario, top-expenses.
"""

from __future__ import annotations

from httpx import AsyncClient


async def _register(client: AsyncClient, email: str) -> tuple[str, str]:
    """Registra un usuario y crea una cuenta, devuelve (token, account_id)."""
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    token = r.json()["access_token"]
    acc = await client.post(
        "/accounts",
        json={"name": "Cuenta principal", "type": "bank", "currency": "EUR"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, acc.json()["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _make_category(client: AsyncClient, token: str, *, name: str, kind: str) -> str:
    r = await client.post(
        "/categories",
        json={"name": name, "kind": kind},
        headers=_auth(token),
    )
    return r.json()["id"]


async def _make_tx(
    client: AsyncClient,
    token: str,
    account_id: str,
    *,
    amount: str,
    occurred_at: str,
    category_id: str | None = None,
    currency: str = "USD",
    description: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "account_id": account_id,
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
    token, _account_id = await _register(client, "dash-empty@example.com")

    r = await client.get("/dashboard/summary", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["income"] == "0"
    assert body["expenses"] == "0"
    assert body["balance"] == "0"
    assert body["transaction_count"] == 0
    assert body["currency"] == "USD"


async def test_summary_aggregates_income_expenses_and_balance(client: AsyncClient) -> None:
    token, account_id = await _register(client, "dash-sum@example.com")
    income_cat = await _make_category(client, token, name="Salario", kind="income")
    expense_cat = await _make_category(client, token, name="Comida", kind="expense")

    await _make_tx(
        client,
        token,
        account_id,
        amount="1000.00",
        occurred_at="2026-04-01T10:00:00Z",
        category_id=income_cat,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="150.50",
        occurred_at="2026-04-02T10:00:00Z",
        category_id=expense_cat,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="49.50",
        occurred_at="2026-04-03T10:00:00Z",
        category_id=expense_cat,
    )

    r = await client.get("/dashboard/summary", headers=_auth(token))
    body = r.json()
    assert body["income"] == "1000.00"
    assert body["expenses"] == "200.00"
    assert body["balance"] == "800.00"
    assert body["transaction_count"] == 3


async def test_summary_filters_by_currency(client: AsyncClient) -> None:
    token, account_id = await _register(client, "dash-cur@example.com")
    cat = await _make_category(client, token, name="Salario", kind="income")

    await _make_tx(
        client,
        token,
        account_id,
        amount="100.00",
        occurred_at="2026-04-01T10:00:00Z",
        category_id=cat,
        currency="USD",
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="200.00",
        occurred_at="2026-04-01T10:00:00Z",
        category_id=cat,
        currency="EUR",
    )

    r_usd = await client.get("/dashboard/summary", headers=_auth(token))
    r_eur = await client.get("/dashboard/summary?currency=EUR", headers=_auth(token))

    assert r_usd.json()["income"] == "100.00"
    assert r_eur.json()["income"] == "200.00"


async def test_summary_filters_by_date_range(client: AsyncClient) -> None:
    token, account_id = await _register(client, "dash-date@example.com")
    cat = await _make_category(client, token, name="Comida", kind="expense")

    await _make_tx(
        client,
        token,
        account_id,
        amount="10.00",
        occurred_at="2026-01-15T10:00:00Z",
        category_id=cat,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="20.00",
        occurred_at="2026-06-15T10:00:00Z",
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
    token, account_id = await _register(client, "dash-uncat@example.com")
    income_cat = await _make_category(client, token, name="Salario", kind="income")

    await _make_tx(
        client,
        token,
        account_id,
        amount="500.00",
        occurred_at="2026-04-01T10:00:00Z",
        category_id=income_cat,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="50.00",
        occurred_at="2026-04-02T10:00:00Z",
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
    token, account_id = await _register(client, "dash-cat@example.com")
    food = await _make_category(client, token, name="Comida", kind="expense")
    transport = await _make_category(client, token, name="Transporte", kind="expense")

    await _make_tx(
        client,
        token,
        account_id,
        amount="30.00",
        occurred_at="2026-04-01T10:00:00Z",
        category_id=food,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="20.00",
        occurred_at="2026-04-02T10:00:00Z",
        category_id=food,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="15.00",
        occurred_at="2026-04-03T10:00:00Z",
        category_id=transport,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="5.00",
        occurred_at="2026-04-04T10:00:00Z",
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
    token, account_id = await _register(client, "dash-kind@example.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")
    income = await _make_category(client, token, name="Ingreso", kind="income")

    await _make_tx(
        client,
        token,
        account_id,
        amount="10.00",
        occurred_at="2026-04-01T10:00:00Z",
        category_id=expense,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="100.00",
        occurred_at="2026-04-01T10:00:00Z",
        category_id=income,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="50.00",
        occurred_at="2026-04-01T10:00:00Z",
        category_id=None,
    )

    r = await client.get("/dashboard/by-category", params={"kind": "expense"}, headers=_auth(token))
    items = r.json()
    assert len(items) == 1
    assert items[0]["category_name"] == "Gasto"


# ---------- /dashboard/by-month ----------


async def test_by_month_returns_12_buckets_with_zero_fill(client: AsyncClient) -> None:
    token, account_id = await _register(client, "dash-month@example.com")
    income = await _make_category(client, token, name="Salario", kind="income")
    expense = await _make_category(client, token, name="Comida", kind="expense")

    await _make_tx(
        client,
        token,
        account_id,
        amount="1000.00",
        occurred_at="2026-03-15T10:00:00Z",
        category_id=income,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="200.00",
        occurred_at="2026-03-20T10:00:00Z",
        category_id=expense,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="2000.00",
        occurred_at="2026-07-15T10:00:00Z",
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
    token, account_id = await _register(client, "dash-year@example.com")
    cat = await _make_category(client, token, name="Salario", kind="income")

    await _make_tx(
        client,
        token,
        account_id,
        amount="500.00",
        occurred_at="2025-06-15T10:00:00Z",
        category_id=cat,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="1000.00",
        occurred_at="2026-06-15T10:00:00Z",
        category_id=cat,
    )

    r = await client.get("/dashboard/by-month?year=2026", headers=_auth(token))
    buckets = {b["month"]: b for b in r.json()}
    assert buckets["2026-06"]["income"] == "1000.00"


# ---------- /dashboard/top-expenses ----------


async def test_top_expenses_sorted_desc_respecting_limit(client: AsyncClient) -> None:
    token, account_id = await _register(client, "dash-top@example.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")

    amounts = ["10.00", "500.00", "50.00", "100.00", "5.00"]
    for idx, amount in enumerate(amounts):
        await _make_tx(
            client,
            token,
            account_id,
            amount=amount,
            occurred_at=f"2026-04-{10 + idx}T10:00:00Z",
            category_id=expense,
            description=f"Gasto {amount}",
        )

    r = await client.get("/dashboard/top-expenses", params={"limit": 3}, headers=_auth(token))
    items = r.json()
    assert len(items) == 3
    assert [i["amount"] for i in items] == ["500.00", "100.00", "50.00"]


async def test_top_expenses_excludes_income_and_uncategorized(client: AsyncClient) -> None:
    token, account_id = await _register(client, "dash-topx@example.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")
    income = await _make_category(client, token, name="Ingreso", kind="income")

    await _make_tx(
        client,
        token,
        account_id,
        amount="999.00",
        occurred_at="2026-04-01T10:00:00Z",
        category_id=income,
        description="Income 999 (should NOT appear)",
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="888.00",
        occurred_at="2026-04-02T10:00:00Z",
        category_id=None,
        description="Uncategorized 888 (should NOT appear)",
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="10.00",
        occurred_at="2026-04-03T10:00:00Z",
        category_id=expense,
        description="Real expense",
    )

    r = await client.get("/dashboard/top-expenses", headers=_auth(token))
    items = r.json()
    assert len(items) == 1
    assert items[0]["description"] == "Real expense"


# ---------- Isolation ----------


async def test_dashboard_user_isolation(client: AsyncClient) -> None:
    """Usuario A no ve agregados de usuario B en ningún endpoint."""
    token_a, account_a = await _register(client, "dashA@example.com")
    token_b, account_b = await _register(client, "dashB@example.com")

    exp_a = await _make_category(client, token_a, name="GastoA", kind="expense")
    exp_b = await _make_category(client, token_b, name="GastoB", kind="expense")

    await _make_tx(
        client,
        token_a,
        account_a,
        amount="100.00",
        occurred_at="2026-04-01T10:00:00Z",
        category_id=exp_a,
        description="A only",
    )
    await _make_tx(
        client,
        token_b,
        account_b,
        amount="999.00",
        occurred_at="2026-04-01T10:00:00Z",
        category_id=exp_b,
        description="B only",
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
    for path in (
        "/dashboard/summary",
        "/dashboard/by-category",
        "/dashboard/by-month",
        "/dashboard/top-expenses",
        "/dashboard/currencies",
    ):
        r = await client.get(path)
        assert r.status_code == 401, path


# ---------- /dashboard/summary previous-period ----------


async def test_summary_previous_period_null_without_date_range(
    client: AsyncClient,
) -> None:
    """Sin date_from/date_to no se calcula periodo previo."""
    token, account_id = await _register(client, "dash-prev-null@example.com")
    cat = await _make_category(client, token, name="Comida", kind="expense")
    await _make_tx(
        client,
        token,
        account_id,
        amount="10.00",
        occurred_at="2026-01-15T10:00:00Z",
        category_id=cat,
    )

    r = await client.get("/dashboard/summary", headers=_auth(token))
    body = r.json()
    assert body["previous_period_income"] is None
    assert body["previous_period_expenses"] is None
    assert body["previous_period_balance"] is None


async def test_summary_previous_period_computed_with_date_range(
    client: AsyncClient,
) -> None:
    """Con date_from y date_to se computa el rango previo de igual longitud."""
    token, account_id = await _register(client, "dash-prev-range@example.com")
    income_cat = await _make_category(client, token, name="Salario", kind="income")
    expense_cat = await _make_category(client, token, name="Comida", kind="expense")

    # Periodo actual: febrero 2026.
    await _make_tx(
        client,
        token,
        account_id,
        amount="100.00",
        occurred_at="2026-02-10T10:00:00Z",
        category_id=income_cat,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="40.00",
        occurred_at="2026-02-15T10:00:00Z",
        category_id=expense_cat,
    )

    # Periodo previo (enero 2026, longitud equivalente).
    await _make_tx(
        client,
        token,
        account_id,
        amount="80.00",
        occurred_at="2026-01-10T10:00:00Z",
        category_id=income_cat,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="30.00",
        occurred_at="2026-01-15T10:00:00Z",
        category_id=expense_cat,
    )

    r = await client.get(
        "/dashboard/summary",
        params={
            "date_from": "2026-02-01T00:00:00Z",
            "date_to": "2026-02-28T23:59:59Z",
        },
        headers=_auth(token),
    )
    body = r.json()
    assert body["income"] == "100.00"
    assert body["expenses"] == "40.00"
    assert body["balance"] == "60.00"
    assert body["previous_period_income"] == "80.00"
    assert body["previous_period_expenses"] == "30.00"
    assert body["previous_period_balance"] == "50.00"


async def test_summary_previous_period_zero_when_no_prior_data(
    client: AsyncClient,
) -> None:
    """Si no hay transacciones en el rango previo, los valores son 0 (no None)."""
    token, account_id = await _register(client, "dash-prev-zero@example.com")
    income_cat = await _make_category(client, token, name="Salario", kind="income")
    await _make_tx(
        client,
        token,
        account_id,
        amount="200.00",
        occurred_at="2026-02-10T10:00:00Z",
        category_id=income_cat,
    )

    r = await client.get(
        "/dashboard/summary",
        params={
            "date_from": "2026-02-01T00:00:00Z",
            "date_to": "2026-02-28T23:59:59Z",
        },
        headers=_auth(token),
    )
    body = r.json()
    assert body["previous_period_income"] == "0"
    assert body["previous_period_expenses"] == "0"
    assert body["previous_period_balance"] == "0"


# ---------- /dashboard/currencies ----------


async def test_currencies_returns_distinct_user_currencies(
    client: AsyncClient,
) -> None:
    token, account_id = await _register(client, "dash-curr@example.com")
    cat = await _make_category(client, token, name="Comida", kind="expense")
    await _make_tx(
        client,
        token,
        account_id,
        amount="10.00",
        currency="EUR",
        occurred_at="2026-01-15T10:00:00Z",
        category_id=cat,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="5.00",
        currency="USD",
        occurred_at="2026-01-16T10:00:00Z",
        category_id=cat,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="3.00",
        currency="EUR",
        occurred_at="2026-01-17T10:00:00Z",
        category_id=cat,
    )

    r = await client.get("/dashboard/currencies", headers=_auth(token))
    assert r.status_code == 200
    assert r.json() == ["EUR", "USD"]


async def test_currencies_empty_for_new_user(client: AsyncClient) -> None:
    token, _account_id = await _register(client, "dash-curr-empty@example.com")
    r = await client.get("/dashboard/currencies", headers=_auth(token))
    assert r.status_code == 200
    assert r.json() == []


async def test_currencies_isolated_per_user(client: AsyncClient) -> None:
    token_a, account_a = await _register(client, "dash-curr-a@example.com")
    token_b, _account_b = await _register(client, "dash-curr-b@example.com")

    cat_a = await _make_category(client, token_a, name="X", kind="expense")
    await _make_tx(
        client,
        token_a,
        account_a,
        amount="1.00",
        currency="JPY",
        occurred_at="2026-01-15T10:00:00Z",
        category_id=cat_a,
    )

    r = await client.get("/dashboard/currencies", headers=_auth(token_b))
    assert r.json() == []


# ───────────────────────────────────────────────────────────────────
# PHASE-25 — /dashboard/category/{id} drill-down
# ───────────────────────────────────────────────────────────────────


async def test_category_detail_returns_kpis_and_evolution(
    client: AsyncClient,
) -> None:
    """`GET /dashboard/category/{id}` devuelve total + count + ticket
    medio + evolución mensual + top tx."""
    token, account_id = await _register(client, "catdetail@example.com")
    cat_id = await _make_category(client, token, name="Comida", kind="expense")
    # 3 tx en el mismo mes
    await _make_tx(
        client,
        token,
        account_id,
        amount="10",
        occurred_at="2026-01-05T10:00:00Z",
        category_id=cat_id,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="20",
        occurred_at="2026-01-15T10:00:00Z",
        category_id=cat_id,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="30",
        occurred_at="2026-02-10T10:00:00Z",
        category_id=cat_id,
    )

    r = await client.get(f"/dashboard/category/{cat_id}?currency=USD", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["category_id"] == cat_id
    assert body["category_name"] == "Comida"
    assert body["category_kind"] == "expense"
    assert body["total"] == "60.00"
    assert body["count"] == 3
    assert body["average_amount"] == "20.00"
    # Evolución: 2 meses (enero y febrero)
    months = {m["month"]: m["total"] for m in body["by_month"]}
    assert months["2026-01"] == "30.00"
    assert months["2026-02"] == "30.00"
    # Top tx: 3 ordenadas desc
    tops = body["top_transactions"]
    assert len(tops) == 3
    assert tops[0]["amount"] == "30.00"
    assert tops[1]["amount"] == "20.00"
    assert tops[2]["amount"] == "10.00"


async def test_category_detail_404_when_not_owned(client: AsyncClient) -> None:
    """Aislamiento: user B no puede consultar categoría de user A."""
    token_a, _ = await _register(client, "catdetail-a@example.com")
    token_b, _ = await _register(client, "catdetail-b@example.com")
    cat_id = await _make_category(client, token_a, name="Comida", kind="expense")
    r = await client.get(f"/dashboard/category/{cat_id}?currency=USD", headers=_auth(token_b))
    assert r.status_code == 404


async def test_category_detail_filters_by_date_range(
    client: AsyncClient,
) -> None:
    """`date_from`/`date_to` afecta a `total`/`count`/`top_transactions`
    pero NO al `by_month` (que mira los últimos N meses)."""
    token, account_id = await _register(client, "catdetail-range@example.com")
    cat_id = await _make_category(client, token, name="Comida", kind="expense")
    await _make_tx(
        client,
        token,
        account_id,
        amount="50",
        occurred_at="2026-01-01T10:00:00Z",
        category_id=cat_id,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="80",
        occurred_at="2026-02-01T10:00:00Z",
        category_id=cat_id,
    )
    r = await client.get(
        f"/dashboard/category/{cat_id}?currency=USD" "&date_from=2026-02-01T00:00:00Z",
        headers=_auth(token),
    )
    body = r.json()
    assert body["total"] == "80.00"
    assert body["count"] == 1
    # by_month sigue mostrando ambos meses (ignora date_from)
    months = {m["month"] for m in body["by_month"]}
    assert "2026-01" in months
    assert "2026-02" in months


async def test_category_detail_zero_count_when_no_tx(
    client: AsyncClient,
) -> None:
    """Categoría sin tx: total=0, count=0, average=0, listas vacías."""
    token, _account_id = await _register(client, "catdetail-empty@example.com")
    cat_id = await _make_category(client, token, name="Vacía", kind="expense")
    r = await client.get(f"/dashboard/category/{cat_id}?currency=USD", headers=_auth(token))
    body = r.json()
    assert body["total"] == "0.00"
    assert body["count"] == 0
    assert body["average_amount"] == "0.00"
    assert body["by_month"] == []
    assert body["top_transactions"] == []
