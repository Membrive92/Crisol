"""Schemas Pydantic de precios / summary (PHASE-44.7, ARCHITECTURE §5.1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class RefreshRequest(BaseModel):
    security_ids: list[uuid.UUID] | None = None


class RefreshResponse(BaseModel):
    refreshed: int
    pricing_enabled: bool


class PositionSummaryResponse(BaseModel):
    model_config = {"from_attributes": True}

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
    has_quote: bool
    last_price: Decimal | None
    prev_close: Decimal | None
    quote_as_of: datetime | None
    quote_stale: bool
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_pct: Decimal | None
    price_effect: Decimal | None
    fx_effect: Decimal | None
    daily_change: Decimal | None
    total_return: Decimal | None
    yield_on_cost: Decimal | None
    weight_pct: Decimal | None


class PortfolioSummaryResponse(BaseModel):
    model_config = {"from_attributes": True}

    pricing_enabled: bool
    base_note: str
    total_cost_basis: Decimal
    total_market_value: Decimal
    total_unrealized_pnl: Decimal
    total_realized_pnl: Decimal
    total_dividends_net: Decimal
    daily_pnl: Decimal
    quoted_count: int
    unquoted_count: int
    positions: list[PositionSummaryResponse]
