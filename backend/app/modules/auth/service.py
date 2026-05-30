"""Lógica de negocio del módulo auth."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
    verify_refresh_token,
)
from app.modules.auth.models import RefreshToken
from app.modules.auth.repository import (
    create_refresh_token as persist_refresh_token,
)
from app.modules.auth.repository import (
    revoke_all_user_tokens,
    revoke_token,
)
from app.modules.auth.schemas import TokenResponse
from app.modules.users.models import User
from app.modules.users.repository import create_user, get_user_by_email


@dataclass(frozen=True, slots=True)
class IssuedSession:
    """Resultado de un login/register/refresh: tokens + TTL del refresh.

    El router usa `tokens` para serializar la respuesta y `refresh_ttl_days`
    para fijar el `Max-Age` de la cookie httpOnly. Se mantienen separados
    para que `TokenResponse` (DTO público) no exponga detalles internos.
    """

    tokens: TokenResponse
    refresh_ttl_days: int


async def register(
    db: AsyncSession,
    email: str,
    password: str,
    display_name: str,
) -> IssuedSession:
    """Registra un nuevo usuario y devuelve tokens + TTL del refresh.

    Raises:
        HTTPException 409: si el email ya está registrado.
    """
    existing = await get_user_by_email(db, email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya está registrado",
        )

    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
    )
    user = await create_user(db, user)
    return await _issue_tokens(db, user)


async def login(
    db: AsyncSession,
    email: str,
    password: str,
    *,
    remember_me: bool = False,
) -> IssuedSession:
    """Autentica un usuario por email/password y devuelve tokens + TTL.

    Si `remember_me=True`, el refresh token (y la cookie en web) se emite
    con el TTL extendido configurado en settings.

    Raises:
        HTTPException 401: si las credenciales son incorrectas.
    """
    user = await get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cuenta desactivada",
        )

    ttl_days = (
        settings.jwt_refresh_token_remember_me_expire_days
        if remember_me
        else settings.jwt_refresh_token_expire_days
    )
    return await _issue_tokens(db, user, ttl_days=ttl_days)


async def refresh(
    db: AsyncSession,
    refresh_token_plain: str,
) -> IssuedSession:
    """Rota un refresh token: revoca el viejo, emite uno nuevo.

    Preserva el "remember_me-ness" del token original: si se emitió con TTL
    extendido (>= remember_me_days), el rotado también, así un usuario que
    pidió 30 días no se degrada a 7 al primer refresh.

    Raises:
        HTTPException 401: si el refresh token es inválido, revocado o expirado.
    """
    active_tokens = await _find_matching_token(db, refresh_token_plain)
    if active_tokens is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o revocado",
        )

    token_record, user_id = active_tokens

    if token_record.expires_at < datetime.now(UTC):
        await revoke_token(db, token_record.id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expirado",
        )

    original_ttl_days = (token_record.expires_at - token_record.created_at).days
    ttl_days = (
        settings.jwt_refresh_token_remember_me_expire_days
        if original_ttl_days >= settings.jwt_refresh_token_remember_me_expire_days
        else settings.jwt_refresh_token_expire_days
    )

    await revoke_token(db, token_record.id)

    access = create_access_token(user_id)
    new_plain, expires_at = create_refresh_token(user_id, ttl_days=ttl_days)
    new_record = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(new_plain),
        expires_at=expires_at,
    )
    await persist_refresh_token(db, new_record)

    tokens = TokenResponse(access_token=access, refresh_token=new_plain)
    return IssuedSession(tokens=tokens, refresh_ttl_days=ttl_days)


async def logout(db: AsyncSession, refresh_token_plain: str) -> None:
    """Revoca el refresh token proporcionado.

    Raises:
        HTTPException 401: si el token no es válido.
    """
    match = await _find_matching_token(db, refresh_token_plain)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido",
        )
    token_record, _ = match
    await revoke_token(db, token_record.id)


async def logout_all(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoca TODOS los refresh tokens del usuario."""
    await revoke_all_user_tokens(db, user_id)


async def _issue_tokens(
    db: AsyncSession, user: User, *, ttl_days: int | None = None
) -> IssuedSession:
    """Emite un par access + refresh token para el usuario."""
    effective_ttl = ttl_days if ttl_days is not None else settings.jwt_refresh_token_expire_days
    access = create_access_token(user.id)
    plain, expires_at = create_refresh_token(user.id, ttl_days=effective_ttl)
    record = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(plain),
        expires_at=expires_at,
    )
    await persist_refresh_token(db, record)
    tokens = TokenResponse(access_token=access, refresh_token=plain)
    return IssuedSession(tokens=tokens, refresh_ttl_days=effective_ttl)


async def _find_matching_token(
    db: AsyncSession, plain: str
) -> tuple[RefreshToken, uuid.UUID] | None:
    """Busca entre los tokens activos uno que matchee el plaintext."""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.revoked.is_(False),
        )
    )
    for token_record in result.scalars():
        if verify_refresh_token(plain, token_record.token_hash):
            return token_record, token_record.user_id
    return None
