"""PHASE-34.2 — `transactions.flow` como fuente de verdad del dinero (ADR-0004).

Golden/regression tests que fijan la semántica NUEVA: el saldo y el
cashflow se derivan de `flow` (+ `account.nature`), NO de la categoría.
Atacan directamente las queries de repositorio sembrando `flow`, porque
es justo lo que la API pública aún no escribe (eso es 34.3).

Cubre los dos bugs medidos en datos reales:
- Una transferencia metida en una categoría de gasto normal NO infla el
  gasto del mes si su `flow` es TRANSFER_* (caso "SCL"→Wise, 5.060 €).
- El `flow` gana a la categoría: un OUT en una categoría `is_transfer`
  SÍ cuenta como gasto.

Y la equivalencia de transición: una fila sin `flow` cae a `category`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.personal_finance.accounts.models import Account, AccountNature, AccountType
from app.modules.personal_finance.accounts.repository import get_balances_for_user
from app.modules.personal_finance.categories.models import Category, CategoryKind
from app.modules.personal_finance.dashboard.repository import get_summary_aggregates
from app.modules.personal_finance.transactions.models import Transaction, TransactionFlow
from app.modules.personal_finance.transfers.service import classify_import_flow
from app.modules.users.models import User

_WHEN = datetime(2026, 2, 15, 12, 0, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def session_factory(test_engine):  # type: ignore[no-untyped-def]
    return async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)


async def _seed_user(session_factory) -> uuid.UUID:  # type: ignore[no-untyped-def]
    uid = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            User(
                id=uid,
                email=f"flow_{uid.hex[:8]}@example.com",
                password_hash="x",
                display_name="Flow",
            )
        )
        await db.commit()
    return uid


async def _seed_account(  # type: ignore[no-untyped-def]
    session_factory,
    user_id: uuid.UUID,
    *,
    nature: AccountNature,
    type_: AccountType,
) -> uuid.UUID:
    aid = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            Account(
                id=aid,
                user_id=user_id,
                name=f"acc_{aid.hex[:6]}",
                nature=nature,
                type=type_,
                currency="EUR",
                opening_balance=Decimal("0"),
            )
        )
        await db.commit()
    return aid


async def _seed_category(  # type: ignore[no-untyped-def]
    session_factory,
    user_id: uuid.UUID,
    *,
    kind: CategoryKind,
    is_transfer: bool = False,
) -> uuid.UUID:
    cid = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            Category(
                id=cid,
                user_id=user_id,
                name=f"cat_{cid.hex[:6]}",
                kind=kind,
                is_transfer=is_transfer,
            )
        )
        await db.commit()
    return cid


async def _seed_tx(  # type: ignore[no-untyped-def]
    session_factory,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    *,
    amount: Decimal,
    flow: TransactionFlow | None,
    category_id: uuid.UUID | None = None,
    description: str | None = None,
) -> uuid.UUID:
    tid = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            Transaction(
                id=tid,
                user_id=user_id,
                account_id=account_id,
                category_id=category_id,
                amount=amount,
                currency="EUR",
                occurred_at=_WHEN,
                description=description,
                flow=flow,
            )
        )
        await db.commit()
    return tid


# ─────────────────────────────────────────────────────────────────────
# Cashflow: el flow manda, no la categoría.
# ─────────────────────────────────────────────────────────────────────


async def test_transfer_flow_in_expense_category_is_excluded_from_cashflow(session_factory) -> None:  # type: ignore[no-untyped-def]
    """El bug medido (5.060 € a Wise en categoría 'SCL' de gasto): un
    movimiento con flow=TRANSFER_OUT NO cuenta como gasto aunque su
    categoría sea de gasto (is_transfer=False)."""
    uid = await _seed_user(session_factory)
    bbva = await _seed_account(
        session_factory, uid, nature=AccountNature.ASSET, type_=AccountType.BANK
    )
    gasto_cat = await _seed_category(
        session_factory, uid, kind=CategoryKind.EXPENSE, is_transfer=False
    )
    # Gasto real: cuenta.
    await _seed_tx(
        session_factory,
        uid,
        bbva,
        amount=Decimal("100"),
        flow=TransactionFlow.OUT,
        category_id=gasto_cat,
    )
    # Transferencia metida en la MISMA categoría de gasto: NO cuenta.
    await _seed_tx(
        session_factory,
        uid,
        bbva,
        amount=Decimal("5000"),
        flow=TransactionFlow.TRANSFER_OUT,
        category_id=gasto_cat,
    )

    async with session_factory() as db:
        _income, expense, count, _unconv = await get_summary_aggregates(db, uid, currency="EUR")
    assert expense == Decimal("100")  # NO 5100
    # La transferencia queda fuera del resumen por completo (no infla ni
    # el gasto ni el total_count): sólo cuenta el gasto real.
    assert count == 1


async def test_out_flow_in_transfer_category_counts_as_expense(session_factory) -> None:  # type: ignore[no-untyped-def]
    """El flow gana a la categoría: un OUT en una categoría is_transfer SÍ
    cuenta como gasto."""
    uid = await _seed_user(session_factory)
    bbva = await _seed_account(
        session_factory, uid, nature=AccountNature.ASSET, type_=AccountType.BANK
    )
    transfer_cat = await _seed_category(
        session_factory, uid, kind=CategoryKind.EXPENSE, is_transfer=True
    )
    await _seed_tx(
        session_factory,
        uid,
        bbva,
        amount=Decimal("50"),
        flow=TransactionFlow.OUT,
        category_id=transfer_cat,
    )

    async with session_factory() as db:
        _income, expense, _count, _unconv = await get_summary_aggregates(db, uid, currency="EUR")
    assert expense == Decimal("50")


async def test_null_flow_falls_back_to_category(session_factory) -> None:  # type: ignore[no-untyped-def]
    """Transición: una fila SIN flow cae a category.kind/is_transfer."""
    uid = await _seed_user(session_factory)
    bbva = await _seed_account(
        session_factory, uid, nature=AccountNature.ASSET, type_=AccountType.BANK
    )
    gasto_cat = await _seed_category(
        session_factory, uid, kind=CategoryKind.EXPENSE, is_transfer=False
    )
    transfer_cat = await _seed_category(
        session_factory, uid, kind=CategoryKind.EXPENSE, is_transfer=True
    )
    # Sin flow + categoría de gasto → gasto.
    await _seed_tx(
        session_factory, uid, bbva, amount=Decimal("80"), flow=None, category_id=gasto_cat
    )
    # Sin flow + categoría is_transfer → excluida.
    await _seed_tx(
        session_factory, uid, bbva, amount=Decimal("999"), flow=None, category_id=transfer_cat
    )

    async with session_factory() as db:
        _income, expense, _count, _unconv = await get_summary_aggregates(db, uid, currency="EUR")
    assert expense == Decimal("80")


# ─────────────────────────────────────────────────────────────────────
# Saldo: el flow + nature mandan el signo.
# ─────────────────────────────────────────────────────────────────────


async def test_balance_asset_signs_from_flow(session_factory) -> None:  # type: ignore[no-untyped-def]
    """Cuenta ASSET: IN suma, OUT resta, TRANSFER_OUT resta (las patas de
    transferencia SÍ mueven el saldo individual). Sin categoría: el flow
    basta para fijar el signo."""
    uid = await _seed_user(session_factory)
    bbva = await _seed_account(
        session_factory, uid, nature=AccountNature.ASSET, type_=AccountType.BANK
    )
    await _seed_tx(session_factory, uid, bbva, amount=Decimal("1000"), flow=TransactionFlow.IN)
    await _seed_tx(session_factory, uid, bbva, amount=Decimal("200"), flow=TransactionFlow.OUT)
    await _seed_tx(
        session_factory, uid, bbva, amount=Decimal("300"), flow=TransactionFlow.TRANSFER_OUT
    )

    async with session_factory() as db:
        balances = await get_balances_for_user(db, uid)
    assert balances[bbva] == Decimal("500")  # 1000 - 200 - 300


async def test_balance_liability_signs_inverted(session_factory) -> None:  # type: ignore[no-untyped-def]
    """Cuenta LIABILITY: OUT (cargo) sube la deuda, IN (pago) la reduce."""
    uid = await _seed_user(session_factory)
    card = await _seed_account(
        session_factory, uid, nature=AccountNature.LIABILITY, type_=AccountType.CREDIT_CARD
    )
    await _seed_tx(session_factory, uid, card, amount=Decimal("400"), flow=TransactionFlow.OUT)
    await _seed_tx(session_factory, uid, card, amount=Decimal("150"), flow=TransactionFlow.IN)

    async with session_factory() as db:
        balances = await get_balances_for_user(db, uid)
    assert balances[card] == Decimal("250")  # +400 - 150


# ─────────────────────────────────────────────────────────────────────
# Operación financiada → deuda: anulación del "cargo espejo" (PHASE-34).
# ─────────────────────────────────────────────────────────────────────


async def test_convert_to_debt_absorbs_mirror_charge(session_factory) -> None:  # type: ignore[no-untyped-def]
    """Al registrar la operación financiada como deuda, el cargo espejo (un
    ADEUDO del MISMO importe que en el banco la compensa) se mueve a la
    papelera → saldo neto 0 + deuda. Un cargo de OTRO importe no se toca."""
    from app.modules.personal_finance.transfers.service import convert_to_debt_operation

    uid = await _seed_user(session_factory)
    bbva = await _seed_account(
        session_factory, uid, nature=AccountNature.ASSET, type_=AccountType.BANK
    )
    card = await _seed_account(
        session_factory, uid, nature=AccountNature.LIABILITY, type_=AccountType.CREDIT_CARD
    )
    abono = await _seed_tx(
        session_factory,
        uid,
        bbva,
        amount=Decimal("824.77"),
        flow=TransactionFlow.IN,
        description="OPERACIÓN FINANCIADA",
    )
    mirror = await _seed_tx(
        session_factory,
        uid,
        bbva,
        amount=Decimal("824.77"),
        flow=TransactionFlow.OUT,
        description="ADEUDO MENSUAL DE TARJETA",
    )
    other = await _seed_tx(
        session_factory,
        uid,
        bbva,
        amount=Decimal("43.93"),
        flow=TransactionFlow.OUT,
        description="ADEUDO MENSUAL DE TARJETA",
    )

    async with session_factory() as db:
        resp = await convert_to_debt_operation(
            db, uid, source_transaction_id=abono, destination_account_id=card, new_liability=None
        )
        await db.commit()

    assert resp.absorbed_mirror_amount == Decimal("824.77")
    async with session_factory() as db:
        m = await db.get(Transaction, mirror)
        o = await db.get(Transaction, other)
    assert m is not None and m.deleted_at is not None  # espejo → papelera
    assert o is not None and o.deleted_at is None  # otro importe intacto


# ─────────────────────────────────────────────────────────────────────
# classify_import_flow — modelo de dinero + tarjeta en el import (PHASE-34.3).
# El signo del extracto manda; la transfer-ness sale de categoría o texto.
# ─────────────────────────────────────────────────────────────────────


def test_classify_normal_expense() -> None:
    assert (
        classify_import_flow(bank_sign=-1, text="MERCADONA", category_is_transfer=False)
        == TransactionFlow.OUT
    )


def test_classify_normal_income() -> None:
    assert (
        classify_import_flow(bank_sign=1, text="NOMINA EMPRESA", category_is_transfer=False)
        == TransactionFlow.IN
    )


def test_classify_transfer_by_description_even_in_expense_category() -> None:
    """El bug 'SCL' (5.060 € a Wise): 'TRANSFERENCIA REALIZADA' se marca
    TRANSFER_OUT aunque la categoría no sea is_transfer → no infla el gasto."""
    assert (
        classify_import_flow(
            bank_sign=-1, text="TRANSFERENCIA REALIZADA Ws", category_is_transfer=False
        )
        == TransactionFlow.TRANSFER_OUT
    )


def test_classify_card_adeudo_is_transfer() -> None:
    """ADEUDO MENSUAL DE TARJETA (2º doble-conteo): pago de tarjeta → TRANSFER."""
    assert (
        classify_import_flow(
            bank_sign=-1, text="ADEUDO MENSUAL DE TARJETA", category_is_transfer=False
        )
        == TransactionFlow.TRANSFER_OUT
    )


def test_classify_operacion_financiada_con_tarjeta_is_expense() -> None:
    """PHASE-38 (decisión del usuario): la CUOTA de una compra a plazos con
    tarjeta cuenta como gasto real del mes (visión de caja), a diferencia del
    ADEUDO/liquidación. La compra original se modela como creación de deuda
    (neutra), así que la cuota no dobla nada; la deuda la descuenta el cuadro."""
    for text in ("OPERACIÓN FINANCIADA CON TARJETA", "Operación financiada con tarjeta"):
        assert (
            classify_import_flow(bank_sign=-1, text=text, category_is_transfer=False)
            == TransactionFlow.OUT
        )


def test_classify_operacion_financiada_bare_is_transfer() -> None:
    """La 'OPERACIÓN FINANCIADA' a secas (evento de CREACIÓN de deuda, sin
    'tarjeta') sigue siendo movimiento interno neutro — no es una cuota."""
    assert (
        classify_import_flow(bank_sign=-1, text="OPERACIÓN FINANCIADA", category_is_transfer=False)
        == TransactionFlow.TRANSFER_OUT
    )


def test_classify_financiada_con_tarjeta_overrides_category_transfer() -> None:
    """El concepto 'financiada con tarjeta' es inequívocamente una cuota:
    gana sobre un `category_is_transfer` mal puesto → gasto, no transferencia."""
    assert (
        classify_import_flow(
            bank_sign=-1, text="OPERACIÓN FINANCIADA CON TARJETA", category_is_transfer=True
        )
        == TransactionFlow.OUT
    )


def test_classify_bizum_is_expense_not_transfer() -> None:
    """BIZUM NO es transferencia (suele ser pago a comercio) → gasto."""
    assert (
        classify_import_flow(
            bank_sign=-1, text="BIZUM ENVIADO: Sin concepto", category_is_transfer=False
        )
        == TransactionFlow.OUT
    )


def test_classify_pago_con_tarjeta_is_expense() -> None:
    """La compra de débito 'PAGO CON TARJETA' NO matchea el pago de tarjeta."""
    assert (
        classify_import_flow(
            bank_sign=-1, text="CONSUM TORRE PACHECO PAGO CON TARJETA", category_is_transfer=False
        )
        == TransactionFlow.OUT
    )


def test_classify_transfer_received() -> None:
    assert (
        classify_import_flow(
            bank_sign=1, text="TRANSFERENCIA RECIBIDA DE JOSE", category_is_transfer=False
        )
        == TransactionFlow.TRANSFER_IN
    )


def test_classify_category_transfer_overrides() -> None:
    """Si la categoría resuelta es is_transfer, manda aunque el texto no lo diga."""
    assert (
        classify_import_flow(bank_sign=-1, text="PAGO X", category_is_transfer=True)
        == TransactionFlow.TRANSFER_OUT
    )


def test_classify_no_sign_no_signal_is_unclassified() -> None:
    """Sin signo, sin texto direccional y sin categoría → None (neutro, no
    revisión): contribuye 0, igual que una tx sin categoría."""
    assert classify_import_flow(bank_sign=0, text="COMPRA", category_is_transfer=False) is None


def test_classify_no_sign_falls_back_to_category_kind() -> None:
    """Extracto sólo-magnitud: la dirección sale del kind de la categoría."""
    assert (
        classify_import_flow(
            bank_sign=0,
            text="COMPRA",
            category_is_transfer=False,
            category_kind=CategoryKind.EXPENSE,
        )
        == TransactionFlow.OUT
    )


def test_classify_no_sign_text_decides_direction() -> None:
    """Sin signo pero 'recibida' en el texto → TRANSFER_IN (gana al category_kind)."""
    assert (
        classify_import_flow(
            bank_sign=0,
            text="TRANSFERENCIA RECIBIDA",
            category_is_transfer=False,
            category_kind=CategoryKind.EXPENSE,
        )
        == TransactionFlow.TRANSFER_IN
    )
