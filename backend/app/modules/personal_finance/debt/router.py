"""Router del módulo deuda (PHASE-30.2, cross-currency en PHASE-30.6)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.debt.schemas import (
    DebtCategorySummary,
    DebtTimeRange,
)
from app.modules.personal_finance.debt.service import compute_category_summary

router = APIRouter(prefix="/debt", tags=["debt"])


@router.get("/category-summary", response_model=DebtCategorySummary)
async def category_summary_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    range: Annotated[DebtTimeRange, Query()] = "ytd",
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
    return await compute_category_summary(
        db, user.id, range_=range, target_currency=target_currency
    )
