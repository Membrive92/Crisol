"""Router del módulo deuda (PHASE-30.2, cross-currency en PHASE-30.6)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.accounts.models import Account
from app.modules.personal_finance.dashboard.schemas import ModuleDashboardSummary
from app.modules.personal_finance.debt.deferral import CycleSelection
from app.modules.personal_finance.debt.deferral_service import (
    apply_deferred_cycle,
    clear_deferred_cycle,
    has_declared_cycle,
    preview_deferred_cycle,
)
from app.modules.personal_finance.debt.schemas import (
    DebtCategorySummary,
    DebtTimeRange,
    DeferredCyclePreview,
    DeferredCyclePurchase,
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


# ── PHASE-47.E2 · el ciclo aplazado ──────────────────────────────────
#
# El sistema INICIA (propone el ciclo con su aritmética a la vista) y el usuario
# DECLARA (ADR-0011). Por eso son dos endpoints y no uno: el GET no escribe
# nada, y el POST sólo escribe lo que el GET ya había enseñado.


def _preview_response(
    liability: Account,
    card: Account | None,
    target: Decimal,
    selection: CycleSelection,
    *,
    already_declared: bool = False,
) -> DeferredCyclePreview:
    return DeferredCyclePreview(
        liability_id=liability.id,
        liability_name=liability.name,
        card_id=card.id if card is not None else None,
        card_name=card.name if card is not None else None,
        receipt_amount=target,
        currency=liability.currency,
        purchases=[
            DeferredCyclePurchase(
                id=p.id,
                occurred_at=p.occurred_at,
                amount=p.amount,
                description=p.description,
            )
            for p in selection.purchases
        ],
        total=selection.total,
        closes_exactly=selection.closes_exactly,
        already_declared=already_declared,
        reason=selection.reason,
    )


@router.get("/liabilities/{liability_id}/deferred-cycle", response_model=DeferredCyclePreview)
async def preview_deferred_cycle_endpoint(
    liability_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeferredCyclePreview:
    """Qué compras cubriría este aplazamiento. No escribe nada."""
    liability, card, target, selection = await preview_deferred_cycle(db, user.id, liability_id)
    declared = await has_declared_cycle(db, user.id, liability_id)
    return _preview_response(liability, card, target, selection, already_declared=declared)


@router.post("/liabilities/{liability_id}/deferred-cycle", response_model=DeferredCyclePreview)
async def apply_deferred_cycle_endpoint(
    liability_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeferredCyclePreview:
    """Marca las compras del ciclo como aplazadas por este recibo.

    409 si el ciclo no cierra al céntimo: sin el ciclo completo no hay nada que
    marcar con honestidad.
    """
    liability, card, target, selection = await apply_deferred_cycle(db, user.id, liability_id)
    await db.commit()
    return _preview_response(liability, card, target, selection, already_declared=True)


@router.delete("/liabilities/{liability_id}/deferred-cycle", status_code=204)
async def clear_deferred_cycle_endpoint(
    liability_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Retira la marca: las compras vuelven a contar como salida de caja."""
    await clear_deferred_cycle(db, user.id, liability_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
