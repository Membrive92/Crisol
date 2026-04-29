"""Acceso a datos del módulo WebAuthn."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.webauthn.models import WebAuthnChallenge, WebAuthnCredential


async def create_challenge(
    db: AsyncSession, challenge: WebAuthnChallenge
) -> WebAuthnChallenge:
    db.add(challenge)
    await db.flush()
    await db.refresh(challenge)
    return challenge


async def consume_challenge(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    purpose: str,
) -> WebAuthnChallenge | None:
    """Devuelve el challenge más reciente para (user, purpose) y lo borra.

    Borrar en el mismo paso evita reutilización: si dos peticiones intentan
    consumirlo, sólo una lo encuentra. Si el challenge expiró, se ignora.
    """
    now = datetime.now(UTC)
    result = await db.execute(
        select(WebAuthnChallenge)
        .where(
            WebAuthnChallenge.user_id == user_id,
            WebAuthnChallenge.purpose == purpose,
            WebAuthnChallenge.expires_at > now,
        )
        .order_by(WebAuthnChallenge.created_at.desc())
        .limit(1)
    )
    challenge = result.scalar_one_or_none()
    if challenge is None:
        return None
    await db.execute(
        delete(WebAuthnChallenge).where(WebAuthnChallenge.id == challenge.id)
    )
    return challenge


async def delete_expired_challenges(db: AsyncSession) -> None:
    """Limpia challenges expirados — se puede llamar en startup u oportunidad."""
    now = datetime.now(UTC)
    await db.execute(
        delete(WebAuthnChallenge).where(WebAuthnChallenge.expires_at <= now)
    )


async def list_user_credentials(
    db: AsyncSession, user_id: uuid.UUID
) -> list[WebAuthnCredential]:
    result = await db.execute(
        select(WebAuthnCredential)
        .where(WebAuthnCredential.user_id == user_id)
        .order_by(WebAuthnCredential.created_at.desc())
    )
    return list(result.scalars().all())


async def get_credential_by_credential_id(
    db: AsyncSession, credential_id: bytes
) -> WebAuthnCredential | None:
    result = await db.execute(
        select(WebAuthnCredential).where(
            WebAuthnCredential.credential_id == credential_id
        )
    )
    return result.scalar_one_or_none()


async def create_credential(
    db: AsyncSession, credential: WebAuthnCredential
) -> WebAuthnCredential:
    db.add(credential)
    await db.flush()
    await db.refresh(credential)
    return credential


async def delete_credential(
    db: AsyncSession, *, user_id: uuid.UUID, credential_pk: uuid.UUID
) -> bool:
    """Borra una credencial concreta del usuario. Devuelve True si existía."""
    result = await db.execute(
        delete(WebAuthnCredential)
        .where(
            WebAuthnCredential.id == credential_pk,
            WebAuthnCredential.user_id == user_id,
        )
        .returning(WebAuthnCredential.id)
    )
    return result.scalar_one_or_none() is not None
