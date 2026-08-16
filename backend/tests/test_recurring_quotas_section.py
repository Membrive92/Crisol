"""PHASE-47.E — La sección «Cuotas recurrentes detectadas» sólo lista tareas.

Reportado en uso, sobre un préstamo YA vinculado: la fila salía con el nombre
`cargoporamortizaciondeprestamo` —la clave interna de agrupación— y con un
botón «Vincular» que pedía hacer algo que el usuario ya había hecho.

Son dos defectos distintos: qué se lista y cómo se escribe.
"""

from __future__ import annotations

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import async_sessionmaker


@pytest_asyncio.fixture
async def session_factory(test_engine):  # type: ignore[no-untyped-def]
    """Sesión contra la BD de test. El gasto fijo se siembra directamente
    porque lo que se prueba es cómo se PUBLICA, no cómo se detecta."""
    return async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "T"},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _debt_category(client: AsyncClient, token: str, name: str) -> str:
    r = await client.post(
        "/categories",
        json={"name": name, "kind": "expense", "role": "DEBT_PAYMENT"},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _fixed_expense(
    session_factory, *, email: str, category_id: str, raw: str  # type: ignore[no-untyped-def]
) -> None:
    from datetime import date

    async with session_factory() as conn:
        uid = (
            await conn.execute(
                sql_text("SELECT id FROM users WHERE email=:e"),
                {"e": email},
            )
        ).scalar_one()
        await conn.execute(
            sql_text(
                "INSERT INTO fixed_expenses (id, user_id, merchant, raw_description, amount,"
                " currency, cadence_days, next_due, status, category_id, first_seen_at,"
                " last_seen_at, occurrence_count, confidence, created_at, updated_at)"
                " VALUES (gen_random_uuid(), :u, 'cargoporamortizaciondeprestamo', :raw,"
                " 232.27, 'EUR', 30, :due, 'CONFIRMED', CAST(:c AS uuid), :seen, :seen,"
                " 6, 0.9, now(), now())"
            ),
            {
                "u": uid,
                "raw": raw,
                "due": date(2026, 8, 31),
                "c": category_id,
                "seen": date(2026, 2, 1),
            },
        )
        await conn.commit()


async def test_the_quota_shows_the_text_the_bank_wrote(
    client: AsyncClient, session_factory  # type: ignore[no-untyped-def]
) -> None:
    """Se publica `raw_description`, no la clave de agrupación.

    `merchant` es minúsculas y sin espacios porque sirve para colapsar
    variantes del mismo concepto. En pantalla se leía
    «cargoporamortizaciondeprestamo».
    """
    token = await _register(client, "quotas@example.com")
    cat = await _debt_category(client, token, "Préstamos e hipotecas")
    raw = "Cargo por amortizacion de prestamo/credito 0182-1051"
    await _fixed_expense(session_factory, email="quotas@example.com", category_id=cat, raw=raw)

    r = await client.get("/debt/category-summary", headers=_auth(token))

    assert r.status_code == 200, r.text
    quotas = r.json()["recurring_quotas"]
    assert len(quotas) == 1
    assert quotas[0]["merchant"] == raw


async def test_a_quota_whose_contract_is_declared_stops_being_listed(
    client: AsyncClient, session_factory  # type: ignore[no-untyped-def]
) -> None:
    """La sección pide vincular lo que FALTA; lo ya vinculado no es tarea.

    Con el contrato declarado seguía saliendo, y con él un botón «Vincular»
    que le decía al usuario que no había hecho algo que sí hizo.
    """
    token = await _register(client, "quotas2@example.com")
    cat = await _debt_category(client, token, "Préstamos e hipotecas")
    await _fixed_expense(
        session_factory, email="quotas2@example.com", category_id=cat, raw="Cargo por amortizacion"
    )

    antes = await client.get("/debt/category-summary", headers=_auth(token))
    assert len(antes.json()["recurring_quotas"]) == 1

    r = await client.post(
        "/accounts",
        json={
            "name": "Prestamo",
            "type": "loan",
            "currency": "EUR",
            "opening_balance": "22000",
            "apr": "0.03",
            "term_months": 120,
            "start_date": "2024-08-31",
            "category_id": cat,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text

    despues = await client.get("/debt/category-summary", headers=_auth(token))
    assert despues.json()["recurring_quotas"] == []
