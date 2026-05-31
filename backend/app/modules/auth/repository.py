"""Queries a DB del módulo auth (refresh tokens)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import RefreshToken


async def create_refresh_token(db: AsyncSession, token: RefreshToken) -> RefreshToken:
    """Persiste un nuevo refresh token."""
    db.add(token)
    await db.flush()
    await db.refresh(token)
    return token


async def get_refresh_token_by_token_id(db: AsyncSession, token_id: str) -> RefreshToken | None:
    """Localiza un refresh token por su `token_id` público (AUDIT-2026-05).

    NO filtra por `revoked`: el caller necesita ver tokens revocados para
    detectar reutilización (replay) y contener el robo revocando la familia.
    """
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_id == token_id))
    return result.scalar_one_or_none()


async def get_refresh_token_by_id(db: AsyncSession, token_id: uuid.UUID) -> RefreshToken | None:
    """Obtiene un refresh token por PK (id)."""
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


async def revoke_family(db: AsyncSession, family_id: uuid.UUID) -> None:
    """Revoca todos los tokens de una familia (contención de robo cuando se
    detecta replay de un token revocado — AUDIT-2026-05)."""
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    await db.flush()


async def purge_expired_tokens(db: AsyncSession) -> int:
    """Borra los refresh tokens YA EXPIRADOS (acota el crecimiento de la
    tabla sin afectar a la detección de replay, que sólo necesita tokens
    revocados pero aún no expirados). Devuelve el nº de filas borradas."""
    result = await db.execute(
        delete(RefreshToken).where(RefreshToken.expires_at < datetime.now(UTC))
    )
    await db.flush()
    return result.rowcount or 0
