"""Matching FIFO de ventas contra lotes (PHASE-44.7, Dec.10).

PURO: sin BD. Pool GLOBAL por security (criterio AEAT), no por cuenta. Consume
los lotes abiertos en orden de fecha de compra; cada trozo consumido guarda el
coste base del lote (en divisa nativa) y su FX, para descomponer luego el P&L
realizado en componente precio vs componente divisa.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


class InsufficientSharesError(Exception):
    """Se intenta vender más de lo que hay en cartera."""

    def __init__(self, requested: Decimal, held: Decimal) -> None:
        self.requested = requested
        self.held = held
        super().__init__(f"Venta de {requested} acciones pero solo hay {held} en cartera")


@dataclass(frozen=True)
class OpenLot:
    """Un lote con su cantidad AÚN no consumida por ventas anteriores."""

    lot_id: uuid.UUID
    trade_date: date
    remaining: Decimal
    price: Decimal
    fx_rate_at_trade: Decimal


@dataclass(frozen=True)
class Allocation:
    """Qué parte de qué lote consume una venta."""

    lot_id: uuid.UUID
    quantity: Decimal
    cost_basis: Decimal
    cost_basis_fx: Decimal


def match_fifo(open_lots: Sequence[OpenLot], quantity: Decimal) -> list[Allocation]:
    """Casa `quantity` acciones contra los lotes abiertos en orden FIFO.

    Lanza `InsufficientSharesError` si no hay suficientes acciones — nunca casa de
    forma parcial silenciosa: vender más de lo que se tiene es un 409, no un
    recorte (el saldo negativo escondería un error de datos del usuario).
    """
    remaining = quantity
    allocations: list[Allocation] = []
    for lot in sorted(open_lots, key=lambda item: (item.trade_date, str(item.lot_id))):
        if remaining <= 0:
            break
        if lot.remaining <= 0:
            continue
        take = min(lot.remaining, remaining)
        allocations.append(
            Allocation(
                lot_id=lot.lot_id,
                quantity=take,
                cost_basis=lot.price,
                cost_basis_fx=lot.fx_rate_at_trade,
            )
        )
        remaining -= take
    if remaining > 0:
        raise InsufficientSharesError(requested=quantity, held=quantity - remaining)
    return allocations
