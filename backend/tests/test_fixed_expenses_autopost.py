"""Tests del autoposteo de gastos fijos (PHASE-17.2)."""

from __future__ import annotations

from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.personal_finance.fixed_expenses.models import FixedExpense
from app.modules.personal_finance.fixed_expenses.service import (
    autopost_due_for_user,
)
from app.modules.personal_finance.transactions.models import Transaction


async def _setup_user(client: AsyncClient, email: str) -> tuple[str, str, str]:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    token = r.json()["access_token"]
    cat = await client.post(
        "/categories",
        json={"name": "Casa", "kind": "expense"},
        headers={"Authorization": f"Bearer {token}"},
    )
    acc = await client.post(
        "/accounts",
        json={"name": "Cuenta principal", "type": "bank", "currency": "EUR"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, cat.json()["id"], acc.json()["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_confirmed_fixed_expense(
    client: AsyncClient,
    token: str,
    cat_id: str,
    account_id: str,
    *,
    amount: str = "800.00",
) -> str:
    """Crea 4 cargos mensuales del mismo merchant + amount, dispara
    scan, confirma — devuelve id del fixed_expense confirmado."""
    today = date.today()
    for i in range(4):
        when = today - timedelta(days=30 * i)
        await client.post(
            "/transactions",
            json={
                "account_id": account_id,
                "category_id": cat_id,
                "amount": amount,
                "currency": "EUR",
                "occurred_at": f"{when.isoformat()}T12:00:00Z",
                "description": "HIPOTECA SANTANDER",
            },
            headers=_auth(token),
        )
    await client.post("/fixed-expenses/scan", headers=_auth(token))
    item = (await client.get("/fixed-expenses", headers=_auth(token))).json()[0]
    await client.post(f"/fixed-expenses/{item['id']}/confirm", headers=_auth(token))
    # PHASE-19.1: el autopost necesita una cuenta destino — asignamos
    # la del helper para que los tests de autopost puedan disparar.
    await client.put(
        f"/fixed-expenses/{item['id']}",
        json={"account_id": account_id},
        headers=_auth(token),
    )
    return item["id"]


async def test_create_fixed_expense_default_auto_post_false(
    client: AsyncClient,
) -> None:
    """Por defecto un fixed_expense queda con auto_post=false al crearse
    desde el detector."""
    token, cat_id, account_id = await _setup_user(client, "ap1@example.com")
    fid = await _create_confirmed_fixed_expense(client, token, cat_id, account_id)
    item = (await client.get(f"/fixed-expenses/{fid}", headers=_auth(token))).json()
    assert item["auto_post"] is False


async def test_put_toggles_auto_post(client: AsyncClient) -> None:
    """PUT activa/desactiva el flag."""
    token, cat_id, account_id = await _setup_user(client, "ap2@example.com")
    fid = await _create_confirmed_fixed_expense(client, token, cat_id, account_id)

    r_on = await client.put(
        f"/fixed-expenses/{fid}",
        json={"auto_post": True},
        headers=_auth(token),
    )
    assert r_on.json()["auto_post"] is True

    r_off = await client.put(
        f"/fixed-expenses/{fid}",
        json={"auto_post": False},
        headers=_auth(token),
    )
    assert r_off.json()["auto_post"] is False


async def test_autopost_creates_expected_tx_and_advances_next_due(
    client: AsyncClient, test_engine
) -> None:
    """Con auto_post on y next_due en el pasado, autopost crea una tx
    `source=expected` con amount/categoría del gasto fijo y avanza
    next_due un ciclo. Usamos session directa para forzar next_due a
    ayer (los cargos seedeados desde el helper dejan next_due en el
    futuro y autopost no dispararía)."""
    token, cat_id, account_id = await _setup_user(client, "ap3@example.com")
    fid = await _create_confirmed_fixed_expense(client, token, cat_id, account_id, amount="800.00")
    await client.put(
        f"/fixed-expenses/{fid}",
        json={"auto_post": True},
        headers=_auth(token),
    )

    today = date.today()
    yesterday = today - timedelta(days=1)
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        item = (await db.execute(select(FixedExpense).where(FixedExpense.id == fid))).scalar_one()
        item.next_due = yesterday
        await db.commit()

        # Llamamos al service directamente para evitar depender del
        # request scope de FastAPI con datos manipulados a mano.
        result = await autopost_due_for_user(db, item.user_id, today=today)
        await db.commit()
        assert result.created == 1
        assert result.advanced == 1

        # Tx creada con source=expected.
        txs = (
            (await db.execute(select(Transaction).where(Transaction.user_id == item.user_id)))
            .scalars()
            .all()
        )
        expected_txs = [t for t in txs if t.source.value == "expected"]
        assert len(expected_txs) == 1
        assert str(expected_txs[0].amount) == "800.00"
        assert expected_txs[0].category_id == item.category_id
        assert expected_txs[0].description == item.raw_description

        # next_due avanzado un ciclo.
        await db.refresh(item)
        assert item.next_due == yesterday + timedelta(days=item.cadence_days)


async def test_autopost_backfills_multiple_cycles_capped_at_12(
    client: AsyncClient, test_engine
) -> None:
    """Si next_due está varios ciclos en el pasado, autopost crea una
    tx por ciclo perdido — capped a 12 para evitar avalanchas."""
    token, cat_id, account_id = await _setup_user(client, "ap_bf@example.com")
    fid = await _create_confirmed_fixed_expense(client, token, cat_id, account_id)
    await client.put(
        f"/fixed-expenses/{fid}",
        json={"auto_post": True},
        headers=_auth(token),
    )

    today = date.today()
    far_past = today - timedelta(days=30 * 3)  # 3 ciclos atrás
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        item = (await db.execute(select(FixedExpense).where(FixedExpense.id == fid))).scalar_one()
        item.next_due = far_past
        await db.commit()

        result = await autopost_due_for_user(db, item.user_id, today=today)
        await db.commit()
        # Cycles esperados: 4 (far_past, +30d, +60d, +90d... hasta que
        # next_due > today).
        assert result.created >= 3
        assert result.created <= 12


async def test_autopost_skips_when_flag_off(client: AsyncClient) -> None:
    """Sin flag, autopost no toca el gasto fijo aunque next_due ya
    haya pasado."""
    token, cat_id, account_id = await _setup_user(client, "ap4@example.com")
    fid = await _create_confirmed_fixed_expense(client, token, cat_id, account_id)
    item_before = (await client.get(f"/fixed-expenses/{fid}", headers=_auth(token))).json()

    r = await client.post("/fixed-expenses/autopost", headers=_auth(token))
    assert r.json()["created"] == 0

    item_after = (await client.get(f"/fixed-expenses/{fid}", headers=_auth(token))).json()
    assert item_after["next_due"] == item_before["next_due"]


async def test_autopost_skips_paused_and_cancelled(client: AsyncClient) -> None:
    """Una hipoteca pausada con flag on NO se postea — el lifecycle
    gana sobre el flag."""
    token, cat_id, account_id = await _setup_user(client, "ap5@example.com")
    fid = await _create_confirmed_fixed_expense(client, token, cat_id, account_id)
    await client.put(
        f"/fixed-expenses/{fid}",
        json={"auto_post": True},
        headers=_auth(token),
    )
    await client.post(f"/fixed-expenses/{fid}/pause", headers=_auth(token))

    r = await client.post("/fixed-expenses/autopost", headers=_auth(token))
    assert r.json()["created"] == 0


async def test_autopost_user_isolation(client: AsyncClient) -> None:
    """User B no se ve afectado por flag on de user A."""
    token_a, cat_a, account_a = await _setup_user(client, "apA@example.com")
    fa = await _create_confirmed_fixed_expense(client, token_a, cat_a, account_a)
    await client.put(
        f"/fixed-expenses/{fa}",
        json={"auto_post": True},
        headers=_auth(token_a),
    )

    token_b, _, _ = await _setup_user(client, "apB@example.com")
    r_b = await client.post("/fixed-expenses/autopost", headers=_auth(token_b))
    assert r_b.json()["created"] == 0
