"""Adapter de precios Finnhub (PHASE-44.7, ARCHITECTURE §8.1).

Free tier: 60 req/min (sobra para <60 posiciones, se serializa el refresh). Sin
`FINNHUB_API_KEY` el adapter queda DESACTIVADO: `quote` devuelve `None` sin
lanzar — la cartera funciona con datos manuales y las posiciones salen "sin
cotización". Nada de tiempo real: `/quote` da precio actual + cierre anterior,
suficiente para valoración y cambio diario.

Este adapter hace UNA cosa: cotizar. La búsqueda de símbolos se retiró de aquí en
PHASE-44.8 E1 (ver el comentario de `adapters/base.py`): el `/search` de Finnhub
no devuelve la bolsa, así que no puede alimentar un buscador multi-mercado.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.modules.investment.pricing.adapters.base import Quote

_BASE_URL = "https://finnhub.io/api/v1"


class FinnhubAdapter:
    """Implementación de `PriceAdapter` sobre Finnhub."""

    def __init__(self, api_key: str, *, timeout_seconds: int = 15) -> None:
        self._api_key = api_key.strip()
        self._timeout = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    async def quote(self, ticker: str) -> Quote | None:
        if not self.enabled:
            return None
        params = {"symbol": ticker.upper(), "token": self._api_key}
        data = await self._get("/quote", params)
        if data is None:
            return None
        price = _to_decimal(data.get("c"))
        if price is None or price == 0:  # Finnhub devuelve c=0 para símbolos que no cubre
            return None
        timestamp = data.get("t")
        as_of = (
            datetime.fromtimestamp(int(timestamp), tz=UTC)
            if isinstance(timestamp, (int, float)) and timestamp
            else datetime.now(UTC)
        )
        return Quote(price=price, prev_close=_to_decimal(data.get("pc")), as_of=as_of)

    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any] | None:
        """GET a Finnhub. Un fallo del proveedor NO propaga: devuelve `None` para
        que el refresh sirva la última cotización con `quote_stale`."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{_BASE_URL}{path}", params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None


def _to_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
