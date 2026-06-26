"""Tests del lote de fixes de auditoría sobre currency / dashboard.

Cubre los cinco hallazgos:

1. sql-no-zero-rate-guard — el cliente rechaza tasas <= 0; la conversión
   en SQL trata una tasa <= 0 como "sin tasa" (NULL) en vez de reventar;
   (la CHECK constraint vive en la migración, no se testea sin DB migrada).
2. sql-crossrate-no-reanchor — `converted_amount_expr` re-ancla ambas
   piernas de una cross-rate a la fecha común más antigua, coincidiendo con
   `currency.service.convert`.
3. jpy-zero-decimal-rounding — `_round_money` redondea JPY a entero.
4. get-summary-prev-period-solape-frontera — una tx en la frontera no se
   cuenta dos veces entre periodo actual y previo.
5. normalize-concept-no-quita-acentos — `normalize_concept` quita acentos
   igual que `category_rules.normalize`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.currency import client, service
from app.modules.currency import repository as rates_repository
from app.modules.currency.exceptions import (
    FrankfurterInvalidResponseError,
    FrankfurterUnavailableError,
)
from app.modules.personal_finance.bank_mappings.repository import normalize_concept
from app.modules.personal_finance.category_rules.repository import normalize as rules_normalize
from app.modules.personal_finance.dashboard.conversion import converted_amount_expr
from app.modules.personal_finance.transactions.models import Transaction

# ---------------------------------------------------------------------------
# Finding 3 — jpy-zero-decimal-rounding (puro, sin DB)
# ---------------------------------------------------------------------------


def test_round_money_jpy_has_zero_decimals() -> None:
    """JPY se redondea a entero (0 decimales)."""
    assert service._round_money(Decimal("1234.56"), "JPY") == Decimal("1235")
    rounded = service._round_money(Decimal("1234.40"), "JPY")
    assert rounded == Decimal("1234")
    assert rounded.as_tuple().exponent == 0


def test_round_money_jpy_banker_rounding_to_integer() -> None:
    """JPY usa ROUND_HALF_EVEN como el resto: 0.5 → al par."""
    assert service._round_money(Decimal("2.5"), "JPY") == Decimal("2")
    assert service._round_money(Decimal("3.5"), "JPY") == Decimal("4")


def test_round_money_default_still_two_decimals() -> None:
    """Sin moneda de 0 decimales, sigue redondeando a céntimos."""
    assert service._round_money(Decimal("1.005"), "EUR") == Decimal("1.00")
    assert service._round_money(Decimal("1.005")) == Decimal("1.00")  # default EUR
    assert service._round_money(Decimal("1.015"), "USD") == Decimal("1.02")


def test_quantum_for_is_case_insensitive() -> None:
    """El mapa de dígitos normaliza la moneda antes de buscar."""
    assert service._quantum_for("jpy") == Decimal("1")
    assert service._quantum_for(" Jpy ") == Decimal("1")
    assert service._quantum_for("usd") == Decimal("0.01")


# ---------------------------------------------------------------------------
# Finding 5 — normalize-concept-no-quita-acentos (puro, sin DB)
# ---------------------------------------------------------------------------


def test_normalize_concept_strips_accents() -> None:
    """'Telefónica' y 'TELEFONICA' colapsan a la misma clave."""
    assert normalize_concept("Telefónica") == normalize_concept("TELEFONICA")
    assert "ó" not in normalize_concept("Telefónica")


def test_normalize_concept_matches_rules_normalize() -> None:
    """Bank-mappings y category_rules comparten EXACTAMENTE la normalización."""
    for sample in ["Café Münich", "  NÓMINA  ", "Pagaré 2026", "über"]:
        assert normalize_concept(sample) == rules_normalize(sample)


def test_normalize_concept_handles_none_and_empty() -> None:
    assert normalize_concept("") == ""
    assert normalize_concept("   ") == ""


# ---------------------------------------------------------------------------
# Finding 1a — client rechaza tasas <= 0 (mock de la respuesta HTTP)
# ---------------------------------------------------------------------------


def _mock_httpx_client(body: dict[str, object]) -> MagicMock:
    """AsyncClient mockeado cuyo `.get` devuelve `body` (mismo patrón que
    `test_currency_client.py`)."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = body
    response.raise_for_status.return_value = None

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


async def test_fetch_rates_rejects_zero_rate() -> None:
    with (
        patch(
            "app.modules.currency.client.httpx.AsyncClient",
            return_value=_mock_httpx_client({"rates": {"USD": 0}}),
        ),
        pytest.raises(FrankfurterInvalidResponseError),
    ):
        await client.fetch_rates(target_date=date(2026, 4, 1), quotes=["USD"])


async def test_fetch_rates_rejects_negative_rate() -> None:
    with (
        patch(
            "app.modules.currency.client.httpx.AsyncClient",
            return_value=_mock_httpx_client({"rates": {"USD": -1.1}}),
        ),
        pytest.raises(FrankfurterInvalidResponseError),
    ):
        await client.fetch_rates(target_date=date(2026, 4, 1), quotes=["USD"])


async def test_fetch_rates_accepts_positive_rate() -> None:
    with patch(
        "app.modules.currency.client.httpx.AsyncClient",
        return_value=_mock_httpx_client({"rates": {"USD": 1.1}}),
    ):
        out = await client.fetch_rates(target_date=date(2026, 4, 1), quotes=["USD"])
    assert out == {"USD": Decimal("1.1")}


# ---------------------------------------------------------------------------
# Helpers DB para los findings que tocan SQL
# ---------------------------------------------------------------------------


async def _session(test_engine):  # type: ignore[no-untyped-def]
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    return factory()


async def _seed_rate(db, rate_date: date, quote: str, rate: str) -> None:  # type: ignore[no-untyped-def]
    await rates_repository.upsert_rates(db, [(rate_date, "EUR", quote, Decimal(rate), "test")])


# ---------------------------------------------------------------------------
# Finding 1b — tasa <= 0 en BD se trata como NULL (no revienta la query)
# ---------------------------------------------------------------------------


async def test_converted_expr_treats_nonpositive_rate_as_null(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
    _block_frankfurter,  # type: ignore[no-untyped-def]
) -> None:
    """Una fila con rate<=0 en BD NO produce división por cero (500); la tx
    queda inconvertible (converted NULL → unconvertible_count) en vez de
    reventar la query.

    Insertamos la tasa por SQL raw porque `upsert_rates` no rechaza 0 — la
    defensa de ESTA capa es la query (CASE/WHERE rate > 0), no el repo. La
    CHECK constraint de BD vive en la migración, que no corre en los tests
    (usan `create_all`), así que el insert de 0 pasa y podemos ejercitar el
    guard de la query.
    """
    from sqlalchemy import text

    token, account_id = await _register(client, "zerorate@test.com")
    expense = (
        await client.post(
            "/categories",
            json={"name": "Gasto", "kind": "expense"},
            headers=_auth(token),
        )
    ).json()["id"]

    # Tx en USD: convertir a EUR hará `amount / from_rate(USD)`.
    r = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "amount": "100",
            "currency": "USD",
            "occurred_at": "2026-04-01T12:00:00Z",
            "category_id": expense,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text

    # Sembrar EUR→USD = 0 por SQL raw (el repo no lo bloquea; la CHECK
    # tampoco está en la tabla de tests).
    async with await _session(test_engine) as db:
        await db.execute(
            text(
                "INSERT INTO exchange_rates (rate_date, base, quote, rate, source) "
                "VALUES (:d, 'EUR', 'USD', 0, 'test')"
            ),
            {"d": date(2026, 4, 1)},
        )
        await db.commit()

        # Ejercitar directamente la expresión de producción: con rate=0 la
        # subquery proyecta NULL y `amount / NULL` → NULL (no división por
        # cero). Esto confirma el guard sin depender del endpoint.
        expr = converted_amount_expr("EUR")
        value = (
            await db.execute(
                select(expr).select_from(Transaction).where(Transaction.currency == "USD")
            )
        ).scalar_one()
        assert value is None

    # Y vía endpoint: la query no revienta (200) y la tx cuenta como
    # inconvertible en vez de provocar un 500 por división por cero.
    summary = await client.get(
        "/dashboard/summary",
        params={"target_currency": "EUR"},
        headers=_auth(token),
    )
    assert summary.status_code == 200, summary.text
    data = summary.json()
    assert Decimal(data["expenses"]) == Decimal("0")
    assert data["unconvertible_count"] == 1


# ---------------------------------------------------------------------------
# Finding 2 — re-anclaje cross-rate en SQL coincide con service.convert
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def _block_frankfurter():
    """Evita fetch real en `ensure_rates_for_dates` durante los tests HTTP."""
    with patch(
        "app.modules.currency.client.fetch_rates",
        new_callable=AsyncMock,
        side_effect=FrankfurterUnavailableError("test offline"),
    ):
        yield


async def _register(client_: AsyncClient, email: str) -> tuple[str, str]:
    r = await client_.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    token = r.json()["access_token"]
    acc = await client_.post(
        "/accounts",
        json={"name": "Cuenta", "type": "bank", "currency": "EUR"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, acc.json()["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_sql_crossrate_reanchors_like_service_convert(
    client: AsyncClient,
    test_engine,  # type: ignore[no-untyped-def]
    _block_frankfurter,  # type: ignore[no-untyped-def]
) -> None:
    """Misma fixture que el test de service.convert (AUDIT-2026-05): EUR→USD
    sembrado 04-01/03/05, EUR→GBP sólo 04-01/03. Una tx en USD del 04-05
    convertida a GBP debe re-anclarse al 04-03 (GBP=0.85, USD=1.15) →
    100 USD * (0.85/1.15) ≈ 73.91 GBP — el MISMO número que produce
    `service.convert`. Sin el fix, la query usaría USD del 04-05 (1.20) →
    70.83 GBP, divergiendo del service.
    """
    token, account_id = await _register(client, "crossrate@test.com")
    expense = (
        await client.post(
            "/categories",
            json={"name": "Gasto", "kind": "expense"},
            headers=_auth(token),
        )
    ).json()["id"]

    # Sembrar tasas.
    async with await _session(test_engine) as db:
        await _seed_rate(db, date(2026, 4, 1), "USD", "1.10")
        await _seed_rate(db, date(2026, 4, 3), "USD", "1.15")
        await _seed_rate(db, date(2026, 4, 5), "USD", "1.20")
        await _seed_rate(db, date(2026, 4, 1), "GBP", "0.80")
        await _seed_rate(db, date(2026, 4, 3), "GBP", "0.85")
        await db.commit()

    # Tx USD del 04-05.
    r = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "amount": "100",
            "currency": "USD",
            "occurred_at": "2026-04-05T12:00:00Z",
            "category_id": expense,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text

    # service.convert como oráculo.
    async with await _session(test_engine) as db:
        oracle = await service.convert(
            db,
            amount=Decimal("100"),
            from_currency="USD",
            to_currency="GBP",
            at_date=date(2026, 4, 5),
        )
    # Re-anclado al 04-03 → 0.85/1.15.
    assert oracle.rate_date == date(2026, 4, 3)

    # La query del dashboard debe componer la MISMA tasa.
    summary = await client.get(
        "/dashboard/summary",
        params={"target_currency": "GBP"},
        headers=_auth(token),
    )
    assert summary.status_code == 200, summary.text
    expenses = Decimal(summary.json()["expenses"])

    expected = Decimal("100") * (Decimal("0.85") / Decimal("1.15"))
    # La query devuelve full precision; comparamos con holgura de 1 céntimo.
    assert abs(expenses - expected) < Decimal("0.01"), (expenses, expected)
    # Y coincide con el oráculo del service (a céntimo).
    assert abs(expenses - oracle.amount) < Decimal("0.01"), (expenses, oracle.amount)
    # Sanity: NO es el valor sin re-anclar (USD 04-05 = 1.20 → 70.83).
    wrong = Decimal("100") * (Decimal("0.85") / Decimal("1.20"))
    assert abs(expenses - wrong) > Decimal("1"), expenses


# ---------------------------------------------------------------------------
# Finding 4 — periodo previo sin solape en la frontera
# ---------------------------------------------------------------------------


async def test_prev_period_excludes_boundary_transaction(
    client: AsyncClient,
    _block_frankfurter,  # type: ignore[no-untyped-def]
) -> None:
    """Una tx con `occurred_at == date_from` cuenta SÓLO en el periodo
    actual, no también en el previo. Antes del fix, el periodo previo
    terminaba en `date_from` inclusivo y la contaba dos veces.
    """
    token, account_id = await _register(client, "boundary@test.com")
    expense = (
        await client.post(
            "/categories",
            json={"name": "Gasto", "kind": "expense"},
            headers=_auth(token),
        )
    ).json()["id"]

    # Tx justo en la frontera (date_from del periodo actual = 2026-03-01).
    r = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "amount": "100",
            "currency": "EUR",
            "occurred_at": "2026-03-01T00:00:00Z",
            "category_id": expense,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text

    # Periodo actual: marzo. Periodo previo: febrero ([prev_from, date_from)).
    summary = await client.get(
        "/dashboard/summary",
        params={
            "currency": "EUR",
            "date_from": "2026-03-01T00:00:00Z",
            "date_to": "2026-03-31T23:59:59Z",
        },
        headers=_auth(token),
    )
    assert summary.status_code == 200, summary.text
    data = summary.json()
    # La tx de la frontera cuenta en el periodo ACTUAL.
    assert Decimal(data["expenses"]) == Decimal("100")
    # Y NO en el previo (sería 100 sin el fix por el solape inclusivo).
    assert Decimal(data["previous_period_expenses"]) == Decimal("0")
