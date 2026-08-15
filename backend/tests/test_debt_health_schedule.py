"""PHASE-37 — debt-health deriva interés y deuda viva del CUADRO de
amortización, no de transacciones en categorías de interés (que están
vacías porque el banco no desglosa el interés: va dentro de la cuota).

MUX por pasivo: para una liability CON cuadro el interés sale del cuadro;
para una SIN cuadro, de sus transacciones `role=DEBT_INTEREST`. Nunca
ambos para la misma deuda (XOR, sin doble conteo — lección PHASE-34).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.personal_finance.accounts.models import Account, AccountNature, AccountType
from app.modules.personal_finance.categories.models import Category, CategoryKind, CategoryRole
from app.modules.personal_finance.debt.health import compute_debt_health
from app.modules.personal_finance.debt.installments_model import LiabilityInstallment
from app.modules.personal_finance.debt.installments_repository import (
    generate_installments_for_account,
    list_installments,
)
from app.modules.personal_finance.debt.repository import debt_movement_bounds
from app.modules.personal_finance.transactions.models import Transaction, TransactionFlow
from app.modules.users.models import User

_YEAR = datetime.now(UTC).year


@pytest_asyncio.fixture
async def session_factory(test_engine):  # type: ignore[no-untyped-def]
    return async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)


async def _setup_loan(session_factory) -> tuple[uuid.UUID, uuid.UUID]:  # type: ignore[no-untyped-def]
    """Usuario con un préstamo (cuadro francés) y sus 3 primeras cuotas
    marcadas pagadas en enero de este año."""
    uid = uuid.uuid4()
    aid = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            User(id=uid, email=f"dh_{uid.hex[:8]}@example.com", password_hash="x", display_name="D")
        )
        await db.flush()
        acc = Account(
            id=aid,
            user_id=uid,
            name="Préstamo",
            nature=AccountNature.LIABILITY,
            type=AccountType.LOAN,
            currency="EUR",
            opening_balance=Decimal("12000"),
            apr=Decimal("0.05"),
            term_months=12,
            start_date=date(_YEAR, 1, 1),
        )
        db.add(acc)
        await db.flush()
        insts = await generate_installments_for_account(db, acc)
        for i in range(3):
            insts[i].paid_at = datetime(_YEAR, 1, 15, tzinfo=UTC)
        await db.commit()
    return uid, aid


async def test_interest_and_debt_from_schedule(session_factory) -> None:  # type: ignore[no-untyped-def]
    uid, aid = await _setup_loan(session_factory)
    async with session_factory() as db:
        insts = await list_installments(db, aid, uid)
        exp_ytd = sum((i.interest for i in insts if i.paid_at is not None), Decimal("0"))
        exp_total = sum((i.interest for i in insts), Decimal("0"))
        exp_remaining = sum((i.interest for i in insts if i.paid_at is None), Decimal("0"))
        exp_outstanding = sum((i.principal for i in insts if i.paid_at is None), Decimal("0"))
        k = await compute_debt_health(db, uid)

    q = Decimal("0.01")
    assert exp_ytd > 0  # sanity: el cuadro SÍ tiene interés (antes salía 0)
    assert k.interest_paid_ytd == exp_ytd.quantize(q)
    assert k.interest_scheduled_total == exp_total.quantize(q)
    assert k.interest_remaining == exp_remaining.quantize(q)
    assert k.total_liabilities == exp_outstanding.quantize(q)
    # Composición de deuda viva por tipo: un único préstamo.
    assert [(s.type, s.amount) for s in k.debt_by_type] == [("loan", exp_outstanding.quantize(q))]


async def test_debt_movement_bounds_include_schedule(session_factory) -> None:  # type: ignore[no-untyped-def]
    """PHASE-37 (follow-up) — el navegador de período toma sus límites también
    del cuadro (due_date de cuotas <= hoy), no sólo de transacciones de deuda:
    un préstamo sin tx de deuda ya no deja el navegador en (None, None)."""
    uid, _aid = await _setup_loan(session_factory)  # préstamo, sin tx de deuda
    async with session_factory() as db:
        lo, hi = await debt_movement_bounds(db, uid, "EUR")
    today = datetime.now(UTC).date()
    assert lo is not None and hi is not None
    assert lo.year == _YEAR  # arranca en el año del préstamo
    assert hi <= today  # no empuja el navegador a cuotas futuras


async def test_debt_movement_bounds_excludes_unpaid_due_installments(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """PHASE-43.x — una cuota sólo VENCIDA pero impaga (p. ej. el mes en curso
    aún sin importar el extracto) NO extiende el navegador: el límite superior
    es la última cuota PAGADA, no la última vencida. Así no se puede seleccionar
    un mes sin datos reales. Fechas del año pasado → siempre <= hoy, sin que el
    test dependa de la fecha de ejecución."""
    uid = uuid.uuid4()
    aid = uuid.uuid4()
    last_year = _YEAR - 1
    async with session_factory() as db:
        db.add(
            User(id=uid, email=f"b_{uid.hex[:8]}@example.com", password_hash="x", display_name="B")
        )
        await db.flush()
        db.add(
            Account(
                id=aid,
                user_id=uid,
                name="Préstamo",
                nature=AccountNature.LIABILITY,
                type=AccountType.LOAN,
                currency="EUR",
                opening_balance=Decimal("1000"),
                apr=Decimal("0.05"),
                term_months=2,
                start_date=date(last_year, 1, 1),
            )
        )
        await db.flush()
        db.add(
            LiabilityInstallment(
                user_id=uid,
                account_id=aid,
                installment_index=1,
                due_date=date(last_year, 3, 1),
                payment=Decimal("100"),
                interest=Decimal("5"),
                principal=Decimal("95"),
                remaining_balance=Decimal("905"),
                paid_at=datetime(last_year, 3, 1, tzinfo=UTC),  # PAGADA
            )
        )
        db.add(
            LiabilityInstallment(
                user_id=uid,
                account_id=aid,
                installment_index=2,
                due_date=date(last_year, 6, 1),  # posterior y <= hoy…
                payment=Decimal("100"),
                interest=Decimal("4"),
                principal=Decimal("96"),
                remaining_balance=Decimal("809"),
                paid_at=None,  # …pero IMPAGA → no debe contar
            )
        )
        await db.commit()
    async with session_factory() as db:
        _lo, hi = await debt_movement_bounds(db, uid, "EUR")
    # La cuota impaga de junio (posterior) queda excluida → el límite es marzo.
    assert hi == date(last_year, 3, 1)


async def test_interest_tx_on_scheduled_liability_not_double_counted(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Una tx DEBT_INTEREST EN la cuenta con cuadro NO se suma al interés:
    su interés ya sale del cuadro (XOR)."""
    uid, aid = await _setup_loan(session_factory)
    async with session_factory() as db:
        insts = await list_installments(db, aid, uid)
        sched_ytd = sum(
            (i.interest for i in insts if i.paid_at is not None), Decimal("0")
        ).quantize(Decimal("0.01"))
        cat = Category(
            user_id=uid,
            name="Intereses préstamo",
            kind=CategoryKind.EXPENSE,
            role=CategoryRole.DEBT_INTEREST,
        )
        db.add(cat)
        await db.flush()
        db.add(
            Transaction(
                user_id=uid,
                account_id=aid,
                amount=Decimal("99.00"),
                currency="EUR",
                occurred_at=datetime(_YEAR, 4, 1, tzinfo=UTC),
                category_id=cat.id,
                flow=TransactionFlow.OUT,
            )
        )
        await db.commit()
        k = await compute_debt_health(db, uid)

    assert k.interest_paid_ytd == sched_ytd  # el 99 NO se cuenta


async def test_interest_tx_on_non_scheduled_liability_counts(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Una tx DEBT_INTEREST en una cuenta SIN cuadro (tarjeta sin plan) SÍ
    cuenta — es la única fuente de su interés."""
    uid = uuid.uuid4()
    card_id = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            User(id=uid, email=f"dh_{uid.hex[:8]}@example.com", password_hash="x", display_name="D")
        )
        await db.flush()
        db.add(
            Account(
                id=card_id,
                user_id=uid,
                name="Tarjeta",
                nature=AccountNature.LIABILITY,
                type=AccountType.CREDIT_CARD,
                currency="EUR",
                opening_balance=Decimal("500"),
            )
        )
        cat = Category(
            user_id=uid,
            name="Intereses tarjeta",
            kind=CategoryKind.EXPENSE,
            role=CategoryRole.DEBT_INTEREST,
        )
        db.add(cat)
        await db.flush()
        db.add(
            Transaction(
                user_id=uid,
                account_id=card_id,
                amount=Decimal("12.00"),
                currency="EUR",
                occurred_at=datetime(_YEAR, 4, 1, tzinfo=UTC),
                category_id=cat.id,
                flow=TransactionFlow.OUT,
            )
        )
        await db.commit()
        k = await compute_debt_health(db, uid)

    assert k.interest_paid_ytd == Decimal("12.00")  # sin cuadro → cuenta la tx
