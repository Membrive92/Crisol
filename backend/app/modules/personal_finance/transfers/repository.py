"""Queries del módulo transfers (PHASE-19.3)."""

from __future__ import annotations

import uuid
from datetime import timedelta

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.categories.models import Category, CategoryKind
from app.modules.personal_finance.transactions.models import Transaction, TransactionFlow

# PHASE-34 — Patrones de descripción de una LIQUIDACIÓN / cargo de tarjeta
# (el "cargo espejo" que compensa el abono de una operación financiada). Se
# exige ESTE patrón además de importe+cuenta exactos para no anular un gasto
# cualquiera del mismo importe por accidente.
_CARD_SETTLEMENT_LIKE = (
    "%adeudo%tarjeta%",
    "%liquidacion%tarjeta%",
    "%liquidación%tarjeta%",
)
# Ventana de fechas alrededor del abono donde buscar el espejo (mismo ciclo).
_MIRROR_WINDOW = timedelta(days=31)


async def find_mirror_charge(
    db: AsyncSession, user_id: uuid.UUID, source: Transaction
) -> Transaction | None:
    """Busca el 'cargo espejo' de una operación financiada (PHASE-34).

    Cuando el banco financia una compra, muestra DOS líneas que se anulan
    (neto 0) y dejan la deuda: el abono `OPERACIÓN FINANCIADA` (+X) y un
    cargo `ADEUDO / LIQUIDACIÓN DE TARJETA` (−X) del MISMO importe. Al
    registrar el abono como deuda, ese cargo queda suelto restando del
    saldo. Esta query lo localiza para anularlo.

    Estricto, para no pillar un gasto cualquiera del mismo importe: misma
    cuenta + MISMO importe exacto + descripción de liquidación/adeudo de
    tarjeta + es un CARGO (salida) + sin emparejar + activa + distinta del
    abono + dentro de ±31 días. Devuelve el más cercano en fecha, o `None`.

    AUDIT-2026-07 (LOW): el espejo es por definición un CARGO, así que se exige
    `flow` de salida (`OUT`/`TRANSFER_OUT`; NULL para filas heredadas), lo que
    descarta un ingreso del mismo importe que casara con la descripción. Riesgo
    residual (aceptado): si el usuario tuviera DOS liquidaciones de tarjeta del
    MISMO importe exacto en ±31 días, se absorbería la más cercana en fecha —
    reversible desde papelera. Un match por comercio/referencia no es viable
    porque la línea ADEUDO no lo trae.
    """
    desc_match = sa.or_(*[Transaction.description.ilike(p) for p in _CARD_SETTLEMENT_LIKE])
    # El espejo es una SALIDA (cargo). `adeudo/liquidacion de tarjeta` cae en
    # los patrones de movimiento interno, así que suele quedar TRANSFER_OUT;
    # aceptamos también OUT y NULL (heredadas) para no perder ningún espejo.
    is_charge = sa.or_(
        Transaction.flow.in_([TransactionFlow.OUT, TransactionFlow.TRANSFER_OUT]),
        Transaction.flow.is_(None),
    )
    distance = sa.func.abs(sa.func.extract("epoch", Transaction.occurred_at - source.occurred_at))
    query = (
        select(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.account_id == source.account_id,
            Transaction.amount == source.amount,
            Transaction.id != source.id,
            Transaction.transfer_pair_id.is_(None),
            Transaction.deleted_at.is_(None),
            Transaction.occurred_at >= source.occurred_at - _MIRROR_WINDOW,
            Transaction.occurred_at <= source.occurred_at + _MIRROR_WINDOW,
            desc_match,
            is_charge,
        )
        .order_by(distance.asc())
        .limit(1)
    )
    return (await db.execute(query)).scalar_one_or_none()


async def get_transaction(
    db: AsyncSession, tx_id: uuid.UUID, user_id: uuid.UUID
) -> Transaction | None:
    """Obtiene una tx activa del usuario (o None). Filtra por
    `deleted_at IS NULL` para no permitir enlazar txs trasheadas.
    """
    query = select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.id == tx_id,
        Transaction.deleted_at.is_(None),
    )
    return (await db.execute(query)).scalar_one_or_none()


async def get_pair(
    db: AsyncSession, tx_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Transaction, Transaction] | None:
    """Devuelve (tx, partner) si la tx tiene pareja activa; None si no."""
    tx = await get_transaction(db, tx_id, user_id)
    if tx is None or tx.transfer_pair_id is None:
        return None
    partner = await get_transaction(db, tx.transfer_pair_id, user_id)
    if partner is None:
        return None
    return tx, partner


async def link_pair(db: AsyncSession, tx_a: Transaction, tx_b: Transaction) -> None:
    """Marca las dos txs como pareja (bidireccional). NO valida nada;
    el caller debe haber comprobado pertenencia + criterio."""
    tx_a.transfer_pair_id = tx_b.id
    tx_b.transfer_pair_id = tx_a.id
    await db.flush()


async def unlink_pair(db: AsyncSession, tx_a: Transaction, tx_b: Transaction) -> None:
    """Deshace la pareja, dejando ambas txs como movimientos normales."""
    tx_a.transfer_pair_id = None
    tx_b.transfer_pair_id = None
    await db.flush()


# PHASE-31.2 — patrones SQL para detectar dirección desde la descripción.
# Espejo de los hints en `transfers/service.py::_INCOMING/_OUTGOING_HINTS`
# pero formateados para `ILIKE` (con %), sin acentos para tolerar
# extractos descabezados, y sin solapamiento entre listas (un texto
# que matchee ambos sería ambiguo y queda fuera).
_INCOMING_PATTERNS_SQL = (
    "%RECIBIDA%",
    "%RECIBIDO%",
    "%ABONO POR TRANSFER%",
    "%ABONO TRANSFER%",
    "%INGRESO POR TRANSFER%",
    "%TRANSFERENCIA DESDE%",
    "%TRASPASO RECIBIDO%",
)
_OUTGOING_PATTERNS_SQL = (
    "%TRANSFERENCIA REALIZADA%",
    "%TRANSFERENCIA HACIA%",
    "%CARGO POR TRANSFER%",
    "%ORDEN DE PAGO%",
    "%TRASPASO ENVIADO%",
)


def _description_matches_any(patterns: tuple[str, ...]) -> sa.ColumnElement[bool]:
    """Devuelve un `OR(ILIKE pattern...)` para Transaction.description.
    Helper para mantener el query de misclassified legible.
    """
    from sqlalchemy import or_

    return or_(*(Transaction.description.ilike(p) for p in patterns))


async def list_misclassified_transfers(
    db: AsyncSession, user_id: uuid.UUID
) -> list[tuple[Transaction, Category, CategoryKind]]:
    """PHASE-31.2 — tx con categoría is_transfer cuyo kind no encaja con
    la dirección que dicta la descripción. Devuelve tuplas
    (tx, current_category, suggested_kind) para que la UI muestre el
    estado actual y la sugerencia.

    Reglas:
      - Categoría is_transfer=true (sino, no es candidata).
      - Si categoría kind=EXPENSE pero descripción matchea hints
        de INCOME → suggested INCOME.
      - Si categoría kind=INCOME pero descripción matchea hints
        de EXPENSE → suggested EXPENSE.
      - `transfer_pair_id IS NULL` para no tocar pares confirmados.
      - `deleted_at IS NULL` (no papelera).

    Si la descripción matchea ambos lados (texto ambiguo o muy raro),
    queda fuera — no se sugiere recategorización sin certeza.
    """
    from sqlalchemy import and_, or_

    incoming_match = _description_matches_any(_INCOMING_PATTERNS_SQL)
    outgoing_match = _description_matches_any(_OUTGOING_PATTERNS_SQL)
    mislabeled_expense = and_(
        Category.kind == CategoryKind.EXPENSE,
        incoming_match,
        ~outgoing_match,  # no ambiguo
    )
    mislabeled_income = and_(
        Category.kind == CategoryKind.INCOME,
        outgoing_match,
        ~incoming_match,
    )
    query = (
        select(Transaction, Category)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_(None))
        .where(Category.is_transfer.is_(True))
        .where(or_(mislabeled_expense, mislabeled_income))
        .order_by(Transaction.occurred_at.desc())
    )
    rows = await db.execute(query)
    out: list[tuple[Transaction, Category, CategoryKind]] = []
    for tx, cat in rows.all():
        suggested = (
            CategoryKind.INCOME if cat.kind == CategoryKind.EXPENSE else CategoryKind.EXPENSE
        )
        out.append((tx, cat, suggested))
    return out


async def get_or_create_default_transfer_category(
    db: AsyncSession, user_id: uuid.UUID, *, kind: CategoryKind
) -> Category:
    """Devuelve la primera categoría `is_transfer=true` del usuario con
    el `kind` pedido (oldest por created_at). Si no existe ninguna,
    crea "Transferencia interna (salida)" o "(entrada)" según kind.

    Por qué dos categorías: PHASE-23.1 separa "es transferencia"
    (flag is_transfer) del signo en el balance (kind). Necesitamos
    una categoría con kind=EXPENSE para la pata saliente y otra con
    kind=INCOME para la pata entrante — los saldos así reflejan el
    movimiento correctamente.
    """
    query = (
        select(Category)
        .where(Category.user_id == user_id)
        .where(Category.is_transfer.is_(True))
        .where(Category.kind == kind)
        .order_by(Category.created_at.asc())
        .limit(1)
    )
    existing = (await db.execute(query)).scalar_one_or_none()
    if existing is not None:
        return existing

    name = (
        "Transferencia interna (salida)"
        if kind == CategoryKind.EXPENSE
        else "Transferencia interna (entrada)"
    )
    cat = Category(
        user_id=user_id,
        name=name,
        kind=kind,
        is_transfer=True,
        color="#6B7280",
        icon="↔️",
    )
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return cat


async def assign_category(db: AsyncSession, tx: Transaction, category_id: uuid.UUID) -> None:
    """Asigna `category_id` a la tx y persiste el cambio."""
    tx.category_id = category_id
    await db.flush()
