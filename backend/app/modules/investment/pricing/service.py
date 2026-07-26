"""Servicio de precios + `/portfolio/summary` (PHASE-44.7, ARCHITECTURE §5.1).

El summary parte de las posiciones de la cartera (coste, realizado, dividendos) y
les añade el valor de mercado desde `price_quotes` (refrescadas on-access). Una
posición sin cotización sale con `market_value=null`, badge "sin cotización" y
FUERA de los totales — nunca valorada a coste como sustituto silencioso
(principio anti-dato-ficticio de PHASE-31.4).

Descomposición del P&L (decisión del usuario, opción A):
    price_effect = qty·(precio_actual − coste_medio)·fx_actual
    fx_effect    = qty·coste_medio·(fx_actual − fx_de_compra)
Sin un feed de FX vivo integrado todavía, `fx_actual` cae a `fx_de_compra`, así
que `fx_effect` es 0 y `price_effect` recoge todo el P&L latente. Cuando el feed
exista, la fórmula reparte sin tocar este código.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.investment.portfolio.service import PositionCore, compute_position_cores
from app.modules.investment.pricing import repository as repo
from app.modules.investment.pricing.adapters.base import PriceAdapter
from app.modules.investment.pricing.refresh import RefreshTarget, refresh_quotes

_ZERO = Decimal(0)
_ONE = Decimal(1)


@dataclass(frozen=True)
class PositionSummary:
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


@dataclass(frozen=True)
class PortfolioSummary:
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
    positions: list[PositionSummary]


def _targets(cores: list[PositionCore]) -> list[RefreshTarget]:
    return [
        RefreshTarget(security_id=c.security_id, ticker=c.ticker, currency=c.currency)
        for c in cores
        if c.quantity > 0 and c.ticker
    ]


async def refresh_portfolio(
    db: AsyncSession,
    adapter: PriceAdapter,
    user_id: uuid.UUID,
    *,
    security_ids: Collection[uuid.UUID] | None = None,
) -> int:
    """Fuerza el refresh (botón manual). Devuelve cuántas cotizaciones se
    trajeron."""
    cores = await compute_position_cores(db, user_id)
    targets = [t for t in _targets(cores) if security_ids is None or t.security_id in security_ids]
    return await refresh_quotes(
        db, adapter, targets, ttl_hours=settings.price_ttl_hours, now=datetime.now(UTC), force=True
    )


async def compute_portfolio_summary(
    db: AsyncSession, adapter: PriceAdapter, user_id: uuid.UUID
) -> PortfolioSummary:
    now = datetime.now(UTC)
    cores = await compute_position_cores(db, user_id)
    await refresh_quotes(db, adapter, _targets(cores), ttl_hours=settings.price_ttl_hours, now=now)
    quotes = await repo.list_quotes(db, [c.security_id for c in cores])
    ttl = timedelta(hours=settings.price_ttl_hours)

    partials: list[PositionSummary] = []
    total_market_value = _ZERO
    total_unrealized = _ZERO
    total_realized = _ZERO
    total_dividends_net = _ZERO
    total_cost_basis = _ZERO
    daily_pnl = _ZERO
    quoted = 0
    unquoted = 0

    for core in cores:
        total_cost_basis += core.cost_basis
        total_realized += core.realized_pnl
        total_dividends_net += core.dividends_net

        quote = quotes.get(core.security_id)
        has_quote = quote is not None and core.quantity > 0
        summary = _position_summary(core, quote, has_quote=has_quote, now=now, ttl=ttl)
        partials.append(summary)

        if has_quote and summary.market_value is not None:
            quoted += 1
            total_market_value += summary.market_value
            total_unrealized += summary.unrealized_pnl or _ZERO
            daily_pnl += summary.daily_change or _ZERO
        elif core.quantity > 0:
            unquoted += 1

    # Segundo pase: peso de cada posición sobre el valor de mercado total.
    positions = [_with_weight(summary, total_market_value) for summary in partials]

    return PortfolioSummary(
        pricing_enabled=_pricing_enabled(),
        base_note=(
            "Totales en divisa nativa de cada posición. La conversión a una divisa "
            "base con FX vivo llegará en una fase futura."
        ),
        total_cost_basis=total_cost_basis,
        total_market_value=total_market_value,
        total_unrealized_pnl=total_unrealized,
        total_realized_pnl=total_realized,
        total_dividends_net=total_dividends_net,
        daily_pnl=daily_pnl,
        quoted_count=quoted,
        unquoted_count=unquoted,
        positions=positions,
    )


def _pricing_enabled() -> bool:
    return bool(settings.finnhub_api_key.strip())


def _position_summary(
    core: PositionCore,
    quote: object,
    *,
    has_quote: bool,
    now: datetime,
    ttl: timedelta,
) -> PositionSummary:
    last_price: Decimal | None = None
    prev_close: Decimal | None = None
    quote_as_of: datetime | None = None
    quote_stale = False
    market_value: Decimal | None = None
    unrealized: Decimal | None = None
    unrealized_pct: Decimal | None = None
    price_effect: Decimal | None = None
    fx_effect: Decimal | None = None
    daily_change: Decimal | None = None
    total_return: Decimal | None = None

    if has_quote and quote is not None:
        last_price = quote.price  # type: ignore[attr-defined]
        prev_close = quote.prev_close  # type: ignore[attr-defined]
        quote_as_of = quote.as_of  # type: ignore[attr-defined]
        quote_stale = (now - quote.fetched_at) >= ttl  # type: ignore[attr-defined]
        market_value = core.quantity * last_price
        unrealized = market_value - core.cost_basis
        unrealized_pct = unrealized / core.cost_basis if core.cost_basis > 0 else None
        if prev_close is not None:
            daily_change = core.quantity * (last_price - prev_close)
        avg_cost = core.avg_cost or _ZERO
        cost_fx = core.cost_fx or _ONE
        current_fx = cost_fx  # sin feed FX vivo → fx_effect 0
        price_effect = core.quantity * (last_price - avg_cost) * current_fx
        fx_effect = core.quantity * avg_cost * (current_fx - cost_fx)
        total_return = unrealized + core.realized_pnl + core.dividends_net

    yield_on_cost = core.dividends_gross / core.cost_basis if core.cost_basis > 0 else None

    return PositionSummary(
        security_id=core.security_id,
        ticker=core.ticker,
        name=core.name,
        currency=core.currency,
        quantity=core.quantity,
        avg_cost=core.avg_cost,
        cost_basis=core.cost_basis,
        realized_pnl=core.realized_pnl,
        dividends_gross=core.dividends_gross,
        dividends_net=core.dividends_net,
        has_quote=has_quote,
        last_price=last_price,
        prev_close=prev_close,
        quote_as_of=quote_as_of,
        quote_stale=quote_stale,
        market_value=market_value,
        unrealized_pnl=unrealized,
        unrealized_pnl_pct=unrealized_pct,
        price_effect=price_effect,
        fx_effect=fx_effect,
        daily_change=daily_change,
        total_return=total_return,
        yield_on_cost=yield_on_cost,
        weight_pct=None,
    )


def _with_weight(summary: PositionSummary, total_market_value: Decimal) -> PositionSummary:
    if summary.market_value is None or total_market_value <= 0:
        return summary
    weight = summary.market_value / total_market_value
    return PositionSummary(**{**summary.__dict__, "weight_pct": weight})
