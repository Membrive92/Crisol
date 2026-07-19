"""Router del módulo deuda (PHASE-30.2, cross-currency en PHASE-30.6)."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.dashboard.schemas import ModuleDashboardSummary
from app.modules.personal_finance.debt.schemas import (
    DebtCategorySummary,
    DebtTimeRange,
)
from app.modules.personal_finance.debt.service import (
    compute_category_summary,
    compute_dashboard_summary,
)

router = APIRouter(prefix="/debt", tags=["debt"])


@router.get("/dashboard-summary", response_model=ModuleDashboardSummary)
async def dashboard_summary_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    date_from: Annotated[
        date | None,
        Query(description="Inicio del rango; con `date_to`, deuda viva al cierre del período."),
    ] = None,
    date_to: Annotated[
        date | None,
        Query(description="Fin del rango; con `date_from`, deuda viva al cierre del período."),
    ] = None,
) -> ModuleDashboardSummary:
    """PHASE-43.4 — tarjeta del módulo Deuda para el dashboard (deuda viva +
    esfuerzo + veredicto). ADR-0006. La deuda viva es period-scoped si se pasa
    `date_from`/`date_to` (al cierre del período), como el Patrimonio Neto."""
    return await compute_dashboard_summary(
        db,
        user.id,
        target_currency=target_currency,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/category-summary", response_model=DebtCategorySummary)
async def category_summary_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    range: Annotated[DebtTimeRange, Query()] = "year",
    anchor: Annotated[
        date | None,
        Query(
            description=(
                "Cualquier día (YYYY-MM-DD) dentro del período a mostrar. "
                "La granularidad la fija `range`; `anchor` decide CUÁL "
                "mes/año. Si se omite, el período en curso. Se ignora con "
                "`range=custom`."
            ),
        ),
    ] = None,
    date_from: Annotated[
        date | None,
        Query(description="Inicio del rango libre (obligatorio con `range=custom`)."),
    ] = None,
    date_to: Annotated[
        date | None,
        Query(description="Fin del rango libre (obligatorio con `range=custom`)."),
    ] = None,
    target_currency: Annotated[
        str | None,
        Query(
            min_length=3,
            max_length=3,
            description=(
                "ISO 4217 a la que convertir todos los importes "
                "(per-tx, igual que dashboard). Si se omite, devuelve "
                "los importes en la moneda nativa del usuario."
            ),
        ),
    ] = None,
) -> DebtCategorySummary:
    """Capa 1 del módulo deuda: KPIs derivados del flujo de
    categorías marcadas como deuda (PHASE-30.2).

    No requiere liability accounts — basta con que el usuario
    categorice sus pagos. Los liability accounts existentes se
    integran como capa de detalle vía `/accounts/debt-health` y la
    capa 2 de la UI.

    PHASE-30.6: el parámetro `target_currency` activa el modo
    cross-currency idéntico al del dashboard — cada tx se convierte
    con la tasa de su `occurred_at`. Txs sin tasa quedan excluidas
    silenciosamente.
    """
    if range == "custom":
        if date_from is None or date_to is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="range=custom requiere date_from y date_to.",
            )
        if date_from > date_to:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="date_from no puede ser posterior a date_to.",
            )
    return await compute_category_summary(
        db,
        user.id,
        range_=range,
        anchor=anchor,
        date_from=date_from,
        date_to=date_to,
        target_currency=target_currency,
    )
