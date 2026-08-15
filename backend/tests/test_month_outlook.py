"""PHASE-37.4 — Proyección de fin de mes + runway.

Cubre: exclusión de cuentas no líquidas del colchón, el conjunto de cargos
comprometidos (gastos fijos + cuotas del mes, con MUX para no doblar los
gastos fijos apuntados a un pasivo con cuadro), la ventana del mes en curso
(no arrastra impagos de meses anteriores), el flag `overdue` y el runway
`None` sin base estructural.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.personal_finance.accounts.models import Account, AccountNature, AccountType
from app.modules.personal_finance.analytics.service import get_month_outlook
from app.modules.personal_finance.categories.models import Category, CategoryKind
from app.modules.personal_finance.debt.installments_model import LiabilityInstallment
from app.modules.personal_finance.fixed_expenses.models import FixedExpense, FixedExpenseStatus
from app.modules.personal_finance.transactions.models import Transaction, TransactionFlow
from app.modules.users.models import User


def _shift_month(d: date, months_back: int) -> date:
    total = (d.year * 12 + (d.month - 1)) - months_back
    year, month0 = divmod(total, 12)
    return date(year, month0 + 1, 15)


_TODAY = datetime.now(UTC).date()
_MONTH_START = date(_TODAY.year, _TODAY.month, 1)


@pytest_asyncio.fixture
async def session_factory(test_engine):  # type: ignore[no-untyped-def]
    return async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)


async def _seed_user(session_factory) -> uuid.UUID:  # type: ignore[no-untyped-def]
    uid = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            User(id=uid, email=f"mo_{uid.hex[:8]}@example.com", password_hash="x", display_name="M")
        )
        await db.commit()
    return uid


def _account(uid: uuid.UUID, **kw: object) -> Account:
    base: dict[str, object] = {
        "id": uuid.uuid4(),
        "user_id": uid,
        "currency": "EUR",
        "opening_balance": Decimal("0"),
    }
    base.update(kw)
    return Account(**base)  # type: ignore[arg-type]


async def test_liquid_balance_excludes_non_liquid(session_factory) -> None:  # type: ignore[no-untyped-def]
    """Sólo bank/savings/cash cuentan como colchón; brokerage/crypto no."""
    uid = await _seed_user(session_factory)
    async with session_factory() as db:
        db.add(
            _account(
                uid,
                name="BBVA",
                nature=AccountNature.ASSET,
                type=AccountType.BANK,
                opening_balance=Decimal("1000"),
            )
        )
        db.add(
            _account(
                uid,
                name="IBKR",
                nature=AccountNature.ASSET,
                type=AccountType.BROKERAGE,
                opening_balance=Decimal("5000"),
            )
        )
        await db.commit()
        m = await get_month_outlook(db, uid, currency="EUR")
    assert m.liquid_balance == Decimal("1000.00")  # brokerage fuera


async def test_committed_items_month_window(session_factory) -> None:  # type: ignore[no-untyped-def]
    """Cargos comprometidos = cuotas del mes (sin pagar) + gastos fijos del
    mes; NO la cuota de un mes anterior (ventana del mes en curso). No se
    de-duplica por cuenta: un gasto fijo es un cargo legítimo aunque apunte a
    una cuenta con cuadro."""
    uid = await _seed_user(session_factory)
    loan_id = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            _account(
                uid,
                name="Cuenta",
                nature=AccountNature.ASSET,
                type=AccountType.BANK,
                opening_balance=Decimal("3000"),
            )
        )
        db.add(
            _account(
                uid,
                id=loan_id,
                name="Préstamo",
                nature=AccountNature.LIABILITY,
                type=AccountType.LOAN,
                apr=Decimal("0.05"),
                term_months=12,
                start_date=_MONTH_START,
            )
        )
        await db.flush()
        # Cuota de ESTE mes sin pagar (día 1) + cuota de un mes anterior sin pagar.
        last_month_end = _MONTH_START - timedelta(days=1)
        db.add(
            LiabilityInstallment(
                user_id=uid,
                account_id=loan_id,
                installment_index=1,
                due_date=_MONTH_START,
                payment=Decimal("200"),
                interest=Decimal("20"),
                principal=Decimal("180"),
                remaining_balance=Decimal("1000"),
                paid_at=None,
            )
        )
        db.add(
            LiabilityInstallment(
                user_id=uid,
                account_id=loan_id,
                installment_index=0,
                due_date=last_month_end,
                payment=Decimal("200"),
                interest=Decimal("22"),
                principal=Decimal("178"),
                remaining_balance=Decimal("1180"),
                paid_at=None,
            )
        )
        # Gasto fijo del mes (día 15) + gasto fijo apuntado al préstamo (MUX out).
        mid = date(_TODAY.year, _TODAY.month, 15)
        db.add(_fixed(uid, "Netflix", Decimal("13.99"), next_due=mid))
        db.add(_fixed(uid, "Cuota banco", Decimal("200"), next_due=mid, account_id=loan_id))
        await db.commit()
        m = await get_month_outlook(db, uid, currency="EUR")

    names = {i.name for i in m.committed_items}
    assert "Préstamo" in names  # cuota del mes
    assert "Netflix" in names  # gasto fijo del mes
    assert "Cuota banco" in names  # gasto fijo del mes (sin de-dup por cuenta)
    # La cuota del mes anterior no arrastra (una sola "Préstamo").
    assert sum(1 for i in m.committed_items if i.name == "Préstamo") == 1
    # committed_remaining == Σ de los items.
    assert m.committed_remaining == sum((i.amount for i in m.committed_items), Decimal("0"))
    # overdue coherente con la fecha respecto a hoy.
    for it in m.committed_items:
        assert it.overdue == (it.expected_date < _TODAY)


async def test_runway_positive_happy_path(session_factory) -> None:  # type: ignore[no-untyped-def]
    """Con colchón líquido y gasto estructural recurrente → runway > 0."""
    uid = await _seed_user(session_factory)
    bbva_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            _account(
                uid,
                id=bbva_id,
                name="BBVA",
                nature=AccountNature.ASSET,
                type=AccountType.BANK,
                opening_balance=Decimal("1200"),
            )
        )
        db.add(Category(id=cat_id, user_id=uid, name="Supermercado", kind=CategoryKind.EXPENSE))
        await db.flush()
        # Gasto recurrente 100/mes los últimos 5 meses (incl. actual) → estructural.
        for i in range(5):
            m = _shift_month(_TODAY, i)
            db.add(
                Transaction(
                    user_id=uid,
                    account_id=bbva_id,
                    amount=Decimal("100"),
                    currency="EUR",
                    occurred_at=datetime(m.year, m.month, m.day, 12, tzinfo=UTC),
                    category_id=cat_id,
                    flow=TransactionFlow.OUT,
                )
            )
        await db.commit()
        m_out = await get_month_outlook(db, uid, currency="EUR")

    # Líquido = apertura 1200 − 500 (5×100 gasto) = 700.
    assert m_out.liquid_balance == Decimal("700.00")
    assert m_out.runway_months is not None
    assert m_out.runway_months > 0


async def test_runway_none_without_structural_base(session_factory) -> None:  # type: ignore[no-untyped-def]
    """Sin gasto estructural (usuario sin histórico) → runway None."""
    uid = await _seed_user(session_factory)
    async with session_factory() as db:
        db.add(
            _account(
                uid,
                name="BBVA",
                nature=AccountNature.ASSET,
                type=AccountType.BANK,
                opening_balance=Decimal("5000"),
            )
        )
        await db.commit()
        m = await get_month_outlook(db, uid, currency="EUR")
    assert m.runway_months is None
    assert m.liquid_balance == Decimal("5000.00")


def _fixed(
    uid: uuid.UUID,
    merchant: str,
    amount: Decimal,
    *,
    next_due: date,
    account_id: uuid.UUID | None = None,
) -> FixedExpense:
    return FixedExpense(
        user_id=uid,
        merchant=merchant,
        raw_description=merchant,
        amount=amount,
        currency="EUR",
        cadence_days=30,
        next_due=next_due,
        status=FixedExpenseStatus.CONFIRMED,
        account_id=account_id,
        first_seen_at=_MONTH_START,
        last_seen_at=_MONTH_START,
        occurrence_count=3,
        confidence=0.9,
    )
