"""PHASE-47.A — `accounts.settlement_account_id`: validación y propuesta.

Declara desde qué cuenta de activo se cobra un pasivo. El dato no existía y sin
él no se puede saber qué cargo cierra el ciclo de qué tarjeta (ADR-0011): el
cargo vive en la cuenta corriente, no en la deuda.

Dos frentes:

1. **Validación**: lo que no puede declararse (un activo cobrándose de otra
   cuenta, una cuenta cobrándose a sí misma, una deuda cobrándose de otra
   deuda, una cuenta de otro usuario) devuelve 400 con motivo, nunca 404 —
   un 404 filtraría la existencia de cuentas ajenas.

2. **Propuesta**: se deriva de los cargos que el usuario YA enlazó a mano
   (PHASE-45), en sus dos formas —contrapartida para un pasivo sin cuadro,
   cuota marcada para uno con cuadro—. Sin evidencia o con empate NO se
   propone: adivinar una cuenta y precargarla en el formulario convertiría una
   suposición en un dato declarado, que es la trampa de [PHASE-44.11].
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.personal_finance.accounts.models import Account, AccountNature, AccountType
from app.modules.personal_finance.debt.installments_model import LiabilityInstallment
from app.modules.personal_finance.transactions.models import Transaction, TransactionFlow
from app.modules.users.models import User


@pytest_asyncio.fixture
async def session_factory(test_engine):  # type: ignore[no-untyped-def]
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


async def _create_account(client: AsyncClient, token: str, **fields: object) -> dict:
    r = await client.post("/accounts", json=fields, headers=_auth(token))
    assert r.status_code == 201, r.text
    return dict(r.json())


# ── 1. Validación ────────────────────────────────────────────────────


async def test_liability_can_declare_the_asset_account_that_settles_it(
    client: AsyncClient,
) -> None:
    token = await _register(client, "settle_ok@example.com")
    bank = await _create_account(client, token, name="BBVA", type="bank", currency="EUR")
    card = await _create_account(
        client,
        token,
        name="Tarjeta",
        type="credit_card",
        currency="EUR",
        settlement_account_id=bank["id"],
    )
    assert card["settlement_account_id"] == bank["id"]

    # Y se puede desvincular enviando null explícito.
    r = await client.put(
        f"/accounts/{card['id']}",
        json={"settlement_account_id": None},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["settlement_account_id"] is None


async def test_asset_account_cannot_declare_a_settlement_account(
    client: AsyncClient,
) -> None:
    """Un activo no se cobra desde otra cuenta: el campo no le aplica."""
    token = await _register(client, "settle_asset@example.com")
    bank = await _create_account(client, token, name="BBVA", type="bank", currency="EUR")
    r = await client.post(
        "/accounts",
        json={
            "name": "Ahorro",
            "type": "savings",
            "currency": "EUR",
            "settlement_account_id": bank["id"],
        },
        headers=_auth(token),
    )
    assert r.status_code == 400, r.text
    assert "deuda" in r.json()["detail"]


async def test_settlement_account_must_be_an_asset(client: AsyncClient) -> None:
    """Apuntar a otra deuda no dice de dónde sale el dinero: mueve la pregunta."""
    token = await _register(client, "settle_liab@example.com")
    other_card = await _create_account(
        client, token, name="Otra tarjeta", type="credit_card", currency="EUR"
    )
    r = await client.post(
        "/accounts",
        json={
            "name": "Tarjeta",
            "type": "credit_card",
            "currency": "EUR",
            "settlement_account_id": other_card["id"],
        },
        headers=_auth(token),
    )
    assert r.status_code == 400, r.text
    assert "activo" in r.json()["detail"]


async def test_account_cannot_settle_itself(client: AsyncClient) -> None:
    token = await _register(client, "settle_self@example.com")
    card = await _create_account(client, token, name="Tarjeta", type="credit_card", currency="EUR")
    r = await client.put(
        f"/accounts/{card['id']}",
        json={"settlement_account_id": card["id"]},
        headers=_auth(token),
    )
    assert r.status_code == 400, r.text
    assert "sí misma" in r.json()["detail"]


async def test_settlement_account_of_another_user_is_rejected_as_400(
    client: AsyncClient,
) -> None:
    """400 «no existe», no 404: un 404 confirmaría que la cuenta ajena existe."""
    token_a = await _register(client, "settle_a@example.com")
    token_b = await _register(client, "settle_b@example.com")
    foreign_bank = await _create_account(
        client, token_b, name="Banco de B", type="bank", currency="EUR"
    )
    r = await client.post(
        "/accounts",
        json={
            "name": "Tarjeta de A",
            "type": "credit_card",
            "currency": "EUR",
            "settlement_account_id": foreign_bank["id"],
        },
        headers=_auth(token_a),
    )
    assert r.status_code == 400, r.text
    assert "no existe" in r.json()["detail"]


# ── 2. Propuesta derivada de los enlaces de PHASE-45 ──────────────────


async def _seed_user_bank_and_card(
    session_factory,  # type: ignore[no-untyped-def]
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Usuario + cuenta corriente + tarjeta (pasivo sin cuadro)."""
    uid, bank_id, card_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with session_factory() as db:
        db.add(
            User(id=uid, email=f"s_{uid.hex[:8]}@example.com", password_hash="x", display_name="S")
        )
        await db.flush()
        db.add(
            Account(
                id=bank_id,
                user_id=uid,
                name="BBVA",
                nature=AccountNature.ASSET,
                type=AccountType.BANK,
                currency="EUR",
                opening_balance=Decimal("1000"),
            )
        )
        db.add(
            Account(
                id=card_id,
                user_id=uid,
                name="Tarjeta BBVA",
                nature=AccountNature.LIABILITY,
                type=AccountType.CREDIT_CARD,
                currency="EUR",
                opening_balance=Decimal("0"),
            )
        )
        await db.commit()
    return uid, bank_id, card_id


async def _add_amortization_link(
    session_factory,  # type: ignore[no-untyped-def]
    *,
    user_id: uuid.UUID,
    charge_account_id: uuid.UUID,
    liability_id: uuid.UUID,
    amount: str,
) -> None:
    """Un cargo en `charge_account_id` + su contrapartida en la deuda (PHASE-45)."""
    async with session_factory() as db:
        charge = Transaction(
            id=uuid.uuid4(),
            user_id=user_id,
            account_id=charge_account_id,
            amount=Decimal(amount),
            currency="EUR",
            occurred_at=datetime(2026, 7, 8, tzinfo=UTC),
            description="Adeudo mensual de tarjeta",
            flow=TransactionFlow.OUT,
        )
        db.add(charge)
        await db.flush()
        db.add(
            Transaction(
                id=uuid.uuid4(),
                user_id=user_id,
                account_id=liability_id,
                amount=Decimal(amount),
                currency="EUR",
                occurred_at=datetime(2026, 7, 8, tzinfo=UTC),
                description="Amortización",
                flow=TransactionFlow.TRANSFER_IN,
                amortization_source_id=charge.id,
            )
        )
        await db.commit()


async def test_no_links_means_no_suggestion(
    client: AsyncClient,
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Sin evidencia no se propone nada. Proponer aquí sería adivinar."""
    from app.modules.personal_finance.debt.attribution import suggest_settlement_account

    uid, _bank_id, card_id = await _seed_user_bank_and_card(session_factory)
    async with session_factory() as db:
        suggestion = await suggest_settlement_account(db, uid, card_id)
    assert suggestion.account_id is None
    assert suggestion.reason is None
    assert suggestion.total == 0


async def test_suggestion_from_counterpart_links(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Pasivo SIN cuadro: los cargos llegan por `amortization_source_id`."""
    from app.modules.personal_finance.debt.attribution import suggest_settlement_account

    uid, bank_id, card_id = await _seed_user_bank_and_card(session_factory)
    for amount in ("406.33", "384.38"):
        await _add_amortization_link(
            session_factory,
            user_id=uid,
            charge_account_id=bank_id,
            liability_id=card_id,
            amount=amount,
        )
    async with session_factory() as db:
        suggestion = await suggest_settlement_account(db, uid, card_id)
    assert suggestion.account_id == bank_id
    assert suggestion.matches == 2
    assert suggestion.total == 2
    assert suggestion.reason is not None
    assert "BBVA" in suggestion.reason


async def test_suggestion_from_paid_installments(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Pasivo CON cuadro: no hay contrapartida, el cargo vive en la cuota.

    Las dos formas cuentan porque cuál se usó depende de si el pasivo tiene
    cuadro, no de dónde sale el dinero — mirar sólo una dejaría a la mitad de
    los pasivos sin propuesta.
    """
    from app.modules.personal_finance.debt.attribution import suggest_settlement_account

    uid, bank_id, card_id = await _seed_user_bank_and_card(session_factory)
    async with session_factory() as db:
        charge = Transaction(
            id=uuid.uuid4(),
            user_id=uid,
            account_id=bank_id,
            amount=Decimal("164.94"),
            currency="EUR",
            occurred_at=datetime(2026, 7, 15, tzinfo=UTC),
            description="Cuota préstamo",
            flow=TransactionFlow.OUT,
        )
        db.add(charge)
        await db.flush()
        db.add(
            LiabilityInstallment(
                id=uuid.uuid4(),
                user_id=uid,
                account_id=card_id,
                installment_index=1,
                due_date=datetime(2026, 7, 15, tzinfo=UTC).date(),
                payment=Decimal("164.94"),
                interest=Decimal("4.94"),
                principal=Decimal("160.00"),
                remaining_balance=Decimal("840.00"),
                paid_at=datetime(2026, 7, 15, tzinfo=UTC),
                paid_transaction_id=charge.id,
            )
        )
        await db.commit()
    async with session_factory() as db:
        suggestion = await suggest_settlement_account(db, uid, card_id)
    assert suggestion.account_id == bank_id
    assert suggestion.matches == 1


async def test_tie_between_two_accounts_proposes_nothing(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Empate → no se elige. Con dos cuentas igual de respaldadas, decidir
    sería una moneda al aire disfrazada de dato (ADR-0011 punto 5)."""
    from app.modules.personal_finance.debt.attribution import suggest_settlement_account

    uid, bank_id, card_id = await _seed_user_bank_and_card(session_factory)
    second_bank = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            Account(
                id=second_bank,
                user_id=uid,
                name="Santander",
                nature=AccountNature.ASSET,
                type=AccountType.BANK,
                currency="EUR",
                opening_balance=Decimal("500"),
            )
        )
        await db.commit()
    await _add_amortization_link(
        session_factory,
        user_id=uid,
        charge_account_id=bank_id,
        liability_id=card_id,
        amount="100.00",
    )
    await _add_amortization_link(
        session_factory,
        user_id=uid,
        charge_account_id=second_bank,
        liability_id=card_id,
        amount="200.00",
    )
    async with session_factory() as db:
        suggestion = await suggest_settlement_account(db, uid, card_id)
    assert suggestion.account_id is None
    assert suggestion.total == 2  # hay evidencia, pero no señala a una sola


async def test_majority_wins_and_the_reason_counts_it(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Con mayoría clara sí se propone, y el motivo lleva el recuento dentro:
    una propuesta sin su evidencia es una opinión que el usuario no puede
    calibrar."""
    from app.modules.personal_finance.debt.attribution import suggest_settlement_account

    uid, bank_id, card_id = await _seed_user_bank_and_card(session_factory)
    second_bank = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            Account(
                id=second_bank,
                user_id=uid,
                name="Santander",
                nature=AccountNature.ASSET,
                type=AccountType.BANK,
                currency="EUR",
                opening_balance=Decimal("500"),
            )
        )
        await db.commit()
    for _ in range(3):
        await _add_amortization_link(
            session_factory,
            user_id=uid,
            charge_account_id=bank_id,
            liability_id=card_id,
            amount="100.00",
        )
    await _add_amortization_link(
        session_factory,
        user_id=uid,
        charge_account_id=second_bank,
        liability_id=card_id,
        amount="200.00",
    )
    async with session_factory() as db:
        suggestion = await suggest_settlement_account(db, uid, card_id)
    assert suggestion.account_id == bank_id
    assert suggestion.matches == 3
    assert suggestion.total == 4
    assert suggestion.reason == "3 de los 4 cargos que amortizan esta deuda salen de «BBVA»"


async def test_one_charge_that_covers_many_installments_votes_once(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Un cargo que cubre VARIAS cuotas cuenta como UN cargo.

    `plan_installments_covering_principal` marca N cuotas con el mismo
    `paid_transaction_id`, así que contar cuotas inflaba la frase que ve el
    usuario («12 de 12 cargos» cuando hubo uno) y podía deshacer un empate
    real: una cuenta con un cargo que cubre cinco cuotas ganaba a otra con
    cuatro cargos de verdad.
    """
    from app.modules.personal_finance.debt.attribution import suggest_settlement_account

    uid, bank_id, card_id = await _seed_user_bank_and_card(session_factory)
    async with session_factory() as db:
        charge = Transaction(
            id=uuid.uuid4(),
            user_id=uid,
            account_id=bank_id,
            amount=Decimal("500.00"),
            currency="EUR",
            occurred_at=datetime(2026, 7, 15, tzinfo=UTC),
            description="Pago de principal",
            flow=TransactionFlow.OUT,
        )
        db.add(charge)
        await db.flush()
        for index in range(1, 6):
            db.add(
                LiabilityInstallment(
                    id=uuid.uuid4(),
                    user_id=uid,
                    account_id=card_id,
                    installment_index=index,
                    due_date=datetime(2026, index, 15, tzinfo=UTC).date(),
                    payment=Decimal("100.00"),
                    interest=Decimal("0.00"),
                    principal=Decimal("100.00"),
                    remaining_balance=Decimal("0.00"),
                    paid_at=datetime(2026, 7, 15, tzinfo=UTC),
                    paid_transaction_id=charge.id,
                )
            )
        await db.commit()
    async with session_factory() as db:
        suggestion = await suggest_settlement_account(db, uid, card_id)
    assert suggestion.matches == 1, "cinco cuotas del mismo cargo cuentan como un cargo"
    assert suggestion.total == 1
    assert suggestion.reason == "el cargo que amortiza esta deuda sale de «BBVA»"


async def test_converting_the_settlement_account_into_a_liability_unlinks_it(
    client: AsyncClient,
) -> None:
    """Si la cuenta de cargo deja de ser un activo, el vínculo se deshace.

    Nadie revalida las referencias ENTRANTES, así que sin esto la conversión
    dejaba a los pasivos apuntando a algo que el propio validador rechaza: la
    siguiente edición de cada uno devolvía 400 sobre un campo que el formulario
    pinta como válido, y no había forma de arreglarlo desde la interfaz.
    """
    token = await _register(client, "settle_convert@example.com")
    bank = await _create_account(client, token, name="BBVA", type="bank", currency="EUR")
    card = await _create_account(
        client,
        token,
        name="Tarjeta",
        type="credit_card",
        currency="EUR",
        settlement_account_id=bank["id"],
    )
    assert card["settlement_account_id"] == bank["id"]

    # La cuenta de cargo pasa a ser una tarjeta (deja de ser activo).
    r = await client.put(
        f"/accounts/{bank['id']}",
        json={"type": "credit_card"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text

    # El pasivo queda desvinculado, y editarlo sigue funcionando.
    r = await client.get(f"/accounts/{card['id']}", headers=_auth(token))
    assert r.json()["settlement_account_id"] is None
    r = await client.put(
        f"/accounts/{card['id']}", json={"name": "Tarjeta BBVA"}, headers=_auth(token)
    )
    assert r.status_code == 200, r.text


async def test_a_liability_that_becomes_an_asset_drops_its_own_link(
    client: AsyncClient,
) -> None:
    """Y el reverso: una cuenta que deja de ser deuda no se cobra de nadie.

    Sin esto el vínculo quedaba persistido e invisible, y volver a convertirla
    en pasivo lo resucitaba."""
    token = await _register(client, "settle_unconvert@example.com")
    bank = await _create_account(client, token, name="BBVA", type="bank", currency="EUR")
    card = await _create_account(
        client,
        token,
        name="Tarjeta",
        type="credit_card",
        currency="EUR",
        settlement_account_id=bank["id"],
    )
    r = await client.put(f"/accounts/{card['id']}", json={"type": "savings"}, headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["settlement_account_id"] is None


async def test_endpoint_returns_the_suggestion_and_404_for_a_foreign_account(
    client: AsyncClient,
) -> None:
    token_a = await _register(client, "settle_ep_a@example.com")
    token_b = await _register(client, "settle_ep_b@example.com")
    card = await _create_account(
        client, token_a, name="Tarjeta", type="credit_card", currency="EUR"
    )
    r = await client.get(f"/accounts/{card['id']}/settlement-candidate", headers=_auth(token_a))
    assert r.status_code == 200, r.text
    assert r.json() == {
        "account_id": None,
        "account_name": None,
        "reason": None,
        "matches": 0,
        "total": 0,
    }
    # Aislamiento: la cuenta de otro usuario no existe para B.
    r = await client.get(f"/accounts/{card['id']}/settlement-candidate", headers=_auth(token_b))
    assert r.status_code == 404


async def test_named_routes_still_resolve_after_the_parametric_one(
    client: AsyncClient,
) -> None:
    """D13 — `/accounts/{account_id}` está declarada DESPUÉS de las nombradas.

    FastAPI resuelve por orden de declaración: si la paramétrica subiera, se
    tragaría `/accounts/balances` intentando parsear «balances» como UUID y
    devolvería 422. Este test es el que impide que alguien la mueva.
    """
    token = await _register(client, "settle_routes@example.com")
    for path in ("/accounts/balances", "/accounts/debt-health"):
        r = await client.get(path, headers=_auth(token))
        assert r.status_code == 200, f"{path} → {r.status_code} {r.text}"
