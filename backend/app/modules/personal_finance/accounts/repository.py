"""Queries a DB del módulo accounts (PHASE-19.1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

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


def signed_amount_expr(account: Any, paired_account: Any) -> ColumnElement[Decimal]:
    """PHASE-37 — expresión de signo COMPARTIDA: cómo una tx afecta al saldo de
    SU cuenta según `account.nature` + flow (incluye el carve-out H-02 de la
    pata-activo de un par de deuda). Un ÚNICO lugar para que
    `get_balances_for_user` y `position_history` (37.1) no diverjan — el
    invariante es que el último punto de la serie de patrimonio == los saldos
    actuales. `account`/`paired_account` son la tabla o el alias de la cuenta y
    su pareja de transferencia.

    Convención (PHASE-19.4 + PHASE-22 + H-02):
    - Pata-activo de conversión a deuda que ENTRA → 0 (dinero prestado, no ahorro).
    - LIABILITY: salida/cargo sube la deuda (+amount), entrada/pago la baja (-amount).
    - ASSET: entrada suma, salida resta.
    - Sin flujo ni categoría → 0 (PHASE-31.3).
    """
    asset_leg_of_debt_pair = (account.nature == AccountNature.ASSET) & (
        paired_account.nature == AccountNature.LIABILITY
    )
    return case(
        (asset_leg_of_debt_pair & is_inflow(), Decimal("0")),
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
    - EXCEPCIÓN deuda (fix pata-activo fantasma): la pata-ACTIVO de un
      par de conversión a deuda (activo↔pasivo, p.ej. una compra
      financiada / aplazamiento de tarjeta) aporta 0. Ese ingreso es
      dinero PRESTADO, no ahorro disponible: si contara, inflaría
      `total_assets` mientras la pata-pasivo eleva `total_liabilities`,
      dejando un "activo fantasma". A diferencia de activo↔activo (donde
      las dos patas caen en total_assets con signo opuesto y se anulan),
      un par activo↔pasivo NO se cancela dentro de un bucket. Se anula
      SÓLO la pata cuya cuenta es ASSET y cuya pareja es LIABILITY; la
      pata-pasivo se mantiene intacta (sigue elevando la deuda y el
      principal de la liability).

    Sólo agrega txs cuya `currency` coincide con la `currency` de la
    cuenta. Multi-divisa dentro de una cuenta queda fuera.

    El saldo final del frontend es:
        opening_balance + balances[account_id]
    """
    # Pareja (self-join) para detectar la pata-activo de un par de deuda.
    # `paired_account.nature == LIABILITY` con esta cuenta ASSET = dinero
    # prestado entrando en un activo → no es patrimonio (ver docstring).
    paired_tx = aliased(Transaction)
    paired_account = aliased(Account)

    # PHASE-34: la dirección la manda `flow`; `account.nature` decide el signo.
    # PHASE-37: la expresión vive en `signed_amount_expr` (compartida con
    # position_history) para no divergir.
    signed_amount = signed_amount_expr(Account, paired_account)
    query = (
        select(
            Transaction.account_id,
            func.coalesce(func.sum(signed_amount), 0),
        )
        .select_from(Transaction)
        .join(Account, Account.id == Transaction.account_id)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .outerjoin(paired_tx, paired_tx.id == Transaction.transfer_pair_id)
        .outerjoin(paired_account, paired_account.id == paired_tx.account_id)
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

    La pata-activo de un par de conversión a deuda también aporta 0 aquí
    (vía la misma señal pareja-LIABILITY que usa `get_balances_for_user`),
    no sólo vía `is_transfer`: así el saldo MOSTRADO de la principal y el
    AGREGADO excluyen el activo fantasma de forma idéntica aunque la tx
    origen no hubiera quedado marcada como transferencia.
    """
    paired_tx = aliased(Transaction)
    paired_account = aliased(Account)
    # PHASE-34: transferencias internas (flow TRANSFER_*; fallback is_transfer)
    # aportan 0 — mover dinero entre cuentas propias no es ahorrar ni gastar.
    signed_amount = case(
        (_is_internal_transfer(), Decimal("0")),
        # Pata-activo de una conversión a deuda (activo↔pasivo): SÓLO la
        # entrada de dinero prestado aporta 0 (consistente con
        # get_balances_for_user, AUDIT-2026-07 H-02). Una salida de activo
        # que amortiza deuda cae a la rama `is_outflow` → -amount.
        (
            (Account.nature == AccountNature.ASSET)
            & (paired_account.nature == AccountNature.LIABILITY)
            & is_inflow(),
            Decimal("0"),
        ),
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
        .outerjoin(paired_tx, paired_tx.id == Transaction.transfer_pair_id)
        .outerjoin(paired_account, paired_account.id == paired_tx.account_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.account_id == account_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.currency == Account.currency)
    )
    return Decimal((await db.execute(query)).scalar_one())


async def get_account_movement_until(
    db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID, *, until: datetime
) -> Decimal:
    """PHASE-39 — Σ firmado de UNA cuenta con `occurred_at <= until`.

    MISMA expresión de signo que `get_balances_for_user`
    (`signed_amount_expr`, incluido el carve-out H-02 de la pata-activo de
    un par de deuda) para que el anclaje sea coherente con el saldo
    mostrado: `opening = saldo_extracto(D) − Σmov(≤D)` garantiza que el
    saldo de la app a fecha D coincide EXACTAMENTE con el del banco.
    """
    paired_tx = aliased(Transaction)
    paired_account = aliased(Account)
    signed_amount = signed_amount_expr(Account, paired_account)
    query = (
        select(func.coalesce(func.sum(signed_amount), 0))
        .select_from(Transaction)
        .join(Account, Account.id == Transaction.account_id)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .outerjoin(paired_tx, paired_tx.id == Transaction.transfer_pair_id)
        .outerjoin(paired_account, paired_account.id == paired_tx.account_id)
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
