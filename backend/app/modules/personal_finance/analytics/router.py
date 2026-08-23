"""Router del módulo analytics (PHASE-37.3+).

Read-only. Mismo modo de moneda que el dashboard: `currency` (legacy,
filtra + agrega crudo) o `target_currency` (convierte por fecha y
agrega). Si no llega ninguno, default legacy `USD` — coherente con
`dashboard.router`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.analytics.schemas import (
    CategoryStructureExplain,
    ExpenseStructureResponse,
    MonthOutlookResponse,
)
from app.modules.personal_finance.analytics.service import (
    explain_expense_structure,
    get_expense_structure,
    get_month_outlook,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

_DEFAULT_CURRENCY = "USD"


def _resolve_currency_params(
    currency: str | None, target_currency: str | None
) -> tuple[str | None, str | None]:
    if target_currency is None and currency is None:
        return _DEFAULT_CURRENCY, None
    return currency, target_currency


@router.get("/expense-structure", response_model=ExpenseStructureResponse)
async def expense_structure_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> ExpenseStructureResponse:
    """Gasto estructural vs puntual + tasa de ahorro dual para el rango."""
    cur, target = _resolve_currency_params(currency, target_currency)
    return await get_expense_structure(
        db,
        user.id,
        currency=cur,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        cycle_start_day=user.cycle_start_day,
    )


@router.get("/expense-structure/explain", response_model=list[CategoryStructureExplain])
async def expense_structure_explain_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[CategoryStructureExplain]:
    """Por qué cada categoría del desglose es Fija o Variable (PHASE-43.2)."""
    cur, target = _resolve_currency_params(currency, target_currency)
    return await explain_expense_structure(
        db,
        user.id,
        currency=cur,
        target_currency=target,
        date_from=date_from,
        date_to=date_to,
        # PHASE-47 — el mismo día que su gemelo `expense-structure`. Sin esto,
        # el VEREDICTO («esta categoría es fija») y el PORQUÉ («porque aparece
        # en 5 de los últimos 6 meses») calculaban su ventana de recurrencia
        # sobre universos distintos, y la web los pide con los MISMOS params.
        # Rompía la garantía que `recurrence.py` declara por escrito: fuente
        # ÚNICA de la aritmética de banda, compartida por los dos.
        cycle_start_day=user.cycle_start_day,
    )


@router.get("/month-outlook", response_model=MonthOutlookResponse)
async def month_outlook_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> MonthOutlookResponse:
    """Proyección de fin de mes (cargos comprometidos) + colchón/runway."""
    cur, target = _resolve_currency_params(currency, target_currency)
    return await get_month_outlook(
        db,
        user.id,
        currency=cur,
        target_currency=target,
        # PHASE-47 — el mes del usuario manda, sin flag: lo declaró en Ajustes.
        cycle_start_day=user.cycle_start_day,
    )
