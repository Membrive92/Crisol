"""Router del módulo fixed_expenses (PHASE-13.1, renombrado en
PHASE-17.1).

Path público: `/fixed-expenses` (kebab-case en URL, snake_case en
módulo Python — convención general FastAPI).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.fixed_expenses.models import FixedExpenseStatus
from app.modules.personal_finance.fixed_expenses.schemas import (
    FixedExpenseResponse,
    ScanResponse,
)
from app.modules.personal_finance.fixed_expenses.service import (
    cancel_fixed_expense,
    confirm_fixed_expense,
    delete_fixed_expense,
    dismiss_fixed_expense,
    get_fixed_expense,
    list_fixed_expenses,
    pause_fixed_expense,
    resume_fixed_expense,
    scan_for_user,
)

router = APIRouter(prefix="/fixed-expenses", tags=["fixed-expenses"])


@router.get("", response_model=list[FixedExpenseResponse])
async def list_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[FixedExpenseStatus | None, Query()] = None,
) -> list[FixedExpenseResponse]:
    """Lista los gastos fijos del usuario, opcionalmente filtrados
    por status (`pending|confirmed|paused|cancelled|dismissed`).
    """
    items = await list_fixed_expenses(db, user.id, status=status)
    return [FixedExpenseResponse.model_validate(s) for s in items]


@router.post("/scan", response_model=ScanResponse)
async def scan_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScanResponse:
    """Re-ejecuta el detector heurístico ahora.

    El cron nocturno (PHASE-13.1) hace lo mismo automáticamente; este
    endpoint permite al usuario forzar un re-scan tras importar /
    crear muchas transacciones.
    """
    result = await scan_for_user(db, user.id)
    await db.commit()
    return result


@router.get("/{fixed_expense_id}", response_model=FixedExpenseResponse)
async def get_endpoint(
    fixed_expense_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FixedExpenseResponse:
    """Obtiene un gasto fijo por ID."""
    item = await get_fixed_expense(db, fixed_expense_id, user.id)
    return FixedExpenseResponse.model_validate(item)


@router.post(
    "/{fixed_expense_id}/confirm", response_model=FixedExpenseResponse
)
async def confirm_endpoint(
    fixed_expense_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FixedExpenseResponse:
    """Marca como `confirmed`. Uno `dismissed` confirmado se reactiva."""
    item = await confirm_fixed_expense(db, fixed_expense_id, user.id)
    await db.commit()
    return FixedExpenseResponse.model_validate(item)


@router.post(
    "/{fixed_expense_id}/dismiss", response_model=FixedExpenseResponse
)
async def dismiss_endpoint(
    fixed_expense_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FixedExpenseResponse:
    """Marca como `dismissed`. El detector NO lo volverá a sugerir."""
    item = await dismiss_fixed_expense(db, fixed_expense_id, user.id)
    await db.commit()
    return FixedExpenseResponse.model_validate(item)


@router.post(
    "/{fixed_expense_id}/pause", response_model=FixedExpenseResponse
)
async def pause_endpoint(
    fixed_expense_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FixedExpenseResponse:
    """Pausa temporal — `confirmed` → `paused` (PHASE-15.2). 409
    desde cualquier otro estado."""
    item = await pause_fixed_expense(db, fixed_expense_id, user.id)
    await db.commit()
    return FixedExpenseResponse.model_validate(item)


@router.post(
    "/{fixed_expense_id}/resume", response_model=FixedExpenseResponse
)
async def resume_endpoint(
    fixed_expense_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FixedExpenseResponse:
    """Reanuda — `paused` → `confirmed` (PHASE-15.2). 409 si no
    está paused."""
    item = await resume_fixed_expense(db, fixed_expense_id, user.id)
    await db.commit()
    return FixedExpenseResponse.model_validate(item)


@router.post(
    "/{fixed_expense_id}/cancel", response_model=FixedExpenseResponse
)
async def cancel_endpoint(
    fixed_expense_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FixedExpenseResponse:
    """Marca como `cancelled` (PHASE-15.2). Aceptable desde
    pending/confirmed/paused. 409 desde dismissed."""
    item = await cancel_fixed_expense(db, fixed_expense_id, user.id)
    await db.commit()
    return FixedExpenseResponse.model_validate(item)


@router.delete(
    "/{fixed_expense_id}", status_code=204, response_class=Response
)
async def delete_endpoint(
    fixed_expense_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """DELETE real. Si el patrón sigue cumpliéndose en el siguiente
    scan, vuelve a aparecer como `pending`.
    """
    await delete_fixed_expense(db, fixed_expense_id, user.id)
    await db.commit()
    return Response(status_code=204)
