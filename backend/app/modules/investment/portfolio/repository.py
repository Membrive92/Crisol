"""Queries a DB de cartera (PHASE-44.7).

Todas las tablas `inv_*` son SCOPED por usuario: cada query filtra por `user_id`.
La posición NO es tabla: se deriva de lotes − allocations.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.investment.portfolio.models import (
    CorporateAction,
    DividendReceived,
    Lot,
    LotAdjustment,
    Sale,
    SaleAllocation,
)

# ── Lotes ─────────────────────────────────────────────────────────────


async def add_lot(db: AsyncSession, lot: Lot) -> Lot:
    db.add(lot)
    await db.flush()
    await db.refresh(lot)
    return lot


async def get_lot(db: AsyncSession, user_id: uuid.UUID, lot_id: uuid.UUID) -> Lot | None:
    stmt = select(Lot).where(Lot.id == lot_id, Lot.user_id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_lots(
    db: AsyncSession, user_id: uuid.UUID, *, security_id: uuid.UUID | None = None
) -> list[Lot]:
    stmt = select(Lot).where(Lot.user_id == user_id)
    if security_id is not None:
        stmt = stmt.where(Lot.security_id == security_id)
    stmt = stmt.order_by(Lot.trade_date, Lot.created_at)
    return list((await db.execute(stmt)).scalars().all())


async def delete_lot(db: AsyncSession, lot: Lot) -> None:
    await db.delete(lot)
    await db.flush()


# ── Ventas + allocations ──────────────────────────────────────────────


async def add_sale(db: AsyncSession, sale: Sale) -> Sale:
    db.add(sale)
    await db.flush()
    await db.refresh(sale)
    return sale


async def add_allocation(db: AsyncSession, allocation: SaleAllocation) -> SaleAllocation:
    db.add(allocation)
    await db.flush()
    return allocation


async def get_sale(db: AsyncSession, user_id: uuid.UUID, sale_id: uuid.UUID) -> Sale | None:
    stmt = select(Sale).where(Sale.id == sale_id, Sale.user_id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_sales(db: AsyncSession, user_id: uuid.UUID) -> list[Sale]:
    stmt = select(Sale).where(Sale.user_id == user_id).order_by(Sale.trade_date, Sale.created_at)
    return list((await db.execute(stmt)).scalars().all())


async def delete_sale(db: AsyncSession, sale: Sale) -> None:
    # Las allocations caen por ON DELETE CASCADE → los lotes recuperan su cantidad.
    await db.delete(sale)
    await db.flush()


async def list_allocations(db: AsyncSession, user_id: uuid.UUID) -> list[SaleAllocation]:
    stmt = (
        select(SaleAllocation)
        .join(Sale, Sale.id == SaleAllocation.sale_id)
        .where(Sale.user_id == user_id)
    )
    return list((await db.execute(stmt)).scalars().all())


async def consumed_by_lot(db: AsyncSession, user_id: uuid.UUID) -> dict[uuid.UUID, object]:
    """`lot_id → cantidad ya consumida por ventas` (para calcular lo abierto)."""
    stmt = (
        select(SaleAllocation.lot_id, func.sum(SaleAllocation.quantity))
        .join(Sale, Sale.id == SaleAllocation.sale_id)
        .where(Sale.user_id == user_id)
        .group_by(SaleAllocation.lot_id)
    )
    return {lot_id: total for lot_id, total in (await db.execute(stmt)).all()}


# ── Dividendos ────────────────────────────────────────────────────────


async def add_dividend(db: AsyncSession, dividend: DividendReceived) -> DividendReceived:
    db.add(dividend)
    await db.flush()
    await db.refresh(dividend)
    return dividend


async def get_dividend(
    db: AsyncSession, user_id: uuid.UUID, dividend_id: uuid.UUID
) -> DividendReceived | None:
    stmt = select(DividendReceived).where(
        DividendReceived.id == dividend_id, DividendReceived.user_id == user_id
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_dividends(db: AsyncSession, user_id: uuid.UUID) -> list[DividendReceived]:
    stmt = (
        select(DividendReceived)
        .where(DividendReceived.user_id == user_id)
        .order_by(DividendReceived.pay_date)
    )
    return list((await db.execute(stmt)).scalars().all())


async def delete_dividend(db: AsyncSession, dividend: DividendReceived) -> None:
    await db.delete(dividend)
    await db.flush()


# ── Acciones corporativas ─────────────────────────────────────────────


async def add_corporate_action(db: AsyncSession, action: CorporateAction) -> CorporateAction:
    db.add(action)
    await db.flush()
    await db.refresh(action)
    return action


async def get_corporate_action(
    db: AsyncSession, user_id: uuid.UUID, action_id: uuid.UUID
) -> CorporateAction | None:
    stmt = select(CorporateAction).where(
        CorporateAction.id == action_id, CorporateAction.user_id == user_id
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_corporate_actions(db: AsyncSession, user_id: uuid.UUID) -> list[CorporateAction]:
    stmt = (
        select(CorporateAction)
        .where(CorporateAction.user_id == user_id)
        .order_by(CorporateAction.action_date)
    )
    return list((await db.execute(stmt)).scalars().all())


async def add_lot_adjustment(db: AsyncSession, adjustment: LotAdjustment) -> LotAdjustment:
    db.add(adjustment)
    await db.flush()
    return adjustment
