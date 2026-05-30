"""Helpers SQL para convertir importes per-transaction (PHASE-8.3).

Las queries del dashboard que aceptan `target_currency` necesitan
multiplicar `Transaction.amount` por la tasa **del día de la
transacción** antes de agregar. Como `exchange_rates` guarda EUR→quote,
la conversión se compone:

    convert(amount, FROM, TO, date) =
        FROM == TO          → amount
        TO   == EUR         → amount / rate(EUR→FROM, date)
        FROM == EUR         → amount * rate(EUR→TO, date)
        otherwise           → amount * rate(EUR→TO, date) / rate(EUR→FROM, date)

`rate(EUR→X, date)` se obtiene como **subquery correlacionada**: la
última tasa estrictamente anterior o igual a `date` dentro de una
ventana de 14 días (igual que `currency.repository.get_rate_with_fallback`).

Cuando la subquery devuelve NULL (sin tasa disponible), la división
propaga NULL → la transacción queda excluida del SUM. Este es el
comportamiento "no inventes datos" del proyecto: mejor sumar
transacciones convertibles y reportar las que no que mezclar monedas
silenciosamente.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    Date,
    Numeric,
    case,
    cast,
    select,
)
from sqlalchemy.sql.elements import ColumnElement

from app.modules.currency.models import ExchangeRate
from app.modules.personal_finance.transactions.models import Transaction

CANONICAL_BASE = "EUR"
_FALLBACK_WINDOW_DAYS = 14


def _latest_rate_subquery(quote: Any, occurred_at: Any) -> ColumnElement[Any]:
    # `quote`/`occurred_at` are SQL column expressions or literals
    # (InstrumentedAttribute / str). Typed as Any because the SQLAlchemy
    # stubs don't treat InstrumentedAttribute[T] as ColumnElement[Any].
    """Subquery escalar correlacionada: última tasa EUR→`quote` ≤ `occurred_at`.

    Acepta `quote` como columna SQL o literal Python. La ventana de
    búsqueda es 14 días. Si no hay tasa, devuelve NULL.

    PostgreSQL admite resta `DATE - integer` para retroceder días, así
    que evitamos `INTERVAL` y los problemas de auto-cast desde VARCHAR.
    """
    rate_date_col = cast(occurred_at, Date)
    floor_date = rate_date_col - _FALLBACK_WINDOW_DAYS
    quote_expr = quote  # SQLAlchemy maneja literal vs column automáticamente.

    return (
        select(ExchangeRate.rate)
        .where(ExchangeRate.base == CANONICAL_BASE)
        .where(ExchangeRate.quote == quote_expr)
        .where(ExchangeRate.rate_date <= rate_date_col)
        .where(ExchangeRate.rate_date >= floor_date)
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
        .correlate(Transaction)
        .scalar_subquery()
    )


def converted_amount_expr(target_currency: str) -> ColumnElement[Any]:
    """Devuelve la expresión `Transaction.amount` convertida a `target_currency`.

    Devuelve NULL para transacciones cuya tasa no está en BD (ni
    exacta ni en la ventana de fallback). El caller debe contar esas
    NULLs si quiere reportar "transacciones sin tasa".
    """
    target = target_currency.upper()
    occurred_at = Transaction.occurred_at
    amount = cast(Transaction.amount, Numeric(20, 8))

    if target == CANONICAL_BASE:
        # Convertir FROM cualquier moneda → EUR.
        from_rate = _latest_rate_subquery(Transaction.currency, occurred_at)
        return case(
            (Transaction.currency == CANONICAL_BASE, amount),
            else_=amount / from_rate,
        )

    # Convertir FROM cualquier moneda → target (no-EUR).
    to_rate = _latest_rate_subquery(target, occurred_at)
    from_rate = _latest_rate_subquery(Transaction.currency, occurred_at)
    return case(
        (Transaction.currency == target, amount),
        (Transaction.currency == CANONICAL_BASE, amount * to_rate),
        else_=amount * to_rate / from_rate,
    )


def amount_is_convertible_expr(target_currency: str) -> ColumnElement[Any]:
    """Boolean expression: True cuando la transacción se puede convertir.

    Útil para contar cuántas transacciones se incluyeron en la SUM
    convertida y cuántas se excluyeron por falta de tasa.
    """
    target = target_currency.upper()
    if target == CANONICAL_BASE:
        # Las que ya son EUR siempre se pueden. Las demás necesitan from_rate.
        from_rate = _latest_rate_subquery(Transaction.currency, Transaction.occurred_at)
        return (Transaction.currency == CANONICAL_BASE) | (from_rate.is_not(None))

    to_rate = _latest_rate_subquery(target, Transaction.occurred_at)
    from_rate = _latest_rate_subquery(Transaction.currency, Transaction.occurred_at)
    # Las que ya están en target siempre. Las EUR sólo necesitan to_rate. El
    # resto necesita ambas.
    return (
        (Transaction.currency == target)
        | ((Transaction.currency == CANONICAL_BASE) & to_rate.is_not(None))
        | (from_rate.is_not(None) & to_rate.is_not(None))
    )
