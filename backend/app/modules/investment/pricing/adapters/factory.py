"""Fábrica del adapter de precios (PHASE-44.7).

Cablea el proveedor activo (`PRICE_PROVIDER`) a la configuración. Hoy solo
Finnhub. La dependencia FastAPI es sobreescribible en tests con un doble.
"""

from __future__ import annotations

from app.core.config import settings
from app.modules.investment.pricing.adapters.base import PriceAdapter
from app.modules.investment.pricing.adapters.finnhub import FinnhubAdapter


def build_price_adapter() -> PriceAdapter:
    return FinnhubAdapter(
        api_key=settings.finnhub_api_key,
        timeout_seconds=settings.price_timeout_seconds,
    )


def get_price_adapter() -> PriceAdapter:
    """Dependencia FastAPI; los tests la sobreescriben con un doble mockeado."""
    return build_price_adapter()
