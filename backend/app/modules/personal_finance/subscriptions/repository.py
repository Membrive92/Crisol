"""Queries del módulo subscriptions (PHASE-13.1)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.subscriptions.models import (
    Subscription,
    SubscriptionStatus,
)


async def list_subscriptions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: SubscriptionStatus | None = None,
) -> list[Subscription]:
    """Lista las subscripciones del usuario, opcionalmente filtradas
    por status. Orden: `next_due ASC` para que la próxima ejecución
    quede arriba.
    """
    query = (
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.next_due.asc())
    )
    if status is not None:
        query = query.where(Subscription.status == status)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_subscription_by_id(
    db: AsyncSession, subscription_id: uuid.UUID, user_id: uuid.UUID
) -> Subscription | None:
    """Obtiene una subscripción por ID, scoped al user."""
    query = select(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.id == subscription_id,
    )
    return (await db.execute(query)).scalar_one_or_none()


async def find_by_fingerprint(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    merchant: str,
    amount: Decimal,
    currency: str,
    cadence_days: int,
) -> Subscription | None:
    """Busca una subscripción existente por su huella
    (merchant + amount + currency + cadence). Usado por el detector
    para refrescar datos en lugar de duplicar.
    """
    query = select(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.merchant == merchant,
        Subscription.amount == amount,
        Subscription.currency == currency,
        Subscription.cadence_days == cadence_days,
    )
    return (await db.execute(query)).scalar_one_or_none()


async def create_subscription(
    db: AsyncSession, subscription: Subscription
) -> Subscription:
    """Persiste una subscripción nueva."""
    db.add(subscription)
    await db.flush()
    await db.refresh(subscription)
    return subscription


async def delete_subscription(db: AsyncSession, subscription: Subscription) -> None:
    """DELETE real."""
    await db.delete(subscription)
    await db.flush()
