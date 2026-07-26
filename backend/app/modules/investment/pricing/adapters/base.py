"""Contrato del adapter de precios (PHASE-44.7, ARCHITECTURE §8.1).

Como el de fundamentales, es un `Protocol`: cambiar de proveedor es un adapter
nuevo. Devuelve cotizaciones EOD/horarias (nunca tiempo real — regulado, de pago,
innecesario para la trazabilidad). `quote` devuelve `None` si el proveedor no
cubre el ticker o no hay credencial: sin cotización NO es un error, es una
posición "sin valorar" (mismo principio anti-dato-ficticio que PHASE-31.4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class Quote:
    """Cotización de un valor. `prev_close` alimenta el cambio diario."""

    price: Decimal
    prev_close: Decimal | None
    as_of: datetime


class PriceAdapter(Protocol):
    async def quote(self, ticker: str) -> Quote | None:
        """Cotización de un ticker, o `None` si no hay cobertura/credencial."""
        ...


# `symbol_search` / `SymbolHit` vivieron aquí y se retiran en PHASE-44.8 E1
# (ADR-0008) sin haber tenido nunca un consumidor. Dos motivos:
#
# 1. El endpoint que los alimentaba —`/search` de Finnhub— NO devuelve la bolsa.
#    Sus únicos cuatro campos son `description`, `displaySymbol`, `symbol` y
#    `type` (verificado en su OpenAPI oficial), así que la implementación rellenaba
#    `exchange` con `displaySymbol`, que es un ticker de visualización. Un buscador
#    multi-mercado sin mercado.
# 2. Buscar un símbolo no es responsabilidad del proveedor de PRECIOS. Se separa
#    en su propio contrato (`catalog/adapters/symbol_search/`, Entrega 5), que es
#    donde vive la decisión de qué proveedor cubre qué mercados.
