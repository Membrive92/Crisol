"""PHASE-43.4 (ADR-0006) — contrato de agregación del dashboard.

Tarjetas de módulo `veredicto + número + link`:
- `/dashboard/module-summary` (Finanzas Domésticas): flujo del MES en curso;
  veredicto por SIGNO del flujo (decisión del usuario), banda muerta ±5%.
- `/debt/dashboard-summary` (Deuda): deuda viva + esfuerzo; veredicto del
  `dti_status` (bandas BdE), `neutral` sin deuda.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.personal_finance.accounts.installments_repository import (
    generate_installments_for_account,
)
from app.modules.personal_finance.accounts.models import (
    Account,
    AccountNature,
    AccountType,
)
from app.modules.personal_finance.debt.service import compute_dashboard_summary
from app.modules.users.models import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "M"},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["access_token"])


async def _account(client: AsyncClient, token: str) -> str:
    r = await client.post(
        "/accounts",
        json={"name": "BBVA", "type": "bank", "currency": "EUR", "opening_balance": "0.00"},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _tx(
    client: AsyncClient,
    token: str,
    account_id: str,
    amount: str,
    flow: str,
    *,
    when: str | None = None,
) -> None:
    # Sin `when`: mes EN CURSO. Con `when`: día ISO exacto (para meses pasados).
    if when is None:
        now = datetime.now(UTC)
        when = now.replace(day=15, hour=12, minute=0, second=0, microsecond=0).isoformat()
    r = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "amount": amount,
            "currency": "EUR",
            "occurred_at": when,
            "flow": flow,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text


async def _module_summary(client: AsyncClient, token: str) -> dict[str, Any]:
    r = await client.get("/dashboard/module-summary?currency=EUR", headers=_auth(token))
    assert r.status_code == 200, r.text
    return dict(r.json())


async def test_module_summary_healthy_when_cashflow_clearly_positive(client: AsyncClient) -> None:
    token = await _register(client, "mod_healthy@example.com")
    acc = await _account(client, token)
    await _tx(client, token, acc, "2000.00", "IN")
    await _tx(client, token, acc, "1000.00", "OUT")  # ahorro 50% ≫ +5%
    body = await _module_summary(client, token)
    assert body["verdict"] == "healthy"
    assert body["headline_value"] == "1000.00"
    assert body["link"] == "/personal-finance/analysis"
    assert body["secondary"][0]["label"] == "Ahorro"


async def test_module_summary_stressed_when_cashflow_clearly_negative(client: AsyncClient) -> None:
    token = await _register(client, "mod_stressed@example.com")
    acc = await _account(client, token)
    await _tx(client, token, acc, "1000.00", "IN")
    await _tx(client, token, acc, "1500.00", "OUT")  # gasta más de lo que ingresa
    body = await _module_summary(client, token)
    assert body["verdict"] == "stressed"
    assert body["headline_value"] == "-500.00"


async def test_module_summary_caution_near_breakeven(client: AsyncClient) -> None:
    token = await _register(client, "mod_caution@example.com")
    acc = await _account(client, token)
    await _tx(client, token, acc, "1000.00", "IN")
    await _tx(client, token, acc, "980.00", "OUT")  # +20 = 2% del ingreso, dentro de ±5%
    body = await _module_summary(client, token)
    assert body["verdict"] == "caution"


async def test_module_summary_neutral_without_income(client: AsyncClient) -> None:
    token = await _register(client, "mod_neutral@example.com")
    acc = await _account(client, token)
    await _tx(client, token, acc, "300.00", "OUT")  # sin ingresos este mes
    body = await _module_summary(client, token)
    assert body["verdict"] == "neutral"
    assert body["secondary"] == []


async def test_module_summary_falls_back_to_latest_month_with_data(client: AsyncClient) -> None:
    """PHASE-43.4 (fix) — con el mes en curso VACÍO (típico de quien importa por
    meses) y sin rango, la card usa el ÚLTIMO mes con datos en vez de salir a 0.
    Reproduce el bug reportado: datos hasta un mes pasado → card siempre 0,00."""
    token = await _register(client, "mod_pastmonth@example.com")
    acc = await _account(client, token)
    # Todo en un mes anterior al actual; el mes en curso queda vacío.
    now = datetime.now(UTC)
    prev_year, prev_month = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
    when = f"{prev_year:04d}-{prev_month:02d}-15T12:00:00Z"
    await _tx(client, token, acc, "2000.00", "IN", when=when)
    await _tx(client, token, acc, "1500.00", "OUT", when=when)

    body = await _module_summary(client, token)  # sin rango → último mes con datos
    assert body["headline_value"] == "500.00"
    assert body["verdict"] == "healthy"


async def test_debt_dashboard_summary_neutral_without_debt(client: AsyncClient) -> None:
    token = await _register(client, "debt_none@example.com")
    await _account(client, token)
    r = await client.get("/debt/dashboard-summary", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] == "neutral"
    assert body["headline_value"] == "0.00"
    assert body["link"] == "/debt"


@pytest_asyncio.fixture
async def session_factory(test_engine):  # type: ignore[no-untyped-def]
    return async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)


async def test_debt_dashboard_summary_period_scoped(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """PHASE-43.x — la deuda viva de la tarjeta es al CIERRE del rango: un pago
    POSTERIOR a `date_to` no la reduce (aún la debías esa fecha); uno anterior
    sí. Así la tarjeta cambia por período, coherente con el Patrimonio Neto y
    con el módulo /debt. Fechas del año pasado → todas pasadas, sin depender de
    la fecha de ejecución."""
    uid = uuid.uuid4()
    ly = datetime.now(UTC).year - 1
    async with session_factory() as db:
        db.add(
            User(id=uid, email=f"d_{uid.hex[:8]}@example.com", password_hash="x", display_name="D")
        )
        await db.flush()
        loan = Account(
            user_id=uid,
            name="Préstamo",
            nature=AccountNature.LIABILITY,
            type=AccountType.LOAN,
            currency="EUR",
            opening_balance=Decimal("1200"),
            apr=Decimal("0.05"),
            term_months=12,
            start_date=date(ly, 1, 1),
        )
        db.add(loan)
        await db.flush()
        insts = await generate_installments_for_account(db, loan)
        # La 1ª cuota se paga en FEBRERO del año pasado.
        insts[0].paid_at = datetime(ly, 2, 15, tzinfo=UTC)
        first_principal = insts[0].principal
        await db.commit()

    async with session_factory() as db:
        # Rango que TERMINA antes del pago (31-ene): la cuota aún se debe.
        before = await compute_dashboard_summary(
            db, uid, date_from=date(ly, 1, 1), date_to=date(ly, 1, 31)
        )
        # Rango que TERMINA después del pago (31-mar): ya no.
        after = await compute_dashboard_summary(
            db, uid, date_from=date(ly, 1, 1), date_to=date(ly, 3, 31)
        )

    # headline es negativo (pasivo): `before` tiene MÁS deuda (más negativo).
    assert before.headline_value < after.headline_value
    # La diferencia es exactamente el principal de la cuota pagada en medio.
    assert after.headline_value - before.headline_value == first_principal.quantize(Decimal("0.01"))
