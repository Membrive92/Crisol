"""Adapter de precios Finnhub (PHASE-44.7, ARCHITECTURE §8.1).

Deja de ser el proveedor por defecto en PHASE-44.11 —pasa a serlo yfinance, que
cubre más de un mercado y no pide credencial—, pero **se conserva** detrás del
selector `PRICE_PROVIDER`: cuesta cero mantenerlo y es la vuelta atrás si
yfinance (que no es oficial) se rompe.

Free tier: 60 req/min (sobra para <60 posiciones, se serializa el refresh). Sin
`FINNHUB_API_KEY` el adapter queda DESACTIVADO: devuelve `QuoteError` en todas
las claves sin lanzar — la cartera funciona con datos manuales y las posiciones
salen "sin cotización". Nada de tiempo real: `/quote` da precio actual + cierre
anterior, suficiente para valoración y cambio diario.

**Es US-only**, y eso es visible en el contrato: un símbolo europeo sale como
`QuoteError` con su motivo (exclusión estándar), nunca como error del summary.

**No declara divisa**: su `/quote` devuelve sólo números (`c`, `pc`, `t`), así
que `Quote.currency` es `None` y quien persiste cae a la del catálogo. Es una
suposición, no un dato — aceptable porque el proveedor sólo cubre EE. UU. y ahí
la divisa del catálogo es USD; ver la regla 2 de `base.py`.

Este adapter hace UNA cosa: cotizar. La búsqueda de símbolos se retiró de aquí en
PHASE-44.8 E1 (ver el comentario de `adapters/base.py`): el `/search` de Finnhub
no devuelve la bolsa, así que no puede alimentar un buscador multi-mercado.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.modules.investment.pricing.adapters.base import Quote, QuoteError, QuoteRequest

_BASE_URL = "https://finnhub.io/api/v1"

#: Plazas que Finnhub cotiza con el ticker desnudo. Fuera de aquí no hay
#: cobertura, y decirlo por adelantado evita gastar una petición para nada.
_US_VENUES = frozenset({"NYSE", "NASDAQ", "CBOE", "OTC", "UNKNOWN", ""})

_DISABLED = QuoteError(reason="proveedor de precios sin credencial configurada")
_NO_COVERAGE = QuoteError(reason="el proveedor sólo cubre mercados de EE. UU.")
_NO_QUOTE = QuoteError(reason="el proveedor no devuelve precio para este símbolo")


class FinnhubAdapter:
    """Implementación de `PriceAdapter` sobre Finnhub."""

    def __init__(self, api_key: str, *, timeout_seconds: int = 15) -> None:
        self._api_key = api_key.strip()
        self._timeout = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    async def quotes(self, requests: Sequence[QuoteRequest]) -> dict[str, Quote | QuoteError]:
        if not self.enabled:
            return {r.key: _DISABLED for r in requests}
        results: dict[str, Quote | QuoteError] = {}
        for request in requests:
            if request.exchange.strip().upper() not in _US_VENUES:
                results[request.key] = _NO_COVERAGE
                continue
            results[request.key] = await self._quote_one(request.ticker)
        return results

    async def _quote_one(self, ticker: str) -> Quote | QuoteError:
        params = {"symbol": ticker.upper(), "token": self._api_key}
        data = await self._get("/quote", params)
        if data is None:
            return _NO_QUOTE
        price = _to_decimal(data.get("c"))
        if price is None or price == 0:  # Finnhub devuelve c=0 para símbolos que no cubre
            return _NO_QUOTE
        timestamp = data.get("t")
        as_of = (
            datetime.fromtimestamp(int(timestamp), tz=UTC)
            if isinstance(timestamp, (int, float)) and timestamp
            else datetime.now(UTC)
        )
        return Quote(
            price=price,
            prev_close=_to_decimal(data.get("pc")),
            currency=None,  # su `/quote` no la trae; ver docstring del módulo
            as_of=as_of,
        )

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
