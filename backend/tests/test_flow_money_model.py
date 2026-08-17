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
# Operación financiada → deuda: las DOS líneas del extracto se quedan y se
# cancelan solas (PHASE-47.F, antes se borraba el "cargo espejo").
# ─────────────────────────────────────────────────────────────────────


async def test_convert_to_debt_keeps_the_mirror_charge_and_nets_to_zero(session_factory) -> None:  # type: ignore[no-untyped-def]
    """El cargo que compensa al abono NO se borra: los dos suman 0 por sí solos.

    Cuando el banco financia una compra imprime dos líneas del mismo importe
    —el abono y el cargo que lo consume— y el saldo del extracto no se mueve.
    Antes se mandaba el cargo a la papelera y se anulaba el abono, lo que da el
    MISMO número por dos correcciones en vez de por ninguna; lo único que
    añadía era una forma de emparejar mal.
    """
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

    async with session_factory() as db:
        await convert_to_debt_operation(
            db, uid, source_transaction_id=abono, destination_account_id=card, new_liability=None
        )
        await db.commit()

    async with session_factory() as db:
        m = await db.get(Transaction, mirror)
        balances = await get_balances_for_user(db, uid)
    assert m is not None and m.deleted_at is None  # el cargo sigue vivo
    assert balances[bbva] == Decimal("0.00")  # +824,77 − 824,77
    assert balances[card] == Decimal("824.77")  # y la deuda queda


async def test_convert_to_debt_keeps_the_financing_credit_in_the_balance(  # type: ignore[no-untyped-def]
    session_factory,
) -> None:
    """El caso REAL de julio de 2026: el abono SIN su cargo gemelo en la cuenta.

    BBVA abonó 700,26 € el 07-jul —el saldo del propio extracto subió de 717,10
    a 1.417,36— y no cobró nada equivalente en esa cuenta: el recibo se saldó
    contra la tarjeta. Al registrarlo como deuda, la app anulaba ese abono, y el
    saldo de BBVA quedaba 700,26 € por debajo del que imprimía el banco.

    Ahora el abono cuenta como lo que es, caja que entró; la deuda la lleva la
    contrapartida y el patrimonio no se mueve, que es lo que significa que te
    presten dinero.
    """
    from app.modules.personal_finance.transfers.service import convert_to_debt_operation

    uid = await _seed_user(session_factory)
    bbva = await _seed_account(
        session_factory, uid, nature=AccountNature.ASSET, type_=AccountType.BANK
    )
    prestamo = await _seed_account(
        session_factory, uid, nature=AccountNature.LIABILITY, type_=AccountType.LOAN
    )
    abono = await _seed_tx(
        session_factory,
        uid,
        bbva,
        amount=Decimal("700.26"),
        flow=TransactionFlow.IN,
        description="Recibo anterior jun-26 Otras financiaciones",
    )

    async with session_factory() as db:
        await convert_to_debt_operation(
            db,
            uid,
            source_transaction_id=abono,
            destination_account_id=prestamo,
            new_liability=None,
        )
        await db.commit()

    async with session_factory() as db:
        origen = await db.get(Transaction, abono)
        balances = await get_balances_for_user(db, uid)
    assert balances[bbva] == Decimal("700.26")
    assert balances[prestamo] == Decimal("700.26")
    # Sale del cashflow (es dinero prestado, no un ingreso) pero conserva su
    # dirección: emparejar cambia QUÉ es el movimiento, no hacia dónde fue.
    assert origen is not None and origen.flow == TransactionFlow.TRANSFER_IN
    assert origen.transfer_pair_id is not None


async def test_convert_to_debt_keeps_the_direction_of_a_charge(session_factory) -> None:  # type: ignore[no-untyped-def]
    """Una tx origen que es un CARGO no se convierte en un abono al emparejarla.

    Se le imponía `TRANSFER_IN` fuera cual fuera su dirección, y era inocuo sólo
    porque el saldo la anulaba justo después. Sin esa anulación, imponerla haría
    que una compra SUBIERA el saldo de la cuenta.
    """
    from app.modules.personal_finance.transfers.service import convert_to_debt_operation

    uid = await _seed_user(session_factory)
    bbva = await _seed_account(
        session_factory, uid, nature=AccountNature.ASSET, type_=AccountType.BANK
    )
    card = await _seed_account(
        session_factory, uid, nature=AccountNature.LIABILITY, type_=AccountType.CREDIT_CARD
    )
    cargo = await _seed_tx(
        session_factory,
        uid,
        bbva,
        amount=Decimal("500.00"),
        flow=TransactionFlow.OUT,
        description="OPERACION FINANCIADA",
    )

    async with session_factory() as db:
        await convert_to_debt_operation(
            db, uid, source_transaction_id=cargo, destination_account_id=card, new_liability=None
        )
        await db.commit()

    async with session_factory() as db:
        origen = await db.get(Transaction, cargo)
        balances = await get_balances_for_user(db, uid)
    assert origen is not None and origen.flow == TransactionFlow.TRANSFER_OUT
    assert balances[bbva] == Decimal("-500.00")


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


# ─────────────────────────────────────────────────────────────────────
# PHASE-46 — La deuda que nace no es un ingreso.
#
# Medido en datos reales: BBVA financió el recibo de tarjeta de junio de 2026 y
# lo presentó con DOS redacciones que ninguna lista conocía, así que julio salió
# con 700,26 € de ingreso que nadie cobró y 700,26 € de gasto ya contado compra
# a compra. El mismo hecho, escrito "OPERACION FINANCIADA" en marzo, se había
# clasificado bien — la diferencia era la redacción, no el hecho.
# ─────────────────────────────────────────────────────────────────────


def test_classify_financing_inflow_is_never_income() -> None:
    """Un abono de financiación NO es ingreso: es un aplazamiento.

    El banco te adelanta un dinero y nace una deuda; contarlo como ingreso
    infla el mes, la tasa de ahorro y el ratio de endeudamiento a la vez.
    """
    for text in (
        "Recibo anterior jun-26 Otras financiaciones",
        "Operacion financiada Otras financiaciones",
        "FINANCIACION DE RECIBO",
    ):
        assert (
            classify_import_flow(bank_sign=1, text=text, category_is_transfer=False)
            == TransactionFlow.TRANSFER_IN
        ), text


def test_classify_financing_wording_as_charge_is_still_a_real_expense() -> None:
    """El MISMO producto con el signo contrario sí es gasto — y por eso la regla
    de arriba mira el signo.

    Cuando llega la cuota de lo financiado, el extracto vuelve a decir "otras
    financiaciones" pero es un cargo. Ese gasto no está contado en ningún otro
    sitio (su compra se modeló como creación de deuda, neutra), así que
    apagarlo por compartir la redacción escondería gasto real — que es
    exactamente el carve-out que costó PHASE-38.
    """
    assert (
        classify_import_flow(
            bank_sign=-1, text="Otras financiaciones cuota 3/36", category_is_transfer=False
        )
        == TransactionFlow.OUT
    )


def test_classify_financing_inflow_without_bank_sign_is_still_not_income() -> None:
    """El extracto de la TARJETA no trae signos, y la regla tenía que mirarlos.

    El caso real de julio de 2026: la financiación del recibo entró desde el
    extracto de la tarjeta, donde `bank_sign` vale 0 porque el fichero sólo
    trae magnitudes. La regla de financiación entrante exigía signo positivo,
    así que no podía dispararse ni cuando la dirección se conocía por otra vía
    —aquí, el kind de la categoría resuelta— y la fila entraba como `IN`:
    700,26 € de ingreso que nadie cobró, el 100 % del ingreso que la app
    atribuía al mes.

    La dirección y el signo no son lo mismo. La regla mira la primera.
    """
    assert (
        classify_import_flow(
            bank_sign=0,
            text="Recibo anterior jun-26 Otras financiaciones",
            category_is_transfer=False,
            category_kind=CategoryKind.INCOME,
        )
        == TransactionFlow.TRANSFER_IN
    )
    # Y el reverso, que es lo que impide arreglar esto de más: sin signo pero
    # con dirección de SALIDA, el mismo producto vuelve a ser gasto real. Quien
    # quite la condición de dirección en vez de cambiarla rompe esta línea.
    assert (
        classify_import_flow(
            bank_sign=0,
            text="Otras financiaciones cuota 3/36",
            category_is_transfer=False,
            category_kind=CategoryKind.EXPENSE,
        )
        == TransactionFlow.OUT
    )


def test_classify_card_settlement_new_wording_is_transfer() -> None:
    """ "Recibo mes anterior" es la liquidación de la tarjeta, igual que
    "Adeudo mensual de tarjeta": las compras ya contaron una a una en su mes,
    así que cobrarla otra vez al liquidarlas dobla el gasto."""
    assert (
        classify_import_flow(
            bank_sign=-1, text="Recibo mes anterior No categorizable", category_is_transfer=False
        )
        == TransactionFlow.TRANSFER_OUT
    )


def test_financing_inflow_and_card_settlement_are_not_confused() -> None:
    """Las dos redacciones se parecen y significan lo CONTRARIO.

    "Recibo anterior … Otras financiaciones" es el abono que crea la deuda;
    "Recibo mes anterior" es el cargo que salda la tarjeta. Si la segunda
    secuencia no exigiera "mes" en medio, el abono se clasificaría como
    liquidación y el buscador del cargo espejo podría absorber la pata
    equivocada.
    """
    from app.modules.personal_finance.debt.reconciliation import (
        is_card_settlement,
        is_financing_inflow,
    )

    abono = "Recibo anterior jun-26 Otras financiaciones"
    cargo = "Recibo mes anterior No categorizable"

    assert is_financing_inflow(abono) and not is_card_settlement(abono)
    assert is_card_settlement(cargo) and not is_financing_inflow(cargo)


def test_card_settlement_definition_is_shared_with_its_sql_consumer() -> None:
    """Gate: el clasificador y el consumidor SQL hablan de LA MISMA lista.

    Eran dos listas —una en el servicio, otra en el repositorio— y divergieron
    en silencio: "Recibo mes anterior" no estaba en ninguna, así que el cargo
    se contó como gasto Y quedó sin absorber. Este test falla si alguien vuelve
    a enumerar liquidaciones en un solo lado.

    Apuntaba al buscador del cargo espejo, que PHASE-47.F retiró. El gate NO se
    va con él: se repunta al consumidor SQL que sobrevive —el dedup de imports—
    porque lo que protege es que la definición siga siendo una sola, no quién
    la use.
    """
    from app.modules.personal_finance.debt.reconciliation import (
        CARD_SETTLEMENT_SEQUENCES,
        sql_like_patterns,
    )
    from app.modules.personal_finance.imports.repository import _CARD_SETTLEMENT_LIKE
    from app.modules.personal_finance.transfers.service import is_internal_movement_text

    assert sql_like_patterns(CARD_SETTLEMENT_SEQUENCES) == _CARD_SETTLEMENT_LIKE
    for tokens in CARD_SETTLEMENT_SEQUENCES:
        ejemplo = " ".join(tokens)
        assert is_internal_movement_text(ejemplo), ejemplo


# ─────────────────────────────────────────────────────────────────────
# PHASE-46 — La columna Saldo decide la dirección cuando el importe no la trae.
# ─────────────────────────────────────────────────────────────────────


def _fila(  # type: ignore[no-untyped-def]
    *, importe: str, saldo: str | None, texto: str, flow=None, fecha_dia: int = 6
):

    from app.modules.personal_finance.imports.service import ParsedRow

    return ParsedRow(
        amount=Decimal(importe),
        occurred_at=datetime(2026, 7, fecha_dia, 12, 0, tzinfo=UTC),
        description=texto,
        category_id=None,
        import_hash=f"h{texto}{importe}{fecha_dia}",
        flow=flow,
        statement_balance=Decimal(saldo) if saldo is not None else None,
        classify_text=texto,
        category_is_transfer=False,
    )


def test_balance_chain_resolves_an_unsigned_inflow() -> None:
    """El caso REAL: `Operación financiada` por 700,26 € entró sin clasificar
    porque el extracto no trae signos y el texto no dice ni abono ni recibido.

    El salto del saldo (717,10 → 1.417,36) prueba que es una entrada, y la
    prueba estaba dentro de la propia fila: PHASE-39 ya guardaba esa columna.
    Como el concepto es una financiación, el flow correcto es `TRANSFER_IN`
    (nace deuda), no `IN`.
    """
    from app.modules.personal_finance.imports.service import resolve_flows_from_balance_chain

    filas = [
        _fila(
            importe="21.97",
            saldo="717.10",
            texto="Www.amazon Pago con tarjeta",
            fecha_dia=5,
            flow=TransactionFlow.OUT,
        ),
        _fila(importe="700.26", saldo="1417.36", texto="Operación financiada 4940121100185049"),
    ]
    assert resolve_flows_from_balance_chain(filas) == (1, 0)
    assert filas[1].flow == TransactionFlow.TRANSFER_IN


def test_balance_chain_resolves_an_unsigned_outflow() -> None:
    from app.modules.personal_finance.imports.service import resolve_flows_from_balance_chain

    filas = [
        _fila(
            importe="10.00", saldo="1000.00", texto="Algo", fecha_dia=5, flow=TransactionFlow.OUT
        ),
        _fila(importe="40.00", saldo="960.00", texto="Concepto mudo"),
    ]
    assert resolve_flows_from_balance_chain(filas) == (1, 0)
    assert filas[1].flow == TransactionFlow.OUT


def test_balance_chain_stays_quiet_when_the_jump_does_not_match() -> None:
    """Si entre dos saldos hay un movimiento que no vemos, el salto no cuadra
    con el importe de la fila — y entonces NO se toca.

    Es la condición que hace segura la regla: una fila neutra es honesta; una
    dirección inventada a partir de un salto que no cuadra, no.
    """
    from app.modules.personal_finance.imports.service import resolve_flows_from_balance_chain

    filas = [
        _fila(
            importe="10.00", saldo="1000.00", texto="Algo", fecha_dia=5, flow=TransactionFlow.OUT
        ),
        _fila(importe="40.00", saldo="925.00", texto="Concepto mudo"),  # salto de 75, no de 40
    ]
    assert resolve_flows_from_balance_chain(filas) == (0, 0)
    assert filas[1].flow is None


def test_balance_chain_corrects_a_row_that_contradicts_the_statement() -> None:
    """PHASE-47.G — cuando el saldo contradice a la conjetura, gana el saldo.

    Este test afirmaba lo contrario («esto sólo rellena huecos») y su escenario
    era EXACTAMENTE el bug: el saldo sube 40 y la fila está marcada como gasto.
    Con esa regla, seis devoluciones entraron como gasto entre abril y julio de
    2026 —238,87 €, con el signo cambiado, que es el doble de error que
    perderlas— y ninguna llegó a contrastarse, porque una conjetura que acierta
    a decidir nunca se comprobaba.
    """
    from app.modules.personal_finance.imports.service import resolve_flows_from_balance_chain

    filas = [
        _fila(
            importe="10.00", saldo="1000.00", texto="Algo", fecha_dia=5, flow=TransactionFlow.OUT
        ),
        _fila(importe="40.00", saldo="1040.00", texto="Otro", flow=TransactionFlow.OUT),
    ]
    assert resolve_flows_from_balance_chain(filas) == (0, 1)
    assert filas[1].flow == TransactionFlow.IN


def test_balance_chain_leaves_alone_a_row_the_statement_confirms() -> None:
    """Y si el saldo confirma lo que la fila decía, no se toca nada.

    Es el guardarraíl del cambio de arriba: la cadena gobierna la DIRECCIÓN y
    sólo eso. Aquí el saldo baja 40 y la fila ya es un gasto — coinciden, así
    que no se reescribe (ni se reclasifica su transfer-ness, que la decide el
    texto y de la que el saldo no sabe nada).
    """
    from app.modules.personal_finance.imports.service import resolve_flows_from_balance_chain

    filas = [
        _fila(
            importe="10.00", saldo="1000.00", texto="Algo", fecha_dia=5, flow=TransactionFlow.OUT
        ),
        _fila(importe="40.00", saldo="960.00", texto="Otro", flow=TransactionFlow.OUT),
    ]
    assert resolve_flows_from_balance_chain(filas) == (0, 0)
    assert filas[1].flow == TransactionFlow.OUT


def test_balance_chain_reads_a_newest_first_statement() -> None:
    """BBVA imprime el más reciente arriba. Si se leyera en el orden del
    fichero, el salto saldría con el signo cambiado y la fila entraría al
    revés — peor que dejarla neutra."""
    from app.modules.personal_finance.imports.service import resolve_flows_from_balance_chain

    filas = [
        _fila(importe="700.26", saldo="1417.36", texto="Operación financiada 4940", fecha_dia=6),
        _fila(
            importe="21.97", saldo="717.10", texto="Amazon", fecha_dia=5, flow=TransactionFlow.OUT
        ),
    ]
    assert resolve_flows_from_balance_chain(filas) == (1, 0)
    assert filas[0].flow == TransactionFlow.TRANSFER_IN


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
