"""AUDIT-2026-06 — Regresiones de la convención de signo de la deuda.

Cubre los hallazgos del grupo "debt signing consistency":

1. `_compute_historical_points` Query B + `_principal_paid_last_n_months`:
   "principal amortizado" cuenta SÓLO la pata income del transfer-pair
   (la que reduce la deuda), no toda tx pareada.
3. `compute_debt_health` usa el principal REAL (cuotas persistidas / tx
   contraparte), no `opening_balance`, para la cuota francesa y los meses
   restantes → convert-to-debt con `opening_balance=0` cuenta.
4. `_interest_paid_ytd` acota `occurred_at <= hoy` (no cuenta interés
   futuro autopostado).
5. `_time_to_payoff_months` descarta horizontes lineales absurdos
   (> `LINEAR_PAYOFF_CAP_MONTHS`).
6. `monthly_income_avg` divide por el nº de meses CON ingreso, no por un
   fijo de 6.
7/8. La convención `else_=0` (tx sin categoría NO contribuye) y la
   dirección por kind son IDÉNTICAS en `daily_liability_flows`,
   `liability_signed_before`, `_compute_historical_points` y
   `get_balances_for_user`.
9. `get_balance_for_account` se eliminó (código muerto).

Las pruebas atacan las funciones directamente con una sesión sembrada
para poder fijar `transfer_pair_id` / cuotas persistidas, cosas que la
API pública no expone trivialmente.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.personal_finance.accounts.installments_model import (
    LiabilityInstallment,
)
from app.modules.personal_finance.accounts.models import (
    Account,
    AccountNature,
    AccountType,
)
from app.modules.personal_finance.categories.models import (
    Category,
    CategoryKind,
    CategoryRole,
)
from app.modules.personal_finance.transactions.models import Transaction
from app.modules.users.models import User

# ─────────────────────────────────────────────────────────────────────
# Helpers de sembrado directo (la API no expone transfer_pair_id ni
# inserción de cuotas).
# ─────────────────────────────────────────────────────────────────────


def _start_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def _closed_month_first(months_ago: int) -> date:
    """Primer día del mes cerrado `months_ago` posiciones atrás
    (1 = último mes cerrado)."""
    today = datetime.now(UTC).date()
    cursor = _start_of_month(today) - timedelta(days=1)  # último mes cerrado
    for _ in range(months_ago - 1):
        cursor = _start_of_month(cursor) - timedelta(days=1)
    return _start_of_month(cursor)


def _dt(d: date) -> datetime:
    return datetime(d.year, d.month, 15, 12, 0, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def session_factory(test_engine):  # type: ignore[no-untyped-def]
    return async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)


async def _seed_user(session_factory) -> uuid.UUID:  # type: ignore[no-untyped-def]
    uid = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            User(
                id=uid,
                email=f"audit_{uid.hex[:8]}@example.com",
                password_hash="x",
                display_name="Audit",
            )
        )
        await db.commit()
    return uid


async def _seed_account(
    session_factory,  # type: ignore[no-untyped-def]
    user_id: uuid.UUID,
    *,
    name: str,
    nature: AccountNature,
    type_: AccountType,
    currency: str = "EUR",
    opening_balance: Decimal = Decimal("0"),
    apr: Decimal | None = None,
    term_months: int | None = None,
    start_date: date | None = None,
) -> uuid.UUID:
    aid = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            Account(
                id=aid,
                user_id=user_id,
                name=name,
                nature=nature,
                type=type_,
                currency=currency,
                opening_balance=opening_balance,
                apr=apr,
                term_months=term_months,
                start_date=start_date,
            )
        )
        await db.commit()
    return aid


async def _seed_category(
    session_factory,  # type: ignore[no-untyped-def]
    user_id: uuid.UUID,
    *,
    name: str,
    kind: CategoryKind,
    role: CategoryRole = CategoryRole.GENERIC,
) -> uuid.UUID:
    cid = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            Category(
                id=cid,
                user_id=user_id,
                name=name,
                kind=kind,
                role=role,
            )
        )
        await db.commit()
    return cid


async def _seed_tx(
    session_factory,  # type: ignore[no-untyped-def]
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    *,
    amount: Decimal,
    occurred_at: datetime,
    category_id: uuid.UUID | None = None,
    transfer_pair_id: uuid.UUID | None = None,
    currency: str = "EUR",
) -> uuid.UUID:
    tid = uuid.uuid4()
    async with session_factory() as db:
        tx = Transaction(
            id=tid,
            user_id=user_id,
            account_id=account_id,
            category_id=category_id,
            amount=amount,
            currency=currency,
            occurred_at=occurred_at,
            transfer_pair_id=None,
        )
        db.add(tx)
        await db.flush()
        if transfer_pair_id is not None:
            # El FK transactions_transfer_pair_id_fkey exige que la contraparte
            # exista. Para estos tests sólo importa que la tx PARTICIPE en una
            # transferencia (transfer_pair_id IS NOT NULL): self-referenciar
            # tras el flush satisface el FK sin sembrar la otra pata.
            tx.transfer_pair_id = tid
        await db.commit()
    return tid


# ─────────────────────────────────────────────────────────────────────
# Fix #2 — _principal_paid_last_n_months: sólo la pata income.
# ─────────────────────────────────────────────────────────────────────


async def test_principal_paid_counts_only_income_leg(session_factory) -> None:  # type: ignore[no-untyped-def]
    """Una cuenta-pasivo con transfer-pair entrante (income, amortiza) y
    saliente (expense, SUBE la deuda) en un mes cerrado: el principal
    amortizado cuenta SÓLO la pata income."""
    from app.modules.personal_finance.accounts.debt_health import (
        _principal_paid_last_n_months,
    )

    uid = await _seed_user(session_factory)
    card = await _seed_account(
        session_factory,
        uid,
        name="Visa",
        nature=AccountNature.LIABILITY,
        type_=AccountType.CREDIT_CARD,
    )
    pay_in = await _seed_category(
        session_factory, uid, name="Pago tarjeta", kind=CategoryKind.INCOME
    )
    charge = await _seed_category(
        session_factory, uid, name="Cargo financiado", kind=CategoryKind.EXPENSE
    )

    last_month = _dt(_closed_month_first(1))
    # Pata income (amortiza): 300. Pata expense (sube deuda): 500. Ambas
    # son transfer-pair en la cuenta-pasivo.
    await _seed_tx(
        session_factory,
        uid,
        card,
        amount=Decimal("300"),
        occurred_at=last_month,
        category_id=pay_in,
        transfer_pair_id=uuid.uuid4(),
    )
    await _seed_tx(
        session_factory,
        uid,
        card,
        amount=Decimal("500"),
        occurred_at=last_month,
        category_id=charge,
        transfer_pair_id=uuid.uuid4(),
    )

    async with session_factory() as db:
        total = await _principal_paid_last_n_months(db, uid, [card], "EUR", months=3)

    # Sólo los 300 de la pata income; los 500 de gasto NO cuentan.
    assert total == Decimal("300")


# ─────────────────────────────────────────────────────────────────────
# Fix #1 — histórico: principal_paid mensual = sólo income leg.
# ─────────────────────────────────────────────────────────────────────


async def test_history_principal_paid_counts_only_income_leg(session_factory) -> None:  # type: ignore[no-untyped-def]
    """`compute_debt_history` reporta como `principal_paid` del mes sólo
    la pata income del transfer-pair, no la de gasto que sube la deuda."""
    from app.modules.personal_finance.accounts.debt_history import (
        compute_debt_history,
    )

    uid = await _seed_user(session_factory)
    card = await _seed_account(
        session_factory,
        uid,
        name="Visa",
        nature=AccountNature.LIABILITY,
        type_=AccountType.CREDIT_CARD,
        opening_balance=Decimal("1000"),
    )
    pay_in = await _seed_category(
        session_factory, uid, name="Pago tarjeta", kind=CategoryKind.INCOME
    )
    charge = await _seed_category(
        session_factory, uid, name="Cargo financiado", kind=CategoryKind.EXPENSE
    )

    target_month = _closed_month_first(1)
    when = _dt(target_month)
    await _seed_tx(
        session_factory,
        uid,
        card,
        amount=Decimal("400"),
        occurred_at=when,
        category_id=pay_in,
        transfer_pair_id=uuid.uuid4(),
    )
    await _seed_tx(
        session_factory,
        uid,
        card,
        amount=Decimal("600"),
        occurred_at=when,
        category_id=charge,
        transfer_pair_id=uuid.uuid4(),
    )

    async with session_factory() as db:
        resp = await compute_debt_history(db, uid, months_back=3, months_ahead=0)

    key = f"{target_month.year:04d}-{target_month.month:02d}"
    point = next(p for p in resp.items if p.month == key)
    # Sólo la pata income (400) amortiza; el cargo de 600 no.
    assert point.principal_paid == Decimal("400.00")


# ─────────────────────────────────────────────────────────────────────
# Fix #7/#8 — tx sin categoría NO contribuye (else_=0), consistente.
# ─────────────────────────────────────────────────────────────────────


async def test_uncategorized_tx_does_not_move_liability_signed_before(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """`liability_signed_before` ignora tx SIN categoría (PHASE-31.3),
    igual que `get_balances_for_user`."""
    from app.modules.personal_finance.debt.repository import (
        liability_signed_before,
    )

    uid = await _seed_user(session_factory)
    card = await _seed_account(
        session_factory,
        uid,
        name="Visa",
        nature=AccountNature.LIABILITY,
        type_=AccountType.CREDIT_CARD,
    )
    charge = await _seed_category(session_factory, uid, name="Compra", kind=CategoryKind.EXPENSE)
    when = _dt(_closed_month_first(2))
    # 200 con categoría expense (sube deuda) + 999 SIN categoría (ignorada).
    await _seed_tx(
        session_factory, uid, card, amount=Decimal("200"), occurred_at=when, category_id=charge
    )
    await _seed_tx(
        session_factory, uid, card, amount=Decimal("999"), occurred_at=when, category_id=None
    )

    before = datetime.now(UTC)
    async with session_factory() as db:
        carry = await liability_signed_before(
            db, uid, liability_ids=[card], before=before, reference_currency="EUR"
        )
    # Sólo los 200 categorizados; la tx sin categoría no aporta.
    assert carry == Decimal("200")


async def test_uncategorized_tx_does_not_move_daily_flows(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """`daily_liability_flows`: una tx sin categoría no cuenta como
    emitida ni amortizado."""
    from app.modules.personal_finance.debt.repository import (
        daily_liability_flows,
    )

    uid = await _seed_user(session_factory)
    card = await _seed_account(
        session_factory,
        uid,
        name="Visa",
        nature=AccountNature.LIABILITY,
        type_=AccountType.CREDIT_CARD,
    )
    charge = await _seed_category(session_factory, uid, name="Compra", kind=CategoryKind.EXPENSE)
    month = _closed_month_first(1)
    day5 = datetime(month.year, month.month, 5, 12, 0, 0, tzinfo=UTC)
    day6 = datetime(month.year, month.month, 6, 12, 0, 0, tzinfo=UTC)
    await _seed_tx(
        session_factory, uid, card, amount=Decimal("100"), occurred_at=day5, category_id=charge
    )
    await _seed_tx(
        session_factory, uid, card, amount=Decimal("777"), occurred_at=day6, category_id=None
    )

    start = datetime(month.year, month.month, 1, tzinfo=UTC)
    import calendar

    last = calendar.monthrange(month.year, month.month)[1]
    end = datetime(month.year, month.month, last, 23, 59, 59, tzinfo=UTC)
    async with session_factory() as db:
        flows = await daily_liability_flows(
            db, uid, liability_ids=[card], start=start, end=end, reference_currency="EUR"
        )
    # Día 5: emitida 100. Día 6: la tx sin categoría no aporta (0, 0).
    assert flows.get(5) == (Decimal("100"), Decimal("0"))
    assert 6 not in flows or flows[6] == (Decimal("0"), Decimal("0"))


async def test_history_signed_else_zero_for_uncategorized(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """`_compute_historical_points`: tx sin categoría no afecta al saldo
    histórico de deuda (else_=0)."""
    from app.modules.personal_finance.accounts.debt_history import (
        compute_debt_history,
    )

    uid = await _seed_user(session_factory)
    card = await _seed_account(
        session_factory,
        uid,
        name="Visa",
        nature=AccountNature.LIABILITY,
        type_=AccountType.CREDIT_CARD,
        opening_balance=Decimal("1000"),
    )
    target_month = _closed_month_first(1)
    when = _dt(target_month)
    # Una tx SIN categoría de 5000 NO debe inflar el saldo histórico.
    await _seed_tx(
        session_factory, uid, card, amount=Decimal("5000"), occurred_at=when, category_id=None
    )

    async with session_factory() as db:
        resp = await compute_debt_history(db, uid, months_back=3, months_ahead=0)
    key = f"{target_month.year:04d}-{target_month.month:02d}"
    point = next(p for p in resp.items if p.month == key)
    # Saldo = opening 1000 (la tx sin categoría no suma).
    assert point.total_debt == Decimal("1000.00")


# ─────────────────────────────────────────────────────────────────────
# Fix #6 — monthly_income_avg divide por meses CON ingreso.
# ─────────────────────────────────────────────────────────────────────


async def test_income_avg_divides_by_months_with_income(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Ingreso en sólo 2 de los últimos 6 meses → media = total/2, no /6."""
    from app.modules.personal_finance.accounts.debt_health import (
        monthly_income_avg,
    )

    uid = await _seed_user(session_factory)
    cte = await _seed_account(
        session_factory,
        uid,
        name="Cte",
        nature=AccountNature.ASSET,
        type_=AccountType.BANK,
    )
    salary = await _seed_category(session_factory, uid, name="Nómina", kind=CategoryKind.INCOME)
    # 2000 en el mes cerrado 1 y 2000 en el mes cerrado 2.
    await _seed_tx(
        session_factory,
        uid,
        cte,
        amount=Decimal("2000"),
        occurred_at=_dt(_closed_month_first(1)),
        category_id=salary,
    )
    await _seed_tx(
        session_factory,
        uid,
        cte,
        amount=Decimal("2000"),
        occurred_at=_dt(_closed_month_first(2)),
        category_id=salary,
    )

    async with session_factory() as db:
        avg = await monthly_income_avg(db, uid, "EUR", months=6)
    # 4000 / 2 meses con ingreso = 2000 (no 4000/6 ≈ 666.67).
    assert avg == Decimal("2000.00")


async def test_income_avg_full_window_unchanged(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Regresión: con ingreso en los 6 meses, la media sigue siendo
    total/6 (comportamiento previo intacto)."""
    from app.modules.personal_finance.accounts.debt_health import (
        monthly_income_avg,
    )

    uid = await _seed_user(session_factory)
    cte = await _seed_account(
        session_factory,
        uid,
        name="Cte",
        nature=AccountNature.ASSET,
        type_=AccountType.BANK,
    )
    salary = await _seed_category(session_factory, uid, name="Nómina", kind=CategoryKind.INCOME)
    for m in range(1, 7):
        await _seed_tx(
            session_factory,
            uid,
            cte,
            amount=Decimal("1500"),
            occurred_at=_dt(_closed_month_first(m)),
            category_id=salary,
        )

    async with session_factory() as db:
        avg = await monthly_income_avg(db, uid, "EUR", months=6)
    assert avg == Decimal("1500.00")


# ─────────────────────────────────────────────────────────────────────
# Fix #4 — interest YTD acotado a hoy.
# ─────────────────────────────────────────────────────────────────────


async def test_interest_ytd_excludes_future(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Interés autopostado a fecha futura NO entra en el YTD."""
    from app.modules.personal_finance.accounts.debt_health import (
        _interest_paid_ytd,
    )

    uid = await _seed_user(session_factory)
    cte = await _seed_account(
        session_factory,
        uid,
        name="Cte",
        nature=AccountNature.ASSET,
        type_=AccountType.BANK,
    )
    interest = await _seed_category(
        session_factory,
        uid,
        name="Intereses",
        kind=CategoryKind.EXPENSE,
        role=CategoryRole.DEBT_INTEREST,
    )
    today = datetime.now(UTC)
    # Pasado (este año, antes de hoy): cuenta. Futuro (este año): NO.
    past = datetime(today.year, 1, 5, 12, 0, 0, tzinfo=UTC)
    future = today + timedelta(days=40)
    await _seed_tx(
        session_factory, uid, cte, amount=Decimal("100"), occurred_at=past, category_id=interest
    )
    await _seed_tx(
        session_factory, uid, cte, amount=Decimal("999"), occurred_at=future, category_id=interest
    )

    async with session_factory() as db:
        ytd = await _interest_paid_ytd(db, uid, "EUR")
    # past=5 enero siempre es <= hoy salvo que hoy sea antes del 5 de enero
    # (improbable en CI). El interés futuro nunca cuenta.
    assert ytd == Decimal("100")


# ─────────────────────────────────────────────────────────────────────
# Fix #5 — payoff lineal acotado.
# ─────────────────────────────────────────────────────────────────────


async def test_linear_payoff_capped_returns_none(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Tarjeta revolving con amortización ínfima → el estimado lineal
    supera el cap y se descarta (None), en vez de devolver siglos."""
    from app.modules.personal_finance.accounts.debt_health import (
        _time_to_payoff_months,
    )

    uid = await _seed_user(session_factory)
    card_id = await _seed_account(
        session_factory,
        uid,
        name="Revolving",
        nature=AccountNature.LIABILITY,
        type_=AccountType.CREDIT_CARD,
        opening_balance=Decimal("10000"),  # sin apr/term → sin schedule
    )
    pay_in = await _seed_category(
        session_factory, uid, name="Pago mínimo", kind=CategoryKind.INCOME
    )
    # 1€ amortizado en los últimos 3 meses → ritmo ~0.33€/mes →
    # 10000/0.33 ≈ 30000 meses, muy por encima del cap (600).
    await _seed_tx(
        session_factory,
        uid,
        card_id,
        amount=Decimal("1"),
        occurred_at=_dt(_closed_month_first(1)),
        category_id=pay_in,
        transfer_pair_id=uuid.uuid4(),
    )

    from sqlalchemy import select as _sel

    async with session_factory() as db:
        card = (await db.execute(_sel(Account).where(Account.id == card_id))).scalar_one()
        ttp = await _time_to_payoff_months(
            db,
            uid,
            [card],
            {card_id: Decimal("10000")},
            "EUR",
            Decimal("10000"),
            installments_by_account={},
            effective_principals={card_id: None},
        )
    assert ttp is None


# ─────────────────────────────────────────────────────────────────────
# Fix #3 — convert-to-debt (opening_balance=0) cuenta vía cuotas /
# tx contraparte.
# ─────────────────────────────────────────────────────────────────────


async def test_debt_health_uses_persisted_installments_for_payment(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Un loan con `opening_balance=0` (convert-to-debt) pero con cuotas
    PERSISTIDAS reporta `monthly_debt_payment` y `time_to_payoff_months`
    no-cero — antes salía a 0 porque la cuota se calculaba sobre
    opening_balance."""
    from app.modules.personal_finance.accounts.debt_health import (
        compute_debt_health,
    )

    uid = await _seed_user(session_factory)
    today = datetime.now(UTC).date()
    start = _start_of_month(today)
    loan = await _seed_account(
        session_factory,
        uid,
        name="Préstamo financiado",
        nature=AccountNature.LIABILITY,
        type_=AccountType.LOAN,
        opening_balance=Decimal("0"),  # convert-to-debt
        apr=Decimal("0.05"),
        term_months=12,
        start_date=start,
    )
    # La contraparte pareada hace que el saldo del pasivo sea > 0
    # (expense en la cuenta-pasivo sube la deuda).
    charge = await _seed_category(
        session_factory, uid, name="Operación financiada", kind=CategoryKind.EXPENSE
    )
    await _seed_tx(
        session_factory,
        uid,
        loan,
        amount=Decimal("1200"),
        occurred_at=_dt(start),
        category_id=charge,
        transfer_pair_id=uuid.uuid4(),
    )
    # Cuotas persistidas (cuadro francés de 1200 a 12 meses): 12 filas.
    async with session_factory() as db:
        remaining = Decimal("1200")
        monthly = Decimal("102.77")  # aprox cuota; el test sólo mira > 0
        for idx in range(1, 13):
            due = date(
                start.year + (start.month - 1 + idx) // 12, (start.month - 1 + idx) % 12 + 1, 1
            )
            principal = Decimal("95.00")
            remaining = remaining - principal
            db.add(
                LiabilityInstallment(
                    user_id=uid,
                    account_id=loan,
                    installment_index=idx,
                    due_date=due,
                    payment=monthly,
                    interest=Decimal("7.77"),
                    principal=principal,
                    remaining_balance=max(remaining, Decimal("0")),
                )
            )
        await db.commit()

    async with session_factory() as db:
        kpis = await compute_debt_health(db, uid)

    # La cuota mensual viene de la cuota persistida (≈ 102.77), no de 0.
    assert kpis.monthly_debt_payment > Decimal("0")
    assert kpis.monthly_debt_payment == Decimal("102.77")
    # time_to_payoff cuenta las 12 cuotas pendientes (todas futuras).
    assert kpis.time_to_payoff_months is not None
    assert kpis.time_to_payoff_months >= 11


async def test_debt_health_uses_counterpart_when_no_installments(
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Loan convert-to-debt con `opening_balance=0` y SIN cuotas
    persistidas: la cuota francesa se deriva del principal de la tx
    contraparte pareada (no de opening_balance=0 → no-cero)."""
    from app.modules.personal_finance.accounts.debt_health import (
        compute_debt_health,
    )

    uid = await _seed_user(session_factory)
    today = datetime.now(UTC).date()
    start = _start_of_month(today)
    loan = await _seed_account(
        session_factory,
        uid,
        name="Préstamo sin cuadro",
        nature=AccountNature.LIABILITY,
        type_=AccountType.LOAN,
        opening_balance=Decimal("0"),
        apr=Decimal("0.05"),
        term_months=12,
        start_date=start,
    )
    charge = await _seed_category(
        session_factory, uid, name="Operación financiada", kind=CategoryKind.EXPENSE
    )
    # Contraparte: principal 1200 (sube la deuda del pasivo).
    await _seed_tx(
        session_factory,
        uid,
        loan,
        amount=Decimal("1200"),
        occurred_at=_dt(start),
        category_id=charge,
        transfer_pair_id=uuid.uuid4(),
    )

    async with session_factory() as db:
        kpis = await compute_debt_health(db, uid)

    # Cuota francesa de 1200 @ 5% / 12m ≈ 102.77 → > 0 (antes era 0).
    assert kpis.monthly_debt_payment > Decimal("0")
    assert kpis.time_to_payoff_months is not None
