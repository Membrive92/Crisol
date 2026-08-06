"""Schemas Pydantic de cartera (PHASE-44.7). Importes/cantidades en Decimal."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.modules.investment.enums import CorpActionType


class LotCreate(BaseModel):
    security_id: uuid.UUID
    account_id: uuid.UUID | None = None
    trade_date: date
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(ge=0)
    fx_rate_at_trade: Decimal | None = Field(default=None, gt=0)
    """Tipo de cambio nativa→EUR de la operación.

    Omitirlo NO significa «1»: significa «no lo sé», y el servidor lo deriva del
    tipo del BCE a la fecha de la operación. El default anterior era un `1`
    literal, que afirmaba paridad con el euro y producía un efecto divisa
    inventado en cuanto la valoración empezó a usar FX vivo (PHASE-44.11.E)."""
    fees: Decimal = Field(default=Decimal(0), ge=0)


class LotResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    security_id: uuid.UUID
    account_id: uuid.UUID | None
    trade_date: date
    quantity: Decimal
    price: Decimal
    fx_rate_at_trade: Decimal
    fees: Decimal
    created_at: datetime


class LotListResponse(BaseModel):
    items: list[LotResponse]


class SaleCreate(BaseModel):
    security_id: uuid.UUID
    trade_date: date
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(ge=0)
    fx_rate_at_trade: Decimal | None = Field(default=None, gt=0)
    """Tipo de cambio nativa→EUR de la operación.

    Omitirlo NO significa «1»: significa «no lo sé», y el servidor lo deriva del
    tipo del BCE a la fecha de la operación. El default anterior era un `1`
    literal, que afirmaba paridad con el euro y producía un efecto divisa
    inventado en cuanto la valoración empezó a usar FX vivo (PHASE-44.11.E)."""
    fees: Decimal = Field(default=Decimal(0), ge=0)


class SaleResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    security_id: uuid.UUID
    trade_date: date
    quantity: Decimal
    price: Decimal
    fx_rate_at_trade: Decimal
    fees: Decimal
    created_at: datetime


class SaleListResponse(BaseModel):
    items: list[SaleResponse]


class DividendCreate(BaseModel):
    security_id: uuid.UUID
    pay_date: date
    ex_date: date | None = None
    gross_amount: Decimal = Field(ge=0)
    withholding_tax: Decimal = Field(default=Decimal(0), ge=0)
    net_amount: Decimal | None = None
    currency: str = Field(min_length=3, max_length=3)
    fx_rate: Decimal = Field(default=Decimal(1), gt=0)


class DividendResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    security_id: uuid.UUID
    ex_date: date | None
    pay_date: date
    gross_amount: Decimal
    withholding_tax: Decimal
    net_amount: Decimal
    currency: str
    fx_rate: Decimal
    created_at: datetime


class DividendListResponse(BaseModel):
    items: list[DividendResponse]


class CorporateActionCreate(BaseModel):
    security_id: uuid.UUID
    action_type: CorpActionType
    action_date: date
    ratio: Decimal | None = Field(default=None, gt=0)
    notes: str | None = None


class CorporateActionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    security_id: uuid.UUID
    action_type: CorpActionType
    action_date: date
    ratio: Decimal | None
    notes: str | None
    applied_at: datetime | None
    created_at: datetime


class CorporateActionListResponse(BaseModel):
    items: list[CorporateActionResponse]


class PositionResponse(BaseModel):
    security_id: uuid.UUID
    ticker: str
    name: str
    currency: str
    quantity: Decimal
    avg_cost: Decimal | None
    cost_basis: Decimal
    realized_pnl: Decimal
    dividends_gross: Decimal
    dividends_net: Decimal


class PositionListResponse(BaseModel):
    items: list[PositionResponse]
