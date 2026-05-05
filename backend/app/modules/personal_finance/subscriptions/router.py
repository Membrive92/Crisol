"""Router del módulo subscriptions (PHASE-13.1)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.subscriptions.models import SubscriptionStatus
from app.modules.personal_finance.subscriptions.schemas import (
    ScanResponse,
    SubscriptionResponse,
)
from app.modules.personal_finance.subscriptions.service import (
    confirm_subscription,
    delete_subscription,
    dismiss_subscription,
    get_subscription,
    list_subscriptions,
    scan_for_user,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("", response_model=list[SubscriptionResponse])
async def list_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[SubscriptionStatus | None, Query()] = None,
) -> list[SubscriptionResponse]:
    """Lista las subscripciones del usuario, opcionalmente filtradas
    por status (`pending|confirmed|dismissed`).
    """
    items = await list_subscriptions(db, user.id, status=status)
    return [SubscriptionResponse.model_validate(s) for s in items]


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


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_endpoint(
    subscription_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionResponse:
    """Obtiene una subscripción por ID."""
    sub = await get_subscription(db, subscription_id, user.id)
    return SubscriptionResponse.model_validate(sub)


@router.post(
    "/{subscription_id}/confirm", response_model=SubscriptionResponse
)
async def confirm_endpoint(
    subscription_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionResponse:
    """Marca como `confirmed`. Una `dismissed` confirmada se reactiva."""
    sub = await confirm_subscription(db, subscription_id, user.id)
    await db.commit()
    return SubscriptionResponse.model_validate(sub)


@router.post(
    "/{subscription_id}/dismiss", response_model=SubscriptionResponse
)
async def dismiss_endpoint(
    subscription_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionResponse:
    """Marca como `dismissed`. El detector NO la volverá a sugerir."""
    sub = await dismiss_subscription(db, subscription_id, user.id)
    await db.commit()
    return SubscriptionResponse.model_validate(sub)


@router.delete(
    "/{subscription_id}", status_code=204, response_class=Response
)
async def delete_endpoint(
    subscription_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """DELETE real. Si el patrón sigue cumpliéndose en el siguiente
    scan, vuelve a aparecer como `pending`.
    """
    await delete_subscription(db, subscription_id, user.id)
    await db.commit()
    return Response(status_code=204)
