"""PHASE-36 — Reconciliación de aportaciones contra el cuadro de deuda.

Cubre: el saldo dirigido por el cuadro (`schedule_outstanding`), la
generación + ancla del cuadro del préstamo, el match aportación→cuota
(préstamo 1:1, tarjeta 1 cuota/cargo + exceso asumido), la idempotencia,
y la exclusión del ADEUDO/financiación entrante.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.personal_finance.accounts.models import Account, AccountNature, AccountType
from app.modules.personal_finance.accounts.service import get_balances
from app.modules.personal_finance.debt.installments_model import LiabilityInstallment
from app.modules.personal_finance.debt.installments_repository import (
    generate_installments_for_account,
    installments_by_account,
    list_installments,
    schedule_outstanding,
)
from app.modules.personal_finance.debt.reconciliation import reconcile_debt_payments
from app.modules.personal_finance.transactions.models import Transaction, TransactionFlow
from app.modules.users.models import User


@pytest_asyncio.fixture
async def session_factory(test_engine):  # type: ignore[no-untyped-def]
    return async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)


async def _seed_user(session_factory) -> uuid.UUID:  # type: ignore[no-untyped-def]
    uid = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            User(
                id=uid, email=f"debt_{uid.hex[:8]}@example.com", password_hash="x", display_name="D"
            )
        )
        await db.commit()
    return uid


async def _seed_account(  # type: ignore[no-untyped-def]
    session_factory,
    user_id,
    *,
    name,
    nature,
    type_,
    opening=Decimal("0"),
    apr=None,
    term=None,
    start=None,
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
                currency="EUR",
                opening_balance=opening,
                apr=apr,
                term_months=term,
                start_date=start,
            )
        )
        await db.commit()
    return aid


async def _seed_tx(  # type: ignore[no-untyped-def]
    session_factory, user_id, account_id, *, amount, when, description, flow=TransactionFlow.OUT
) -> uuid.UUID:
    tid = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            Transaction(
                id=tid,
                user_id=user_id,
                account_id=account_id,
                amount=amount,
                currency="EUR",
                occurred_at=when,
                description=description,
                flow=flow,
            )
        )
        await db.commit()
    return tid


# ── schedule_outstanding (unidad pura) ──────────────────────────────────
def test_schedule_outstanding_none_when_empty() -> None:
    assert schedule_outstanding([]) is None


def test_schedule_outstanding_sums_unpaid_principal() -> None:
    rows = [
        LiabilityInstallment(principal=Decimal("100"), paid_at=datetime(2026, 1, 1, tzinfo=UTC)),
        LiabilityInstallment(principal=Decimal("100"), paid_at=None),
        LiabilityInstallment(principal=Decimal("50"), paid_at=None),
    ]
    assert schedule_outstanding(rows) == Decimal("150")


# ── Reconciliación del préstamo: genera cuadro + ancla + match ──────────
async def test_reconcile_loan_generates_anchors_and_matches(session_factory) -> None:  # type: ignore[no-untyped-def]
    uid = await _seed_user(session_factory)
    bank = await _seed_account(
        session_factory, uid, name="BBVA", nature=AccountNature.ASSET, type_=AccountType.BANK
    )
    loan = await _seed_account(
        session_factory,
        uid,
        name="Prestamo",
        nature=AccountNature.LIABILITY,
        type_=AccountType.LOAN,
        opening=Decimal("22000"),
        apr=Decimal("0.0490"),
        term=120,
        start=date(2024, 8, 31),
    )
    for m in range(2, 6):  # feb..may 2026
        await _seed_tx(
            session_factory,
            uid,
            bank,
            amount=Decimal("232.27"),
            when=datetime(2026, m, 1, tzinfo=UTC),
            description="CARGO POR AMORTIZACION DE PRESTAMO",
        )

    async with session_factory() as db:
        plan = await reconcile_debt_payments(db, uid, dry_run=False)
        await db.commit()

    loan_plan = next(p for p in plan["liabilities"] if p["name"] == "Prestamo")  # type: ignore[index]
    assert loan_plan["generate_schedule"] is True
    assert loan_plan["schedule_rows"] == 120
    assert loan_plan["matched"] == 4

    async with session_factory() as db:
        insts = await list_installments(db, loan, uid)
    paid = [i for i in insts if i.paid_at is not None]
    matched = [i for i in paid if i.paid_transaction_id is not None]
    anchored = [i for i in paid if i.paid_transaction_id is None]

    # AUDIT-2026-07 (LOW): aserciones exactas, no `>= 1` / `< 22000`.
    # 1) Cuadro francés: Σ del principal de TODAS las cuotas == capital exacto.
    total_principal = sum((i.principal for i in insts), Decimal("0"))
    assert total_principal.quantize(Decimal("0.01")) == Decimal("22000.00")
    # 2) `schedule_outstanding` == Σ principal de las NO pagadas (por definición
    #    — atrapa una regresión en el cálculo del saldo dirigido por cuadro).
    unpaid_principal = sum((i.principal for i in insts if i.paid_at is None), Decimal("0"))
    assert schedule_outstanding(insts) == unpaid_principal
    # 3) El conjunto PAGADO es EXACTAMENTE el de cuotas con vencimiento ≤ el
    #    último pago (may 2026): las 4 con tx real (feb..may) + el resto ancladas
    #    antes de la ventana de datos. Ni anticipa futuras ni deja huecos.
    expected_paid = [i for i in insts if i.due_date <= date(2026, 5, 31)]
    assert len(matched) == 4
    assert len(paid) == len(expected_paid)
    assert len(anchored) == len(expected_paid) - 4
    assert int(loan_plan["anchored"]) == len(anchored)


# ── Reconciliación de tarjeta financiada: match + exceso asumido ────────
async def test_reconcile_card_matches_and_assumes_excess(session_factory) -> None:  # type: ignore[no-untyped-def]
    uid = await _seed_user(session_factory)
    bank = await _seed_account(
        session_factory, uid, name="BBVA", nature=AccountNature.ASSET, type_=AccountType.BANK
    )
    card = await _seed_account(
        session_factory,
        uid,
        name="Compra financiada",
        nature=AccountNature.LIABILITY,
        type_=AccountType.CREDIT_CARD,
        opening=Decimal("824.77"),
        apr=Decimal("0.2160"),
        term=9,
        start=date(2026, 1, 6),
    )
    # Generar el cuadro de la compra (9 cuotas).
    async with session_factory() as db:
        acc = await db.get(Account, card)
        assert acc is not None
        await generate_installments_for_account(db, acc)
        await db.commit()
    # Cargos agregados del banco (> cuota de 100.08): el exceso es deuda previa.
    for m, amt in [(2, "373.93"), (3, "200.46"), (4, "287.36"), (5, "316.35")]:
        await _seed_tx(
            session_factory,
            uid,
            bank,
            amount=Decimal(amt),
            when=datetime(2026, m, 4, tzinfo=UTC),
            description="OPERACIÓN FINANCIADA CON TARJETA",
        )

    async with session_factory() as db:
        plan = await reconcile_debt_payments(db, uid, dry_run=False)
        await db.commit()

    card_plan = next(p for p in plan["liabilities"] if p["name"] == "Compra financiada")  # type: ignore[index]
    assert card_plan["matched"] == 4
    # Exceso = Σ(cargo − cuota 100.08) = 273.85+100.38+187.28+216.27 = 777.78
    assert Decimal(card_plan["assumed_unregistered_debt"]) == Decimal("777.78")  # type: ignore[index]
    async with session_factory() as db:
        insts = await list_installments(db, card, uid)
    assert sum(1 for i in insts if i.paid_at is not None) == 4
    # Saldo del cuadro baja desde 824.77.
    assert schedule_outstanding(insts) < Decimal("824.77")


async def test_reconcile_splits_aggregate_charge_across_cards(session_factory) -> None:  # type: ignore[no-untyped-def]
    """PHASE-36.1 — un cargo mensual AGREGADO paga la siguiente cuota de CADA
    tarjeta con cuadro ya iniciada (mes cargo ≥ mes inicio). Un plan que
    arrancó más tarde NO se paga con cargos anteriores a su inicio; el exceso
    del cargo se imputa al plan que casó primero. Idempotente."""
    uid = await _seed_user(session_factory)
    bank = await _seed_account(
        session_factory, uid, name="BBVA", nature=AccountNature.ASSET, type_=AccountType.BANK
    )
    # Compra "antigua" (inicia enero) y compra "nueva" (inicia abril).
    old = await _seed_account(
        session_factory,
        uid,
        name="Compra financiada",
        nature=AccountNature.LIABILITY,
        type_=AccountType.CREDIT_CARD,
        opening=Decimal("824.77"),
        apr=Decimal("0.2160"),
        term=9,
        start=date(2026, 1, 6),
    )
    new = await _seed_account(
        session_factory,
        uid,
        name="Compra financiada mar-2026",
        nature=AccountNature.LIABILITY,
        type_=AccountType.CREDIT_CARD,
        opening=Decimal("239.00"),
        apr=Decimal("0.2160"),
        term=9,
        start=date(2026, 4, 5),
    )
    async with session_factory() as db:
        for aid in (old, new):
            acc = await db.get(Account, aid)
            assert acc is not None
            await generate_installments_for_account(db, acc)
        await db.commit()
    # Cargos agregados enero, febrero, marzo, mayo (sin abril).
    for m, amt in [(1, "373.93"), (2, "200.46"), (3, "287.36"), (5, "316.35")]:
        await _seed_tx(
            session_factory,
            uid,
            bank,
            amount=Decimal(amt),
            when=datetime(2026, m, 4, tzinfo=UTC),
            description="OPERACIÓN FINANCIADA CON TARJETA",
        )

    async with session_factory() as db:
        plan = await reconcile_debt_payments(db, uid, dry_run=False)
        await db.commit()

    plans = {p["name"]: p for p in plan["liabilities"]}  # type: ignore[index]
    # La antigua casa las 4 (todos los cargos ≥ su inicio de enero).
    assert plans["Compra financiada"]["matched"] == 4
    # La nueva SÓLO casa 1 (sólo el cargo de mayo ≥ su inicio de abril; los de
    # enero/febrero/marzo son anteriores a que existiera el plan).
    assert plans["Compra financiada mar-2026"]["matched"] == 1
    # El exceso baja respecto al caso de una sola tarjeta (777.78) justo en la
    # cuota que ahora cubre la nueva compra (≈29): se imputa a la que casó 1ª.
    assert Decimal(plans["Compra financiada"]["assumed_unregistered_debt"]) == Decimal("748.78")

    async with session_factory() as db:
        new_insts = await list_installments(db, new, uid)
    paid = [i for i in new_insts if i.paid_at is not None]
    assert len(paid) == 1 and paid[0].installment_index == 1

    # Idempotencia: re-ejecutar no cambia los pagos ni el exceso.
    async with session_factory() as db:
        plan2 = await reconcile_debt_payments(db, uid, dry_run=False)
        await db.commit()
    plans2 = {p["name"]: p for p in plan2["liabilities"]}  # type: ignore[index]
    assert Decimal(plans2["Compra financiada"]["assumed_unregistered_debt"]) == Decimal("748.78")
    async with session_factory() as db:
        assert sum(1 for i in await list_installments(db, new, uid) if i.paid_at is not None) == 1
        assert sum(1 for i in await list_installments(db, old, uid) if i.paid_at is not None) == 4


async def test_reconcile_excess_attribution_is_idempotent_across_runs(session_factory) -> None:  # type: ignore[no-untyped-def]
    """PHASE-36.1 — el EXCESO por plan debe ser idéntico entre ejecuciones
    idénticas, incluso cuando la tarjeta que ordena primera agota su cuadro
    mientras otra posterior sigue casando (y sin vínculo de categoría, que es
    lo que fuerza el fallback a `first_matched`). Regresión del bug donde en
    re-runs `first_matched` quedaba None y el exceso migraba a cards[0]."""
    uid = await _seed_user(session_factory)
    bank = await _seed_account(
        session_factory, uid, name="BBVA", nature=AccountNature.ASSET, type_=AccountType.BANK
    )
    # 'Alfa' ordena primera (mismo inicio, nombre menor) y agota su cuadro en 1 cuota.
    alfa = await _seed_account(
        session_factory,
        uid,
        name="Alfa",
        nature=AccountNature.LIABILITY,
        type_=AccountType.CREDIT_CARD,
        opening=Decimal("100.00"),
        apr=Decimal("0"),
        term=1,
        start=date(2026, 1, 6),
    )
    zeta = await _seed_account(
        session_factory,
        uid,
        name="Zeta",
        nature=AccountNature.LIABILITY,
        type_=AccountType.CREDIT_CARD,
        opening=Decimal("90.00"),
        apr=Decimal("0"),
        term=9,
        start=date(2026, 1, 6),
    )
    async with session_factory() as db:
        for aid in (alfa, zeta):
            acc = await db.get(Account, aid)
            assert acc is not None
            await generate_installments_for_account(db, acc)
        await db.commit()
    # Cargos agregados grandes (exceso positivo), SIN category_id.
    for m in (1, 2):
        await _seed_tx(
            session_factory,
            uid,
            bank,
            amount=Decimal("500.00"),
            when=datetime(2026, m, 4, tzinfo=UTC),
            description="OPERACIÓN FINANCIADA CON TARJETA",
        )

    async with session_factory() as db:
        run1 = await reconcile_debt_payments(db, uid, dry_run=False)
        await db.commit()
    async with session_factory() as db:
        run2 = await reconcile_debt_payments(db, uid, dry_run=False)
        await db.commit()

    def assumed(plan: object, name: str) -> Decimal:
        p = next(x for x in plan["liabilities"] if x["name"] == name)  # type: ignore[index]
        return Decimal(p["assumed_unregistered_debt"])  # type: ignore[index]

    # El exceso del cargo de febrero lo casó Zeta en run1 (Alfa ya agotada);
    # debe SEGUIR imputado a Zeta en run2, no migrar a Alfa (cards[0]).
    assert assumed(run1, "Zeta") == assumed(run2, "Zeta")
    assert assumed(run1, "Alfa") == assumed(run2, "Alfa")
    assert assumed(run2, "Zeta") > Decimal("0")


# ── Idempotencia + exclusión de ADEUDO / financiación entrante ──────────
async def test_reconcile_idempotent_and_excludes_noise(session_factory) -> None:  # type: ignore[no-untyped-def]
    uid = await _seed_user(session_factory)
    bank = await _seed_account(
        session_factory, uid, name="BBVA", nature=AccountNature.ASSET, type_=AccountType.BANK
    )
    loan = await _seed_account(
        session_factory,
        uid,
        name="Prestamo",
        nature=AccountNature.LIABILITY,
        type_=AccountType.LOAN,
        opening=Decimal("10000"),
        apr=Decimal("0.03"),
        term=60,
        start=date(2025, 1, 31),
    )
    await _seed_tx(
        session_factory,
        uid,
        bank,
        amount=Decimal("179.69"),
        when=datetime(2026, 2, 1, tzinfo=UTC),
        description="CARGO POR AMORTIZACION DE PRESTAMO",
    )
    # Ruido que NO debe matchear: ADEUDO (liquidación) + financiación entrante.
    await _seed_tx(
        session_factory,
        uid,
        bank,
        amount=Decimal("500"),
        when=datetime(2026, 2, 2, tzinfo=UTC),
        description="ADEUDO MENSUAL DE TARJETA",
        flow=TransactionFlow.TRANSFER_OUT,
    )
    await _seed_tx(
        session_factory,
        uid,
        bank,
        amount=Decimal("239"),
        when=datetime(2026, 3, 1, tzinfo=UTC),
        description="OPERACION FINANCIADA",
        flow=TransactionFlow.TRANSFER_IN,
    )

    async with session_factory() as db:
        await reconcile_debt_payments(db, uid, dry_run=False)
        await db.commit()
    async with session_factory() as db:
        insts1 = await list_installments(db, loan, uid)
    matched1 = [i for i in insts1 if i.paid_transaction_id is not None]
    assert len(matched1) == 1  # sólo la amortización, ni ADEUDO ni entrante

    # Segunda pasada: idempotente (no marca cuotas adicionales).
    async with session_factory() as db:
        await reconcile_debt_payments(db, uid, dry_run=False)
        await db.commit()
    async with session_factory() as db:
        insts2 = await list_installments(db, loan, uid)
    matched2 = [i for i in insts2 if i.paid_transaction_id is not None]
    assert len(matched2) == 1


# ── El saldo mostrado (get_balances) sale del cuadro tras reconciliar ───
async def test_balance_is_schedule_driven_after_reconcile(session_factory) -> None:  # type: ignore[no-untyped-def]
    uid = await _seed_user(session_factory)
    bank = await _seed_account(
        session_factory, uid, name="BBVA", nature=AccountNature.ASSET, type_=AccountType.BANK
    )
    loan = await _seed_account(
        session_factory,
        uid,
        name="Prestamo",
        nature=AccountNature.LIABILITY,
        type_=AccountType.LOAN,
        opening=Decimal("22000"),
        apr=Decimal("0.0490"),
        term=120,
        start=date(2024, 8, 31),
    )
    await _seed_tx(
        session_factory,
        uid,
        bank,
        amount=Decimal("232.27"),
        when=datetime(2026, 2, 1, tzinfo=UTC),
        description="CARGO POR AMORTIZACION DE PRESTAMO",
    )
    async with session_factory() as db:
        await reconcile_debt_payments(db, uid, dry_run=False)
        await db.commit()
    async with session_factory() as db:
        balances = await get_balances(db, uid)
        insts = await list_installments(db, loan, uid)
    loan_item = next(b for b in balances.items if b.account_id == loan)
    # El saldo mostrado del préstamo == Σ principal de cuotas no pagadas.
    assert loan_item.current_balance == schedule_outstanding(insts)
    assert loan_item.current_balance < Decimal("22000")


# ── installments_by_account agrupa correctamente ────────────────────────
async def test_installments_by_account_groups(session_factory) -> None:  # type: ignore[no-untyped-def]
    uid = await _seed_user(session_factory)
    loan = await _seed_account(
        session_factory,
        uid,
        name="Prestamo",
        nature=AccountNature.LIABILITY,
        type_=AccountType.LOAN,
        opening=Decimal("5000"),
        apr=Decimal("0.03"),
        term=12,
        start=date(2026, 1, 31),
    )
    async with session_factory() as db:
        acc = await db.get(Account, loan)
        assert acc is not None
        await generate_installments_for_account(db, acc)
        await db.commit()
    async with session_factory() as db:
        grouped = await installments_by_account(db, uid, [loan])
    assert len(grouped[loan]) == 12
