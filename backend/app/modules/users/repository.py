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
