"""Queries del módulo transfers (PHASE-19.3)."""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

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
    distance = sa.func.abs(
        sa.func.extract("epoch", Transaction.occurred_at - source.occurred_at)
    )
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


async def list_unmatched_active_transactions(
    db: AsyncSession, user_id: uuid.UUID
) -> list[tuple[Transaction, CategoryKind | None]]:
    """Lista todas las txs activas del usuario sin pareja, junto con
    el `kind` de su categoría (o None si no tiene). El matcher usa el
    kind para emparejar income con expense.

    PHASE-23.1: excluye las txs cuya categoría tiene `is_transfer=true`
    — ya están marcadas como transferencia y no necesitan emparejarse.
    """
    query = (
        select(Transaction, Category.kind)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
            Transaction.transfer_pair_id.is_(None),
        )
        .where((Category.is_transfer.is_(None)) | (Category.is_transfer.is_(False)))
        .order_by(Transaction.occurred_at.asc())
    )
    rows = await db.execute(query)
    return [(tx, kind) for tx, kind in rows.all()]


async def list_pairs(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[Transaction, Transaction]]:
    """Lista pares emparejados del usuario, devolviendo (out, in).

    Usa `Transaction.amount` (el out se identifica por categoría
    `expense` cuando hay categoría; si no hay, asumimos que la fila
    con `transfer_pair_id < self.id` es out — esto sólo importa para
    presentar al usuario, el modelo no asume cuál es cuál).
    """
    # Selecciona todas las activas con pareja. Las agrupamos en pares
    # por unicidad de tupla ordenada (min_id, max_id).
    query = (
        select(Transaction, Category.kind)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
            Transaction.transfer_pair_id.is_not(None),
        )
        .order_by(Transaction.occurred_at.asc())
    )
    rows = (await db.execute(query)).all()
    by_id: dict[uuid.UUID, tuple[Transaction, CategoryKind | None]] = {
        tx.id: (tx, kind) for tx, kind in rows
    }
    seen: set[frozenset[uuid.UUID]] = set()
    pairs: list[tuple[Transaction, Transaction]] = []
    for tx_a, kind_a in rows:
        if tx_a.transfer_pair_id is None:
            continue
        partner = by_id.get(tx_a.transfer_pair_id)
        if partner is None:
            continue
        tx_b, kind_b = partner
        key = frozenset({tx_a.id, tx_b.id})
        if key in seen:
            continue
        seen.add(key)
        # Decide cuál es "out" para presentación: la que tenga categoría
        # con kind=expense; si ninguna lo tiene, usamos el orden por id.
        if kind_a == CategoryKind.EXPENSE or kind_b == CategoryKind.INCOME:
            pairs.append((tx_a, tx_b))
        elif kind_b == CategoryKind.EXPENSE or kind_a == CategoryKind.INCOME:
            pairs.append((tx_b, tx_a))
        else:
            # Sin pista — ordenamos por id para determinismo.
            if tx_a.id < tx_b.id:
                pairs.append((tx_a, tx_b))
            else:
                pairs.append((tx_b, tx_a))
    return pairs


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


def find_candidate_pairs(
    items: list[tuple[Transaction, CategoryKind | None]],
    *,
    window_days: int,
) -> list[tuple[Transaction, Transaction, int]]:
    """Recorre las txs no emparejadas y devuelve pares (out, in, delta_days)
    candidatos según el criterio:

    - mismo `amount` (Decimal exacto)
    - misma `currency`
    - cuentas distintas (`account_id` diferente)
    - `occurred_at` dentro de ±window_days
    - kind opuesto (expense vs income) cuando ambas tienen categoría
      con kind. Si una de las dos no tiene categoría, igualmente
      proponemos el par (el usuario decide).
    - cada tx aparece como mucho en UN par sugerido (las ambigüedades
      se resuelven por proximidad de fecha y luego por id determinista).

    No toca BD — es lógica pura para que el caller decida qué hacer
    con los pares (auto-link los no ambiguos, devolver el resto para
    confirmación).
    """
    out_candidates: list[tuple[Transaction, CategoryKind | None]] = []
    in_candidates: list[tuple[Transaction, CategoryKind | None]] = []
    unknown: list[tuple[Transaction, CategoryKind | None]] = []
    for tx, kind in items:
        if kind == CategoryKind.EXPENSE:
            out_candidates.append((tx, kind))
        elif kind == CategoryKind.INCOME:
            in_candidates.append((tx, kind))
        else:
            unknown.append((tx, kind))

    # Las "unknown" pueden actuar de cualquier lado — las añadimos a
    # ambos pools con su kind real (None) para que el matcher las
    # considere por importe/fecha/cuenta.
    out_pool = out_candidates + unknown
    in_pool = in_candidates + unknown

    used: set[uuid.UUID] = set()
    pairs: list[tuple[Transaction, Transaction, int]] = []

    # Estable: iteramos `out_pool` por fecha asc y para cada salida
    # buscamos la mejor entrada candidata aún disponible.
    out_pool_sorted = sorted(out_pool, key=lambda t: t[0].occurred_at)

    for out_tx, _out_kind in out_pool_sorted:
        if out_tx.id in used:
            continue
        best: tuple[Transaction, int] | None = None
        for in_tx, _in_kind in in_pool:
            if in_tx.id in used or in_tx.id == out_tx.id:
                continue
            if in_tx.amount != out_tx.amount:
                continue
            if in_tx.currency != out_tx.currency:
                continue
            if in_tx.account_id == out_tx.account_id:
                continue
            delta = abs((in_tx.occurred_at - out_tx.occurred_at).days)
            if delta > window_days:
                continue
            # Mejor candidato: menor delta; en empate, id menor para
            # determinismo (evita flapping entre runs).
            if best is None or delta < best[1] or (delta == best[1] and in_tx.id < best[0].id):
                best = (in_tx, delta)
        if best is not None:
            in_tx, delta = best
            pairs.append((out_tx, in_tx, delta))
            used.add(out_tx.id)
            used.add(in_tx.id)

    return pairs


# P1 (transfers-ux) — términos que delatan un movimiento entre cuentas en
# extractos de banca ESPAÑOLA. Antes sólo se buscaba "%transfer%" (inglés),
# así que BIZUM y TRASPASO — lo más frecuente — nunca salían como
# "sospechosas". `%TRANSFER%` cubre además "TRANSFERENCIA" (la contiene) y
# el inglés. Es una bandeja de REVISIÓN: tolera falsos positivos a cambio de
# no dejar fuera las transferencias reales. ILIKE es case-insensitive.
_TRANSFER_DISCOVERY_PATTERNS_SQL = (
    "%TRANSFER%",  # transfer / transferencia (EN + ES)
    "%TRANSF.%",  # abreviatura "transf." de algunos bancos
    "%TRASPASO%",
    "%BIZUM%",
    "%ENVIO DE DINERO%",
    "%ENVIO INMEDIATO%",
)


async def list_suspect_transactions(
    db: AsyncSession, user_id: uuid.UUID
) -> list[tuple[Transaction, uuid.UUID | None, str | None]]:
    """PHASE-23.1 / P1: lista txs activas, sin pareja, NO marcadas como
    transfer (categoría con `is_transfer=true`), cuya `description`
    delata un movimiento entre cuentas (transferencia, traspaso, Bizum…
    ver `_TRANSFER_DISCOVERY_PATTERNS_SQL`).

    Devuelve (tx, current_category_id, current_category_name) para que
    el frontend muestre la categoría actual antes de remarcar.
    """
    query = (
        select(Transaction, Category.id, Category.name)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_(None))
        .where((Category.is_transfer.is_(None)) | (Category.is_transfer.is_(False)))
        .where(_description_matches_any(_TRANSFER_DISCOVERY_PATTERNS_SQL))
        .order_by(Transaction.occurred_at.desc())
    )
    rows = await db.execute(query)
    return [(tx, cat_id, cat_name) for tx, cat_id, cat_name in rows.all()]


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


def filter_unambiguous(
    pairs: list[tuple[Transaction, Transaction, int]],
) -> tuple[list[tuple[Transaction, Transaction, int]], list[tuple[Transaction, Transaction, int]]]:
    """Separa pares en (sin ambigüedad, con ambigüedad).

    Un par es ambiguo si comparte el mismo (amount, currency, account_pair)
    con otro par del lote — el usuario debe confirmar cuál es cuál.
    Aquí "sin ambigüedad" significa que no hay otro par con la misma
    huella de identidad.
    """
    # Cuenta huellas: (amount, currency, frozenset({out_acc, in_acc}))
    counts: dict[tuple[Decimal, str, frozenset[uuid.UUID]], int] = {}
    for out_tx, in_tx, _ in pairs:
        key = (
            out_tx.amount,
            out_tx.currency,
            frozenset({out_tx.account_id, in_tx.account_id}),
        )
        counts[key] = counts.get(key, 0) + 1

    unambiguous: list[tuple[Transaction, Transaction, int]] = []
    ambiguous: list[tuple[Transaction, Transaction, int]] = []
    for out_tx, in_tx, delta in pairs:
        key = (
            out_tx.amount,
            out_tx.currency,
            frozenset({out_tx.account_id, in_tx.account_id}),
        )
        if counts[key] == 1:
            unambiguous.append((out_tx, in_tx, delta))
        else:
            ambiguous.append((out_tx, in_tx, delta))
    return unambiguous, ambiguous
