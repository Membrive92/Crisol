"""Lógica de negocio del módulo analytics (PHASE-37.3).

Orquesta la heurística de recurrencia (`recurrence.py`) con las queries
(`repository.py`) para producir la respuesta de gasto estructural vs
puntual y la tasa de ahorro dual.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.analytics import repository as repo
from app.modules.personal_finance.analytics.recurrence import (
    RECURRENCE_WINDOW_MONTHS,
    classify_recurring_categories,
)
from app.modules.personal_finance.analytics.schemas import (
    CategoryAmount,
    ExpenseStructureResponse,
    TxRef,
)
from app.modules.personal_finance.categories.models import CategoryKind
from app.modules.personal_finance.dashboard.repository import get_totals_by_kind
from app.modules.personal_finance.dashboard.service import ensure_rates_for_user_scope


def _month_floor_shift(dt: datetime, months_back: int) -> datetime:
    """Primer día (UTC 00:00) del mes que está `months_back` meses antes
    del mes de `dt`. `months_back=0` → primer día del mes de `dt`."""
    total = (dt.year * 12 + (dt.month - 1)) - months_back
    year, month0 = divmod(total, 12)
    return datetime(year, month0 + 1, 1, tzinfo=UTC)


def _safe_rate(income: Decimal, expense: Decimal) -> float | None:
    """(income - expense) / income como float; None si income <= 0."""
    if income <= 0:
        return None
    return float((income - expense) / income)


async def get_expense_structure(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> ExpenseStructureResponse:
    """Calcula el desglose estructural/puntual del gasto del rango.

    La ventana de recurrencia (para clasificar categorías recurrentes y
    la media mensual estructural) se ancla al final del rango pedido
    (`date_to`) o a "ahora" si el rango es abierto — así ver un período
    pasado usa el histórico hasta ese punto, no el actual.
    """
    window_end = date_to if date_to is not None else datetime.now(UTC)
    window_start = _month_floor_shift(window_end, RECURRENCE_WINDOW_MONTHS - 1)

    if target_currency is not None:
        # Cubrir toda la ventana (no sólo el rango) para que la conversión
        # del histórico de recurrencia no deje meses fuera por falta de tasa.
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=target_currency,
            date_from=window_start,
            date_to=window_end,
        )

    # Reglas 1 y 2 (fixed_expense confirmado + rol de deuda) ∪ regla 3
    # (recurrencia por importe estable sobre la ventana).
    seed = await repo.seed_structural_category_ids(db, user_id)
    monthly = await repo.monthly_expense_by_category(
        db,
        user_id,
        window_start=window_start,
        window_end=window_end,
        currency=currency,
        target_currency=target_currency,
    )
    recurring = classify_recurring_categories(monthly)
    structural_ids = seed | recurring

    structural_total, exceptional_total = await repo.expense_split_totals(
        db,
        user_id,
        structural_category_ids=structural_ids,
        currency=currency,
        target_currency=target_currency,
        date_from=date_from,
        date_to=date_to,
    )
    monthly_avg = await repo.structural_monthly_avg(
        db,
        user_id,
        structural_category_ids=structural_ids,
        window_start=window_start,
        window_end=window_end,
        currency=currency,
        target_currency=target_currency,
    )

    totals = await get_totals_by_kind(
        db,
        user_id,
        currency=currency,
        target_currency=target_currency,
        date_from=date_from,
        date_to=date_to,
    )
    income_total = totals[CategoryKind.INCOME]
    # Gasto bruto = estructural + puntual (mismos filtros que el split);
    # equivale al gasto de `get_totals_by_kind`.
    gross_expense = structural_total + exceptional_total

    top_rows = await repo.top_exceptional_transactions(
        db,
        user_id,
        structural_category_ids=structural_ids,
        currency=currency,
        target_currency=target_currency,
        date_from=date_from,
        date_to=date_to,
        limit=5,
    )
    by_cat_rows = await repo.exceptional_by_category(
        db,
        user_id,
        structural_category_ids=structural_ids,
        currency=currency,
        target_currency=target_currency,
        date_from=date_from,
        date_to=date_to,
    )

    return ExpenseStructureResponse(
        reference_currency=(target_currency or currency or "EUR"),
        income_total=income_total,
        structural_total=structural_total,
        exceptional_total=exceptional_total,
        structural_monthly_avg=monthly_avg,
        savings_rate_gross=_safe_rate(income_total, gross_expense),
        savings_rate_structural=_safe_rate(income_total, structural_total),
        top_exceptional=[
            TxRef(
                id=tx.id,
                description=tx.description,
                amount=tx.amount,
                converted_amount=converted,
                currency=tx.currency,
                occurred_at=tx.occurred_at,
                category_id=tx.category_id,
                category_name=name,
            )
            for tx, name, converted in top_rows
        ],
        exceptional_by_category=[
            CategoryAmount(
                category_id=cid,
                category_name=name,
                color=color,
                icon=icon,
                total=total,
            )
            for cid, name, color, icon, total in by_cat_rows
        ],
    )
