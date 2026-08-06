"""Contrato del adapter de precios (PHASE-44.11, ARCHITECTURE §8.1).

Como el de fundamentales, es un `Protocol`: cambiar de proveedor es un adapter
nuevo. Devuelve cotizaciones EOD/horarias (nunca tiempo real — regulado, de pago,
innecesario para la trazabilidad).

Tres reglas del contrato, todas aprendidas de un fallo concreto:

1. **Un símbolo sin cotización NO es un error del lote.** `quotes` devuelve un
   `QuoteError` por símbolo, nunca lanza por uno malo. Una posición sin
   cotización sale "sin valorar" y fuera de totales, jamás valorada a coste como
   sustituto silencioso (principio anti-dato-ficticio de PHASE-31.4).

2. **La divisa la declara el PROVEEDOR, no el catálogo** (PHASE-44.11 D4).
   Antes se persistía `Security.currency` junto al precio del proveedor, que es
   una afirmación sobre un dato que no habíamos comprobado: un valor de la Bolsa
   de Londres catalogado como `GBP` cuyo proveedor devuelve peniques se
   persistía como libras y su valor de mercado salía **100 veces mayor**. Ahora
   `Quote.currency` viaja con el precio y es lo que se guarda; si discrepa del
   catálogo, se marca — no se silencia.

3. **La búsqueda de símbolos no vive aquí** (ADR-0008). Ver el comentario final.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class QuoteRequest:
    """Un símbolo a cotizar.

    `key` es una cadena de correlación **opaca** para el adapter: la pone quien
    llama (hoy el `security_id`) y vuelve como clave del resultado. Existe
    porque `ticker` no es único —`MCD/NYSE` y un hipotético `MCD/XLON` son dos
    securities— y usar el ticker como clave del dict las colapsaría.
    """

    key: str
    ticker: str
    exchange: str


@dataclass(frozen=True)
class Quote:
    """Cotización de un valor. `prev_close` alimenta el cambio diario."""

    price: Decimal
    prev_close: Decimal | None
    currency: str | None
    """Divisa **del proveedor**, ya normalizada a ISO-4217 (regla 2).

    `None` significa "este proveedor no declara divisa" (es el caso de Finnhub:
    su `/quote` devuelve sólo números). Quien persiste cae entonces a la del
    catálogo, que es lo único que hay — pero es una suposición, no un dato, y
    por eso se distingue de una divisa afirmada.
    """
    as_of: datetime


@dataclass(frozen=True)
class QuoteError:
    """Por qué un símbolo concreto no trae cotización.

    `reason` se muestra al usuario en la posición, así que se escribe para él y
    no para el log: "sin cobertura del proveedor", no "HTTP 404".
    """

    reason: str


class PriceAdapter(Protocol):
    async def quotes(
        self, requests: list[QuoteRequest] | tuple[QuoteRequest, ...]
    ) -> dict[str, Quote | QuoteError]:
        """Cotiza un lote. Devuelve una entrada por `request.key`, siempre.

        Nunca lanza por un símbolo concreto: el fallo de uno es un `QuoteError`
        en su clave y el resto del lote sigue. Un fallo global (sin credencial,
        proveedor caído entero) se expresa como `QuoteError` en todas las
        claves, no como excepción — la cartera nunca se bloquea por precios.
        """
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
#
# PHASE-44.11 lo reconfirma: yfinance SÍ devuelve bolsa, así que la objeción (1)
# decae, pero la (2) —de diseño— sigue en pie. Si yfinance resulta buena fuente
# de búsqueda, entra por el slot del catálogo, no por aquí.
