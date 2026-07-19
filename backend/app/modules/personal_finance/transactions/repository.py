"""Queries a DB del módulo transactions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import Delete, Select, Update, case, cast, func, null, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.personal_finance.accounts.models import Account, AccountNature
from app.modules.personal_finance.categories.models import (
    Category,
    CategoryKind,
    CategoryRole,
)
from app.modules.personal_finance.dashboard.conversion import converted_amount_expr
from app.modules.personal_finance.transactions.models import Transaction, TransactionFlow


def _debt_only_condition(own_account: Any, partner_account: Any) -> Any:
    """Condición 'la tx es de deuda': su categoría tiene rol de deuda (un PAGO)
    o es pata de un par de conversión a deuda (activo↔pasivo — dinero prestado).
    EXCLUYE los movimientos de una cuenta que NO cuenta como deuda
    (`counts_as_debt=False`, tarjeta revolving pagada íntegra): su cuenta O su
    pareja tiene el flag apagado → adeudo/liquidación, no deuda real.

    Requiere que la query tenga joins a `Category` (por `category_id`), a
    `own_account` (la cuenta propia) y a `partner_account` (la de la pareja).
    Misma señal que la columna `is_debt_pair` del listado, más el rol.
    """
    is_debt = Category.role.in_([CategoryRole.DEBT_PAYMENT, CategoryRole.DEBT_INTEREST]) | (
        Transaction.transfer_pair_id.is_not(None)
        & (
            (own_account.nature == AccountNature.LIABILITY)
            | (partner_account.nature == AccountNature.LIABILITY)
        )
    )
    # Excluir si la cuenta propia o la pareja es una cuenta no-deuda (revolving).
    # `partner_account` viene de un outerjoin (NULL sin pareja) → coalesce a True.
    from_non_debt = (own_account.counts_as_debt.is_(False)) | (
        func.coalesce(partner_account.counts_as_debt, True).is_(False)
    )
    return is_debt & ~from_non_debt


# `active`  → `deleted_at IS NULL`  (default — listado normal, dashboard).
# `trashed` → `deleted_at IS NOT NULL` (endpoint /trash, restore, purge).
# `any`     → sin filtro (uso interno, p.ej. lookup para restore/purge
#             que ya saben qué transacción quieren).
DeletedScope = Literal["active", "trashed", "any"]


def _scope[Q: Select[Any] | Update | Delete](
    query: Q,
    user_id: uuid.UUID,
    *,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    uncategorized: bool = False,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    deleted: DeletedScope = "active",
) -> Q:
    """Filtros comunes (user_id obligatorio + opcionales).

    Aplicable tanto a SELECT como a UPDATE (bulk soft-delete) — el
    `where()` chaining funciona idéntico en ambos.

    `uncategorized=True` filtra las tx SIN categoría (`category_id IS
    NULL`) y, al ser el caso "sin categoría", IGNORA `category_id` (no
    tiene sentido pedir ambos). Sostiene el atajo "Ver y categorizar"
    del banner de transacciones sin clasificar.
    """
    conditions: list[Any] = [Transaction.user_id == user_id]
    if deleted == "active":
        conditions.append(Transaction.deleted_at.is_(None))
    elif deleted == "trashed":
        conditions.append(Transaction.deleted_at.is_not(None))
    if account_id is not None:
        conditions.append(Transaction.account_id == account_id)
    if uncategorized:
        conditions.append(Transaction.category_id.is_(None))
    elif category_id is not None:
        conditions.append(Transaction.category_id == category_id)
    if date_from is not None:
        conditions.append(Transaction.occurred_at >= date_from)
    if date_to is not None:
        conditions.append(Transaction.occurred_at <= date_to)
    if search:
        conditions.append(Transaction.description.ilike(f"%{search}%"))
    # SQLAlchemy's .where() doesn't preserve the Q TypeVar (it returns the
    # union of the bound); the runtime type matches the input statement.
    return query.where(*conditions)  # type: ignore[return-value]


async def list_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    uncategorized: bool = False,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    target_currency: str | None = None,
    debt_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Transaction, Decimal | None, bool]], int]:
    """Lista transacciones activas filtradas + total count.

    Las soft-deleted no aparecen — para verlas usar `list_trashed_transactions`.

    `debt_only=True` restringe a transacciones de deuda (rol de categoría
    `DEBT_PAYMENT`/`DEBT_INTEREST` o pata de par de conversión a deuda). Sirve
    para listar los movimientos de deuda de un periodo SIN que el tope de
    `limit` deje fuera los antiguos (son pocos, caben sin truncar).

    Cuando se pasa `target_currency`, cada fila incluye el importe
    convertido a esa moneda con la tasa **del día de su `occurred_at`**
    (vía `converted_amount_expr`). NULL si no hay tasa disponible. En
    modo legacy (`target_currency=None`) la segunda parte de la tupla
    es siempre `None`.

    El tercer elemento de la tupla es `is_debt_pair`: `True` cuando la
    tx forma parte de un par de conversión a deuda (activo↔pasivo), es
    decir cuando su cuenta O la cuenta de su pareja es una liability. La
    UI usa esa señal para marcar la fila como "Deuda" (en vez de
    "Transferencia") y pintar el importe en neutro — coherente con que
    la pata-activo aporta 0 al patrimonio (fix activo-fantasma). Un par
    de transferencia interna activo↔activo da `False`.
    """
    count_query = select(func.count()).select_from(Transaction)
    if debt_only:
        # Mismos joins que el items_query para poder aplicar la condición de
        # deuda también al recuento (si no, `total` no cuadraría con las filas).
        own_c = aliased(Account)
        partner_tx_c = aliased(Transaction)
        partner_account_c = aliased(Account)
        count_query = (
            count_query.join(own_c, own_c.id == Transaction.account_id)
            .outerjoin(partner_tx_c, partner_tx_c.id == Transaction.transfer_pair_id)
            .outerjoin(partner_account_c, partner_account_c.id == partner_tx_c.account_id)
            .outerjoin(Category, Category.id == Transaction.category_id)
            .where(_debt_only_condition(own_c, partner_account_c))
        )
    count_query = _scope(
        count_query,
        user_id,
        account_id=account_id,
        category_id=category_id,
        uncategorized=uncategorized,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    total = (await db.execute(count_query)).scalar_one()

    if target_currency is not None:
        converted_col = converted_amount_expr(target_currency).label("converted_amount")
    else:
        converted_col = null().label("converted_amount")

    # Self-joins para clasificar el par: la cuenta propia y la de la
    # pareja (si la hay). Una fila es "pata de deuda" SÓLO si está
    # emparejada (`transfer_pair_id` no nulo) Y alguna de las dos patas
    # vive en una liability (par activo↔pasivo). El requisito de
    # emparejamiento es clave: sin él, un cargo normal en una tarjeta
    # (cuenta liability, sin par) saldría marcado como deuda. El inner
    # join sobre la cuenta propia es seguro: `account_id` es NOT NULL
    # desde PHASE-21.2.
    own_account = aliased(Account)
    partner_tx = aliased(Transaction)
    partner_account = aliased(Account)
    is_debt_pair_col = case(
        (
            Transaction.transfer_pair_id.is_not(None)
            & (
                (own_account.nature == AccountNature.LIABILITY)
                | (partner_account.nature == AccountNature.LIABILITY)
            ),
            True,
        ),
        else_=False,
    ).label("is_debt_pair")

    items_query = (
        select(Transaction, converted_col, is_debt_pair_col)
        .join(own_account, own_account.id == Transaction.account_id)
        .outerjoin(partner_tx, partner_tx.id == Transaction.transfer_pair_id)
        .outerjoin(partner_account, partner_account.id == partner_tx.account_id)
    )
    if debt_only:
        items_query = items_query.outerjoin(Category, Category.id == Transaction.category_id).where(
            _debt_only_condition(own_account, partner_account)
        )
    items_query = _scope(
        items_query,
        user_id,
        account_id=account_id,
        category_id=category_id,
        uncategorized=uncategorized,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    items_query = items_query.order_by(Transaction.occurred_at.desc()).limit(limit).offset(offset)

    result = await db.execute(items_query)
    items: list[tuple[Transaction, Decimal | None, bool]] = []
    for tx, converted, is_debt_pair in result.all():
        items.append(
            (tx, Decimal(converted) if converted is not None else None, bool(is_debt_pair))
        )
    return items, total


async def list_trashed_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Transaction], int]:
    """Lista transacciones en papelera del usuario, ordenadas por
    `deleted_at DESC` (las más recientemente borradas primero).

    No acepta filtros adicionales — la papelera es una vista plana de
    "qué borré recientemente". Si crece y hace falta buscar, añadir
    filtros entonces.
    """
    count_query = select(func.count()).select_from(Transaction)
    count_query = _scope(count_query, user_id, deleted="trashed")
    total = (await db.execute(count_query)).scalar_one()

    items_query = (
        _scope(select(Transaction), user_id, deleted="trashed")
        .order_by(Transaction.deleted_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(items_query)
    return list(result.scalars().all()), total


async def get_transaction_by_id(
    db: AsyncSession,
    transaction_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    deleted: DeletedScope = "active",
) -> Transaction | None:
    """Obtiene una transacción por ID, filtrando por user_id.

    Por defecto sólo devuelve activas. Para restore/purge el caller
    pide `deleted="trashed"` (sólo papelera) o `deleted="any"`
    (cualquiera, p.ej. para reads internas).
    """
    query = select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.id == transaction_id,
    )
    if deleted == "active":
        query = query.where(Transaction.deleted_at.is_(None))
    elif deleted == "trashed":
        query = query.where(Transaction.deleted_at.is_not(None))
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_uncategorized_summary(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[int, Decimal, str]:
    """Conteo, importe total y moneda mayoritaria de las tx activas sin
    categoría (AUDIT-2026-05: extraído del router).

    Si el usuario tiene tx sin categoría en varias monedas, devuelve la
    moneda con más tx y el total en esa moneda — caso borde razonable
    para el banner UX. Sin tx sin categoría → `(0, Decimal('0'), 'EUR')`.
    """
    rows = (
        await db.execute(
            select(
                func.count(Transaction.id),
                func.coalesce(func.sum(Transaction.amount), 0),
                Transaction.currency,
            )
            .where(Transaction.user_id == user_id)
            .where(Transaction.deleted_at.is_(None))
            .where(Transaction.category_id.is_(None))
            .group_by(Transaction.currency)
        )
    ).all()
    if not rows:
        return (0, Decimal("0"), "EUR")
    rows_sorted = sorted(rows, key=lambda r: r[0], reverse=True)
    _count, amount, currency = rows_sorted[0]
    total_count = sum(int(r[0]) for r in rows)
    return (total_count, Decimal(amount or 0), str(currency))


async def create_transaction(db: AsyncSession, transaction: Transaction) -> Transaction:
    """Persiste una nueva transacción."""
    db.add(transaction)
    await db.flush()
    await db.refresh(transaction)
    return transaction


async def soft_delete_transaction(db: AsyncSession, transaction: Transaction) -> Transaction:
    """Marca la transacción como borrada (mueve a papelera).

    Usa `datetime.now(UTC)` (Python-side) en lugar de `func.now()` por
    coherencia con el typing del campo (`Mapped[datetime | None]`); la
    diferencia de microsegundos vs server-clock es irrelevante para el
    uso de papelera (ordenar deleted_at desc).

    PHASE-41: una transferencia interna es ATÓMICA. Al trashear una pata
    trasheamos también su pareja y CONSERVAMOS `transfer_pair_id` en ambas.
    Así restaurar re-vincula el par gratis (`restore_transaction`) y NUNCA
    queda una pata activa apuntando a una fila borrada — la discrepancia
    silenciosa que AUDIT-2026-05 intentó resolver anulando el enlace: las dos
    activas se excluyen del cashflow por estar emparejadas; las dos borradas,
    por `deleted_at`. Para borrar UNA sola pata, deshaz el enlace antes (mismo
    contrato que editar una pata emparejada).
    """
    now = datetime.now(UTC)
    transaction.deleted_at = now
    if transaction.transfer_pair_id is not None:
        partner = await db.get(Transaction, transaction.transfer_pair_id)
        if (
            partner is not None
            and partner.user_id == transaction.user_id
            and partner.deleted_at is None
        ):
            partner.deleted_at = now
    await db.flush()
    await db.refresh(transaction)
    return transaction


async def bulk_soft_delete_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
) -> int:
    """Mueve a papelera todas las transacciones activas del usuario que
    matcheen los filtros. Devuelve el número de filas afectadas.

    Usa los mismos filtros que `list_transactions` para que "borrar todo
    lo que veo en pantalla con este filtro" sea exacto. Si no se pasa
    ningún filtro, mueve todas las transacciones activas del usuario.

    AUDIT-2026-07 (H-01): `account_id` se propaga a `_scope` como los demás
    filtros. Antes el endpoint no lo declaraba y FastAPI lo descartaba, así
    que "borrar todo" con el listado filtrado por una cuenta trasheaba TODAS
    las cuentas — el alcance real no coincidía con el prometido en el diálogo.
    """
    # AUDIT-2026-05 / PHASE-41: capturamos los ids que ESTE bulk va a trashear
    # ANTES de hacerlo, para propagar la papelera SÓLO a las parejas de las
    # filas que acabamos de mover. (Una versión anterior usaba "todas las
    # trasheadas del usuario", lo que afectaba a parejas preexistentes aunque
    # no matchearan el filtro del bulk.)
    select_ids = _scope(
        select(Transaction.id),
        user_id,
        account_id=account_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        deleted="active",
    )
    to_delete_ids = list((await db.execute(select_ids)).scalars().all())

    stmt = update(Transaction).values(deleted_at=datetime.now(UTC))
    stmt = _scope(
        stmt,
        user_id,
        account_id=account_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        deleted="active",
    )
    result = await db.execute(stmt)

    # PHASE-41: propaga la papelera a la pareja ACTIVA de cualquier pata recién
    # trasheada (transferencia atómica). Conservamos los punteros para que
    # restaurar re-vincule. Sustituye al antiguo `orphan_unlink`, que anulaba
    # el superviviente (dejaba media pareja suelta y perdía el enlace).
    if to_delete_ids:
        cascade_trash = (
            update(Transaction)
            .where(Transaction.user_id == user_id)
            .where(Transaction.deleted_at.is_(None))
            .where(Transaction.transfer_pair_id.in_(to_delete_ids))
            .values(deleted_at=datetime.now(UTC))
        )
        await db.execute(cascade_trash)
    await db.flush()
    # SQLAlchemy tipa execute() como Result (sin `rowcount`); en un DML el
    # runtime devuelve CursorResult, que sí lo expone.
    return result.rowcount or 0  # type: ignore[attr-defined]


async def bulk_update_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    transaction_ids: list[uuid.UUID],
    category_id: uuid.UUID | None,
) -> int:
    """PHASE-34 — Asigna `category_id` a un conjunto EXPLÍCITO de tx activas
    (selección por checkbox en la lista). Relabel money-neutral: el dinero
    (signo del saldo, cashflow) lo manda `flow` y NO cambia al mover la
    etiqueta. `category_id=None` quita la categoría. Filtra por `user_id`
    (aislamiento) y excluye soft-deleted. Devuelve filas afectadas.

    AUDIT-2026-07 (LOW): antes de relabelar, FIJAMOS `flow` para las filas SIN
    flow (heredadas) derivándolo de su categoría ACTUAL (mismo mapeo que
    `_flow_from_category`/backfill 34.1). Sin esto, una fila sin flow dependía
    del fallback por categoría, así que recategorizarla PODÍA invertir su
    dirección en silencio — el "relabel puro" no era money-neutral para esas
    filas. Al pinchar el flow primero, el dinero queda anclado y no se mueve.
    """
    if not transaction_ids:
        return 0
    pin_flow = (
        update(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.id.in_(transaction_ids))
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.flow.is_(None))
        .where(Transaction.category_id == Category.id)
        .values(
            # `cast` al tipo enum de la columna: sin él SQLAlchemy renderiza el
            # CASE como `text` y Postgres rechaza asignarlo a `transactionflow`.
            flow=cast(
                case(
                    (
                        Category.is_transfer.is_(True) & (Category.kind == CategoryKind.INCOME),
                        TransactionFlow.TRANSFER_IN,
                    ),
                    (Category.is_transfer.is_(True), TransactionFlow.TRANSFER_OUT),
                    (Category.kind == CategoryKind.INCOME, TransactionFlow.IN),
                    (Category.kind == CategoryKind.EXPENSE, TransactionFlow.OUT),
                    else_=None,
                ),
                Transaction.flow.type,
            )
        )
    )
    await db.execute(pin_flow)
    stmt = (
        update(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.id.in_(transaction_ids))
        .where(Transaction.deleted_at.is_(None))
        .values(category_id=category_id)
    )
    result = await db.execute(stmt)
    await db.flush()
    # SQLAlchemy tipa execute() como Result (sin `rowcount`); en un DML el
    # runtime devuelve CursorResult, que sí lo expone.
    return result.rowcount or 0  # type: ignore[attr-defined]


async def bulk_reassign_account(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    target_account_id: uuid.UUID,
    target_currency: str,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
) -> int:
    """PHASE-32 — Mueve a `target_account_id` todas las tx activas del
    usuario que matcheen los filtros (mismos que el listado). Devuelve
    cuántas se reasignaron.

    Excluye:
    - Transferencias internas (`transfer_pair_id` no nulo): mover una
      sola pata corrompería el par. El usuario las gestiona aparte.
    - Las que ya están en la cuenta destino (no-op).
    - **HIGH#3**: las de una divisa distinta a `target_currency` (la de la
      cuenta destino). El saldo por cuenta sólo agrega txs cuya
      `currency == account.currency` (ver `get_balances_for_user`), así
      que mover una tx EUR a una cuenta USD la haría DESAPARECER del saldo
      de ambas cuentas — pérdida silenciosa. Se quedan donde están; el
      caller informa cuántas se omitieron por divisa.
    """
    stmt = update(Transaction).values(account_id=target_account_id)
    stmt = _scope(
        stmt,
        user_id,
        account_id=account_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        deleted="active",
    )
    stmt = (
        stmt.where(Transaction.transfer_pair_id.is_(None))
        .where(Transaction.account_id != target_account_id)
        .where(Transaction.currency == target_currency)
    )
    result = await db.execute(stmt)
    await db.flush()
    # SQLAlchemy tipa execute() como Result (sin `rowcount`); en un DML el
    # runtime devuelve CursorResult, que sí lo expone.
    return result.rowcount or 0  # type: ignore[attr-defined]


async def count_reassignable_skipped_by_currency(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    target_account_id: uuid.UUID,
    target_currency: str,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
) -> int:
    """HIGH#3 — cuántas tx matchean los filtros del reassign pero NO se
    mueven por tener una divisa distinta a la de la cuenta destino (las
    dejamos donde están para no sacarlas del saldo). Mismo scope que
    `bulk_reassign_account` salvo el signo del filtro de divisa.
    """
    stmt = select(func.count()).select_from(Transaction)
    stmt = _scope(
        stmt,
        user_id,
        account_id=account_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        deleted="active",
    )
    stmt = (
        stmt.where(Transaction.transfer_pair_id.is_(None))
        .where(Transaction.account_id != target_account_id)
        .where(Transaction.currency != target_currency)
    )
    return int((await db.execute(stmt)).scalar_one())


async def bulk_restore_trashed(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Restaura todas las transacciones del usuario que estén en papelera.

    Devuelve cuántas se restauraron. Idempotente: si la papelera está
    vacía, devuelve 0 sin tocar nada.

    PHASE-41: tras restaurar, sanea medias-parejas heredadas — anula
    `transfer_pair_id` en cualquier tx activa cuya pareja no esté activa y
    apuntando de vuelta. No-op para pares creados tras el borrado atómico
    (siempre simétricos); evita dejar una pata excluida del cashflow cuya
    contrapartida ya no existe.
    """
    stmt = update(Transaction).values(deleted_at=None)
    stmt = _scope(stmt, user_id, deleted="trashed")
    result = await db.execute(stmt)
    partner = aliased(Transaction)
    healthy_partner = (
        select(partner.id)
        .where(partner.id == Transaction.transfer_pair_id)
        .where(partner.deleted_at.is_(None))
        .where(partner.transfer_pair_id == Transaction.id)
        .exists()
    )
    heal = (
        update(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_not(None))
        .where(~healthy_partner)
        .values(transfer_pair_id=None)
    )
    await db.execute(heal)
    await db.flush()
    # SQLAlchemy tipa execute() como Result (sin `rowcount`); en un DML el
    # runtime devuelve CursorResult, que sí lo expone.
    return result.rowcount or 0  # type: ignore[attr-defined]


async def bulk_purge_trashed(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Elimina permanente (DELETE real) todas las transacciones del
    usuario que estén en papelera. Devuelve cuántas se eliminaron.

    Operación IRREVERSIBLE. El caller debe haber confirmado con el
    usuario antes de invocar.
    """
    # Necesitamos contar primero porque algunas variantes de
    # asyncpg/sqlalchemy no devuelven `rowcount` fiable en bulk
    # DELETE; preferimos un SELECT COUNT explícito sobre la misma
    # condición para tener una respuesta determinista al caller.
    count_query = select(func.count()).select_from(Transaction)
    count_query = _scope(count_query, user_id, deleted="trashed")
    count = (await db.execute(count_query)).scalar_one()

    if count == 0:
        return 0

    from sqlalchemy import delete as sa_delete

    delete_stmt = sa_delete(Transaction)
    delete_stmt = _scope(delete_stmt, user_id, deleted="trashed")
    await db.execute(delete_stmt)
    await db.flush()
    return int(count)


async def restore_transaction(db: AsyncSession, transaction: Transaction) -> Transaction:
    """Quita la marca de borrado (saca de papelera).

    PHASE-41: si la tx es pata de una transferencia, restaura también su
    contrapartida y re-vincula el par (atómico). Si la pareja fue purgada o
    re-emparejada en otro sitio, la tx vuelve SIN pareja — nunca dejamos una
    pata activa apuntando a una fila ausente.
    """
    transaction.deleted_at = None
    pair_id = transaction.transfer_pair_id
    if pair_id is not None:
        partner = await db.get(Transaction, pair_id)
        if (
            partner is not None
            and partner.user_id == transaction.user_id
            # La pareja sigue apuntando de vuelta, o está suelta (asimetría
            # heredada) → seguro (re)establecer el enlace bidireccional.
            and partner.transfer_pair_id in (transaction.id, None)
        ):
            partner.deleted_at = None
            partner.transfer_pair_id = transaction.id
            transaction.transfer_pair_id = partner.id
        else:
            transaction.transfer_pair_id = None
    await db.flush()
    await db.refresh(transaction)
    return transaction


async def purge_transaction(db: AsyncSession, transaction: Transaction) -> None:
    """Elimina la transacción de forma permanente (DELETE real)."""
    await db.delete(transaction)
    await db.flush()
