"""Cálculo de cuadro de amortización francés para liabilities (PHASE-22.3).

Sistema francés: cuota constante a lo largo del plazo. Cada mes la
cuota se divide en intereses (parte decreciente) + amortización del
principal (parte creciente).

Fórmula de la cuota:
    cuota = P * (i * (1+i)^n) / ((1+i)^n - 1)
donde:
    P = principal inicial (positivo)
    i = tasa mensual (apr_anual / 12)
    n = plazo en meses

Iteración mes a mes:
    intereses_mes = saldo_pendiente * i
    principal_mes = cuota - intereses_mes
    saldo_pendiente -= principal_mes

Sólo aplicable cuando `apr`, `term_months` y `opening_balance > 0`.
Para tarjetas (saldo arrastrado sin plan fijo) no aplica — el caller
debe filtrar.
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from typing import NamedTuple

CENT = Decimal("0.01")


class AmortizationRow(NamedTuple):
    """Una fila del cuadro de amortización."""

    month: int  # 1..term_months
    due_date: date
    payment: Decimal
    interest: Decimal
    principal: Decimal
    remaining_balance: Decimal


def _round_cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_EVEN)


def _add_month(d: date, months: int) -> date:
    """Suma `months` meses a `d` cuidando el clamp del último día.

    `(2026-01-31, +1)` → `2026-02-28`. Mantiene el día del mes si cabe;
    si no, último día válido del nuevo mes.
    """
    total = d.month - 1 + months
    new_year = d.year + total // 12
    new_month = total % 12 + 1
    last_day = calendar.monthrange(new_year, new_month)[1]
    return date(new_year, new_month, min(d.day, last_day))


def compute_monthly_payment(principal: Decimal, apr: Decimal, term_months: int) -> Decimal:
    """Cuota mensual constante del sistema francés.

    `apr` es la tasa **anual** como decimal (0.035 = 3.5%). Si `apr=0`
    la cuota es lineal (principal / term_months).
    """
    if principal <= 0 or term_months <= 0:
        return Decimal("0")
    if apr == 0:
        return _round_cents(principal / Decimal(term_months))
    i = apr / Decimal(12)
    one_plus_i = Decimal(1) + i
    factor = one_plus_i**term_months
    payment = principal * (i * factor) / (factor - Decimal(1))
    return _round_cents(payment)


def build_schedule(
    *,
    principal: Decimal,
    apr: Decimal,
    term_months: int,
    start_date: date,
) -> list[AmortizationRow]:
    """Genera el cuadro francés completo.

    Convención (PHASE-24.3, alineada con la presentación de BBVA y
    otros bancos españoles): **todas las cuotas tienen el mismo
    `payment` exacto**. El residuo de redondeo se absorbe en el
    `principal` del último mes (su importe puede diferir uno o dos
    céntimos vs los anteriores, pero la cuota total al usuario sigue
    siendo idéntica). Esto asegura que `Σ(payments) == n × payment`
    exactamente y permite que `extra_charges = total_to_pay − Σ`
    coincida con la comisión real que cobra el banco.
    """
    if principal <= 0 or term_months <= 0:
        return []
    payment = compute_monthly_payment(principal, apr, term_months)
    i = apr / Decimal(12) if apr > 0 else Decimal(0)
    remaining = principal
    rows: list[AmortizationRow] = []
    for month_idx in range(1, term_months + 1):
        interest_month = _round_cents(remaining * i) if i > 0 else Decimal("0")
        # Último mes: ajustamos el `principal` para liquidar la deuda
        # exactamente (`remaining → 0`); el `payment` mostrado al usuario
        # sigue siendo el constante — el residuo de céntimos queda
        # absorbido en `principal` vs el split teórico.
        if month_idx == term_months:
            principal_month = remaining
            remaining = Decimal("0")
        else:
            principal_month = _round_cents(payment - interest_month)
            remaining = _round_cents(remaining - principal_month)
        due = _add_month(start_date, month_idx)
        rows.append(
            AmortizationRow(
                month=month_idx,
                due_date=due,
                payment=payment,
                interest=interest_month,
                principal=principal_month,
                remaining_balance=remaining,
            )
        )
    return rows
