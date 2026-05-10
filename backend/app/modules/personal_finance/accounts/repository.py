"""Queries a DB del módulo accounts (PHASE-19.1)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.models import Account
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
    query = select(Account).where(
        Account.user_id == user_id, Account.id == account_id
    )
    return (await db.execute(query)).scalar_one_or_none()


async def get_account_by_name(
    db: AsyncSession, user_id: uuid.UUID, *, name: str
) -> Account | None:
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


async def get_balances_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> dict[uuid.UUID, Decimal]:
    """Suma neta de cada cuenta del usuario en la moneda nativa de la
    cuenta (sin conversión cross-currency).

    Convención (PHASE-19.4):
    - `kind=income`     → suma al saldo
    - `kind=expense`    → resta al saldo
    - sin categoría     → suma (signed amount es positivo y la
                          interpretación por defecto es ingreso)
    - txs en papelera   → no cuentan
    - transferencias    → SÍ cuentan al saldo individual de su cuenta
                          (el signo lo da el `kind` de su categoría
                          igual que cualquier otra tx)

    Sólo agrega txs cuya `currency` coincide con la `currency` de la
    cuenta — txs en otra moneda dentro de una cuenta multi-divisa se
    ignoran de momento (PHASE-19.4 mínimo viable; PHASE-19.5 puede
    sumar otras divisas convirtiéndolas).

    El saldo final del frontend es:
        opening_balance + balances[account_id]

    Esta función NO añade el opening_balance — eso lo hace el caller.
    """
    signed_amount = case(
        (Category.kind == CategoryKind.EXPENSE, -Transaction.amount),
        (Category.kind == CategoryKind.INCOME, Transaction.amount),
        else_=Transaction.amount,
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
) -> Decimal:
    """Igual que `get_balances_for_user` pero para una sola cuenta.

    `account_currency` se pasa porque la query filtra por igualdad de
    currency contra la cuenta — el caller la conoce ya.
    """
    signed_amount = case(
        (Category.kind == CategoryKind.EXPENSE, -Transaction.amount),
        (Category.kind == CategoryKind.INCOME, Transaction.amount),
        else_=Transaction.amount,
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
