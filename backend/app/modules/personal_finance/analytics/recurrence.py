"""Heurística estructural vs puntual del gasto (PHASE-37.3).

Un gasto es **estructural** (recurrente, forma parte del coste de vida
del usuario) si cumple CUALQUIERA de:

1. Su categoría tiene un `fixed_expense` confirmado apuntándola
   (aproximación a nivel de categoría de la regla "matchea un gasto
   fijo": si tienes un gasto fijo confirmado en "Gimnasio", los gastos
   de esa categoría son estructurales).
2. Su categoría tiene rol de deuda (`DEBT_PAYMENT`/`DEBT_INTEREST`) —
   las cuotas son estructurales por definición.
3. Su categoría **recurre**: aparece en ≥ `RECURRENCE_MIN_MONTHS` de los
   últimos `RECURRENCE_WINDOW_MONTHS` meses con un importe mensual
   dentro de ±`RECURRENCE_BAND` de la mediana (estabilidad de importe).

Todo lo demás es **puntual**. El override manual por transacción
(`transactions.is_exceptional`) gana SIEMPRE sobre esta heurística — se
aplica en la capa SQL (`repository.is_structural_expr`), no aquí.

Esta parte —la regla 3— es una función PURA sobre totales mensuales por
categoría, para poder testearla sin BD. Las reglas 1 y 2 son consultas
de conjunto directas y viven en `repository.py`.

Nota de honestidad (del phase doc): la regla 3 clasificará mal algunos
casos (un gasto grande puntual en una categoría habitualmente estable
cuenta como estructural; el primer mes de un recurrente nuevo cuenta como
puntual). Es el trade-off aceptado; el override existe para eso. Revisar
`N`/`M`/banda en `lessons.md` tras 1-2 meses de uso real si hace falta.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from decimal import Decimal

# Parámetros de la regla 3 (nombrados y ajustables — ver nota de honestidad).
RECURRENCE_MIN_MONTHS = 4
"""N — meses (con importe en banda) mínimos dentro de la ventana."""
RECURRENCE_WINDOW_MONTHS = 6
"""M — tamaño de la ventana de meses hacia atrás que se inspecciona."""
RECURRENCE_BAND = Decimal("0.40")
"""±banda relativa alrededor de la mediana para considerar 'estable'."""


def _median(values: Sequence[Decimal]) -> Decimal:
    """Mediana de una secuencia no vacía de Decimals."""
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal("2")


def classify_recurring_categories(
    monthly_totals: Mapping[uuid.UUID, Sequence[Decimal]],
    *,
    min_months: int = RECURRENCE_MIN_MONTHS,
    band: Decimal = RECURRENCE_BAND,
) -> set[uuid.UUID]:
    """Devuelve el conjunto de categorías 'recurrentes' (regla 3).

    `monthly_totals[cat]` es la lista de totales mensuales de la categoría
    dentro de la ventana — un elemento por mes CON actividad (los meses
    sin gasto en esa categoría no aparecen). Una categoría es recurrente
    si ≥ `min_months` de esos meses tienen un total dentro de ±`band` de
    la mediana de sus totales activos.

    La mediana como centro (en vez de la media) resiste un mes atípico:
    un único mes con el triple de gasto no desplaza el centro lo bastante
    como para sacar de banda a los meses normales.
    """
    recurring: set[uuid.UUID] = set()
    for category_id, totals in monthly_totals.items():
        active = [t for t in totals if t > 0]
        if len(active) < min_months:
            continue
        median = _median(active)
        if median <= 0:
            continue
        low = median * (Decimal("1") - band)
        high = median * (Decimal("1") + band)
        in_band = sum(1 for t in active if low <= t <= high)
        if in_band >= min_months:
            recurring.add(category_id)
    return recurring
