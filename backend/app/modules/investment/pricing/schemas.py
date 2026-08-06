"""Schemas Pydantic de precios / summary (PHASE-44.7, ARCHITECTURE §5.1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
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
    exclusion_reason: str | None
    """Por qué la posición no entra en los totales. `None` si sí entra."""
    last_price: Decimal | None
    prev_close: Decimal | None
    quote_as_of: datetime | None
    quote_stale: bool
    quote_currency: str | None
    currency_mismatch: bool
    """La divisa del proveedor discrepa de la del catálogo (PHASE-44.11 D4).
    La UI lo muestra en la posición: se valora con la del proveedor."""
    market_value: Decimal | None
    market_value_base: Decimal | None
    cost_basis_base: Decimal
    """Coste en base al tipo de la FECHA DE COMPRA, no al de hoy."""
    unrealized_pnl_base: Decimal | None
    fx_rate: Decimal | None
    fx_as_of: date | None
    """Fecha efectiva del tipo aplicado — no siempre es hoy (un lunes se usa el
    del viernes). Un valor con precio de hoy y tasa de hace días debe decirlo."""
    unrealized_pnl: Decimal | None
    unrealized_pnl_pct: Decimal | None
    price_effect: Decimal | None
    fx_effect: Decimal | None
    daily_change: Decimal | None
    total_return: Decimal | None
    yield_on_cost: Decimal | None
    weight_pct: Decimal | None


class CurrencyExposureResponse(BaseModel):
    model_config = {"from_attributes": True}

    currency: str
    market_value_base: Decimal
    weight_pct: Decimal


class PortfolioSummaryResponse(BaseModel):
    model_config = {"from_attributes": True}

    pricing_enabled: bool
    base_currency: str
    base_note: str
    total_cost_basis: Decimal
    """Suma en divisa NATIVA. Sólo interpretable si la cartera es monodivisa."""
    total_cost_basis_base: Decimal
    total_market_value: Decimal
    total_market_value_base: Decimal
    total_unrealized_pnl: Decimal
    total_unrealized_pnl_base: Decimal
    total_realized_pnl: Decimal
    total_dividends_net: Decimal
    daily_pnl: Decimal
    quoted_count: int
    unquoted_count: int
    currency_exposure: list[CurrencyExposureResponse]
    positions: list[PositionSummaryResponse]
