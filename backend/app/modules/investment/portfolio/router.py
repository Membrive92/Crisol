"""Router de cartera (PHASE-44.7, ARCHITECTURE §5). Todo scoped por usuario."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.investment.portfolio import service
from app.modules.investment.portfolio.schemas import (
    CorporateActionCreate,
    CorporateActionListResponse,
    CorporateActionResponse,
    DividendCreate,
    DividendListResponse,
    DividendResponse,
    LotCreate,
    LotListResponse,
    LotResponse,
    PositionListResponse,
    PositionResponse,
    SaleCreate,
    SaleListResponse,
    SaleResponse,
)

router = APIRouter(prefix="/portfolio", tags=["investment:portfolio"])

Db = Annotated[AsyncSession, Depends(get_db)]


# ── Lotes ─────────────────────────────────────────────────────────────


@router.post("/lots", response_model=LotResponse, status_code=201)
async def create_lot_endpoint(body: LotCreate, user: CurrentUser, db: Db) -> LotResponse:
    lot = await service.create_lot(
        db,
        user.id,
        security_id=body.security_id,
        trade_date=body.trade_date,
        quantity=body.quantity,
        price=body.price,
        fx_rate_at_trade=body.fx_rate_at_trade,
        fees=body.fees,
        account_id=body.account_id,
    )
    await db.commit()
    return LotResponse.model_validate(lot)


@router.get("/lots", response_model=LotListResponse)
async def list_lots_endpoint(
    user: CurrentUser,
    db: Db,
    security_id: Annotated[uuid.UUID | None, Query()] = None,
) -> LotListResponse:
    lots = await service.list_lots(db, user.id, security_id=security_id)
    return LotListResponse(items=[LotResponse.model_validate(lot) for lot in lots])


@router.delete("/lots/{lot_id}", status_code=204, response_class=Response)
async def delete_lot_endpoint(lot_id: uuid.UUID, user: CurrentUser, db: Db) -> Response:
    await service.delete_lot(db, user.id, lot_id)
    await db.commit()
    return Response(status_code=204)


# ── Ventas ────────────────────────────────────────────────────────────


@router.post("/sales", response_model=SaleResponse, status_code=201)
async def create_sale_endpoint(body: SaleCreate, user: CurrentUser, db: Db) -> SaleResponse:
    """Registra una venta y la casa contra los lotes vía FIFO. 409 si intentas
    vender más de lo que tienes."""
    sale = await service.create_sale(
        db,
        user.id,
        security_id=body.security_id,
        trade_date=body.trade_date,
        quantity=body.quantity,
        price=body.price,
        fx_rate_at_trade=body.fx_rate_at_trade,
        fees=body.fees,
    )
    await db.commit()
    return SaleResponse.model_validate(sale)


@router.get("/sales", response_model=SaleListResponse)
async def list_sales_endpoint(user: CurrentUser, db: Db) -> SaleListResponse:
    sales = await service.list_sales(db, user.id)
    return SaleListResponse(items=[SaleResponse.model_validate(s) for s in sales])


@router.delete("/sales/{sale_id}", status_code=204, response_class=Response)
async def delete_sale_endpoint(sale_id: uuid.UUID, user: CurrentUser, db: Db) -> Response:
    """Borra una venta; sus allocations caen en cascada y los lotes recuperan su
    cantidad disponible."""
    await service.delete_sale(db, user.id, sale_id)
    await db.commit()
    return Response(status_code=204)


# ── Dividendos ────────────────────────────────────────────────────────


@router.post("/dividends", response_model=DividendResponse, status_code=201)
async def create_dividend_endpoint(
    body: DividendCreate, user: CurrentUser, db: Db
) -> DividendResponse:
    dividend = await service.create_dividend(
        db,
        user.id,
        security_id=body.security_id,
        pay_date=body.pay_date,
        ex_date=body.ex_date,
        gross_amount=body.gross_amount,
        withholding_tax=body.withholding_tax,
        net_amount=body.net_amount,
        currency=body.currency,
        fx_rate=body.fx_rate,
    )
    await db.commit()
    return DividendResponse.model_validate(dividend)


@router.get("/dividends", response_model=DividendListResponse)
async def list_dividends_endpoint(user: CurrentUser, db: Db) -> DividendListResponse:
    dividends = await service.list_dividends(db, user.id)
    return DividendListResponse(items=[DividendResponse.model_validate(d) for d in dividends])


@router.delete("/dividends/{dividend_id}", status_code=204, response_class=Response)
async def delete_dividend_endpoint(dividend_id: uuid.UUID, user: CurrentUser, db: Db) -> Response:
    await service.delete_dividend(db, user.id, dividend_id)
    await db.commit()
    return Response(status_code=204)


# ── Acciones corporativas ─────────────────────────────────────────────


@router.post("/corporate-actions", response_model=CorporateActionResponse, status_code=201)
async def register_corporate_action_endpoint(
    body: CorporateActionCreate, user: CurrentUser, db: Db
) -> CorporateActionResponse:
    """Registra una acción corporativa (no la aplica todavía)."""
    action = await service.register_corporate_action(
        db,
        user.id,
        security_id=body.security_id,
        action_type=body.action_type,
        action_date=body.action_date,
        ratio=body.ratio,
        notes=body.notes,
    )
    await db.commit()
    return CorporateActionResponse.model_validate(action)


@router.get("/corporate-actions", response_model=CorporateActionListResponse)
async def list_corporate_actions_endpoint(user: CurrentUser, db: Db) -> CorporateActionListResponse:
    actions = await service.list_corporate_actions(db, user.id)
    return CorporateActionListResponse(
        items=[CorporateActionResponse.model_validate(a) for a in actions]
    )


@router.post("/corporate-actions/{action_id}/apply", response_model=CorporateActionResponse)
async def apply_corporate_action_endpoint(
    action_id: uuid.UUID, user: CurrentUser, db: Db
) -> CorporateActionResponse:
    """Aplica split/stock_dividend a los lotes (auditado). 400 para
    spinoff/return_of_capital (aún no soportadas), 409 si ya estaba aplicada."""
    action = await service.apply_corporate_action(db, user.id, action_id)
    await db.commit()
    return CorporateActionResponse.model_validate(action)


# ── Posiciones ────────────────────────────────────────────────────────


@router.get("/positions", response_model=PositionListResponse)
async def list_positions_endpoint(user: CurrentUser, db: Db) -> PositionListResponse:
    """Posiciones derivadas (lotes − allocations): cantidad, coste base, P&L
    realizado y dividendos. El valor de mercado llega con el módulo de precios."""
    cores = await service.compute_position_cores(db, user.id)
    return PositionListResponse(
        items=[
            PositionResponse(
                security_id=c.security_id,
                ticker=c.ticker,
                name=c.name,
                currency=c.currency,
                quantity=c.quantity,
                avg_cost=c.avg_cost,
                cost_basis=c.cost_basis,
                realized_pnl=c.realized_pnl,
                dividends_gross=c.dividends_gross,
                dividends_net=c.dividends_net,
            )
            for c in cores
        ]
    )
