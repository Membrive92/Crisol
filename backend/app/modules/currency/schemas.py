"""Schemas Pydantic del módulo currency."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Indica de qué fecha sale la tasa devuelta:
# - `exact`    → la tasa pedida existe para esa fecha exacta.
# - `previous` → no había tasa exacta; se usó la última anterior dentro
#                de la ventana de fallback (típico fines de semana).
# - `same`     → la conversión es trivial (from == to); no hubo lookup.
# - `missing`  → no hay tasa ni fallback; el caller debe decidir cómo
#                señalizarlo. La conversión devuelve el importe sin
#                tocar (rate = 1) y `rate_date` será el `at_date` pedido.
RateFallback = Literal["exact", "previous", "same", "missing"]


class ConversionResult(BaseModel):
    """Resultado interno de `service.convert`.

    Es lo que se devuelve a otros módulos del backend; el endpoint HTTP
    `/currency/convert` lo expone tal cual a través de `ConvertResponse`.
    """

    model_config = ConfigDict(extra="ignore")

    amount: Decimal = Field(description="Importe ya convertido a `to_currency`")
    rate: Decimal = Field(description="Tasa aplicada (1 from = rate to)")
    rate_date: date = Field(description="Fecha efectiva de la tasa usada")
    fallback: RateFallback


class ConvertResponse(ConversionResult):
    """Respuesta HTTP de `/currency/convert`. Idéntica a ConversionResult."""


class ExchangeRateRow(BaseModel):
    """Una fila de tasa para la respuesta de `/currency/rates`."""

    quote: str = Field(min_length=3, max_length=3)
    rate: Decimal


class RatesResponse(BaseModel):
    """Respuesta del endpoint `/currency/rates?date=YYYY-MM-DD`."""

    rate_date: date
    base: str = Field(default="EUR", min_length=3, max_length=3)
    rates: list[ExchangeRateRow]
