"""PHASE-47.E4 — Quién cobra el cargo AGREGADO de la tarjeta, y quién no.

BBVA cobra en UNA sola línea mensual («Operación financiada con tarjeta 4940…»)
la suma de las cuotas de todo lo que se financió en esa tarjeta. La
reconciliación reparte ese cargo avanzando **una** cuota de cada plan.

El pool era `type == CREDIT_CARD`, y eso dejaba fuera un caso real: cuando el
banco aplaza el RECIBO de la tarjeta, el usuario da de alta la deuda como
préstamo —es lo que el banco le vende— y entonces su cuota no se atribuía
**jamás**. El pasivo no amortizaba por esa vía y el descuadre no tenía arreglo.

Abrirlo del todo tampoco vale, y ése es el riesgo que estos tests custodian: el
préstamo personal también se cobra de la misma cuenta, pero tiene su PROPIA
línea de cargo. Si entrara en el pool del agregado, avanzaría **dos** cuotas al
mes en silencio — el peor modo de fallo posible, porque el saldo baja el doble
de rápido y ningún error salta.

Lo que separa a los dos es de qué tarjeta cuelga cada uno (PHASE-35), y da igual
cómo esté tipado el hijo: el banco cobra dentro de la línea agregada justo lo
que se financió en esa tarjeta.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.personal_finance.accounts.models import Account, AccountNature, AccountType
from app.modules.personal_finance.debt.installments_repository import (
    generate_installments_for_account,
    list_installments,
)
from app.modules.personal_finance.debt.reconciliation import build_reconcile_plan
from app.modules.personal_finance.transactions.models import Transaction, TransactionFlow
from app.modules.users.models import User

_AGGREGATED = "Operacion financiada con tarjeta 4940121100185049"
_LOAN_CHARGE = "Cargo por amortizacion de prestamo/credito"


@pytest_asyncio.fixture
async def session_factory(test_engine):  # type: ignore[no-untyped-def]
    return async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)


async def _seed(session_factory):  # type: ignore[no-untyped-def]
    """Un banco, una tarjeta, una compra a plazos colgada de ella, un recibo
    aplazado dado de alta como PRÉSTAMO y suelto, y el préstamo personal."""
    uid = uuid.uuid4()
    ids = {k: uuid.uuid4() for k in ("bank", "card", "child", "deferred", "loan")}
    async with session_factory() as db:
        db.add(
            User(id=uid, email=f"e4_{uid.hex[:8]}@example.com", password_hash="x", display_name="E")
        )
        await db.flush()
        db.add(
            Account(
                id=ids["bank"],
                user_id=uid,
                name="BBVA",
                nature=AccountNature.ASSET,
                type=AccountType.BANK,
                currency="EUR",
                opening_balance=Decimal("5000"),
            )
        )
        db.add(
            Account(
                id=ids["card"],
                user_id=uid,
                name="Tarjeta",
                nature=AccountNature.LIABILITY,
                type=AccountType.CREDIT_CARD,
                currency="EUR",
                opening_balance=Decimal("0"),
            )
        )
        await db.flush()
        # Compra a plazos colgada de la tarjeta (el caso que YA funcionaba).
        child = Account(
            id=ids["child"],
            user_id=uid,
            name="Compra a plazos",
            nature=AccountNature.LIABILITY,
            type=AccountType.CREDIT_CARD,
            currency="EUR",
            opening_balance=Decimal("1200"),
            apr=Decimal("0.1000"),
            term_months=12,
            start_date=date(2026, 1, 5),
            parent_account_id=ids["card"],
        )
        # El recibo aplazado: dado de alta como PRÉSTAMO y SIN colgar de nadie.
        deferred = Account(
            id=ids["deferred"],
            user_id=uid,
            name="Recibo aplazado",
            nature=AccountNature.LIABILITY,
            type=AccountType.LOAN,
            currency="EUR",
            opening_balance=Decimal("700.26"),
            apr=Decimal("0.1800"),
            term_months=36,
            start_date=date(2026, 1, 6),
        )
        # El préstamo personal: cobra su PROPIA línea cada mes.
        loan = Account(
            id=ids["loan"],
            user_id=uid,
            name="Prestamo",
            nature=AccountNature.LIABILITY,
            type=AccountType.LOAN,
            currency="EUR",
            opening_balance=Decimal("22000"),
            apr=Decimal("0.0490"),
            term_months=120,
            start_date=date(2026, 1, 3),
        )
        for acc in (child, deferred, loan):
            db.add(acc)
        await db.flush()
        for acc in (child, deferred, loan):
            await generate_installments_for_account(db, acc)
        await db.commit()
    return uid, ids


async def _charge(session_factory, uid, bank_id, *, amount, description, day):  # type: ignore[no-untyped-def]
    async with session_factory() as db:
        db.add(
            Transaction(
                id=uuid.uuid4(),
                user_id=uid,
                account_id=bank_id,
                amount=Decimal(amount),
                currency="EUR",
                occurred_at=datetime(2026, 2, day, tzinfo=UTC),
                description=description,
                flow=TransactionFlow.OUT,
            )
        )
        await db.commit()


async def _paid(session_factory, uid, account_id) -> int:  # type: ignore[no-untyped-def]
    async with session_factory() as db:
        rows = await list_installments(db, account_id, uid)
        return sum(1 for r in rows if r.paid_at is not None)


async def _apply(session_factory, uid) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as db:
        await build_reconcile_plan(db, uid)  # calienta; el plan se recalcula al aplicar
    from app.modules.personal_finance.debt.reconciliation import reconcile_debt_payments

    async with session_factory() as db:
        await reconcile_debt_payments(db, uid, dry_run=False)
        await db.commit()


# ── El arreglo ───────────────────────────────────────────────────────


async def test_una_financiacion_colgada_de_la_tarjeta_entra_en_el_reparto(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Un pasivo tipo PRÉSTAMO que cuelga de la tarjeta cobra del cargo agregado.

    Es el caso del recibo aplazado: el banco lo vende como préstamo pero lo
    cobra dentro de la línea de la tarjeta. Antes de E4 su cuota no se atribuía
    nunca porque el pool exigía `type == CREDIT_CARD`.
    """
    uid, ids = await _seed(session_factory)
    async with session_factory() as db:
        acc = await db.get(Account, ids["deferred"])
        assert acc is not None
        acc.parent_account_id = ids["card"]
        await db.commit()

    await _charge(
        session_factory, uid, ids["bank"], amount="150.00", description=_AGGREGATED, day=4
    )
    await _apply(session_factory, uid)

    assert (
        await _paid(session_factory, uid, ids["deferred"]) == 1
    ), "la financiación colgada de la tarjeta no cobró del cargo agregado"
    assert await _paid(session_factory, uid, ids["child"]) == 1


async def test_sin_colgar_de_la_tarjeta_no_entra(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Y si no cuelga de ninguna tarjeta, no entra: el vínculo lo declara el
    usuario, no se adivina por el tipo ni por la cuenta de cargo."""
    uid, ids = await _seed(session_factory)
    await _charge(
        session_factory, uid, ids["bank"], amount="150.00", description=_AGGREGATED, day=4
    )
    await _apply(session_factory, uid)

    assert await _paid(session_factory, uid, ids["deferred"]) == 0
    assert await _paid(session_factory, uid, ids["child"]) == 1


# ── El guardarraíl: el préstamo personal NO se toca ──────────────────


async def test_el_prestamo_con_linea_propia_no_avanza_por_el_cargo_agregado(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """EL RIESGO DE LA FASE. El préstamo personal se cobra de la misma cuenta,
    pero tiene su propia línea. Si entrara en el pool del agregado avanzaría DOS
    cuotas al mes: una por su línea y otra por la de la tarjeta. El saldo
    bajaría al doble de velocidad y nada saltaría.

    Este test es la razón de que el pool sea «de qué tarjeta cuelga» y no «de
    qué cuenta se cobra».

    Y comprueba la otra mitad del arreglo: colgar el recibo aplazado de la
    tarjeta lo saca del pool de préstamos, así que el cargo de amortización
    vuelve a resolver sin ambigüedad. Sin eso, dos pasivos de tipo LOAN dejan
    ese cargo sin destino y **el préstamo de verdad no amortiza** — lo destapó
    este mismo test, fallando con 0 cuotas pagadas.
    """
    uid, ids = await _seed(session_factory)
    async with session_factory() as db:
        acc = await db.get(Account, ids["deferred"])
        assert acc is not None
        acc.parent_account_id = ids["card"]
        await db.commit()

    # Los dos cargos del mismo mes, como en el extracto real.
    await _charge(
        session_factory, uid, ids["bank"], amount="232.27", description=_LOAN_CHARGE, day=3
    )
    await _charge(
        session_factory, uid, ids["bank"], amount="150.00", description=_AGGREGATED, day=4
    )
    await _apply(session_factory, uid)

    assert (
        await _paid(session_factory, uid, ids["loan"]) == 1
    ), "el préstamo avanzó más (o menos) de una cuota: su línea propia paga UNA"
    # Y cada cargo alimentó su pool, sin cruzarse.
    assert await _paid(session_factory, uid, ids["deferred"]) == 1
    assert await _paid(session_factory, uid, ids["child"]) == 1


async def test_un_prestamo_colgado_de_la_tarjeta_sigue_cobrando_solo_una_vez(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Caso límite del anterior: aunque alguien cuelgue el préstamo personal de
    la tarjeta, sus dos cargos del mes no pueden avanzarle dos cuotas.

    Hoy lo impide que cada rama procese su propia transacción y que el agregado
    avance como mucho una cuota por plan. Si eso cambiara, este test lo caza.
    """
    uid, ids = await _seed(session_factory)
    async with session_factory() as db:
        acc = await db.get(Account, ids["loan"])
        assert acc is not None
        acc.parent_account_id = ids["card"]
        await db.commit()

    await _charge(
        session_factory, uid, ids["bank"], amount="232.27", description=_LOAN_CHARGE, day=3
    )
    await _charge(
        session_factory, uid, ids["bank"], amount="150.00", description=_AGGREGATED, day=4
    )
    await _apply(session_factory, uid)

    assert (
        await _paid(session_factory, uid, ids["loan"]) <= 1
    ), "dos cargos del mismo mes avanzaron dos cuotas del mismo préstamo"


# ── Declarar el vínculo desde la API ─────────────────────────────────


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "T"},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_se_puede_declarar_la_tarjeta_padre_despues_de_crear(
    client: AsyncClient,
) -> None:
    """Antes de E4 sólo se podía al crear, y eso dejaba sin arreglo una deuda ya
    dada de alta suelta — que es exactamente el caso real del usuario."""
    token = await _register(client, "e4_reparent@example.com")
    card = (
        await client.post(
            "/accounts",
            json={"name": "Tarjeta", "type": "credit_card", "currency": "EUR"},
            headers=_auth(token),
        )
    ).json()
    loan = (
        await client.post(
            "/accounts",
            json={
                "name": "Recibo aplazado",
                "type": "loan",
                "currency": "EUR",
                "opening_balance": "700.26",
                "apr": "0.1800",
                "term_months": 36,
                "start_date": "2026-08-06",
            },
            headers=_auth(token),
        )
    ).json()
    assert loan["parent_account_id"] is None

    r = await client.put(
        f"/accounts/{loan['id']}",
        json={"parent_account_id": card["id"]},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["parent_account_id"] == card["id"]

    # Y se puede retirar.
    r = await client.put(
        f"/accounts/{loan['id']}", json={"parent_account_id": None}, headers=_auth(token)
    )
    assert r.status_code == 200, r.text
    assert r.json()["parent_account_id"] is None


async def test_no_se_puede_colgar_de_algo_que_no_es_una_tarjeta(
    client: AsyncClient,
) -> None:
    token = await _register(client, "e4_badparent@example.com")
    bank = (
        await client.post(
            "/accounts",
            json={"name": "BBVA", "type": "bank", "currency": "EUR"},
            headers=_auth(token),
        )
    ).json()
    loan = (
        await client.post(
            "/accounts",
            json={
                "name": "Prestamo",
                "type": "loan",
                "currency": "EUR",
                "opening_balance": "1000",
                "apr": "0.05",
                "term_months": 12,
                "start_date": "2026-01-01",
            },
            headers=_auth(token),
        )
    ).json()

    r = await client.put(
        f"/accounts/{loan['id']}",
        json={"parent_account_id": bank["id"]},
        headers=_auth(token),
    )
    assert r.status_code == 400, r.text
    assert "tarjeta" in r.json()["detail"]

    r = await client.put(
        f"/accounts/{loan['id']}",
        json={"parent_account_id": loan["id"]},
        headers=_auth(token),
    )
    assert r.status_code == 400, r.text
    assert "sí misma" in r.json()["detail"]
