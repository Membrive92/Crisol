"""Tests del modo cross-currency del dashboard (PHASE-8.3).

Cubre la conversión per-transaction usando la tasa del día de cada
transacción. Las tasas se siembran directamente en `exchange_rates`
para no depender de frankfurter en CI.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.currency import repository as rates_repository
from app.modules.currency.exceptions import FrankfurterUnavailableError


async def _register(client: AsyncClient, email: str) -> tuple[str, str]:
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
    currency: str,
    category_id: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "account_id": account_id,
        "amount": amount,
        "currency": currency,
        "occurred_at": occurred_at,
    }
    if category_id is not None:
        payload["category_id"] = category_id
    r = await client.post("/transactions", json=payload, headers=_auth(token))
    assert r.status_code == 201, r.text


async def _seed_rates(test_engine, rows: list[tuple[date, str, str, str]]) -> None:  # type: ignore[no-untyped-def]
    """rows: list of (rate_date, base, quote, rate_string)."""
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    async with factory() as db:
        await rates_repository.upsert_rates(
            db,
            [(d, base, quote, Decimal(rate), "test") for d, base, quote, rate in rows],
        )
        await db.commit()


import pytest_asyncio  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _mock_frankfurter():
    """Bloquea el fetch real a frankfurter para todos los tests de
    este módulo. El dashboard service llama a `ensure_rates_for_dates`
    que dispara `client.fetch_rates`; si no lo mockeamos, la suite
    depende de la red y de la fecha real del CI. Los seeds explícitos
    siguen siendo la única fuente de tasas en estos tests.
    """
    with patch(
        "app.modules.currency.client.fetch_rates",
        new_callable=AsyncMock,
        side_effect=FrankfurterUnavailableError("test offline"),
    ):
        yield


# ---------- summary ----------


async def test_summary_target_currency_converts_each_tx_with_its_date_rate(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
) -> None:
    """27,66€ del 19-feb + 2 USD del 03-may → convertir cada uno con su tasa."""
    token, account_id = await _register(client, "tgt@test.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")

    await _make_tx(
        client,
        token,
        account_id,
        amount="27.66",
        currency="EUR",
        occurred_at="2026-02-19T12:00:00Z",
        category_id=expense,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="2.00",
        currency="USD",
        occurred_at="2026-05-03T02:00:00Z",
        category_id=expense,
    )

    # Tasas: el 19-feb EUR/USD valía 1.05; el 3-may, 1.17.
    await _seed_rates(
        test_engine,
        [
            (date(2026, 2, 19), "EUR", "USD", "1.05"),
            (date(2026, 5, 3), "EUR", "USD", "1.17"),
        ],
    )

    r = await client.get(
        "/dashboard/summary",
        params={"target_currency": "USD"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    data = r.json()
    # 27.66 EUR → 29.043 USD (x1.05) + 2.00 USD = 31.04 USD (banker)
    # No estamos usando ROUND_HALF_EVEN aquí porque la query SUM
    # devuelve full-precision Decimal y Pydantic lo serializa.
    assert Decimal(data["expenses"]) == Decimal("31.0430000000")
    assert data["currency"] == "USD"
    assert data["transaction_count"] == 2
    assert data["unconvertible_count"] == 0


async def test_summary_target_currency_to_eur_uses_inverse_rate(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
) -> None:
    """target=EUR sobre una transacción USD: divide por la tasa EUR→USD."""
    token, account_id = await _register(client, "tgteur@test.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")

    await _make_tx(
        client,
        token,
        account_id,
        amount="100",
        currency="USD",
        occurred_at="2026-02-19T12:00:00Z",
        category_id=expense,
    )
    await _seed_rates(
        test_engine,
        [(date(2026, 2, 19), "EUR", "USD", "1.25")],
    )

    r = await client.get(
        "/dashboard/summary",
        params={"target_currency": "EUR"},
        headers=_auth(token),
    )
    data = r.json()
    # 100 USD ÷ 1.25 = 80 EUR
    assert Decimal(data["expenses"]) == Decimal("80.00000000")
    assert data["currency"] == "EUR"


async def test_summary_target_currency_uses_previous_within_window(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
) -> None:
    """Si no hay tasa exacta, usa la última anterior dentro de 14 días."""
    token, account_id = await _register(client, "win@test.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")

    # Transacción el 13-mar; tasa más cercana es del 6-mar (7 días antes).
    await _make_tx(
        client,
        token,
        account_id,
        amount="100",
        currency="EUR",
        occurred_at="2026-03-13T12:00:00Z",
        category_id=expense,
    )
    await _seed_rates(
        test_engine,
        [(date(2026, 3, 6), "EUR", "USD", "1.10")],
    )

    r = await client.get(
        "/dashboard/summary",
        params={"target_currency": "USD"},
        headers=_auth(token),
    )
    data = r.json()
    # 100 EUR x 1.10 = 110 USD usando la tasa del 6-mar
    assert Decimal(data["expenses"]) == Decimal("110.00000000")
    assert data["unconvertible_count"] == 0


async def test_summary_target_currency_excludes_unconvertible_outside_window(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
) -> None:
    """Tasa más antigua que 14 días → transacción no se incluye en SUM."""
    token, account_id = await _register(client, "out@test.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")

    await _make_tx(
        client,
        token,
        account_id,
        amount="100",
        currency="EUR",
        occurred_at="2026-03-30T12:00:00Z",
        category_id=expense,
    )
    # Tasa del 1-mar: 29 días antes → fuera de la ventana.
    await _seed_rates(
        test_engine,
        [(date(2026, 3, 1), "EUR", "USD", "1.10")],
    )

    r = await client.get(
        "/dashboard/summary",
        params={"target_currency": "USD"},
        headers=_auth(token),
    )
    data = r.json()
    # La transacción se excluyó del total convertido.
    assert Decimal(data["expenses"]) == Decimal("0")
    assert data["transaction_count"] == 1
    assert data["unconvertible_count"] == 1


async def test_summary_target_currency_skips_conversion_when_currency_matches(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
) -> None:
    """Transacciones ya en target no necesitan tasa."""
    token, account_id = await _register(client, "skip@test.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")
    await _make_tx(
        client,
        token,
        account_id,
        amount="100",
        currency="USD",
        occurred_at="2026-02-19T12:00:00Z",
        category_id=expense,
    )
    # No sembramos tasas — la transacción está en USD, no necesita conversión.

    r = await client.get(
        "/dashboard/summary",
        params={"target_currency": "USD"},
        headers=_auth(token),
    )
    data = r.json()
    assert Decimal(data["expenses"]) == Decimal("100")
    assert data["unconvertible_count"] == 0


# ---------- by-month ----------


async def test_by_month_target_currency_aggregates_per_month(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
) -> None:
    """Cada mes agrega sus transacciones convertidas con la tasa del día."""
    token, account_id = await _register(client, "month@test.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")

    # Febrero: 1 transacción 100 EUR a tasa 1.10 → 110 USD
    await _make_tx(
        client,
        token,
        account_id,
        amount="100",
        currency="EUR",
        occurred_at="2026-02-15T12:00:00Z",
        category_id=expense,
    )
    # Marzo: 1 transacción 100 EUR a tasa 1.20 → 120 USD
    await _make_tx(
        client,
        token,
        account_id,
        amount="100",
        currency="EUR",
        occurred_at="2026-03-15T12:00:00Z",
        category_id=expense,
    )
    await _seed_rates(
        test_engine,
        [
            (date(2026, 2, 15), "EUR", "USD", "1.10"),
            (date(2026, 3, 15), "EUR", "USD", "1.20"),
        ],
    )

    r = await client.get(
        "/dashboard/by-month",
        params={"target_currency": "USD", "year": 2026},
        headers=_auth(token),
    )
    data = r.json()
    feb = next(b for b in data if b["month"] == "2026-02")
    mar = next(b for b in data if b["month"] == "2026-03")
    assert Decimal(feb["expenses"]) == Decimal("110.00000000")
    assert Decimal(mar["expenses"]) == Decimal("120.00000000")


# ---------- by-category ----------


async def test_by_category_target_currency_sums_converted(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
) -> None:
    """Una categoría con transacciones en monedas distintas: conversión per-tx."""
    token, account_id = await _register(client, "cat@test.com")
    cat = await _make_category(client, token, name="Comida", kind="expense")

    await _make_tx(
        client,
        token,
        account_id,
        amount="100",
        currency="EUR",
        occurred_at="2026-02-19T12:00:00Z",
        category_id=cat,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="50",
        currency="USD",
        occurred_at="2026-05-03T12:00:00Z",
        category_id=cat,
    )
    await _seed_rates(
        test_engine,
        [
            (date(2026, 2, 19), "EUR", "USD", "1.10"),
            (date(2026, 5, 3), "EUR", "USD", "1.17"),
        ],
    )

    r = await client.get(
        "/dashboard/by-category",
        params={"target_currency": "USD", "kind": "expense"},
        headers=_auth(token),
    )
    data = r.json()
    comida = next(b for b in data if b["category_name"] == "Comida")
    # 100 EUR x 1.10 + 50 USD = 110 + 50 = 160 USD
    assert Decimal(comida["total"]) == Decimal("160.00000000")
    assert comida["count"] == 2


# ---------- top-expenses ----------


async def test_top_expenses_target_currency_sorts_by_converted(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
) -> None:
    """100 EUR (x1.20 = 120 USD) > 110 USD pese a que el USD nominal es mayor."""
    token, account_id = await _register(client, "top@test.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")

    await _make_tx(
        client,
        token,
        account_id,
        amount="110",
        currency="USD",
        occurred_at="2026-02-15T12:00:00Z",
        category_id=expense,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="100",
        currency="EUR",
        occurred_at="2026-02-15T12:00:00Z",
        category_id=expense,
    )
    await _seed_rates(
        test_engine,
        [(date(2026, 2, 15), "EUR", "USD", "1.20")],
    )

    r = await client.get(
        "/dashboard/top-expenses",
        params={"target_currency": "USD", "limit": 10},
        headers=_auth(token),
    )
    items = r.json()
    assert len(items) == 2
    # El primero es el EUR (120 USD convertido), no el USD (110 nominal).
    assert Decimal(items[0]["amount"]) == Decimal("120.00000000")
    assert Decimal(items[1]["amount"]) == Decimal("110.00000000")


# ---------- legacy mode coexistence ----------


async def test_legacy_currency_mode_unchanged(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
) -> None:
    """`?currency=EUR` mantiene comportamiento pre-PHASE-8.3."""
    token, account_id = await _register(client, "legacy@test.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")
    await _make_tx(
        client,
        token,
        account_id,
        amount="100",
        currency="EUR",
        occurred_at="2026-02-19T12:00:00Z",
        category_id=expense,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="50",
        currency="USD",
        occurred_at="2026-02-19T12:00:00Z",
        category_id=expense,
    )

    r = await client.get(
        "/dashboard/summary",
        params={"currency": "EUR"},
        headers=_auth(token),
    )
    data = r.json()
    # Solo cuenta EUR — la USD se filtra fuera. Sin conversión, sin
    # `unconvertible_count`.
    assert Decimal(data["expenses"]) == Decimal("100")
    assert data["currency"] == "EUR"
    assert data["unconvertible_count"] == 0
    # transaction_count cuenta TODAS las del scope (filtradas por moneda).
    assert data["transaction_count"] == 1


# ---------- top-expenses: original_amount/original_currency (PHASE-8.4) ----------


async def test_top_expenses_target_currency_exposes_original(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
) -> None:
    """top-expenses devuelve `amount` (convertido) + `original_amount`/`original_currency`."""
    token, account_id = await _register(client, "topog@test.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")

    await _make_tx(
        client,
        token,
        account_id,
        amount="100",
        currency="EUR",
        occurred_at="2026-02-15T12:00:00Z",
        category_id=expense,
    )
    await _seed_rates(
        test_engine,
        [(date(2026, 2, 15), "EUR", "USD", "1.20")],
    )

    r = await client.get(
        "/dashboard/top-expenses",
        params={"target_currency": "USD", "limit": 10},
        headers=_auth(token),
    )
    items = r.json()
    assert len(items) == 1
    item = items[0]
    assert Decimal(item["amount"]) == Decimal("120.00000000")  # convertido
    assert Decimal(item["original_amount"]) == Decimal("100.00")
    assert item["original_currency"] == "EUR"


async def test_top_expenses_legacy_original_equals_amount(
    client: AsyncClient,
) -> None:
    """En modo legacy, original_amount/currency coinciden con amount/currency activos."""
    token, account_id = await _register(client, "topleg@test.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")
    await _make_tx(
        client,
        token,
        account_id,
        amount="42.50",
        currency="EUR",
        occurred_at="2026-02-15T12:00:00Z",
        category_id=expense,
    )

    r = await client.get(
        "/dashboard/top-expenses",
        params={"currency": "EUR", "limit": 10},
        headers=_auth(token),
    )
    items = r.json()
    assert len(items) == 1
    assert Decimal(items[0]["amount"]) == Decimal("42.50")
    assert Decimal(items[0]["original_amount"]) == Decimal("42.50")
    assert items[0]["original_currency"] == "EUR"


# ---------- /transactions con target_currency (PHASE-8.4) ----------


async def test_transactions_target_currency_returns_converted_per_row(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
) -> None:
    """/transactions?target_currency=USD añade converted_amount + converted_currency por fila."""
    token, account_id = await _register(client, "txconv@test.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")

    await _make_tx(
        client,
        token,
        account_id,
        amount="100",
        currency="EUR",
        occurred_at="2026-02-15T12:00:00Z",
        category_id=expense,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="50",
        currency="EUR",
        occurred_at="2026-03-15T12:00:00Z",
        category_id=expense,
    )
    await _seed_rates(
        test_engine,
        [
            (date(2026, 2, 15), "EUR", "USD", "1.10"),
            (date(2026, 3, 15), "EUR", "USD", "1.20"),
        ],
    )

    r = await client.get(
        "/transactions",
        params={"target_currency": "USD"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    # Orden: descendente por occurred_at → primero la del 15-mar.
    first, second = body["items"][0], body["items"][1]
    assert first["currency"] == "EUR"
    assert first["converted_currency"] == "USD"
    assert Decimal(first["converted_amount"]) == Decimal("60.00000000")  # 50 x 1.20
    assert Decimal(second["converted_amount"]) == Decimal("110.00000000")  # 100 x 1.10


async def test_transactions_legacy_mode_converted_fields_null(
    client: AsyncClient,
) -> None:
    """Sin target_currency, converted_amount y converted_currency vienen como null."""
    token, account_id = await _register(client, "txleg@test.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")
    await _make_tx(
        client,
        token,
        account_id,
        amount="25",
        currency="EUR",
        occurred_at="2026-02-15T12:00:00Z",
        category_id=expense,
    )

    r = await client.get("/transactions", headers=_auth(token))
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["converted_amount"] is None
    assert item["converted_currency"] is None


async def test_transactions_target_currency_missing_rate_yields_null_converted(
    client: AsyncClient,
) -> None:
    """Una fila sin tasa disponible devuelve converted_amount=null pero sigue listada."""
    token, account_id = await _register(client, "txmiss@test.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")
    # Sin sembrar tasas — frankfurter está mockeado a offline (autouse).
    await _make_tx(
        client,
        token,
        account_id,
        amount="100",
        currency="EUR",
        occurred_at="2026-02-15T12:00:00Z",
        category_id=expense,
    )

    r = await client.get(
        "/transactions",
        params={"target_currency": "USD"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["currency"] == "EUR"
    # converted_amount es null cuando la subquery de la tasa devuelve NULL.
    assert item["converted_amount"] is None


async def test_transactions_target_currency_matches_skips_conversion(
    client: AsyncClient,
) -> None:
    """Tx ya en target → converted_amount == amount sin necesitar tasa."""
    token, account_id = await _register(client, "txmatch@test.com")
    expense = await _make_category(client, token, name="Gasto", kind="expense")
    await _make_tx(
        client,
        token,
        account_id,
        amount="42",
        currency="USD",
        occurred_at="2026-02-15T12:00:00Z",
        category_id=expense,
    )

    r = await client.get(
        "/transactions",
        params={"target_currency": "USD"},
        headers=_auth(token),
    )
    item = r.json()["items"][0]
    assert item["currency"] == "USD"
    assert item["converted_currency"] == "USD"
    assert Decimal(item["converted_amount"]) == Decimal("42.00")
