"""Acciones corporativas (PHASE-44.7, Dec.9).

PURO: sin BD. Solo `split` y `stock_dividend` se APLICAN en el MVP —ambas escalan
cantidad y precio por un ratio, manteniendo el coste base invariante—. `spinoff`
y `return_of_capital` se pueden REGISTRAR pero aplicarlas exige datos que el
modelo (`ratio` escalar) no expresa (security destino, fracción de base), así que
se rechazan al aplicar hasta una fase futura.
"""

from __future__ import annotations

from decimal import Decimal

from app.modules.investment.enums import CorpActionType

APPLICABLE: frozenset[CorpActionType] = frozenset(
    {CorpActionType.SPLIT, CorpActionType.STOCK_DIVIDEND}
)
"""Acciones que el MVP sabe aplicar. Split (4:1 → ratio 4) y stock dividend
(10% → ratio 1,10) tienen la MISMA mecánica: ×ratio a la cantidad, ÷ratio al
precio, coste base intacto."""


def is_applicable(action_type: CorpActionType) -> bool:
    return action_type in APPLICABLE


def apply_ratio(quantity: Decimal, price: Decimal, ratio: Decimal) -> tuple[Decimal, Decimal]:
    """Nueva (cantidad, precio) tras aplicar el ratio. `quantity·price` invariante."""
    return quantity * ratio, price / ratio
