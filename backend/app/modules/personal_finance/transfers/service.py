"""Lógica de negocio del módulo transfers (PHASE-19.3)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.debt_reconciliation import (
    is_card_financed_op,
)
from app.modules.personal_finance.accounts.installments_repository import (
    generate_installments_for_account,
)
from app.modules.personal_finance.accounts.models import (
    Account,
    AccountNature,
    AccountType,
)
from app.modules.personal_finance.accounts.repository import (
    create_account as repo_create_account,
)
from app.modules.personal_finance.accounts.repository import (
    get_account_by_id,
    get_account_by_name,
)
from app.modules.personal_finance.categories.models import CategoryKind
from app.modules.personal_finance.categories.repository import (
    get_category_by_id,
)
from app.modules.personal_finance.transactions.models import (
    Transaction,
    TransactionFlow,
    TransactionSource,
)
from app.modules.personal_finance.transfers.repository import (
    assign_category as repo_assign_category,
)
from app.modules.personal_finance.transfers.repository import (
    find_mirror_charge,
    get_or_create_default_transfer_category,
    list_misclassified_transfers,
)
from app.modules.personal_finance.transfers.repository import (
    get_pair as repo_get_pair,
)
from app.modules.personal_finance.transfers.repository import (
    get_transaction as repo_get_tx,
)
from app.modules.personal_finance.transfers.repository import (
    link_pair as repo_link_pair,
)
from app.modules.personal_finance.transfers.repository import (
    unlink_pair as repo_unlink_pair,
)
from app.modules.personal_finance.transfers.schemas import (
    MisclassifiedTransfer,
    NewLiabilityForDebt,
    ReclassifyBulkResponse,
    TransferPairResponse,
)


def _delta_days(tx_a: Transaction, tx_b: Transaction) -> int:
    return abs((tx_a.occurred_at - tx_b.occurred_at).days)


def _pair_to_schema(
    out_tx: Transaction,
    in_tx: Transaction,
    *,
    absorbed_mirror_amount: Decimal | None = None,
) -> TransferPairResponse:
    return TransferPairResponse(
        out_transaction_id=out_tx.id,
        in_transaction_id=in_tx.id,
        amount=out_tx.amount,
        currency=out_tx.currency,
        out_account_id=out_tx.account_id,
        in_account_id=in_tx.account_id,
        out_occurred_at=out_tx.occurred_at,
        in_occurred_at=in_tx.occurred_at,
        delta_days=_delta_days(out_tx, in_tx),
        absorbed_mirror_amount=absorbed_mirror_amount,
    )


async def link_manually(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    out_transaction_id: uuid.UUID,
    in_transaction_id: uuid.UUID,
) -> TransferPairResponse:
    """Enlaza dos transacciones explícitamente como par de transferencia.

    Validaciones (todas → 400/409):
    - Las dos pertenecen al usuario y están activas.
    - Son distintas.
    - Cuentas distintas.
    - Mismo amount + currency.
    - Ninguna está ya emparejada (si lo está, primero hay que desenlazar).
    """
    if out_transaction_id == in_transaction_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes enlazar una transacción consigo misma.",
        )
    out_tx = await repo_get_tx(db, out_transaction_id, user_id)
    in_tx = await repo_get_tx(db, in_transaction_id, user_id)
    if out_tx is None or in_tx is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Una de las transacciones no existe o no es tuya.",
        )
    if out_tx.transfer_pair_id is not None or in_tx.transfer_pair_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Alguna de las transacciones ya forma parte de otra "
                "transferencia. Deshaz ese enlace antes de crear uno nuevo."
            ),
        )
    if out_tx.account_id == in_tx.account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Una transferencia interna requiere dos cuentas distintas.",
        )
    if out_tx.amount != in_tx.amount or out_tx.currency != in_tx.currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "El importe y la moneda deben coincidir entre las dos " "transacciones del par."
            ),
        )
    # PHASE-34: al emparejar, ambas patas son transferencia interna.
    out_tx.flow = TransactionFlow.TRANSFER_OUT
    in_tx.flow = TransactionFlow.TRANSFER_IN
    await repo_link_pair(db, out_tx, in_tx)
    return _pair_to_schema(out_tx, in_tx)


async def unlink(
    db: AsyncSession,
    user_id: uuid.UUID,
    transaction_id: uuid.UUID,
) -> None:
    """Deshace el par del que `transaction_id` forma parte. 404 si no
    pertenece al usuario o no está emparejada."""
    pair = await repo_get_pair(db, transaction_id, user_id)
    if pair is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La transacción no existe o no está emparejada.",
        )
    tx_a, tx_b = pair
    await repo_unlink_pair(db, tx_a, tx_b)


async def list_misclassified(db: AsyncSession, user_id: uuid.UUID) -> list[MisclassifiedTransfer]:
    """PHASE-31.2 — tx con categoría is_transfer cuyo kind no encaja con
    la dirección de su descripción. La UI las muestra agrupadas para
    recategorizar en bloque."""
    rows = await list_misclassified_transfers(db, user_id)
    return [
        MisclassifiedTransfer(
            transaction_id=tx.id,
            amount=tx.amount,
            currency=tx.currency,
            account_id=tx.account_id,
            occurred_at=tx.occurred_at,
            description=tx.description,
            current_category_id=cat.id,
            current_category_name=cat.name,
            current_category_kind=cat.kind.value,
            suggested_kind=suggested.value,
        )
        for tx, cat, suggested in rows
    ]


async def reclassify_bulk(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    transaction_ids: list[uuid.UUID],
    target_category_id: uuid.UUID | None = None,
) -> ReclassifyBulkResponse:
    """PHASE-31.2 — recategorizar en bloque las tx seleccionadas.

    Si `target_category_id` viene, se aplica a TODAS las tx (validando
    que pertenece al usuario y que su kind tiene sentido para is_transfer).

    Si NO viene, para cada tx el service infiere el kind opuesto al
    actual (las tx de la UI ya vienen identificadas como mal direccionadas)
    y busca/crea la categoría is_transfer del kind correcto vía
    `get_or_create_default_transfer_category`. Esto cubre el caso típico
    del bulk-fix tras un import: el usuario marca varias y se mueven al
    par opuesto sin tener que elegir categoría destino.

    Devuelve `{reclassified: N, errors: [...]}`. Una tx que no exista o
    no sea del usuario suma a `errors` con su id y mensaje, no aborta
    el resto.
    """
    if target_category_id is not None:
        target_cat = await get_category_by_id(db, target_category_id, user_id)
        if target_cat is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La categoría destino no existe o no es tuya.",
            )
        if not target_cat.is_transfer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=("La categoría destino debe ser una transferencia " "(is_transfer=true)."),
            )

    reclassified = 0
    errors: list[str] = []
    for tx_id in transaction_ids:
        tx = await repo_get_tx(db, tx_id, user_id)
        if tx is None:
            errors.append(f"{tx_id}: no encontrada")
            continue
        if tx.transfer_pair_id is not None:
            errors.append(f"{tx_id}: ya está en un par, no se toca")
            continue
        chosen_cat_id: uuid.UUID
        chosen_kind: CategoryKind
        if target_category_id is not None:
            chosen_cat_id = target_category_id
            chosen_kind = target_cat.kind  # type: ignore[union-attr]
        else:
            current_cat = (
                await get_category_by_id(db, tx.category_id, user_id) if tx.category_id else None
            )
            if current_cat is None or not current_cat.is_transfer:
                errors.append(
                    f"{tx_id}: la tx no está en una categoría is_transfer; "
                    "no se puede inferir el destino sin target_category_id"
                )
                continue
            opposite = (
                CategoryKind.INCOME
                if current_cat.kind == CategoryKind.EXPENSE
                else CategoryKind.EXPENSE
            )
            opposite_cat = await get_or_create_default_transfer_category(db, user_id, kind=opposite)
            chosen_cat_id = opposite_cat.id
            chosen_kind = opposite
        # PHASE-34: la dirección la fija el flow según el kind elegido.
        tx.flow = (
            TransactionFlow.TRANSFER_IN
            if chosen_kind == CategoryKind.INCOME
            else TransactionFlow.TRANSFER_OUT
        )
        await repo_assign_category(db, tx, chosen_cat_id)
        reclassified += 1

    return ReclassifyBulkResponse(reclassified=reclassified, errors=errors)


_INCOMING_DESCRIPTION_HINTS = (
    "recibida",
    "recibido",
    "entrante",
    "entrada",
    "a favor",
    "abono por transfer",
    "abono transfer",
    "ingreso por transfer",
    "transferencia desde",
    "transf desde",
    "traspaso recibido",
    "traspaso de",
    "provisión de",
    "provision de",
)

_OUTGOING_DESCRIPTION_HINTS = (
    "realizada",
    "realizado",
    "enviada",
    "enviado",
    "saliente",
    "salida",
    "transferencia hacia",
    "transf hacia",
    "cargo por transfer",
    "orden de pago",
    "ordenes pago",
    "traspaso enviado",
    "traspaso a",
)


def infer_transfer_kind(
    description: str | None,
    *,
    existing_category_kind: CategoryKind | None = None,
) -> CategoryKind | None:
    """PHASE-31.5 — Heurística para decidir si una tx es salida
    (EXPENSE) o entrada (INCOME) cuando el usuario la marca como
    transferencia.

    Orden de señales:
    1. Si la tx ya tiene categoría con kind explícito, respetarlo —
       asumimos que el rules engine + el usuario lo decidieron bien y
       no queremos sobreescribir esa decisión sólo porque la
       descripción no matchea nuestros hints.
    2. Si la descripción matchea hints INCOME → INCOME.
    3. Si la descripción matchea hints EXPENSE → EXPENSE.
    4. Si nada matchea, devolver `None` — el caller decide si fallar
       o pedir input al usuario. Antes devolvía EXPENSE por defecto,
       lo que producía cargos falsos cuando la descripción era
       ambigua (caso reportado).
    """
    if existing_category_kind is not None:
        return existing_category_kind
    if description is None:
        return None
    lowered = description.lower()
    incoming = any(hint in lowered for hint in _INCOMING_DESCRIPTION_HINTS)
    outgoing = any(hint in lowered for hint in _OUTGOING_DESCRIPTION_HINTS)
    # AUDIT MEDIUM#8 — guard de ambigüedad: si el texto matchea AMBAS listas
    # (p. ej. "TRASPASO A FAVOR DE JOSE" lleva "a favor"=incoming y
    # "traspaso a"=outgoing), no adivinamos: devolvemos None y el caller
    # decide (en imports, cae al signo del extracto). Antes ganaba siempre
    # incoming por orden, pudiendo invertir el signo.
    if incoming and not outgoing:
        return CategoryKind.INCOME
    if outgoing and not incoming:
        return CategoryKind.EXPENSE
    return None


# Alias retro-compatible: la función era privada hasta PHASE-32, cuando se
# expuso para reutilizarla en el pipeline de imports (corrección de
# dirección de transferencias). Tests y callers internos previos siguen
# importando el nombre con guion bajo.
_infer_transfer_kind = infer_transfer_kind


# ─────────────────────────────────────────────────────────────────────
# PHASE-34 — Clasificación de `flow` (modelo de dinero + tarjeta, ADR-0004)
# ─────────────────────────────────────────────────────────────────────

# Patrones de descripción que marcan un MOVIMIENTO INTERNO (no gasto ni
# ingreso real del mes): transferencias entre cuentas propias y pagos /
# liquidaciones de tarjeta de crédito.
#
# Modelo de tarjeta (cuentas exactas, vista unificada): las COMPRAS con
# tarjeta ya cuentan como gasto en el extracto de la tarjeta; el ADEUDO /
# liquidación / cuota financiada que las salda desde el banco es PAGO DE
# DEUDA (traspaso a la tarjeta), no gasto nuevo → se marca TRANSFER_* para
# no duplicar. BIZUM se EXCLUYE a propósito (suele ser pago a comercio →
# gasto real). OJO: estos patrones NO matchean "pago con tarjeta" (la
# compra de débito), que sí es gasto.
_INTERNAL_MOVEMENT_PATTERNS = (
    "transferencia",
    "transf.",
    "traspaso",
    "envio de dinero",
    "envío de dinero",
    "envio inmediato",
    "envío inmediato",
    "adeudo mensual de tarjeta",
    "liquidacion de tarjeta",
    "liquidación de tarjeta",
    "operacion financiada",
    "operación financiada",
    "cuota de tarjeta",
)


def is_internal_movement_text(text: str | None) -> bool:
    """True si la descripción indica un movimiento interno (transferencia o
    pago/liquidación de tarjeta) que NO debe contar como gasto/ingreso."""
    if not text:
        return False
    lowered = text.lower()
    return any(pattern in lowered for pattern in _INTERNAL_MOVEMENT_PATTERNS)


# AUDIT-2026-07 (W-01): marcadores de ingreso EXTERNO inequívoco. Una nómina o
# pensión pagada por transferencia es ingreso real, NUNCA un movimiento interno
# entre cuentas propias — sin esto, "TRANSFERENCIA ... NÓMINA" caía en el patrón
# "transferencia" y se excluía del cashflow, infravalorando el ingreso (y con
# él la tasa de ahorro y el DTI). No resuelve TODA la ambigüedad (una
# transferencia recibida de un tercero sigue siendo indistinguible por texto de
# un traspaso propio), pero corrige el caso de mayor impacto sin regresar la
# detección ES de traspasos/BIZUM.
_EXTERNAL_INCOME_MARKERS = ("nomina", "nómina", "pension", "pensión")


def _has_external_income_marker(text: str | None) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in _EXTERNAL_INCOME_MARKERS)


def classify_import_flow(
    *,
    bank_sign: int,
    text: str | None,
    category_is_transfer: bool,
    category_kind: CategoryKind | None = None,
) -> TransactionFlow | None:
    """Decide el `flow` de una fila importada (PHASE-34, ADR-0004).

    Dirección (entra/sale), por orden de fiabilidad:
    1. SIGNO DEL EXTRACTO (`bank_sign`) — invariante duro cuando existe.
    2. Si el extracto no trae signo (`bank_sign == 0`): el TEXTO
       (`infer_transfer_kind`: recibida/realizada…).
    3. Si el texto tampoco decide: el `category_kind` de la categoría
       resuelta (extractos sólo-magnitud, comportamiento histórico).
    4. Sin ninguna señal → `None`: movimiento sin clasificar (contribuye 0
       al saldo y queda fuera del cashflow, igual que una tx sin categoría).

    "Transfer-ness": de la categoría resuelta (`is_transfer`) O de la
    descripción (`is_internal_movement_text` — transferencia o pago de
    tarjeta). Nunca se infiere la dirección de `category.kind` cuando hay
    signo de extracto.
    """
    # La "transfer-ness" por TEXTO se tempera con el override de ingreso
    # externo (W-01): una nómina/pensión por transferencia es ingreso real. El
    # override NO pisa un `category_is_transfer` explícito (señal más fuerte que
    # el heurístico de descripción).
    text_says_internal = is_internal_movement_text(text) and not _has_external_income_marker(
        text
    )
    # PHASE-38 (decisión del usuario): la CUOTA de una compra a plazos con
    # tarjeta ("OPERACIÓN FINANCIADA CON TARJETA") SÍ cuenta como gasto real
    # del mes (visión de caja), a diferencia de la liquidación de tarjeta
    # ("ADEUDO MENSUAL DE TARJETA") o la creación de deuda ("OPERACIÓN
    # FINANCIADA" a secas), que siguen siendo movimientos internos neutros.
    # La compra financiada NO aparece como gasto en ningún otro sitio (la
    # compra original se modela como creación de deuda, neutra), así que
    # contar la cuota no dobla nada; la deuda la sigue descontando el cuadro
    # vía reconciliación (independiente del `flow`). `is_card_financed_op` es
    # la MISMA definición que usa la reconciliación → clasificador y matcher
    # no divergen (exige "operaci"+"financiada"+"tarjeta"; excluye el ADEUDO
    # y la "OPERACIÓN FINANCIADA" a secas). Gana sobre `text_says_internal`
    # (que también matchea por "operación financiada") y sobre un
    # `category_is_transfer` mal puesto: el concepto es inequívocamente cuota.
    is_transfer = (category_is_transfer or text_says_internal) and not is_card_financed_op(text)
    if bank_sign > 0:
        income = True
    elif bank_sign < 0:
        income = False
    else:
        kind = infer_transfer_kind(text) or category_kind
        if kind is None:
            return None
        income = kind == CategoryKind.INCOME
    if is_transfer:
        return TransactionFlow.TRANSFER_IN if income else TransactionFlow.TRANSFER_OUT
    return TransactionFlow.IN if income else TransactionFlow.OUT


async def convert_to_internal_transfer(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    source_transaction_id: uuid.UUID,
    originating_account_id: uuid.UUID,
    beneficiary_account_id: uuid.UUID,
) -> TransferPairResponse:
    """PHASE-23.1: convierte una tx existente en una transferencia
    interna entre las dos cuentas indicadas (ordenante + beneficiaria),
    crea la contraparte y empareja ambas vía `transfer_pair_id`.

    Reglas:
    1. La tx origen debe pertenecer al usuario y no estar pareada ya.
    2. Las dos cuentas deben ser distintas, del usuario y same currency
       (cross-currency es follow-up).
    3. La tx origen debe coincidir con la ordenante O con la
       beneficiaria — no se admite "ninguna de las dos".
    4. La categoría del origen se fuerza al kind correcto según su
       rol (ordenante → EXPENSE, beneficiaria → INCOME). Así el
       saldo de su cuenta refleja el signo real aunque el import
       hubiera asignado la categoría equivocada.
    5. Se crea la contraparte en la cuenta opuesta con el kind
       complementario, source=MANUAL y categoría is_transfer.
    6. Ambas quedan fuera del cashflow gracias a
       `transfer_pair_id IS NOT NULL` (dashboard/budgets ya lo respetan).
    """
    source = await repo_get_tx(db, source_transaction_id, user_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La transacción origen no existe o no es tuya.",
        )
    if source.transfer_pair_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "La transacción ya forma parte de un par. Deshaz el " "enlace antes de convertirla."
            ),
        )

    if originating_account_id == beneficiary_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La cuenta ordenante y la beneficiaria deben ser distintas.",
        )

    # La tx origen debe ser una de las dos. Si no coincide, el usuario
    # ha elegido un par que no incluye la cuenta en la que vive la tx
    # original — eso no se puede convertir (habría que crear AMBOS lados
    # desde cero, que es otro flujo, "Nueva transferencia").
    if source.account_id == originating_account_id:
        source_role = "originating"
        counterpart_account_id = beneficiary_account_id
    elif source.account_id == beneficiary_account_id:
        source_role = "beneficiary"
        counterpart_account_id = originating_account_id
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "La transacción origen no está en la cuenta ordenante "
                "ni en la beneficiaria seleccionadas."
            ),
        )

    originating = await get_account_by_id(db, originating_account_id, user_id)
    beneficiary = await get_account_by_id(db, beneficiary_account_id, user_id)
    if originating is None or beneficiary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Una de las cuentas indicadas no existe o no es tuya.",
        )
    if originating.currency != source.currency or beneficiary.currency != source.currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Transferencias cross-currency no soportadas todavía — "
                "ambas cuentas deben tener la misma moneda que la tx."
            ),
        )

    # Kind canónico según el rol del origen:
    #   - ordenante: el dinero SALE → EXPENSE en su cuenta.
    #   - beneficiaria: el dinero ENTRA → INCOME en su cuenta.
    source_kind = CategoryKind.EXPENSE if source_role == "originating" else CategoryKind.INCOME
    counterpart_kind = (
        CategoryKind.INCOME if source_kind == CategoryKind.EXPENSE else CategoryKind.EXPENSE
    )

    # Forzamos la categoría del origen al kind correcto — éste es el
    # fix clave: si la tx vino con "Transferencias (Gasto)" pero
    # realmente era un abono, la reemplazamos por "Transferencias
    # (Ingreso)" para que el saldo de la cuenta deje de pintar un cargo.
    canonical_source_category = await get_or_create_default_transfer_category(
        db, user_id, kind=source_kind
    )
    if source.category_id != canonical_source_category.id:
        await repo_assign_category(db, source, canonical_source_category.id)
    # PHASE-34: la dirección la fija el flow según el rol del origen.
    source.flow = (
        TransactionFlow.TRANSFER_OUT
        if source_kind == CategoryKind.EXPENSE
        else TransactionFlow.TRANSFER_IN
    )

    counterpart_category = await get_or_create_default_transfer_category(
        db, user_id, kind=counterpart_kind
    )

    # Descripción humana en la contraparte: "Transferencia desde X" si
    # la contraparte recibe el dinero, "hacia X" si lo manda.
    other_account = beneficiary if source_role == "originating" else originating
    source_account_name = originating.name if source_role == "originating" else beneficiary.name
    label = "desde" if counterpart_kind == CategoryKind.INCOME else "hacia"
    counterpart = Transaction(
        user_id=user_id,
        account_id=counterpart_account_id,
        category_id=counterpart_category.id,
        amount=source.amount,
        currency=source.currency,
        occurred_at=source.occurred_at,
        description=f"Transferencia {label} {source_account_name}",
        source=TransactionSource.MANUAL,
        flow=(
            TransactionFlow.TRANSFER_OUT
            if counterpart_kind == CategoryKind.EXPENSE
            else TransactionFlow.TRANSFER_IN
        ),
    )
    _ = other_account  # explicitamente ignorado; se computó arriba para validación de scope
    db.add(counterpart)
    await db.flush()

    await repo_link_pair(db, source, counterpart)

    # Devolvemos el par siempre como (out, in) — el out es el ordenante,
    # el in es la beneficiaria. Cualquiera de los dos puede ser el
    # source o el counterpart según el rol elegido.
    if source_role == "originating":
        return _pair_to_schema(source, counterpart)
    return _pair_to_schema(counterpart, source)


_LIABILITY_TYPES = {
    AccountType.CREDIT_CARD,
    AccountType.LOAN,
    AccountType.MORTGAGE,
}
# PHASE-24.2: tarjetas también pueden tener plan fijo (financiadas).
_LIABILITY_TYPES_AMORT = {
    AccountType.LOAN,
    AccountType.MORTGAGE,
    AccountType.CREDIT_CARD,
}


async def convert_to_debt_operation(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    source_transaction_id: uuid.UUID,
    destination_account_id: uuid.UUID | None,
    new_liability: NewLiabilityForDebt | None,
) -> TransferPairResponse:
    """PHASE-24: convierte una tx en operación financiada.

    Modelo: la tx origen suele ser un ingreso en una cuenta asset (el
    banco "te abona" el importe financiado). La contraparte se crea
    como gasto en una cuenta liability (`credit_card` / `loan` /
    `mortgage`) → el saldo de la liability sube por el importe (debt
    contraída). Ambas quedan emparejadas → fuera del cashflow.

    Exactamente uno de `destination_account_id` o `new_liability` debe
    venir:
    - `destination_account_id`: usa una liability existente del usuario.
    - `new_liability`: crea la cuenta al vuelo (apr/term/start_date
      opcionales pero recomendados para que el módulo de amortización
      muestre el cuadro).
    """
    source = await repo_get_tx(db, source_transaction_id, user_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La transacción origen no existe o no es tuya.",
        )
    if source.transfer_pair_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "La transacción ya forma parte de un par. Deshaz el " "enlace antes de convertirla."
            ),
        )
    if (destination_account_id is None) == (new_liability is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Debes indicar `destination_account_id` (liability "
                "existente) o `new_liability` (crear nueva), pero no "
                "ambos a la vez."
            ),
        )

    if new_liability is not None:
        liability = await _create_liability_for_debt(
            db,
            user_id,
            spec=new_liability,
            default_start=source.occurred_at.date(),
            default_currency=source.currency,
        )
        # PHASE-24.1: generar cuotas con principal = importe financiado
        # (la liability tiene opening_balance=0 porque la deuda se
        # representa vía la tx contraparte que se crea más abajo).
        await generate_installments_for_account(db, liability, principal_override=source.amount)
    else:
        assert destination_account_id is not None  # narrow for mypy
        found = await get_account_by_id(db, destination_account_id, user_id)
        if found is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La cuenta destino no existe o no es tuya.",
            )
        liability = found
        if liability.nature != AccountNature.LIABILITY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "La cuenta destino debe ser de tipo deuda " "(tarjeta, préstamo o hipoteca)."
                ),
            )

    if liability.id == source.account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La cuenta destino debe ser distinta a la del origen.",
        )
    if liability.currency != source.currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Operaciones financiadas cross-currency no soportadas "
                "todavía — la cuenta de deuda debe tener la misma moneda."
            ),
        )

    src_account = await get_account_by_id(db, source.account_id, user_id)
    source_name = src_account.name if src_account is not None else "otra cuenta"

    # La contraparte SIEMPRE es EXPENSE en la liability — eso hace que
    # la deuda suba (liability+expense → +amount en balance). El kind
    # del origen aquí no importa para la dirección como en transfer
    # asset↔asset; el contrato es "deuda contraída" = liability sube.
    counterpart_category = await get_or_create_default_transfer_category(
        db, user_id, kind=CategoryKind.EXPENSE
    )
    counterpart = Transaction(
        user_id=user_id,
        account_id=liability.id,
        category_id=counterpart_category.id,
        amount=source.amount,
        currency=source.currency,
        occurred_at=source.occurred_at,
        description=f"Deuda contraída desde {source_name}",
        source=TransactionSource.MANUAL,
        # La contraparte en la liability sube la deuda (salida de valor).
        flow=TransactionFlow.TRANSFER_OUT,
    )
    db.add(counterpart)
    await db.flush()

    # PHASE-34: la pata origen (dinero PRESTADO entrando en el activo) es
    # TRANSFER_IN; el carve-out pata-activo del saldo la sigue dejando en 0.
    source.flow = TransactionFlow.TRANSFER_IN
    await repo_link_pair(db, source, counterpart)

    # PHASE-34 — Anular el "cargo espejo": cuando el banco financia una
    # compra muestra el abono (esta tx, +X) y un cargo `ADEUDO/LIQUIDACIÓN
    # DE TARJETA` del MISMO importe (−X) que lo compensa (neto 0). Si lo
    # dejáramos suelto restaría del saldo sin contraparte. Lo movemos a la
    # papelera (reversible) — el saldo queda en neto 0 + la deuda creada.
    absorbed_mirror_amount: Decimal | None = None
    mirror = await find_mirror_charge(db, user_id, source)
    if mirror is not None:
        mirror.deleted_at = datetime.now(UTC)
        # AUDIT-2026-07 (H-04): marca el borrado como "absorbido por el
        # sistema" (no papelera de usuario) para que reimportar el extracto
        # no resucite este −X — `find_existing_hashes` lo tratará como
        # existente.
        mirror.absorbed_as_mirror = True
        await db.flush()
        absorbed_mirror_amount = mirror.amount

    # Para el response, presentamos el par con el origen como "in"
    # (entró dinero en BBVA) y la contraparte como "out" (deuda creada
    # en la liability).
    return _pair_to_schema(counterpart, source, absorbed_mirror_amount=absorbed_mirror_amount)


async def _create_liability_for_debt(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    spec: NewLiabilityForDebt,
    default_start: date,
    default_currency: str,
) -> Account:
    """Crea una nueva cuenta liability con los datos del spec. Aplica
    las mismas validaciones que `accounts.service.create_account`
    (nombre único, tipo soportado, amortización sólo para loan/mortgage)
    pero las hereda inline para no acoplar transfers con accounts.service.
    """
    try:
        account_type = AccountType(spec.type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de cuenta no soportado.",
        ) from exc
    if account_type not in _LIABILITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Para registrar una operación financiada, el tipo de "
                "cuenta nueva debe ser deuda (credit_card / loan / "
                "mortgage)."
            ),
        )
    duplicate = await get_account_by_name(db, user_id, name=spec.name)
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya tienes una cuenta con ese nombre.",
        )
    accepts_amortization = account_type in _LIABILITY_TYPES_AMORT
    currency = (spec.currency or default_currency).upper()
    # PHASE-35 — compra a plazos anidada bajo una tarjeta: valida el padre y
    # exige plan propio. Mismos invariantes que `accounts.service.create_account`,
    # con una diferencia: el capital NO viene de `opening_balance` (queda 0) sino
    # del importe de la tx origen (via `principal_override`); la fecha por defecto
    # es la de la tx. Por eso aquí sólo exigimos TIN + plazo.
    if spec.parent_account_id is not None:
        parent = await get_account_by_id(db, spec.parent_account_id, user_id)
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La tarjeta a la que asociar la compra no existe.",
            )
        if parent.is_archived:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La tarjeta indicada está archivada; no puedes anidar compras en ella.",
            )
        if parent.type != AccountType.CREDIT_CARD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se pueden añadir compras a plazos a una tarjeta de crédito.",
            )
        if parent.parent_account_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede anidar: la tarjeta indicada ya es una compra a plazos.",
            )
        if account_type != AccountType.CREDIT_CARD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Una compra a plazos debe ser de tipo tarjeta de crédito.",
            )
        if spec.apr is None or spec.term_months is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Una compra a plazos necesita TIN y plazo (meses) para generar "
                    "su cuadro; el importe se toma de la transacción."
                ),
            )
    account = Account(
        user_id=user_id,
        name=spec.name,
        type=account_type,
        nature=AccountNature.LIABILITY,
        currency=currency,
        color=spec.color,
        icon=spec.icon,
        apr=spec.apr if accepts_amortization else None,
        tae=spec.tae if accepts_amortization else None,
        term_months=spec.term_months if accepts_amortization else None,
        start_date=((spec.start_date or default_start) if accepts_amortization else None),
        total_to_pay=spec.total_to_pay if accepts_amortization else None,
        interest_only_first_payment=(
            spec.interest_only_first_payment if accepts_amortization else None
        ),
        parent_account_id=spec.parent_account_id,
    )
    return await repo_create_account(db, account)
