"""Queries a DB del módulo accounts (PHASE-19.1)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.models import Account, AccountNature
from app.modules.personal_finance.categories.models import Category, CategoryKind
from app.modules.personal_finance.transactions.models import Transaction, TransactionFlow


# PHASE-34 (ADR-0004): la dirección del dinero la manda `transactions.flow`.
# Durante la transición, las filas sin flow (heredadas / write path aún sin
# migrar) caen a `category.kind`/`is_transfer` como antes. El fallback —y el
# join a Category de estas queries— se elimina en 34.6 cuando todo el write
# path escriba flow. Equivalente por construcción: el backfill de 34.1 hizo
# flow ≡ derivación por categoría.
def is_outflow() -> ColumnElement[bool]:
    """Movimiento de salida (resta del bolsillo del titular en la cuenta)."""
    return Transaction.flow.in_([TransactionFlow.OUT, TransactionFlow.TRANSFER_OUT]) | (
        Transaction.flow.is_(None) & (Category.kind == CategoryKind.EXPENSE)
    )


def is_inflow() -> ColumnElement[bool]:
    """Movimiento de entrada (suma al bolsillo del titular en la cuenta)."""
    return Transaction.flow.in_([TransactionFlow.IN, TransactionFlow.TRANSFER_IN]) | (
        Transaction.flow.is_(None) & (Category.kind == CategoryKind.INCOME)
    )


def _is_internal_transfer() -> ColumnElement[bool]:
    """Transferencia interna entre cuentas propias (neutra para ahorro/cashflow)."""
    return Transaction.flow.in_([TransactionFlow.TRANSFER_IN, TransactionFlow.TRANSFER_OUT]) | (
        Transaction.flow.is_(None) & Category.is_transfer.is_(True)
    )


def signed_amount_expr(account: Any) -> ColumnElement[Decimal]:
    """PHASE-37 — expresión de signo COMPARTIDA: cómo una tx afecta al saldo de
    SU cuenta según `account.nature` + flow. Un ÚNICO lugar para que
    `get_balances_for_user` y `position_history` (37.1) no diverjan — el
    invariante es que el último punto de la serie de patrimonio == los saldos
    actuales. `account` es la tabla o el alias de la cuenta.

    Convención (PHASE-19.4 + PHASE-22):
    - LIABILITY: salida/cargo sube la deuda (+amount), entrada/pago la baja (-amount).
    - ASSET: entrada suma, salida resta.
    - Sin flujo ni categoría → 0 (PHASE-31.3).

    **Aquí vivía un carve-out y por qué ya no (PHASE-47.F).** La pata-activo de
    un par de deuda —el abono con el que el banco te presta el dinero— aportaba
    0, con el argumento de que era un «activo fantasma» que inflaría el
    patrimonio. El argumento estaba invertido: caja +X contra deuda +X deja el
    patrimonio IGUAL, mientras que caja 0 contra deuda +X lo deja en −X. O sea
    que la app apuntaba la deuda y escondía el dinero, y recibir un préstamo te
    empobrecía sobre el papel.

    El coste real fue peor que un patrimonio torcido: el abono de 700,26 € que
    BBVA ingresó el 07-jul-2026 —con el saldo del propio extracto subiendo de
    717,10 a 1.417,36— desaparecía del saldo de la cuenta, que quedaba 700,26 €
    por debajo del banco. Un saldo de activo tiene un testigo externo
    (`anchored_statement_balance`, PHASE-39) y ninguna línea que el banco
    imprimió puede aportar 0 sin romperlo.
    """
    return case(
        ((account.nature == AccountNature.LIABILITY) & is_outflow(), Transaction.amount),
        ((account.nature == AccountNature.LIABILITY) & is_inflow(), -Transaction.amount),
        (is_outflow(), -Transaction.amount),
        (is_inflow(), Transaction.amount),
        else_=Decimal("0"),
    )


async def clear_settlement_references_to(
    db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID
) -> int:
    """PHASE-47.A — Desvincula los pasivos que declaraban cobrarse desde
    `account_id`. Devuelve cuántos se han desvinculado.

    Se llama cuando esa cuenta deja de ser un activo (cambio de tipo). El
    validador de `settlement_account_id` sólo mira la cuenta que se está
    editando, así que sin esto la conversión dejaría referencias que el propio
    validador rechaza: la siguiente edición de cada pasivo afectado devolvería
    un 400 sobre un campo que el formulario ya pinta como válido, y no habría
    forma de arreglarlo desde la interfaz.
    """
    stmt = (
        update(Account)
        .where(Account.user_id == user_id)
        .where(Account.settlement_account_id == account_id)
        .values(settlement_account_id=None)
    )
    result = await db.execute(stmt)
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def clear_default_accounts(
    db: AsyncSession, user_id: uuid.UUID, *, except_id: uuid.UUID | None = None
) -> None:
    """Desmarca `is_default` en todas las cuentas del usuario (PHASE-32),
    opcionalmente preservando `except_id`. Garantiza una sola cuenta
    principal por usuario."""
    stmt = (
        update(Account)
        .where(Account.user_id == user_id)
        .where(Account.is_default.is_(True))
        .values(is_default=False)
    )
    if except_id is not None:
        stmt = stmt.where(Account.id != except_id)
    await db.execute(stmt)


async def list_accounts(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    include_archived: bool = False,
) -> list[Account]:
    """Lista las cuentas del usuario ordenadas por `display_order` y nombre."""
    query = select(Account).where(Account.user_id == user_id)
    if not include_archived:
        query = query.where(Account.is_archived.is_(False))
    query = query.order_by(Account.display_order.asc(), Account.name.asc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_account_by_id(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID
) -> Account | None:
    """Obtiene una cuenta por ID, filtrando por user_id."""
    query = select(Account).where(Account.user_id == user_id, Account.id == account_id)
    return (await db.execute(query)).scalar_one_or_none()


async def get_account_by_name(db: AsyncSession, user_id: uuid.UUID, *, name: str) -> Account | None:
    """Match case-insensitive por nombre — usado para validar duplicados.

    AUDIT-2026-05: el match se hace en SQL (`lower()`) en vez de cargar
    todas las cuentas y escanear en Python. `lower()` cubre los nombres
    de cuenta reales; difiere de `casefold()` sólo en unicode exótico,
    irrelevante para este guard de duplicados.
    """
    query = (
        select(Account)
        .where(Account.user_id == user_id)
        .where(func.lower(Account.name) == name.lower())
        .limit(1)
    )
    return (await db.execute(query)).scalars().first()


async def count_transactions_for_account(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID
) -> int:
    """Cuántas transacciones (incluida papelera) están asociadas a la cuenta.

    Se usa antes de borrar para decidir entre hard delete o forzar
    archivar.
    """
    query = (
        select(func.count(Transaction.id))
        .where(Transaction.user_id == user_id)
        .where(Transaction.account_id == account_id)
    )
    return int((await db.execute(query)).scalar_one())


async def count_child_accounts(
    db: AsyncSession, parent_account_id: uuid.UUID, user_id: uuid.UUID
) -> int:
    """Cuántas cuentas hijas (compras a plazos, PHASE-35) cuelgan de esta
    cuenta. Se usa antes de borrar: `parent_account_id` es `ON DELETE
    CASCADE`, así que un DELETE real de la cuenta padre arrastraría sus
    hijas y la tx de deuda emparejada de cada una — resucitando el activo
    fantasma y perdiendo la deuda. El service lo valida y fuerza archivar."""
    query = (
        select(func.count(Account.id))
        .where(Account.user_id == user_id)
        .where(Account.parent_account_id == parent_account_id)
    )
    return int((await db.execute(query)).scalar_one())


async def create_account(db: AsyncSession, account: Account) -> Account:
    """Persiste una nueva cuenta."""
    db.add(account)
    await db.flush()
    await db.refresh(account)
    return account


async def delete_account(db: AsyncSession, account: Account) -> None:
    """DELETE real. Sólo permitido si la cuenta no tiene transacciones
    (el service lo valida antes y lanza 409 si no se cumple)."""
    await db.delete(account)
    await db.flush()


async def get_balances_for_user(db: AsyncSession, user_id: uuid.UUID) -> dict[uuid.UUID, Decimal]:
    """Suma neta de cada cuenta del usuario en la moneda nativa de la
    cuenta (sin conversión cross-currency).

    Convención del signo (PHASE-19.4 + PHASE-22):
    - Cuenta `nature=asset` (cte, broker, ahorro, cripto, cash):
        income suma, expense resta. Saldo positivo = dinero disponible.
    - Cuenta `nature=liability` (tarjeta, préstamo, hipoteca):
        expense **suma** (la compra aumenta la deuda), income **resta**
        (un pago/transfer entrante reduce la deuda). Saldo positivo =
        cuánto debes.
    - Sin categoría: el signo natural por `nature` (asset suma, liability
      suma como una entrada cualquiera).
    - Txs en papelera no cuentan.
    - Las transferencias internas activo↔activo SÍ cuentan al saldo
      individual de su cuenta. Modo cash para TODAS las cuentas
      (PHASE-23.1) — esta función es la fuente del saldo cash y del
      patrimonio neto agregado, donde las DOS patas de una transferencia
      interna activo↔activo se cancelan. El "ahorro neto" de la cuenta
      principal (PHASE-32) es un refinamiento de DISPLAY que vive en
      `service.get_balances` vía `get_net_savings_movement_for_account`;
      NO se aplica aquí para no romper la cancelación de patas en el
      agregado (si lo hiciéramos, una transferencia interna a la cuenta
      principal encogería el patrimonio neto — bug HIGH#1).
    - Un par activo↔pasivo (conversión a deuda) NO recibe trato especial
      desde PHASE-47.F: el abono con el que el banco presta el dinero es
      una línea del extracto y suma al activo, mientras la contrapartida
      eleva el pasivo. El patrimonio no se mueve, que es justo lo que
      significa recibir un préstamo. Ver `signed_amount_expr`.

    Sólo agrega txs cuya `currency` coincide con la `currency` de la
    cuenta. Multi-divisa dentro de una cuenta queda fuera.

    El saldo final del frontend es:
        opening_balance + balances[account_id]
    """
    # PHASE-34: la dirección la manda `flow`; `account.nature` decide el signo.
    # PHASE-37: la expresión vive en `signed_amount_expr` (compartida con
    # position_history) para no divergir.
    #
    # El `outerjoin(Category)` NO es opcional: `is_inflow`/`is_outflow` caen a
    # `Category.kind` cuando `flow` es NULL (filas heredadas) y sin el join
    # SQLAlchemy mete `categories` en el FROM como producto cartesiano.
    signed_amount = signed_amount_expr(Account)
    query = (
        select(
            Transaction.account_id,
            func.coalesce(func.sum(signed_amount), 0),
        )
        .select_from(Transaction)
        .join(Account, Account.id == Transaction.account_id)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.currency == Account.currency)
        .group_by(Transaction.account_id)
    )
    result = await db.execute(query)
    return {acc_id: Decimal(total) for acc_id, total in result.all()}


async def get_net_savings_movement_for_account(
    db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID
) -> Decimal:
    """Movimiento neto de UNA cuenta excluyendo transferencias internas
    (AHORRO NETO de la cuenta principal, PHASE-32).

    Igual convención de signo que `get_balances_for_user`, pero las txs
    cuya categoría es `is_transfer` aportan 0: mover dinero entre tus
    propias cuentas no es ahorrar ni gastar. Se usa SÓLO para el saldo
    que se MUESTRA de la cuenta principal; los agregados de patrimonio
    siguen usando el saldo cash de `get_balances_for_user` para que las
    dos patas de una transferencia interna se cancelen (HIGH#1).

    Aquí había una COPIA del carve-out de la pata-activo, retirada en
    PHASE-47.F con él. Era además redundante: las dos patas de un par de
    deuda son `TRANSFER_*`, así que la rama de transferencia interna de
    arriba ya las deja en 0 sin necesidad de mirar la naturaleza de la
    pareja.
    """
    # PHASE-34: transferencias internas (flow TRANSFER_*; fallback is_transfer)
    # aportan 0 — mover dinero entre cuentas propias no es ahorrar ni gastar.
    signed_amount = case(
        (_is_internal_transfer(), Decimal("0")),
        ((Account.nature == AccountNature.LIABILITY) & is_outflow(), Transaction.amount),
        ((Account.nature == AccountNature.LIABILITY) & is_inflow(), -Transaction.amount),
        (is_outflow(), -Transaction.amount),
        (is_inflow(), Transaction.amount),
        else_=Decimal("0"),
    )
    query = (
        select(func.coalesce(func.sum(signed_amount), 0))
        .select_from(Transaction)
        .join(Account, Account.id == Transaction.account_id)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.account_id == account_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.currency == Account.currency)
    )
    return Decimal((await db.execute(query)).scalar_one())


@dataclass(frozen=True, slots=True)
class StatementSeam:
    """Un tramo del extracto que la app no tiene (PHASE-47.G)."""

    after: datetime
    """Fecha del último movimiento conocido antes del hueco."""
    before: datetime
    """Fecha del primer movimiento conocido después."""
    amount: Decimal
    """Cuánto se movió el saldo ahí dentro, con signo. Negativo = salió dinero."""


async def find_statement_seams(
    db: AsyncSession, user_id: uuid.UUID
) -> dict[uuid.UUID, list[StatementSeam]]:
    """Dónde le falta extracto a cada cuenta, por cuenta.

    **Cómo se sabe.** Cada fila importada de un extracto con columna Saldo
    guarda el saldo que el banco imprimió DESPUÉS de ella (PHASE-39). Así que
    toda fila tiene un saldo anterior implícito: `saldo − movimiento`. Si ese
    valor no aparece en ninguna otra fila de la cuenta, entre medias hay
    movimientos que la app no tiene.

    La fila MÁS ANTIGUA de cada cuenta rompe la cadena por definición —no hay
    nada antes— y no cuenta como hueco. Las demás sí: son la costura entre dos
    extractos que no se tocan.

    **Por qué hace falta decirlo.** Un hueco no da ningún error: al anclar el
    saldo (PHASE-39), la diferencia se absorbe en `opening_balance` y la cuenta
    sigue cuadrando con el banco a día de hoy. Lo único que se rompe, en
    silencio, es la historia. En los datos del usuario había 1.211,95 € entre
    el 30-jun y el 5-jul de 2026 que no estaban en ningún extracto importado, y
    la app no tenía forma de decirlo.
    """
    rows = (
        (
            await db.execute(
                select(
                    Transaction.account_id,
                    Transaction.occurred_at,
                    Transaction.amount,
                    Transaction.flow,
                    Transaction.statement_balance,
                    Category.kind,
                )
                .outerjoin(Category, Category.id == Transaction.category_id)
                .where(Transaction.user_id == user_id)
                .where(Transaction.deleted_at.is_(None))
                .where(Transaction.statement_balance.is_not(None))
                .order_by(Transaction.account_id, Transaction.occurred_at)
            )
        )
        .tuples()
        .all()
    )

    by_account: dict[uuid.UUID, list[tuple[datetime, Decimal, Decimal]]] = {}
    for account_id, occurred_at, amount, flow, balance, kind in rows:
        if balance is None:  # el WHERE ya lo filtra; el tipo no lo sabe
            continue
        outflow = flow in (TransactionFlow.OUT, TransactionFlow.TRANSFER_OUT) or (
            flow is None and kind == CategoryKind.EXPENSE
        )
        signed = -amount if outflow else amount
        by_account.setdefault(account_id, []).append((occurred_at, signed, balance))

    seams: dict[uuid.UUID, list[StatementSeam]] = {}
    for account_id, entries in by_account.items():
        balances = {balance for _when, _signed, balance in entries}
        for index, (when, signed, balance) in enumerate(entries):
            previous_balance = balance - signed
            if previous_balance in balances:
                continue
            # El último saldo conocido ANTES de esta fila. Sirve para dos cosas
            # y las dos importan: da el importe exacto del hueco, y exime a la
            # fila más antigua de cada cuenta —que rompe la cadena por
            # definición, porque no hay nada antes—. Sin esa exención, toda
            # cuenta avisaria de un hueco inexistente al importar su primer
            # extracto, y un aviso que sale siempre se deja de leer.
            earlier = [e for e in entries[:index] if e[0] < when]
            if not earlier:
                continue
            last_when, _last_signed, last_balance = earlier[-1]
            seams.setdefault(account_id, []).append(
                StatementSeam(
                    after=last_when,
                    before=when,
                    amount=(previous_balance - last_balance).quantize(Decimal("0.01")),
                )
            )
    return seams


async def get_account_movement_until(
    db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID, *, until: datetime
) -> Decimal:
    """PHASE-39 — Σ firmado de UNA cuenta con `occurred_at <= until`.

    MISMA expresión de signo que `get_balances_for_user`
    (`signed_amount_expr`) para que el anclaje sea coherente con el saldo
    mostrado: `opening = saldo_extracto(D) − Σmov(≤D)` garantiza que el
    saldo de la app a fecha D coincide EXACTAMENTE con el del banco.
    """
    signed_amount = signed_amount_expr(Account)
    query = (
        select(func.coalesce(func.sum(signed_amount), 0))
        .select_from(Transaction)
        .join(Account, Account.id == Transaction.account_id)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.account_id == account_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.currency == Account.currency)
        .where(Transaction.occurred_at <= until)
    )
    return Decimal((await db.execute(query)).scalar_one())


# AUDIT-2026-06 (fix #9) — Se eliminó `get_balance_for_account`. Era
# código MUERTO (ningún caller en código ni tests; sólo aparecía en docs
# históricas de PHASE-21.2/31). Replicaba la convención de signo de
# `get_balances_for_user` con un `case` PARALELO que NUNCA recibió el
# carve-out de PHASE-32 (la cuenta `is_default`/`is_transfer` que refleja
# ahorro neto), así que era una bomba latente: cualquiera que lo
# resucitara obtendría un saldo de la cuenta principal divergente del de
# `/balances`. La fuente ÚNICA de verdad del signo del saldo es
# `get_balances_for_user`.
