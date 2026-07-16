"""Tests del endpoint Capa 1 (`/debt/category-summary`) — PHASE-30.2."""

from __future__ import annotations

from datetime import UTC, datetime
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


async def _create_account(client: AsyncClient, token: str, **fields: object) -> dict:
    r = await client.post("/accounts", json=fields, headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()


async def _create_category(
    client: AsyncClient,
    token: str,
    name: str,
    kind: str = "expense",
    role: str = "GENERIC",
) -> str:
    r = await client.post(
        "/categories",
        json={"name": name, "kind": kind, "role": role},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _post_tx(
    client: AsyncClient,
    token: str,
    account_id: str,
    category_id: str,
    amount: str,
    occurred_at: str,
    description: str = "",
    currency: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "account_id": account_id,
        "category_id": category_id,
        "amount": amount,
        "occurred_at": occurred_at,
        "description": description,
    }
    if currency is not None:
        payload["currency"] = currency
    r = await client.post(
        "/transactions",
        json=payload,
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text


# ─────────────────────────────────────────────────────────────────────


async def test_summary_empty_user_returns_zeros(client: AsyncClient) -> None:
    """Usuario sin movimientos: KPIs en 0 y series vacías-coherentes."""
    token = await _register(client, "summary_empty@example.com")
    r = await client.get("/debt/category-summary", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert Decimal(body["total_payments"]) == Decimal("0")
    assert Decimal(body["capital_amortized"]) == Decimal("0")
    assert Decimal(body["interests_and_fees"]) == Decimal("0")
    assert body["by_type"] == []
    assert body["effort_ratio_strict"] is None
    assert body["effort_ratio_strict_status"] == "unknown"
    assert body["effort_ratio_extended"] is None
    assert body["recurring_quotas"] == []


async def test_summary_aggregates_debt_payments_and_interests(
    client: AsyncClient,
) -> None:
    """Pagos de hipoteca (DEBT_PAYMENT) + intereses (DEBT_INTEREST)
    se separan correctamente y by_type clasifica por nombre."""
    token = await _register(client, "summary_basic@example.com")
    cte = await _create_account(
        client,
        token,
        name="Cte",
        type="bank",
        currency="EUR",
        opening_balance="5000",
    )
    cap_id = await _create_category(client, token, "Préstamos e hipotecas", role="DEBT_PAYMENT")
    int_id = await _create_category(client, token, "Intereses hipoteca", role="DEBT_INTEREST")
    year = datetime.now(UTC).year
    await _post_tx(client, token, cte["id"], cap_id, "800.00", f"{year}-03-01T12:00:00Z")
    await _post_tx(client, token, cte["id"], int_id, "200.00", f"{year}-03-01T12:00:00Z")

    r = await client.get("/debt/category-summary?range=year", headers=_auth(token))
    body = r.json()
    assert Decimal(body["total_payments"]) == Decimal("1000.00")
    assert Decimal(body["capital_amortized"]) == Decimal("800.00")
    assert Decimal(body["interests_and_fees"]) == Decimal("200.00")
    # PHASE-30.7: "Préstamos e hipotecas" cae en LOAN (loan-first
    # precedence). "Intereses hipoteca" cae en MORTGAGE (sólo
    # contiene "hipoteca"). Total combinado = 1000.
    by_type_map = {b["type"]: Decimal(b["amount"]) for b in body["by_type"]}
    assert by_type_map.get("loan", Decimal("0")) == Decimal("800.00")
    assert by_type_map.get("mortgage", Decimal("0")) == Decimal("200.00")


async def test_summary_by_type_classifies_by_name(client: AsyncClient) -> None:
    """Hipoteca explícita / Préstamo / Tarjeta caen en buckets
    distintos por nombre con loan-first precedence.

    PHASE-30.7 — "Hipoteca BBVA" cae en mortgage porque NO contiene
    "préstamo". "Préstamos e hipotecas" caería en loan (ver test
    dedicado). "Préstamo coche" → loan. "Tarjeta de crédito" → card.
    """
    token = await _register(client, "summary_by_type@example.com")
    cte = await _create_account(
        client,
        token,
        name="Cte",
        type="bank",
        currency="EUR",
        opening_balance="5000",
    )
    mortgage_id = await _create_category(client, token, "Hipoteca BBVA", role="DEBT_PAYMENT")
    loan_id = await _create_category(client, token, "Préstamo coche", role="DEBT_PAYMENT")
    card_id = await _create_category(client, token, "Tarjeta de crédito", role="DEBT_PAYMENT")
    year = datetime.now(UTC).year
    await _post_tx(client, token, cte["id"], mortgage_id, "500", f"{year}-03-01T00:00:00Z")
    await _post_tx(client, token, cte["id"], loan_id, "300", f"{year}-03-01T00:00:00Z")
    await _post_tx(client, token, cte["id"], card_id, "200", f"{year}-03-01T00:00:00Z")

    r = await client.get("/debt/category-summary?range=year", headers=_auth(token))
    body = r.json()
    by_type_map = {b["type"]: Decimal(b["amount"]) for b in body["by_type"]}
    assert by_type_map["mortgage"] == Decimal("500.00")
    assert by_type_map["loan"] == Decimal("300.00")
    assert by_type_map["credit_card"] == Decimal("200.00")


async def test_summary_prestamos_hipotecas_seed_classified_as_loan(
    client: AsyncClient,
) -> None:
    """PHASE-30.7 regresión: la categoría seed "Préstamos e
    hipotecas" debe caer en LOAN (no mortgage) porque la mayoría
    de usuarios sin hipoteca real la usan para préstamos.
    """
    token = await _register(client, "summary_seed_loan@example.com")
    cte = await _create_account(
        client,
        token,
        name="Cte",
        type="bank",
        currency="EUR",
        opening_balance="5000",
    )
    seed_id = await _create_category(client, token, "Préstamos e hipotecas", role="DEBT_PAYMENT")
    year = datetime.now(UTC).year
    await _post_tx(client, token, cte["id"], seed_id, "500", f"{year}-03-01T00:00:00Z")
    r = await client.get("/debt/category-summary?range=year", headers=_auth(token))
    body = r.json()
    by_type_map = {b["type"]: Decimal(b["amount"]) for b in body["by_type"]}
    assert by_type_map.get("loan", Decimal("0")) == Decimal("500.00")
    assert "mortgage" not in by_type_map


async def test_summary_linked_account_type_overrides_name_match(
    client: AsyncClient,
) -> None:
    """PHASE-30.7 — Si la categoría está vinculada a una mortgage
    (account.type), debe caer en MORTGAGE aunque su nombre matchee
    'préstamo' (la cuenta vinculada gana sobre el matching de
    nombre)."""
    token = await _register(client, "summary_linked@example.com")
    cte = await _create_account(
        client,
        token,
        name="Cte",
        type="bank",
        currency="EUR",
        opening_balance="5000",
    )
    cat_id = await _create_category(client, token, "Préstamo BBVA largo plazo", role="DEBT_PAYMENT")
    # Vincula esa categoría a una hipoteca declarada.
    await _create_account(
        client,
        token,
        name="Hipoteca BBVA",
        type="mortgage",
        currency="EUR",
        opening_balance="180000",
        apr="0.035",
        term_months=240,
        start_date="2026-01-01",
        category_id=cat_id,
    )
    year = datetime.now(UTC).year
    await _post_tx(client, token, cte["id"], cat_id, "750", f"{year}-03-01T00:00:00Z")
    r = await client.get("/debt/category-summary?range=year", headers=_auth(token))
    body = r.json()
    by_type_map = {b["type"]: Decimal(b["amount"]) for b in body["by_type"]}
    # Nombre matchearía "préstamo" → loan; cuenta vinculada es
    # mortgage → debe ganar la cuenta.
    assert by_type_map.get("mortgage", Decimal("0")) == Decimal("750.00")
    assert "loan" not in by_type_map


async def test_summary_year_returns_ytd_buckets(client: AsyncClient) -> None:
    """`range=year` devuelve `today.month` puntos (enero..mes actual)."""
    token = await _register(client, "summary_year@example.com")
    cte = await _create_account(
        client,
        token,
        name="Cte",
        type="bank",
        currency="EUR",
        opening_balance="5000",
    )
    cap_id = await _create_category(client, token, "Préstamos e hipotecas", role="DEBT_PAYMENT")
    today = datetime.now(UTC)
    await _post_tx(
        client,
        token,
        cte["id"],
        cap_id,
        "100.00",
        f"{today.year:04d}-{today.month:02d}-01T12:00:00Z",
    )
    r = await client.get("/debt/category-summary?range=year", headers=_auth(token))
    body = r.json()
    assert len(body["monthly_series"]) == today.month
    assert body["monthly_series"][-1]["month"] == f"{today.year:04d}-{today.month:02d}"


async def _insert_fixed_expense(
    test_engine,  # type: ignore[no-untyped-def]
    *,
    user_id,  # type: ignore[no-untyped-def]
    merchant: str,
    amount: Decimal,
    category_id,  # type: ignore[no-untyped-def]
    currency: str = "EUR",
    cadence_days: int = 30,
) -> None:
    from datetime import date as _date

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.modules.personal_finance.fixed_expenses.models import (
        FixedExpense,
        FixedExpenseStatus,
    )

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    today = _date.today()
    async with factory() as session:
        session.add(
            FixedExpense(
                user_id=user_id,
                merchant=merchant,
                raw_description=merchant,
                amount=amount,
                currency=currency,
                cadence_days=cadence_days,
                next_due=today,
                status=FixedExpenseStatus.CONFIRMED,
                category_id=category_id,
                first_seen_at=today,
                last_seen_at=today,
                occurrence_count=6,
                confidence=0.99,
            )
        )
        await session.commit()


async def _fetch_user_and_category_ids(
    test_engine,  # type: ignore[no-untyped-def]
    email: str,
    category_name: str,
):  # type: ignore[no-untyped-def]
    from sqlalchemy import select as _sa_select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.modules.personal_finance.categories.models import Category
    from app.modules.users.models import User

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        user = (await session.execute(_sa_select(User).where(User.email == email))).scalar_one()
        cat = (
            await session.execute(
                _sa_select(Category)
                .where(Category.user_id == user.id)
                .where(Category.name == category_name)
            )
        ).scalar_one()
        return user.id, cat.id


async def test_effort_ratio_strict_uses_avg_payments_over_income(
    client: AsyncClient,
) -> None:
    """`effort_ratio_strict` = avg(debt_payments_per_month) / monthly_income."""
    token = await _register(client, "summary_effort@example.com")
    cte = await _create_account(
        client,
        token,
        name="Cte",
        type="bank",
        currency="EUR",
        opening_balance="5000",
    )
    cap_id = await _create_category(client, token, "Préstamos e hipotecas", role="DEBT_PAYMENT")
    salary_id = await _create_category(client, token, "Salario", kind="income")

    # 6 meses cerrados de ingreso (2000/mes) + 6 meses cerrados de
    # pago de deuda (500/mes). El cálculo del income usa los 6 meses
    # completos previos al actual.
    today = datetime.now(UTC).date()
    from datetime import timedelta as _td

    last_full_end = today.replace(day=1) - _td(days=1)
    # Generamos 6 meses cerrados retrocediendo desde el último mes
    # completo.
    cursor = last_full_end
    for _ in range(6):
        month_first = cursor.replace(day=1)
        iso = f"{month_first.year:04d}-{month_first.month:02d}-15T12:00:00Z"
        await _post_tx(client, token, cte["id"], salary_id, "2000.00", iso)
        await _post_tx(client, token, cte["id"], cap_id, "500.00", iso)
        cursor = month_first - _td(days=1)

    r = await client.get("/debt/category-summary?range=year", headers=_auth(token))
    body = r.json()
    # Esperamos ratio ≈ 500 / 2000 = 0.25 → healthy (< 0.30)
    assert body["effort_ratio_strict"] is not None
    assert 0.20 < body["effort_ratio_strict"] < 0.30
    assert body["effort_ratio_strict_status"] == "healthy"


async def test_effort_extended_includes_non_debt_fixed_expenses(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
) -> None:
    """`effort_ratio_extended` añade fixed_expenses confirmados que NO
    son de deuda; el ratio sube respecto al strict."""
    token = await _register(client, "summary_extended@example.com")
    cte = await _create_account(
        client,
        token,
        name="Cte",
        type="bank",
        currency="EUR",
        opening_balance="5000",
    )
    salary_id = await _create_category(client, token, "Salario", kind="income")
    cap_id = await _create_category(client, token, "Préstamos e hipotecas", role="DEBT_PAYMENT")

    today = datetime.now(UTC).date()
    from datetime import timedelta as _td

    last_full_end = today.replace(day=1) - _td(days=1)
    cursor = last_full_end
    for _ in range(6):
        month_first = cursor.replace(day=1)
        iso = f"{month_first.year:04d}-{month_first.month:02d}-15T12:00:00Z"
        await _post_tx(client, token, cte["id"], salary_id, "2000.00", iso)
        await _post_tx(client, token, cte["id"], cap_id, "500.00", iso)
        cursor = month_first - _td(days=1)

    # Confirma un fixed expense mensual de 200€ con categoría no-debt.
    # El cron de detección no se ejecuta en test, lo creamos directamente.
    await _create_category(client, token, "Netflix", kind="expense")
    user_id, netflix_id = await _fetch_user_and_category_ids(
        test_engine, "summary_extended@example.com", "Netflix"
    )
    await _insert_fixed_expense(
        test_engine,
        user_id=user_id,
        merchant="NETFLIX",
        amount=Decimal("200.00"),
        category_id=netflix_id,
    )

    r = await client.get("/debt/category-summary?range=year", headers=_auth(token))
    body = r.json()
    # Strict ≈ 500/2000 = 0.25; extended ≈ (500+200)/2000 = 0.35
    assert body["effort_ratio_strict"] is not None
    assert body["effort_ratio_extended"] is not None
    assert body["effort_ratio_extended"] > body["effort_ratio_strict"]
    # 0.35 → frontera caution; el status puede ser "caution" o "healthy"
    # dependiendo del redondeo. Sólo aseguramos que NO es stressed.
    assert body["effort_ratio_extended_status"] in {"healthy", "caution"}


async def test_recurring_quotas_lists_only_debt_categories(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
) -> None:
    """`recurring_quotas` sólo incluye fixed_expenses con categoría de
    deuda — excluye Netflix y compañía."""
    token = await _register(client, "summary_recurring@example.com")
    await _create_category(client, token, "Hipoteca", kind="expense", role="DEBT_PAYMENT")
    await _create_category(client, token, "Netflix", kind="expense")

    user_id, hipoteca_id = await _fetch_user_and_category_ids(
        test_engine, "summary_recurring@example.com", "Hipoteca"
    )
    _, netflix_id = await _fetch_user_and_category_ids(
        test_engine, "summary_recurring@example.com", "Netflix"
    )
    await _insert_fixed_expense(
        test_engine,
        user_id=user_id,
        merchant="BBVA HIPOTECA",
        amount=Decimal("850.00"),
        category_id=hipoteca_id,
    )
    await _insert_fixed_expense(
        test_engine,
        user_id=user_id,
        merchant="NETFLIX",
        amount=Decimal("15.00"),
        category_id=netflix_id,
    )

    r = await client.get("/debt/category-summary?range=year", headers=_auth(token))
    body = r.json()
    assert len(body["recurring_quotas"]) == 1
    assert body["recurring_quotas"][0]["merchant"] == "BBVA HIPOTECA"


async def test_classify_effort_bands(client: AsyncClient) -> None:
    """Bandas BdE 30/35% (sin red): 0.28 healthy, 0.32 caution, 0.40 stressed."""
    from app.modules.personal_finance.accounts.debt_health import classify_effort

    assert classify_effort(None) == "unknown"
    assert classify_effort(0.0) == "healthy"
    assert classify_effort(0.28) == "healthy"
    assert classify_effort(0.30) == "caution"
    assert classify_effort(0.32) == "caution"
    assert classify_effort(0.35) == "caution"
    assert classify_effort(0.36) == "stressed"
    assert classify_effort(0.40) == "stressed"


# ─────────────────────────────────────────────────────────────────────
# PHASE-30.6 — Cross-currency (target_currency)
# ─────────────────────────────────────────────────────────────────────


async def _seed_rates(test_engine, rows):  # type: ignore[no-untyped-def]
    """Helper duplicado de `test_dashboard_cross_currency` para no
    crear cross-imports entre suites de test."""
    from decimal import Decimal as _Dec

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.modules.currency import repository as rates_repository

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    async with factory() as db:
        await rates_repository.upsert_rates(
            db,
            [(d, base, quote, _Dec(rate), "test") for d, base, quote, rate in rows],
        )
        await db.commit()


async def test_summary_target_currency_returns_target_in_reference(
    client: AsyncClient,
) -> None:
    """`?target_currency=USD` → reference_currency en la respuesta = USD."""
    token = await _register(client, "summary_tc_ref@example.com")
    r = await client.get("/debt/category-summary?target_currency=USD", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["reference_currency"] == "USD"


async def test_summary_target_currency_converts_per_tx(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
) -> None:
    """Sembrado EUR→USD 1.1 + EUR→GBP 0.8 a una fecha conocida. Pago de
    100 EUR + 50 GBP a esa fecha → con target=USD esperamos
    `100 * 1.1 + 50 * (1.1 / 0.8) = 110 + 68.75 = 178.75`."""
    from datetime import UTC, datetime
    from datetime import date as _date

    token = await _register(client, "summary_tc_convert@example.com")
    eur_cte = await _create_account(
        client,
        token,
        name="EUR",
        type="bank",
        currency="EUR",
        opening_balance="5000",
    )
    gbp_cte = await _create_account(
        client,
        token,
        name="GBP",
        type="bank",
        currency="GBP",
        opening_balance="5000",
    )
    debt_cat = await _create_category(client, token, "Préstamos e hipotecas", role="DEBT_PAYMENT")

    seed_day = _date(datetime.now(UTC).year, 3, 15)
    iso = f"{seed_day.isoformat()}T12:00:00Z"
    await _seed_rates(
        test_engine,
        [
            (seed_day, "EUR", "USD", "1.1"),
            (seed_day, "EUR", "GBP", "0.8"),
        ],
    )

    await _post_tx(
        client,
        token,
        eur_cte["id"],
        debt_cat,
        "100.00",
        iso,
        currency="EUR",
    )
    await _post_tx(
        client,
        token,
        gbp_cte["id"],
        debt_cat,
        "50.00",
        iso,
        currency="GBP",
    )

    r = await client.get(
        "/debt/category-summary?range=year&target_currency=USD",
        headers=_auth(token),
    )
    body = r.json()
    assert body["reference_currency"] == "USD"
    # 100 EUR @ 1.1 + 50 GBP @ (1.1/0.8)
    total = Decimal(body["total_payments"])
    assert Decimal("178.50") <= total <= Decimal("179.00"), f"got {total}"


async def test_summary_native_mode_unchanged(client: AsyncClient) -> None:
    """Sin `target_currency` la respuesta sigue siendo la moneda nativa
    (regresión: el campo añadido no debería cambiar el contrato previo)."""
    token = await _register(client, "summary_native@example.com")
    cte = await _create_account(
        client,
        token,
        name="EUR",
        type="bank",
        currency="EUR",
        opening_balance="100",
    )
    cat = await _create_category(client, token, "Préstamos e hipotecas", role="DEBT_PAYMENT")
    year = datetime.now(UTC).year
    await _post_tx(client, token, cte["id"], cat, "200.00", f"{year}-03-01T12:00:00Z")
    r = await client.get("/debt/category-summary?range=year", headers=_auth(token))
    body = r.json()
    assert body["reference_currency"] == "EUR"
    assert Decimal(body["total_payments"]) == Decimal("200.00")


async def test_debt_health_target_currency_converts_balances(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
) -> None:
    """Una hipoteca EUR de 100k con `target=USD` y tasa EUR→USD=1.1
    debe reportar `total_liabilities ≈ 110000` y reference_currency=USD."""
    token = await _register(client, "health_tc_balance@example.com")
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
    from datetime import date as _date

    await _seed_rates(test_engine, [(_date.today(), "EUR", "USD", "1.10")])

    r = await client.get("/accounts/debt-health?target_currency=USD", headers=_auth(token))
    body = r.json()
    assert body["reference_currency"] == "USD"
    # 100000 EUR × 1.10 = 110000 USD
    assert Decimal("109999") <= Decimal(body["total_liabilities"]) <= Decimal("110001")


async def test_time_to_payoff_uses_schedule_for_mortgage(
    client: AsyncClient,
) -> None:
    """Una hipoteca recién abierta con plazo 240m debe reportar
    `time_to_payoff_months ≈ 240` (todas las cuotas pendientes),
    NO una proyección lineal disparada/cortísima."""
    token = await _register(client, "ttp_mortgage@example.com")
    # Hipoteca de hoy a 240m
    today = datetime.now(UTC).date()
    await _create_account(
        client,
        token,
        name="Hipoteca",
        type="mortgage",
        currency="EUR",
        opening_balance="200000",
        apr="0.035",
        term_months=240,
        start_date=f"{today.year:04d}-{today.month:02d}-01",
    )
    r = await client.get("/accounts/debt-health", headers=_auth(token))
    body = r.json()
    assert body["time_to_payoff_months"] == 240


# ─────────────────────────────────────────────────────────────────────
# PHASE-30.8 — Navegador de período (anchor + límites + effort scoped)
# ─────────────────────────────────────────────────────────────────────


def test_resolve_range_past_and_current_periods() -> None:
    """`_resolve_range` con anchor: períodos pasados completos, el actual
    recortado a hoy. `anchor=None` == comportamiento previo."""
    from datetime import date

    from app.modules.personal_finance.debt.service import _resolve_range

    today = date(2026, 5, 15)

    # Mes pasado completo.
    start, end, buckets = _resolve_range("month", date(2024, 4, 10), today)
    assert (start, end) == (date(2024, 4, 1), date(2024, 4, 30))
    assert buckets == [date(2024, 4, 1)]

    # Año pasado completo → 12 buckets.
    start, end, buckets = _resolve_range("year", date(2024, 8, 1), today)
    assert (start, end) == (date(2024, 1, 1), date(2024, 12, 31))
    assert len(buckets) == 12

    # Año en curso (anchor None) → YTD, end == hoy.
    start, end, buckets = _resolve_range("year", None, today)
    assert (start, end) == (date(2026, 1, 1), today)
    assert len(buckets) == 5  # Ene..May


def test_resolve_period_end() -> None:
    from datetime import date

    from app.modules.personal_finance.debt.service import resolve_period_end

    today = date(2026, 5, 15)
    assert resolve_period_end("year", date(2024, 3, 1), today) == date(2024, 12, 31)
    assert resolve_period_end("year", None, today) == today  # actual → recortado
    assert resolve_period_end("month", date(2024, 2, 9), today) == date(2024, 2, 29)


async def test_summary_anchor_targets_past_month(client: AsyncClient) -> None:
    """`anchor` selecciona un mes pasado concreto, no el actual."""
    token = await _register(client, "anchor_month@example.com")
    cte = await _create_account(
        client,
        token,
        name="Cte",
        type="bank",
        currency="EUR",
        opening_balance="5000",
    )
    cap_id = await _create_category(client, token, "Préstamos e hipotecas", role="DEBT_PAYMENT")
    await _post_tx(client, token, cte["id"], cap_id, "100.00", "2024-03-15T12:00:00Z")
    await _post_tx(client, token, cte["id"], cap_id, "200.00", "2024-04-15T12:00:00Z")

    r = await client.get(
        "/debt/category-summary?range=month&anchor=2024-04-10", headers=_auth(token)
    )
    body = r.json()
    assert body["range_start"] == "2024-04-01"
    assert body["range_end"] == "2024-04-30"
    assert body["total_payments"] == "200.00"
    assert len(body["monthly_series"]) == 1
    assert body["monthly_series"][0]["month"] == "2024-04"


async def test_summary_anchor_past_year_full_12_buckets(client: AsyncClient) -> None:
    """`range=year` con anchor en un año pasado → 12 buckets completos."""
    token = await _register(client, "anchor_year@example.com")
    cte = await _create_account(
        client,
        token,
        name="Cte",
        type="bank",
        currency="EUR",
        opening_balance="5000",
    )
    cap_id = await _create_category(client, token, "Préstamos e hipotecas", role="DEBT_PAYMENT")
    await _post_tx(client, token, cte["id"], cap_id, "100.00", "2024-02-15T12:00:00Z")

    r = await client.get(
        "/debt/category-summary?range=year&anchor=2024-06-01", headers=_auth(token)
    )
    body = r.json()
    assert len(body["monthly_series"]) == 12
    assert body["monthly_series"][0]["month"] == "2024-01"
    assert body["monthly_series"][-1]["month"] == "2024-12"


async def test_summary_available_bounds(client: AsyncClient) -> None:
    """`available_from/to` = primer/último mes con movimientos de deuda."""
    token = await _register(client, "anchor_bounds@example.com")
    cte = await _create_account(
        client,
        token,
        name="Cte",
        type="bank",
        currency="EUR",
        opening_balance="5000",
    )
    cap_id = await _create_category(client, token, "Préstamos e hipotecas", role="DEBT_PAYMENT")
    await _post_tx(client, token, cte["id"], cap_id, "100.00", "2024-03-15T12:00:00Z")
    await _post_tx(client, token, cte["id"], cap_id, "100.00", "2025-09-20T12:00:00Z")

    r = await client.get(
        "/debt/category-summary?range=year&anchor=2024-06-01", headers=_auth(token)
    )
    body = r.json()
    assert body["available_from"] == "2024-03"
    assert body["available_to"] == "2025-09"


async def test_summary_available_bounds_null_when_empty(client: AsyncClient) -> None:
    """Sin movimientos de deuda → `available_from/to` son `null`."""
    token = await _register(client, "anchor_bounds_empty@example.com")
    await _create_account(
        client,
        token,
        name="Cte",
        type="bank",
        currency="EUR",
        opening_balance="5000",
    )
    r = await client.get("/debt/category-summary?range=year", headers=_auth(token))
    body = r.json()
    assert body["available_from"] is None
    assert body["available_to"] is None


async def test_daily_series_tracks_balance_emission_and_payment(client: AsyncClient) -> None:
    """PHASE-30.9 — `range=month` devuelve la serie diaria: línea de saldo
    (apertura + emisión − amortización) + barras emitida/amortizado/interés.

    Tarjeta EUR (apertura 1000): compra +500 el día 5, pago 300 el día 20
    (income a la tarjeta), interés 50 el día 10 en una cuenta bank (sólo
    barra de interés, no toca el saldo)."""
    token = await _register(client, "daily_series@example.com")
    card = await _create_account(
        client, token, name="Visa", type="credit_card", currency="EUR", opening_balance="1000"
    )
    bank = await _create_account(
        client, token, name="Cte", type="bank", currency="EUR", opening_balance="0"
    )
    purchase = await _create_category(client, token, "Compra tarjeta", kind="expense")
    payment = await _create_category(client, token, "Pago tarjeta", kind="income")
    interest = await _create_category(client, token, "Intereses tarjeta", role="DEBT_INTEREST")

    await _post_tx(client, token, card["id"], purchase, "500.00", "2024-04-05T12:00:00Z")
    await _post_tx(client, token, card["id"], payment, "300.00", "2024-04-20T12:00:00Z")
    await _post_tx(client, token, bank["id"], interest, "50.00", "2024-04-10T12:00:00Z")

    r = await client.get(
        "/debt/category-summary?range=month&anchor=2024-04-10", headers=_auth(token)
    )
    body = r.json()
    daily = body["daily_series"]
    assert daily is not None
    assert len(daily) == 30  # abril completo (mes pasado)
    by_day = {p["day"]: p for p in daily}
    assert Decimal(by_day[1]["balance"]) == Decimal("1000.00")
    assert Decimal(by_day[5]["emitida"]) == Decimal("500.00")
    assert Decimal(by_day[5]["balance"]) == Decimal("1500.00")
    assert Decimal(by_day[10]["interest"]) == Decimal("50.00")
    assert Decimal(by_day[10]["balance"]) == Decimal("1500.00")  # interés no mueve principal
    assert Decimal(by_day[20]["amortizado"]) == Decimal("300.00")
    assert Decimal(by_day[20]["balance"]) == Decimal("1200.00")


async def test_daily_series_fallback_without_liabilities(client: AsyncClient) -> None:
    """PHASE-30.9 — sin cuentas-pasivo, la serie diaria cae a barras de
    pagos categorizados (capital DEBT_PAYMENT) + interés, sin línea de
    saldo (`balance=None`)."""
    token = await _register(client, "daily_fallback@example.com")
    cte = await _create_account(
        client, token, name="Cte", type="bank", currency="EUR", opening_balance="5000"
    )
    cap_id = await _create_category(client, token, "Préstamos e hipotecas", role="DEBT_PAYMENT")
    await _post_tx(client, token, cte["id"], cap_id, "400.00", "2024-04-07T12:00:00Z")

    r = await client.get(
        "/debt/category-summary?range=month&anchor=2024-04-10", headers=_auth(token)
    )
    daily = r.json()["daily_series"]
    assert daily is not None
    by_day = {p["day"]: p for p in daily}
    assert by_day[7]["balance"] is None
    assert Decimal(by_day[7]["amortizado"]) == Decimal("400.00")
    assert Decimal(by_day[7]["emitida"]) == Decimal("0")


async def test_daily_series_null_for_year_range(client: AsyncClient) -> None:
    """`range=year` no trae serie diaria (se usa la mensual)."""
    token = await _register(client, "daily_year@example.com")
    await _create_account(
        client, token, name="Cte", type="bank", currency="EUR", opening_balance="100"
    )
    r = await client.get("/debt/category-summary?range=year", headers=_auth(token))
    assert r.json()["daily_series"] is None


async def test_summary_future_anchor_is_graceful(client: AsyncClient) -> None:
    """Un anchor en el futuro (defensa; las flechas lo evitan) no rompe:
    devuelve ceros y la tasa de esfuerzo `None` (sin meses cerrados)."""
    token = await _register(client, "anchor_future@example.com")
    cte = await _create_account(
        client,
        token,
        name="Cte",
        type="bank",
        currency="EUR",
        opening_balance="5000",
    )
    cap_id = await _create_category(client, token, "Préstamos e hipotecas", role="DEBT_PAYMENT")
    await _post_tx(client, token, cte["id"], cap_id, "100.00", "2024-04-15T12:00:00Z")

    r = await client.get(
        "/debt/category-summary?range=month&anchor=2099-01-15", headers=_auth(token)
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total_payments"] == "0.00"
    assert body["effort_ratio_strict"] is None


async def test_effort_ratio_scoped_to_anchor_period(client: AsyncClient) -> None:
    """La tasa de esfuerzo se promedia sobre los meses cerrados del
    período elegido: año pasado completo → media mensual real."""
    token = await _register(client, "anchor_effort@example.com")
    cte = await _create_account(
        client,
        token,
        name="Cte",
        type="bank",
        currency="EUR",
        opening_balance="5000",
    )
    cap_id = await _create_category(client, token, "Préstamos e hipotecas", role="DEBT_PAYMENT")
    salary_id = await _create_category(client, token, "Nómina", kind="income")
    for month in range(1, 13):
        iso = f"2024-{month:02d}-15T12:00:00Z"
        await _post_tx(client, token, cte["id"], salary_id, "2000.00", iso)
        await _post_tx(client, token, cte["id"], cap_id, "400.00", iso)

    r = await client.get(
        "/debt/category-summary?range=year&anchor=2024-06-01", headers=_auth(token)
    )
    body = r.json()
    # 12 meses cerrados → media deuda 400, media ingreso 2000 → 0.20.
    assert body["monthly_debt_payment_avg"] == "400.00"
    assert body["monthly_income_avg"] == "2000.00"
    assert body["effort_ratio_strict"] is not None
    assert abs(body["effort_ratio_strict"] - 0.20) < 0.001


# ── range=custom (PHASE-41) ──────────────────────────────────────────────────


async def test_summary_custom_range_is_day_exact_on_both_ends(client: AsyncClient) -> None:
    """`range=custom` usa `date_from`/`date_to` day-exact: excluye pagos
    ANTERIORES a `date_from` y POSTERIORES a `date_to`, aunque caigan en un
    mes tocado por el rango."""
    token = await _register(client, "custom_dayexact@example.com")
    cte = await _create_account(
        client, token, name="Cte", type="bank", currency="EUR", opening_balance="5000"
    )
    cap_id = await _create_category(client, token, "Préstamos e hipotecas", role="DEBT_PAYMENT")
    await _post_tx(client, token, cte["id"], cap_id, "50.00", "2024-04-05T12:00:00Z")  # antes
    await _post_tx(client, token, cte["id"], cap_id, "200.00", "2024-04-20T12:00:00Z")  # dentro
    await _post_tx(client, token, cte["id"], cap_id, "300.00", "2024-05-10T12:00:00Z")  # después

    r = await client.get(
        "/debt/category-summary?range=custom&date_from=2024-04-10&date_to=2024-05-05",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["range_start"] == "2024-04-10"
    assert body["range_end"] == "2024-05-05"
    # Sólo el pago del 20-abr entra en la ventana [10-abr, 05-may].
    assert body["total_payments"] == "200.00"
    # El rango toca abril y mayo → 2 buckets mensuales.
    assert [p["month"] for p in body["monthly_series"]] == ["2024-04", "2024-05"]


async def test_summary_custom_requires_date_from_and_to(client: AsyncClient) -> None:
    """`range=custom` sin `date_from`/`date_to` → 422."""
    token = await _register(client, "custom_missing@example.com")
    r = await client.get("/debt/category-summary?range=custom", headers=_auth(token))
    assert r.status_code == 422, r.text
    r2 = await client.get(
        "/debt/category-summary?range=custom&date_from=2024-05-10&date_to=2024-04-01",
        headers=_auth(token),
    )
    assert r2.status_code == 422, r2.text
