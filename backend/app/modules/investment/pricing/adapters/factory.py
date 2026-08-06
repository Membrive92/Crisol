"""Fábrica del adapter de precios (PHASE-44.7, selector cableado en 44.11.B).

`PRICE_PROVIDER` elige. El default es **yfinance** desde PHASE-44.11: cubre más
de un mercado y no pide credencial, así que la cartera vale precios recién
instalado el proyecto. Finnhub sigue disponible con `PRICE_PROVIDER=finnhub`,
que es la vuelta atrás de un solo cambio de variable de entorno si yfinance —que
no es oficial— se rompe.

Un valor desconocido en `PRICE_PROVIDER` **no arranca en silencio con otra
cosa**: lanza. Caer al default enmascararía una errata de despliegue y el
usuario vería precios de un proveedor que no eligió.
"""

from __future__ import annotations

from app.core.config import settings
from app.modules.investment.pricing.adapters.base import PriceAdapter
from app.modules.investment.pricing.adapters.finnhub import FinnhubAdapter
from app.modules.investment.pricing.adapters.yfinance import YFinanceAdapter


def build_price_adapter() -> PriceAdapter:
    provider = settings.price_provider.strip().lower()
    if provider == "yfinance":
        return YFinanceAdapter(
            throttle_seconds=settings.price_throttle_seconds,
            timeout_seconds=settings.price_timeout_seconds,
        )
    if provider == "finnhub":
        return FinnhubAdapter(
            api_key=settings.finnhub_api_key,
            timeout_seconds=settings.price_timeout_seconds,
        )
    raise ValueError(
        f"PRICE_PROVIDER desconocido: {settings.price_provider!r}. "
        "Valores admitidos: 'yfinance', 'finnhub'."
    )


def get_price_adapter() -> PriceAdapter:
    """Dependencia FastAPI; los tests la sobreescriben con un doble mockeado."""
    return build_price_adapter()
