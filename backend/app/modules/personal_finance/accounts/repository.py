"""Queries a DB del módulo accounts (PHASE-19.1)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.personal_finance.accounts.models import Account, AccountNature
from app.modules.personal_finance.categories.models import Category, CategoryKind
from app.modules.personal_finance.transactions.models import Transaction


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
    asset_leg_of_debt_pair = (Account.nature == AccountNature.ASSET) & (
        paired_account.nature == AccountNature.LIABILITY
    )

    signed_amount = case(
        # Pata-activo de una conversión a deuda (activo↔pasivo): dinero
        # prestado, no ahorro. Va PRIMERO para ganar a las ramas por kind.
        (asset_leg_of_debt_pair, Decimal("0")),
        # Liability: signos invertidos respecto a asset.
        (
            (Account.nature == AccountNature.LIABILITY) & (Category.kind == CategoryKind.EXPENSE),
            Transaction.amount,
        ),
        (
            (Account.nature == AccountNature.LIABILITY) & (Category.kind == CategoryKind.INCOME),
            -Transaction.amount,
        ),
        # Asset (default).
        (Category.kind == CategoryKind.EXPENSE, -Transaction.amount),
        (Category.kind == CategoryKind.INCOME, Transaction.amount),
        # PHASE-31.3 — tx sin categoría (kind=NULL tras outerjoin) o con
        # categoría sin kind no contribuye al saldo. Antes era
        # `else_=Transaction.amount`, que producía un cargo / abono
        # arbitrario en función del importe firmado en la BD — ruido
        # silencioso cuando un import fallaba y la tx quedaba sin
        # categorizar. El banner UX educa al usuario para categorizar.
        else_=Decimal("0"),
    )
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
    signed_amount = case(
        (Category.is_transfer.is_(True), Decimal("0")),
        # Pata-activo de una conversión a deuda (activo↔pasivo): dinero
        # prestado, no ahorro (consistente con get_balances_for_user).
        (
            (Account.nature == AccountNature.ASSET)
            & (paired_account.nature == AccountNature.LIABILITY),
            Decimal("0"),
        ),
        (
            (Account.nature == AccountNature.LIABILITY) & (Category.kind == CategoryKind.EXPENSE),
            Transaction.amount,
        ),
        (
            (Account.nature == AccountNature.LIABILITY) & (Category.kind == CategoryKind.INCOME),
            -Transaction.amount,
        ),
        (Category.kind == CategoryKind.EXPENSE, -Transaction.amount),
        (Category.kind == CategoryKind.INCOME, Transaction.amount),
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


# AUDIT-2026-06 (fix #9) — Se eliminó `get_balance_for_account`. Era
# código MUERTO (ningún caller en código ni tests; sólo aparecía en docs
# históricas de PHASE-21.2/31). Replicaba la convención de signo de
# `get_balances_for_user` con un `case` PARALELO que NUNCA recibió el
# carve-out de PHASE-32 (la cuenta `is_default`/`is_transfer` que refleja
# ahorro neto), así que era una bomba latente: cualquiera que lo
# resucitara obtendría un saldo de la cuenta principal divergente del de
# `/balances`. La fuente ÚNICA de verdad del signo del saldo es
# `get_balances_for_user`.
