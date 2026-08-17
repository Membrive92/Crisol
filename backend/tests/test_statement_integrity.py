"""PHASE-47.G — la app compara su saldo con el del banco y dice dónde le falta.

El testigo lleva desde PHASE-39 en la BD (`transactions.statement_balance`, el
saldo que el banco imprimió tras cada movimiento) y sólo se escribía. Con él,
un hueco de extracto es DEMOSTRABLE: si el saldo anterior implícito de una fila
no aparece en ninguna otra, entre medias hay movimientos que no tenemos.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.personal_finance.accounts.models import Account, AccountNature, AccountType
from app.modules.personal_finance.accounts.repository import find_statement_seams
from app.modules.personal_finance.transactions.models import Transaction, TransactionFlow
from app.modules.users.models import User


@pytest_asyncio.fixture
async def session_factory(test_engine):  # type: ignore[no-untyped-def]
    return async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)


async def _seed(session_factory, filas):  # type: ignore[no-untyped-def]
    """Crea usuario + cuenta y siembra `(dia, importe, flow, saldo)`."""
    uid, aid = uuid.uuid4(), uuid.uuid4()
    async with session_factory() as db:
        db.add(
            User(
                id=uid,
                email=f"seam_{uid.hex[:8]}@example.com",
                password_hash="x",
                display_name="S",
            )
        )
        await db.flush()  # el usuario primero: la cuenta tiene FK a él
        db.add(
            Account(
                id=aid,
                user_id=uid,
                name="BBVA",
                nature=AccountNature.ASSET,
                type=AccountType.BANK,
                currency="EUR",
                opening_balance=Decimal("0"),
            )
        )
        for dia, importe, flow, saldo in filas:
            db.add(
                Transaction(
                    id=uuid.uuid4(),
                    user_id=uid,
                    account_id=aid,
                    amount=Decimal(importe),
                    currency="EUR",
                    occurred_at=(
                        datetime(2026, 6, dia, 12, 0, tzinfo=UTC)
                        if dia <= 30
                        else datetime(2026, 7, dia - 30, 12, 0, tzinfo=UTC)
                    ),
                    flow=flow,
                    statement_balance=Decimal(saldo),
                )
            )
        await db.commit()
    return uid, aid


async def test_a_continuous_statement_has_no_seams(session_factory) -> None:  # type: ignore[no-untyped-def]
    """Cadena que cuadra fila a fila: nada que avisar."""
    uid, aid = await _seed(
        session_factory,
        [
            (1, "100.00", TransactionFlow.OUT, "900.00"),
            (2, "50.00", TransactionFlow.OUT, "850.00"),
            (3, "200.00", TransactionFlow.IN, "1050.00"),
        ],
    )
    async with session_factory() as db:
        seams = await find_statement_seams(db, uid)
    assert seams.get(aid, []) == []


async def test_a_gap_between_two_statements_is_reported_with_its_amount(session_factory) -> None:  # type: ignore[no-untyped-def]
    """El caso REAL: el extracto de junio acaba el 29 y el de julio empieza el 5.

    Entre medias el banco movió 1.211,95 € que la app no tiene. No da ningún
    error por sí solo —al anclar el saldo, la diferencia se absorbe en el saldo
    inicial y la cuenta sigue cuadrando a día de hoy—, así que si no se dice, no
    se entera nadie: lo único que se rompe, en silencio, es la historia.
    """
    uid, aid = await _seed(
        session_factory,
        [
            (28, "20.00", TransactionFlow.OUT, "1953.91"),
            (29, "20.00", TransactionFlow.OUT, "1933.91"),
            # …aquí faltan movimientos por −1.211,95…
            (35, "9.00", TransactionFlow.IN, "730.96"),  # 5-jul: previo 721,96
            (35, "33.58", TransactionFlow.IN, "764.54"),
        ],
    )
    async with session_factory() as db:
        seams = await find_statement_seams(db, uid)

    encontrados = seams.get(aid, [])
    assert len(encontrados) == 1, encontrados
    seam = encontrados[0]
    assert seam.after.date() == datetime(2026, 6, 29, tzinfo=UTC).date()
    assert seam.before.date() == datetime(2026, 7, 5, tzinfo=UTC).date()
    assert seam.amount == Decimal("-1211.95")


async def test_the_oldest_row_is_not_a_gap(session_factory) -> None:  # type: ignore[no-untyped-def]
    """La primera fila rompe la cadena por definición: no hay nada antes.

    Es el guardarraíl del detector. Sin él, TODA cuenta avisaría de un hueco
    inexistente el día que se importa su primer extracto — y un aviso que sale
    siempre se deja de leer, que es la forma más cara de no tener aviso.
    """
    uid, aid = await _seed(
        session_factory,
        [
            (1, "100.00", TransactionFlow.OUT, "900.00"),
            (2, "50.00", TransactionFlow.OUT, "850.00"),
        ],
    )
    async with session_factory() as db:
        seams = await find_statement_seams(db, uid)
    assert seams.get(aid, []) == []
