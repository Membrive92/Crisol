"""Lógica de negocio del módulo subscriptions (PHASE-13.1)."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.subscriptions import detector
from app.modules.personal_finance.subscriptions.models import (
    Subscription,
    SubscriptionStatus,
)
from app.modules.personal_finance.subscriptions.repository import (
    create_subscription as persist_subscription,
)
from app.modules.personal_finance.subscriptions.repository import (
    delete_subscription as remove_subscription,
)
from app.modules.personal_finance.subscriptions.repository import (
    find_by_fingerprint,
    get_subscription_by_id,
)
from app.modules.personal_finance.subscriptions.repository import (
    list_subscriptions as list_in_db,
)
from app.modules.personal_finance.subscriptions.schemas import ScanResponse


async def list_subscriptions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: SubscriptionStatus | None = None,
) -> list[Subscription]:
    """Lista del usuario, ordenada por `next_due`."""
    return await list_in_db(db, user_id, status=status)


async def get_subscription(
    db: AsyncSession, subscription_id: uuid.UUID, user_id: uuid.UUID
) -> Subscription:
    """Obtiene una subscripción o 404."""
    sub = await get_subscription_by_id(db, subscription_id, user_id)
    if sub is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Subscripción no encontrada",
        )
    return sub


async def confirm_subscription(
    db: AsyncSession, subscription_id: uuid.UUID, user_id: uuid.UUID
) -> Subscription:
    """`pending` → `confirmed`."""
    sub = await get_subscription(db, subscription_id, user_id)
    if sub.status == SubscriptionStatus.DISMISSED:
        # Confirmar una dismissed la reactiva — útil si el usuario se
        # arrepintió. Pasa por pending como audit trail mínimo.
        sub.status = SubscriptionStatus.PENDING
    sub.status = SubscriptionStatus.CONFIRMED
    await db.flush()
    await db.refresh(sub)
    return sub


async def dismiss_subscription(
    db: AsyncSession, subscription_id: uuid.UUID, user_id: uuid.UUID
) -> Subscription:
    """Marca como dismissed; el detector NO la volverá a sugerir."""
    sub = await get_subscription(db, subscription_id, user_id)
    sub.status = SubscriptionStatus.DISMISSED
    await db.flush()
    await db.refresh(sub)
    return sub


async def delete_subscription(
    db: AsyncSession, subscription_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Borra permanente. Una subscripción borrada y luego re-detectada
    en el siguiente scan re-aparecerá como `pending` — coherente con
    "borrar = empezar de cero".
    """
    sub = await get_subscription(db, subscription_id, user_id)
    await remove_subscription(db, sub)


async def scan_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> ScanResponse:
    """Ejecuta el detector y persiste/refresca subscripciones.

    Política:
    - Patrones que ya tienen un row (mismo fingerprint): se refrescan
      `last_seen_at`, `next_due`, `occurrence_count` y `confidence`.
      `status` y `category_id` NO se tocan — respetan la decisión del
      usuario.
    - Patrones nuevos sin fingerprint match: se crean como `pending`.
    - Patrones que matchean a una subscripción `dismissed`: NO se
      crean fila nueva (la `dismissed` ya existe; sólo se refresca).
      Resultado: el usuario que descartó algo no lo vuelve a ver.
    """
    candidates = await detector.detect_for_user(db, user_id)

    created = 0
    updated = 0
    for cand in candidates:
        existing = await find_by_fingerprint(
            db,
            user_id,
            merchant=cand.merchant,
            amount=cand.amount,
            currency=cand.currency,
            cadence_days=cand.cadence_days,
        )
        if existing is not None:
            existing.last_seen_at = cand.last_seen_at
            existing.next_due = cand.next_due
            existing.occurrence_count = cand.occurrence_count
            existing.confidence = cand.confidence
            existing.raw_description = cand.raw_description
            updated += 1
        else:
            sub = Subscription(
                user_id=user_id,
                merchant=cand.merchant,
                raw_description=cand.raw_description,
                amount=cand.amount,
                currency=cand.currency,
                cadence_days=cand.cadence_days,
                next_due=cand.next_due,
                status=SubscriptionStatus.PENDING,
                category_id=cand.category_id,
                first_seen_at=cand.first_seen_at,
                last_seen_at=cand.last_seen_at,
                occurrence_count=cand.occurrence_count,
                confidence=cand.confidence,
            )
            await persist_subscription(db, sub)
            created += 1

    await db.flush()

    # Activas = todo lo que no esté dismissed (pending + confirmed).
    pending = await list_in_db(db, user_id, status=SubscriptionStatus.PENDING)
    confirmed = await list_in_db(db, user_id, status=SubscriptionStatus.CONFIRMED)
    return ScanResponse(
        created=created,
        updated=updated,
        total_active_after=len(pending) + len(confirmed),
    )
