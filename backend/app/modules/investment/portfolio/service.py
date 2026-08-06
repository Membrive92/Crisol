"""Lógica de negocio de la cartera (PHASE-44.7).

Una venta dispara el FIFO y persiste las allocations (409 si no hay acciones
suficientes). Una acción corporativa se registra y luego se aplica de forma
auditada. La posición se DERIVA de lotes − allocations, nunca se almacena.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.currency import service as currency_service
from app.modules.investment.catalog.models import Security
from app.modules.investment.catalog.service import get_security
from app.modules.investment.enums import CorpActionType
from app.modules.investment.portfolio import repository as repo
from app.modules.investment.portfolio.corporate_actions import apply_ratio, is_applicable
from app.modules.investment.portfolio.fifo import (
    InsufficientSharesError,
    OpenLot,
    match_fifo,
)
from app.modules.investment.portfolio.models import (
    CorporateAction,
    DividendReceived,
    Lot,
    LotAdjustment,
    Sale,
    SaleAllocation,
)

_ZERO = Decimal(0)


def _dec(value: object) -> Decimal:
    return value if isinstance(value, Decimal) else _ZERO


async def _ensure_security(db: AsyncSession, security_id: uuid.UUID) -> Security:
    return await get_security(db, security_id)  # 404 si no existe


# ── Lotes ─────────────────────────────────────────────────────────────


async def resolve_trade_fx(
    db: AsyncSession,
    *,
    declared: Decimal | None,
    security_currency: str,
    trade_date: date,
) -> Decimal:
    """Tipo de cambio nativa→base de una operación.

    Si el cliente lo declara, manda el cliente: puede tener el cambio real de su
    bróker, que es mejor dato que la referencia del BCE.

    Si NO lo declara, se **deriva** del tipo del BCE a la fecha de la operación
    (PHASE-44.11.E, decisión del usuario 2026-08-02). Antes el schema ponía `1`
    por defecto, lo que era inocuo mientras nadie usaba el dato —`fx_effect` era
    siempre 0— y pasó a ser una afirmación falsa («compraste a 1 USD = 1 EUR»)
    en cuanto la valoración empezó a usar FX vivo: la pantalla mostraba un
    efecto divisa que nadie había introducido.

    Si no hay tipo para esa fecha (`fallback="missing"`), se cae a `1`: es lo
    único que se puede persistir en una columna NOT NULL, y la lectura vuelve a
    tratarlo como desconocido. Ocurre sólo con divisas fuera de la cobertura del
    BCE.
    """
    if declared is not None:
        return declared
    currency = (security_currency or "").strip().upper()
    if not currency or currency == currency_service.CANONICAL_BASE:
        return Decimal(1)
    result = await currency_service.convert(
        db,
        amount=Decimal(1),
        from_currency=currency,
        to_currency=currency_service.CANONICAL_BASE,
        at_date=trade_date,
    )
    return Decimal(1) if result.fallback == "missing" else result.rate


async def create_lot(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    security_id: uuid.UUID,
    trade_date: date,
    quantity: Decimal,
    price: Decimal,
    fx_rate_at_trade: Decimal | None,
    fees: Decimal,
    account_id: uuid.UUID | None,
) -> Lot:
    security = await _ensure_security(db, security_id)
    lot = Lot(
        user_id=user_id,
        security_id=security_id,
        account_id=account_id,
        trade_date=trade_date,
        quantity=quantity,
        price=price,
        fx_rate_at_trade=await resolve_trade_fx(
            db,
            declared=fx_rate_at_trade,
            security_currency=security.currency,
            trade_date=trade_date,
        ),
        fees=fees,
    )
    return await repo.add_lot(db, lot)


async def delete_lot(db: AsyncSession, user_id: uuid.UUID, lot_id: uuid.UUID) -> None:
    lot = await repo.get_lot(db, user_id, lot_id)
    if lot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado.")
    await repo.delete_lot(db, lot)


async def list_lots(
    db: AsyncSession, user_id: uuid.UUID, *, security_id: uuid.UUID | None
) -> list[Lot]:
    return await repo.list_lots(db, user_id, security_id=security_id)


# ── Ventas (FIFO) ─────────────────────────────────────────────────────


async def create_sale(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    security_id: uuid.UUID,
    trade_date: date,
    quantity: Decimal,
    price: Decimal,
    fx_rate_at_trade: Decimal | None,
    fees: Decimal,
) -> Sale:
    security = await _ensure_security(db, security_id)
    sale_fx = await resolve_trade_fx(
        db,
        declared=fx_rate_at_trade,
        security_currency=security.currency,
        trade_date=trade_date,
    )
    lots = await repo.list_lots(db, user_id, security_id=security_id)
    consumed = await repo.consumed_by_lot(db, user_id)
    open_lots = [
        OpenLot(
            lot_id=lot.id,
            trade_date=lot.trade_date,
            remaining=lot.quantity - _dec(consumed.get(lot.id)),
            price=lot.price,
            fx_rate_at_trade=lot.fx_rate_at_trade,
        )
        for lot in lots
    ]
    try:
        allocations = match_fifo(open_lots, quantity)
    except InsufficientSharesError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No puedes vender {exc.requested}: solo tienes {exc.held} de este valor.",
        ) from exc

    sale = await repo.add_sale(
        db,
        Sale(
            user_id=user_id,
            security_id=security_id,
            trade_date=trade_date,
            quantity=quantity,
            price=price,
            fx_rate_at_trade=sale_fx,
            fees=fees,
        ),
    )
    for allocation in allocations:
        await repo.add_allocation(
            db,
            SaleAllocation(
                sale_id=sale.id,
                lot_id=allocation.lot_id,
                quantity=allocation.quantity,
                cost_basis=allocation.cost_basis,
                cost_basis_fx=allocation.cost_basis_fx,
            ),
        )
    return sale


async def delete_sale(db: AsyncSession, user_id: uuid.UUID, sale_id: uuid.UUID) -> None:
    sale = await repo.get_sale(db, user_id, sale_id)
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada.")
    await repo.delete_sale(db, sale)


async def list_sales(db: AsyncSession, user_id: uuid.UUID) -> list[Sale]:
    return await repo.list_sales(db, user_id)


# ── Dividendos ────────────────────────────────────────────────────────


async def create_dividend(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    security_id: uuid.UUID,
    pay_date: date,
    ex_date: date | None,
    gross_amount: Decimal,
    withholding_tax: Decimal,
    net_amount: Decimal | None,
    currency: str,
    fx_rate: Decimal,
) -> DividendReceived:
    await _ensure_security(db, security_id)
    net = net_amount if net_amount is not None else gross_amount - withholding_tax
    dividend = DividendReceived(
        user_id=user_id,
        security_id=security_id,
        ex_date=ex_date,
        pay_date=pay_date,
        gross_amount=gross_amount,
        withholding_tax=withholding_tax,
        net_amount=net,
        currency=currency.upper(),
        fx_rate=fx_rate,
    )
    return await repo.add_dividend(db, dividend)


async def delete_dividend(db: AsyncSession, user_id: uuid.UUID, dividend_id: uuid.UUID) -> None:
    dividend = await repo.get_dividend(db, user_id, dividend_id)
    if dividend is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dividendo no encontrado."
        )
    await repo.delete_dividend(db, dividend)


async def list_dividends(db: AsyncSession, user_id: uuid.UUID) -> list[DividendReceived]:
    return await repo.list_dividends(db, user_id)


# ── Acciones corporativas ─────────────────────────────────────────────


async def register_corporate_action(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    security_id: uuid.UUID,
    action_type: CorpActionType,
    action_date: date,
    ratio: Decimal | None,
    notes: str | None,
) -> CorporateAction:
    await _ensure_security(db, security_id)
    action = CorporateAction(
        user_id=user_id,
        security_id=security_id,
        action_type=action_type,
        action_date=action_date,
        ratio=ratio,
        notes=notes,
    )
    return await repo.add_corporate_action(db, action)


async def apply_corporate_action(
    db: AsyncSession, user_id: uuid.UUID, action_id: uuid.UUID
) -> CorporateAction:
    """Aplica split/stock_dividend a los lotes anteriores a la fecha, auditado y
    reversible. spinoff/return_of_capital: 400 (registrar sí, aplicar aún no)."""
    action = await repo.get_corporate_action(db, user_id, action_id)
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Acción corporativa no encontrada."
        )
    if action.applied_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Esta acción corporativa ya se aplicó."
        )
    if not is_applicable(action.action_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Solo split y stock_dividend se pueden aplicar por ahora. spinoff y "
                "return_of_capital se registran pero aplicarlas llegará en una fase futura."
            ),
        )
    if action.ratio is None or action.ratio <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La acción necesita un ratio > 0 para aplicarse.",
        )

    lots = await repo.list_lots(db, user_id, security_id=action.security_id)
    for lot in lots:
        if lot.trade_date >= action.action_date:
            continue
        old_quantity, old_price = lot.quantity, lot.price
        lot.quantity, lot.price = apply_ratio(old_quantity, old_price, action.ratio)
        for field, old, new in (
            ("quantity", old_quantity, lot.quantity),
            ("price", old_price, lot.price),
        ):
            await repo.add_lot_adjustment(
                db,
                LotAdjustment(
                    corporate_action_id=action.id,
                    lot_id=lot.id,
                    field=field,
                    old_value=old,
                    new_value=new,
                ),
            )
    action.applied_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(action)
    return action


async def list_corporate_actions(db: AsyncSession, user_id: uuid.UUID) -> list[CorporateAction]:
    return await repo.list_corporate_actions(db, user_id)


# ── Posiciones (derivadas) ────────────────────────────────────────────


@dataclass(frozen=True)
class PositionCore:
    """Agregado por security SIN precio de mercado (eso llega con pricing en la
    siguiente fase). Coste base, cantidad, P&L realizado y dividendos."""

    security_id: uuid.UUID
    ticker: str
    name: str
    exchange: str
    """Plaza normalizada. La necesita el adapter de precios para construir el
    símbolo del proveedor: `(ticker, exchange)` → `'ULVR.L'` (PHASE-44.11.B)."""
    currency: str
    quantity: Decimal
    avg_cost: Decimal | None
    cost_fx: Decimal | None
    """FX medio (nativa→base) de las compras abiertas, ponderado por cantidad.
    Lo usa el summary para descomponer el P&L en componente precio vs divisa."""
    cost_basis: Decimal
    realized_pnl: Decimal
    dividends_gross: Decimal
    dividends_net: Decimal


async def compute_position_cores(db: AsyncSession, user_id: uuid.UUID) -> list[PositionCore]:
    """Deriva las posiciones de lotes − allocations. Reutilizable por
    `/portfolio/summary` (que le añade el valor de mercado)."""
    lots = await repo.list_lots(db, user_id, security_id=None)
    consumed = await repo.consumed_by_lot(db, user_id)
    sales = await repo.list_sales(db, user_id)
    allocations = await repo.list_allocations(db, user_id)
    dividends = await repo.list_dividends(db, user_id)

    security_ids = {lot.security_id for lot in lots} | {d.security_id for d in dividends}
    securities: dict[uuid.UUID, Security] = {}
    if security_ids:
        rows = (await db.execute(select(Security).where(Security.id.in_(security_ids)))).scalars()
        securities = {s.id: s for s in rows}

    # Coste base y cantidad por security (sobre la parte ABIERTA de cada lote).
    quantity: dict[uuid.UUID, Decimal] = {}
    cost_open: dict[uuid.UUID, Decimal] = {}  # remaining*price (sin fees)
    cost_basis: dict[uuid.UUID, Decimal] = {}  # + fees prorrateadas
    fx_weighted: dict[uuid.UUID, Decimal] = {}  # remaining*fx (para el FX medio)
    for lot in lots:
        remaining = lot.quantity - _dec(consumed.get(lot.id))
        if remaining <= 0:
            continue
        sid = lot.security_id
        quantity[sid] = quantity.get(sid, _ZERO) + remaining
        cost_open[sid] = cost_open.get(sid, _ZERO) + remaining * lot.price
        fx_weighted[sid] = fx_weighted.get(sid, _ZERO) + remaining * lot.fx_rate_at_trade
        fee_share = lot.fees * (remaining / lot.quantity) if lot.quantity else _ZERO
        cost_basis[sid] = cost_basis.get(sid, _ZERO) + remaining * lot.price + fee_share

    # P&L realizado por security: proceeds − coste asignado − fees, por venta.
    allocated_cost_by_sale: dict[uuid.UUID, Decimal] = {}
    for allocation in allocations:
        allocated_cost_by_sale[allocation.sale_id] = (
            allocated_cost_by_sale.get(allocation.sale_id, _ZERO)
            + allocation.quantity * allocation.cost_basis
        )
    realized: dict[uuid.UUID, Decimal] = {}
    for sale in sales:
        pnl = sale.quantity * sale.price - allocated_cost_by_sale.get(sale.id, _ZERO) - sale.fees
        realized[sale.security_id] = realized.get(sale.security_id, _ZERO) + pnl

    dividends_gross: dict[uuid.UUID, Decimal] = {}
    dividends_net: dict[uuid.UUID, Decimal] = {}
    for dividend in dividends:
        dividends_gross[dividend.security_id] = (
            dividends_gross.get(dividend.security_id, _ZERO) + dividend.gross_amount
        )
        dividends_net[dividend.security_id] = (
            dividends_net.get(dividend.security_id, _ZERO) + dividend.net_amount
        )

    positions: list[PositionCore] = []
    involved = set(quantity) | set(realized) | set(dividends_gross)
    for sid in involved:
        security = securities.get(sid)
        qty = quantity.get(sid, _ZERO)
        positions.append(
            PositionCore(
                security_id=sid,
                ticker=security.ticker if security else "",
                name=security.name if security else "",
                exchange=security.exchange if security else "UNKNOWN",
                currency=security.currency if security else "USD",
                quantity=qty,
                avg_cost=(cost_open[sid] / qty) if qty > 0 and sid in cost_open else None,
                cost_fx=(fx_weighted[sid] / qty) if qty > 0 and sid in fx_weighted else None,
                cost_basis=cost_basis.get(sid, _ZERO),
                realized_pnl=realized.get(sid, _ZERO),
                dividends_gross=dividends_gross.get(sid, _ZERO),
                dividends_net=dividends_net.get(sid, _ZERO),
            )
        )
    positions.sort(key=lambda p: p.ticker)
    return positions
