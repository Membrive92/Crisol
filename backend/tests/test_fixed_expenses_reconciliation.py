"""Tests de reconciliación import ↔ tx expected (PHASE-17.3)."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.personal_finance.fixed_expenses.models import FixedExpense
from app.modules.personal_finance.fixed_expenses.reconciliation import (
    reconcile_with_expected,
)
from app.modules.personal_finance.fixed_expenses.service import (
    autopost_due_for_user,
)
from app.modules.personal_finance.transactions.models import (
    Transaction,
    TransactionSource,
)


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


async def _create_expected_tx(
    client: AsyncClient,
    token: str,
    cat_id: str,
    account_id: str,
    test_engine,
    *,
    occurred_at: date,
    amount: str = "800.00",
    description: str = "HIPOTECA SANTANDER",
) -> tuple[str, str]:
    """Crea un fixed_expense confirmado con auto_post=True, fuerza
    next_due al pasado y dispara autopost para que cree la tx
    expected. Devuelve (fid, expected_tx_id)."""
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
                "description": description,
            },
            headers=_auth(token),
        )
    await client.post("/fixed-expenses/scan", headers=_auth(token))
    item = (await client.get("/fixed-expenses", headers=_auth(token))).json()[0]
    fid = item["id"]
    await client.post(f"/fixed-expenses/{fid}/confirm", headers=_auth(token))
    await client.put(
        f"/fixed-expenses/{fid}",
        json={"auto_post": True, "account_id": account_id},
        headers=_auth(token),
    )

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        fx = (
            await db.execute(select(FixedExpense).where(FixedExpense.id == fid))
        ).scalar_one()
        fx.next_due = occurred_at
        await db.commit()
        result = await autopost_due_for_user(db, fx.user_id, today=today)
        await db.commit()
        assert result.created >= 1

        # ID de la tx expected creada por autopost.
        tx = (
            await db.execute(
                select(Transaction)
                .where(Transaction.user_id == fx.user_id)
                .where(Transaction.source == TransactionSource.EXPECTED)
            )
        ).scalars().first()
        assert tx is not None
        return fid, str(tx.id)


def _make_csv(rows: list[tuple[str, str, str]]) -> bytes:
    """rows: (occurred_at_iso, amount, description)."""
    lines = ["fecha,importe,descripcion"]
    for occ, amt, desc in rows:
        lines.append(f"{occ},{amt},{desc}")
    return "\n".join(lines).encode("utf-8")


def _import_payload(cat_id: str, account_id: str) -> dict:
    """Form data para POST /imports — column_mappings como JSON string."""
    import json as _json

    return {
        "account_id": account_id,
        "currency": "EUR",
        "default_category_id": cat_id,
        "column_mappings": _json.dumps(
            {
                "amount": "importe",
                "occurred_at": "fecha",
                "description": "descripcion",
            }
        ),
    }


async def test_reconcile_returns_existing_when_match(
    client: AsyncClient, test_engine
) -> None:
    """Tx expected creada por autopost → import con merchant + amount +
    fecha próximos → devuelve la expected existente con import_hash y
    description actualizada. NO crea fila nueva."""
    token, cat_id, account_id = await _setup_user(client, "rec1@example.com")
    today = date.today()
    yesterday = today - timedelta(days=1)
    fid, expected_tx_id = await _create_expected_tx(
        client, token, cat_id, account_id, test_engine, occurred_at=yesterday
    )

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        # Token user_id
        from app.modules.users.models import User

        user = (
            await db.execute(select(User).where(User.email == "rec1@example.com"))
        ).scalar_one()

        match = await reconcile_with_expected(
            db,
            user.id,
            account_id=uuid.UUID(account_id),
            occurred_at=datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC),
            amount=Decimal("800.00"),
            currency="EUR",
            description="HIPOTECA SANTANDER OFICINA 1234",  # más detallado, mismo prefijo
            import_hash="hash_123",
        )
        assert match is not None
        assert str(match.id) == expected_tx_id
        assert match.import_hash == "hash_123"
        assert match.description == "HIPOTECA SANTANDER OFICINA 1234"
        assert match.source == TransactionSource.EXPECTED  # no cambia source
        await db.commit()


async def test_reconcile_no_match_when_amount_differs(
    client: AsyncClient, test_engine
) -> None:
    """Mismo merchant + fecha pero amount distinto → no match."""
    token, cat_id, account_id = await _setup_user(client, "rec2@example.com")
    today = date.today()
    yesterday = today - timedelta(days=1)
    await _create_expected_tx(
        client, token, cat_id, account_id, test_engine, occurred_at=yesterday, amount="800.00"
    )

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        from app.modules.users.models import User

        user = (
            await db.execute(select(User).where(User.email == "rec2@example.com"))
        ).scalar_one()

        match = await reconcile_with_expected(
            db,
            user.id,
            account_id=uuid.UUID(account_id),
            occurred_at=datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC),
            amount=Decimal("750.00"),  # distinto
            currency="EUR",
            description="HIPOTECA SANTANDER",
            import_hash="hash_x",
        )
        assert match is None


async def test_reconcile_no_match_when_outside_date_window(
    client: AsyncClient, test_engine
) -> None:
    """Fuera de ±3 días → no match."""
    token, cat_id, account_id = await _setup_user(client, "rec3@example.com")
    today = date.today()
    long_ago = today - timedelta(days=10)
    await _create_expected_tx(
        client, token, cat_id, account_id, test_engine, occurred_at=long_ago
    )

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        from app.modules.users.models import User

        user = (
            await db.execute(select(User).where(User.email == "rec3@example.com"))
        ).scalar_one()

        match = await reconcile_with_expected(
            db,
            user.id,
            account_id=uuid.UUID(account_id),
            occurred_at=datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC),
            amount=Decimal("800.00"),
            currency="EUR",
            description="HIPOTECA SANTANDER",
            import_hash="hash_x",
        )
        assert match is None


async def test_reconcile_no_match_when_merchant_different(
    client: AsyncClient, test_engine
) -> None:
    """Mismo amount + fecha pero merchant sin prefijo común → no match."""
    token, cat_id, account_id = await _setup_user(client, "rec4@example.com")
    today = date.today()
    yesterday = today - timedelta(days=1)
    await _create_expected_tx(
        client, token, cat_id, account_id, test_engine, occurred_at=yesterday
    )

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        from app.modules.users.models import User

        user = (
            await db.execute(select(User).where(User.email == "rec4@example.com"))
        ).scalar_one()

        match = await reconcile_with_expected(
            db,
            user.id,
            account_id=uuid.UUID(account_id),
            occurred_at=datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC),
            amount=Decimal("800.00"),
            currency="EUR",
            description="MERCADONA COMPRA",  # nada que ver
            import_hash="hash_x",
        )
        assert match is None


async def test_reconcile_skips_already_reconciled(
    client: AsyncClient, test_engine
) -> None:
    """Una expected con import_hash ya asignado no se vuelve a
    reconciliar (no debería matchear dos imports al mismo evento)."""
    token, cat_id, account_id = await _setup_user(client, "rec5@example.com")
    today = date.today()
    yesterday = today - timedelta(days=1)
    fid, expected_tx_id = await _create_expected_tx(
        client, token, cat_id, account_id, test_engine, occurred_at=yesterday
    )

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        from app.modules.users.models import User

        tx = (
            await db.execute(
                select(Transaction).where(Transaction.id == expected_tx_id)
            )
        ).scalar_one()
        tx.import_hash = "first_import"
        await db.commit()

        user = (
            await db.execute(select(User).where(User.email == "rec5@example.com"))
        ).scalar_one()

        match = await reconcile_with_expected(
            db,
            user.id,
            account_id=uuid.UUID(account_id),
            occurred_at=datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC),
            amount=Decimal("800.00"),
            currency="EUR",
            description="HIPOTECA SANTANDER",
            import_hash="second_import",
        )
        assert match is None


async def test_imports_pipeline_reconciles_expected_via_csv(
    client: AsyncClient, test_engine
) -> None:
    """Un CSV importado que coincide con una expected reconcilia en
    lugar de crear duplicada (smoke del pipeline completo)."""
    token, cat_id, account_id = await _setup_user(client, "rec_pipe@example.com")
    today = date.today()
    yesterday = today - timedelta(days=1)
    fid, expected_tx_id = await _create_expected_tx(
        client, token, cat_id, account_id, test_engine, occurred_at=yesterday
    )

    csv = _make_csv(
        [(today.isoformat(), "800.00", "HIPOTECA SANTANDER OFICINA 1234")]
    )
    files = {"file": ("hipoteca.csv", io.BytesIO(csv), "text/csv")}
    r = await client.post(
        "/imports",
        data=_import_payload(cat_id, account_id),
        files=files,
        headers=_auth(token),
    )
    assert r.status_code == 201
    job = r.json()
    assert job["status"] == "completed"
    # rows_ok = 1 porque cuenta tanto inserted como reconciled.
    assert job["rows_ok"] == 1

    # Verifica que NO hay duplicado: sólo una tx con ese amount/fecha.
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        rows = (
            await db.execute(
                select(Transaction).where(
                    Transaction.amount == Decimal("800.00"),
                    Transaction.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        # Sólo la expected reconciliada (los 4 cargos seedeados son
        # parte del histórico que el detector usó, pero no son de
        # 800.00 si tienen fecha distinta — sí tienen). Así que sólo
        # contamos las del intervalo de reconciliación.
        # La expected ahora tiene import_hash; las otras 4 son tx
        # manuales source=manual.
        reconciled = [
            t for t in rows
            if t.source == TransactionSource.EXPECTED and t.import_hash is not None
        ]
        assert len(reconciled) == 1
        assert str(reconciled[0].id) == expected_tx_id
