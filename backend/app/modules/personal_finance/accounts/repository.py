"""Queries a DB del módulo accounts (PHASE-19.1)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.models import Account, AccountNature
from app.modules.personal_finance.categories.models import Category, CategoryKind
from app.modules.personal_finance.transactions.models import Transaction


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
    """Match case-insensitive por nombre — usado para validar duplicados."""
    target = name.casefold()
    query = select(Account).where(Account.user_id == user_id)
    rows = (await db.execute(query)).scalars().all()
    for acc in rows:
        if acc.name.casefold() == target:
            return acc
    return None


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
    - Las transferencias internas SÍ cuentan al saldo individual de su
      cuenta (el `transfer_pair_id` excluye sólo de los agregados del
      dashboard, no del saldo por cuenta).

    Sólo agrega txs cuya `currency` coincide con la `currency` de la
    cuenta. Multi-divisa dentro de una cuenta queda fuera.

    El saldo final del frontend es:
        opening_balance + balances[account_id]
    """
    signed_amount = case(
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
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.currency == Account.currency)
        .group_by(Transaction.account_id)
    )
    result = await db.execute(query)
    return {acc_id: Decimal(total) for acc_id, total in result.all()}


async def get_balance_for_account(
    db: AsyncSession,
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    account_currency: str,
    account_nature: AccountNature = AccountNature.ASSET,
) -> Decimal:
    """Igual que `get_balances_for_user` pero para una sola cuenta.

    `account_nature` decide la convención del signo (ver
    `get_balances_for_user`). Default `ASSET` para compatibilidad con
    callers existentes.
    """
    # PHASE-31.3 — `else_=Decimal("0")` igual que `get_balances_for_user`.
    if account_nature == AccountNature.LIABILITY:
        signed_amount = case(
            (Category.kind == CategoryKind.EXPENSE, Transaction.amount),
            (Category.kind == CategoryKind.INCOME, -Transaction.amount),
            else_=Decimal("0"),
        )
    else:
        signed_amount = case(
            (Category.kind == CategoryKind.EXPENSE, -Transaction.amount),
            (Category.kind == CategoryKind.INCOME, Transaction.amount),
            else_=Decimal("0"),
        )
    query = (
        select(func.coalesce(func.sum(signed_amount), 0))
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.account_id == account_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.currency == account_currency)
    )
    return Decimal((await db.execute(query)).scalar_one())
