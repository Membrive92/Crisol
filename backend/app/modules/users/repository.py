"""Queries a DB del módulo users."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User


def normalize_email(email: str) -> str:
    """Normaliza un email para almacenamiento/lookup (AUDIT-2026-05): trim +
    lowercase. Evita cuentas duplicadas por casing (`User@x.com` vs
    `user@x.com`) y logins inconsistentes."""
    return email.strip().lower()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Obtiene un usuario por su ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Obtiene un usuario por su email (case-insensitive — AUDIT-2026-05).

    Compara con `lower(email)` para encontrar al usuario sea cual sea el
    casing almacenado, sin depender de una migración de datos previa.
    """
    result = await db.execute(
        select(User).where(func.lower(User.email) == normalize_email(email)).limit(1)
    )
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user: User) -> User:
    """Persiste un nuevo usuario."""
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(
    db: AsyncSession,
    user: User,
    *,
    cycle_start_day: int | None,
) -> User:
    """Actualiza las preferencias del usuario ya cargado y lo devuelve fresco.

    El `refresh` tras el `flush` no es cosmético: `updated_at` lleva
    `onupdate=func.now()`, así que tras el UPDATE el valor que calcula la BD no
    vuelve al objeto en memoria y el atributo queda *stale*. Serializarlo desde
    Pydantic (síncrono) dispararía un lazy load sobre una sesión async y
    reventaría con `MissingGreenlet` (lección PHASE-4.1).

    No hace lookup por `user_id`: recibe el `User` que `get_current_user` ya
    cargó en esta misma sesión, así que el aislamiento lo garantiza el token —
    no hay forma de nombrar a otro usuario en el body.
    """
    user.cycle_start_day = cycle_start_day
    await db.flush()
    await db.refresh(user)
    return user
