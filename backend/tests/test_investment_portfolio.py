"""Tests de cartera (PHASE-44.7).

FIFO se testea puro; el resto end-to-end con un security resuelto vía adapter
falso.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.main import app
from app.modules.investment.fundamentals.adapters.base import SecurityIdentity
from app.modules.investment.fundamentals.adapters.factory import get_fundamentals_adapter
from app.modules.investment.portfolio.fifo import (
    InsufficientSharesError,
    OpenLot,
    match_fifo,
)

_L1 = uuid.uuid4()
_L2 = uuid.uuid4()


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


_MCD = SecurityIdentity(
    ticker="MCD",
    cik="0000063908",
    name="MCDONALDS CORP",
    sic="5812",
    is_reit=False,
    is_financial=False,
)


class _FakeAdapter:
    async def resolve(self, ticker: str) -> SecurityIdentity:
        return _MCD

    async def fetch_facts(self, identity: SecurityIdentity, *, refresh: bool = False) -> tuple[()]:
        return ()


async def _security(client: AsyncClient, token: str) -> str:
    app.dependency_overrides[get_fundamentals_adapter] = _FakeAdapter
    r = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )
    return r.json()["id"]


# ── FIFO (puro) ───────────────────────────────────────────────────────


def test_fifo_consume_el_lote_mas_antiguo_primero() -> None:
    lots = [
        OpenLot(_L2, date(2023, 1, 1), Decimal(5), Decimal(10), Decimal(1)),
        OpenLot(_L1, date(2022, 1, 1), Decimal(10), Decimal(8), Decimal(1)),
    ]
    allocations = match_fifo(lots, Decimal(12))
    assert [(a.lot_id, a.quantity) for a in allocations] == [
        (_L1, Decimal(10)),
        (_L2, Decimal(2)),
    ]
    assert allocations[0].cost_basis == Decimal(8)  # coste del lote consumido


def test_fifo_vender_de_mas_lanza() -> None:
    lots = [OpenLot(_L1, date(2022, 1, 1), Decimal(3), Decimal(8), Decimal(1))]
    with pytest.raises(InsufficientSharesError):
        match_fifo(lots, Decimal(5))


# ── Ventas E2E ────────────────────────────────────────────────────────


async def _lot(
    client: AsyncClient, token: str, sid: str, *, qty: str, price: str, day: str
) -> None:
    r = await client.post(
        "/investment/portfolio/lots",
        json={"security_id": sid, "trade_date": day, "quantity": qty, "price": price},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text


async def test_venta_casa_fifo_y_posicion_baja(client: AsyncClient) -> None:
    token = await _register(client, "pf1@example.com")
    sid = await _security(client, token)
    await _lot(client, token, sid, qty="10", price="100", day="2022-01-01")
    await _lot(client, token, sid, qty="5", price="120", day="2023-01-01")

    sale = await client.post(
        "/investment/portfolio/sales",
        json={"security_id": sid, "trade_date": "2024-01-01", "quantity": "12", "price": "150"},
        headers=_auth(token),
    )
    assert sale.status_code == 201, sale.text

    positions = await client.get("/investment/portfolio/positions", headers=_auth(token))
    pos = positions.json()["items"][0]
    assert Decimal(pos["quantity"]) == Decimal(3)  # 15 - 12
    # realizado: 12*150 - (10*100 + 2*120) = 1800 - 1240 = 560
    assert Decimal(pos["realized_pnl"]) == Decimal(560)


async def test_vender_mas_de_lo_que_hay_da_409(client: AsyncClient) -> None:
    token = await _register(client, "pf2@example.com")
    sid = await _security(client, token)
    await _lot(client, token, sid, qty="5", price="100", day="2022-01-01")

    sale = await client.post(
        "/investment/portfolio/sales",
        json={"security_id": sid, "trade_date": "2024-01-01", "quantity": "9", "price": "150"},
        headers=_auth(token),
    )
    assert sale.status_code == 409
    assert "solo tienes" in sale.json()["detail"]


async def test_borrar_venta_devuelve_las_acciones(client: AsyncClient) -> None:
    token = await _register(client, "pf3@example.com")
    sid = await _security(client, token)
    await _lot(client, token, sid, qty="10", price="100", day="2022-01-01")
    sale = await client.post(
        "/investment/portfolio/sales",
        json={"security_id": sid, "trade_date": "2024-01-01", "quantity": "6", "price": "150"},
        headers=_auth(token),
    )
    await client.delete(f"/investment/portfolio/sales/{sale.json()['id']}", headers=_auth(token))
    positions = await client.get("/investment/portfolio/positions", headers=_auth(token))
    assert Decimal(positions.json()["items"][0]["quantity"]) == Decimal(10)


# ── Acciones corporativas ─────────────────────────────────────────────


async def test_split_ajusta_lotes_y_es_reversible(client: AsyncClient) -> None:
    token = await _register(client, "pf4@example.com")
    sid = await _security(client, token)
    await _lot(client, token, sid, qty="10", price="100", day="2022-01-01")

    action = await client.post(
        "/investment/portfolio/corporate-actions",
        json={
            "security_id": sid,
            "action_type": "split",
            "action_date": "2023-01-01",
            "ratio": "2",
        },
        headers=_auth(token),
    )
    applied = await client.post(
        f"/investment/portfolio/corporate-actions/{action.json()['id']}/apply",
        headers=_auth(token),
    )
    assert applied.status_code == 200
    assert applied.json()["applied_at"] is not None

    lots = await client.get(f"/investment/portfolio/lots?security_id={sid}", headers=_auth(token))
    lot = lots.json()["items"][0]
    assert Decimal(lot["quantity"]) == Decimal(20)
    assert Decimal(lot["price"]) == Decimal(50)
    # coste base invariante: 20*50 == 10*100
    positions = await client.get("/investment/portfolio/positions", headers=_auth(token))
    assert Decimal(positions.json()["items"][0]["cost_basis"]) == Decimal(1000)


async def test_spinoff_no_se_puede_aplicar_aun(client: AsyncClient) -> None:
    token = await _register(client, "pf5@example.com")
    sid = await _security(client, token)
    action = await client.post(
        "/investment/portfolio/corporate-actions",
        json={"security_id": sid, "action_type": "spinoff", "action_date": "2023-01-01"},
        headers=_auth(token),
    )
    assert action.status_code == 201  # registrar sí
    applied = await client.post(
        f"/investment/portfolio/corporate-actions/{action.json()['id']}/apply",
        headers=_auth(token),
    )
    assert applied.status_code == 400  # aplicar no


# ── Dividendos ────────────────────────────────────────────────────────


async def test_dividendo_calcula_neto_y_suma_en_posicion(client: AsyncClient) -> None:
    token = await _register(client, "pf6@example.com")
    sid = await _security(client, token)
    await _lot(client, token, sid, qty="10", price="100", day="2022-01-01")
    div = await client.post(
        "/investment/portfolio/dividends",
        json={
            "security_id": sid,
            "pay_date": "2023-03-01",
            "gross_amount": "100",
            "withholding_tax": "15",
            "currency": "USD",
        },
        headers=_auth(token),
    )
    assert Decimal(div.json()["net_amount"]) == Decimal(85)
    positions = await client.get("/investment/portfolio/positions", headers=_auth(token))
    assert Decimal(positions.json()["items"][0]["dividends_net"]) == Decimal(85)


# ── Scoping ───────────────────────────────────────────────────────────


async def test_lotes_scoped_por_usuario(client: AsyncClient) -> None:
    token_a = await _register(client, "pf7a@example.com")
    sid = await _security(client, token_a)
    await _lot(client, token_a, sid, qty="10", price="100", day="2022-01-01")

    token_b = await _register(client, "pf7b@example.com")
    theirs = await client.get("/investment/portfolio/lots", headers=_auth(token_b))
    assert theirs.json()["items"] == []
