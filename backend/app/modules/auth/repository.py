"""Queries a DB del módulo auth (refresh tokens)."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import RefreshToken


async def create_refresh_token(db: AsyncSession, token: RefreshToken) -> RefreshToken:
    """Persiste un nuevo refresh token."""
    db.add(token)
    await db.flush()
    await db.refresh(token)
    return token


async def get_refresh_token_by_id(db: AsyncSession, token_id: uuid.UUID) -> RefreshToken | None:
    """Obtiene un refresh token por ID."""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.id == token_id,
            RefreshToken.revoked.is_(False),
        )
    )
    return result.scalar_one_or_none()


async def get_active_tokens_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[RefreshToken]:
    """Obtiene todos los refresh tokens activos de un usuario."""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked.is_(False),
        )
    )
    return list(result.scalars().all())


async def revoke_token(db: AsyncSession, token_id: uuid.UUID) -> None:
    """Revoca un refresh token por su ID."""
    await db.execute(update(RefreshToken).where(RefreshToken.id == token_id).values(revoked=True))
    await db.flush()


async def revoke_all_user_tokens(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoca TODOS los refresh tokens de un usuario (logout de todos los dispositivos)."""
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    await db.flush()
