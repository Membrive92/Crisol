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
    func,
    literal,
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

    # AUDIT — sql-no-zero-rate-guard (b): defensa en profundidad. Aunque el
    # cliente HTTP (a) ya rechaza tasas <= 0, una fila histórica corrupta o
    # cargada por otra vía haría que `amount / from_rate` reventara con
    # división por cero (500) o invirtiera el signo. Proyectamos la tasa con
    # un CASE que devuelve NULL si no es estrictamente positiva → la fila
    # queda "inconvertible" (mismo comportamiento que "sin tasa") en lugar
    # de propagar un error. Filtramos también en el WHERE para no elegir una
    # fila no-positiva como "última" tapando una válida más antigua.
    positive_rate = case(
        (ExchangeRate.rate > literal(0), ExchangeRate.rate),
        else_=None,
    )

    return (
        select(positive_rate)
        .where(ExchangeRate.base == CANONICAL_BASE)
        .where(ExchangeRate.quote == quote_expr)
        .where(ExchangeRate.rate > literal(0))
        .where(ExchangeRate.rate_date <= rate_date_col)
        .where(ExchangeRate.rate_date >= floor_date)
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
        .correlate(Transaction)
        .scalar_subquery()
    )


def _latest_rate_date_subquery(quote: Any, occurred_at: Any) -> ColumnElement[Any]:
    """Subquery escalar: la `rate_date` de la última tasa EUR→`quote` ≤ `occurred_at`.

    Gemela de `_latest_rate_subquery` pero devuelve la FECHA en vez de la
    tasa. Sirve para calcular el ancla común de una cross-rate (AUDIT —
    sql-crossrate-no-reanchor): necesitamos saber a qué fecha resolvió cada
    pierna antes de poder re-anclarlas a la más antigua.
    """
    rate_date_col = cast(occurred_at, Date)
    floor_date = rate_date_col - _FALLBACK_WINDOW_DAYS

    return (
        select(ExchangeRate.rate_date)
        .where(ExchangeRate.base == CANONICAL_BASE)
        .where(ExchangeRate.quote == quote)
        .where(ExchangeRate.rate > literal(0))
        .where(ExchangeRate.rate_date <= rate_date_col)
        .where(ExchangeRate.rate_date >= floor_date)
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
        .correlate(Transaction)
        .scalar_subquery()
    )


def _rate_at_anchor_subquery(quote: Any, anchor_date: Any) -> ColumnElement[Any]:
    """Última tasa EUR→`quote` ≤ `anchor_date` (mismo criterio que `_latest_…`).

    `anchor_date` es una expresión de fecha (no `occurred_at`): la fecha
    común a la que re-anclamos ambas piernas de una cross-rate. La ventana
    de 14 días se mide igualmente hacia atrás desde el ancla.
    """
    floor_date = anchor_date - _FALLBACK_WINDOW_DAYS
    positive_rate = case(
        (ExchangeRate.rate > literal(0), ExchangeRate.rate),
        else_=None,
    )
    return (
        select(positive_rate)
        .where(ExchangeRate.base == CANONICAL_BASE)
        .where(ExchangeRate.quote == quote)
        .where(ExchangeRate.rate > literal(0))
        .where(ExchangeRate.rate_date <= anchor_date)
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
        # Convertir FROM cualquier moneda → EUR. Una sola pierna (EUR→FROM):
        # no hay nada que re-anclar.
        from_rate = _latest_rate_subquery(Transaction.currency, occurred_at)
        return case(
            (Transaction.currency == CANONICAL_BASE, amount),
            else_=amount / from_rate,
        )

    # Convertir FROM cualquier moneda → target (no-EUR).
    #
    # Cuando la tx ya está en target → amount tal cual (sin tasa).
    # Cuando la tx está en EUR → una sola pierna (EUR→target): no se re-ancla.
    to_rate = _latest_rate_subquery(target, occurred_at)

    # AUDIT — sql-crossrate-no-reanchor: en una cross-rate real (la tx no es
    # ni EUR ni target) las dos piernas EUR→X se resolvían con ventanas de
    # fallback independientes y podían acabar en fechas distintas, componiendo
    # una tasa fresca con una rancia. Replicamos el re-anclaje de
    # `currency.service.convert` (AUDIT-2026-05): ambas piernas se anclan a la
    # fecha común más antigua de las dos `rate_date` resueltas
    # (`LEAST(from_date, to_date)`) y se re-leen a ese ancla. Así
    # `converted_amount_expr` y `service.convert` componen la MISMA tasa.
    from_date = _latest_rate_date_subquery(Transaction.currency, occurred_at)
    to_date = _latest_rate_date_subquery(target, occurred_at)
    anchor = func.least(from_date, to_date)
    from_rate_anchored = _rate_at_anchor_subquery(Transaction.currency, anchor)
    to_rate_anchored = _rate_at_anchor_subquery(target, anchor)

    return case(
        (Transaction.currency == target, amount),
        (Transaction.currency == CANONICAL_BASE, amount * to_rate),
        else_=amount * to_rate_anchored / from_rate_anchored,
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
