"""Lógica de negocio del módulo auth."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    parse_refresh_token_id,
    verify_password,
    verify_refresh_token,
)
from app.modules.auth.models import RefreshToken
from app.modules.auth.repository import (
    create_refresh_token as persist_refresh_token,
)
from app.modules.auth.repository import (
    get_refresh_token_by_token_id,
    revoke_family,
    revoke_token,
)
from app.modules.auth.schemas import TokenResponse
from app.modules.users.models import User
from app.modules.users.repository import create_user, get_user_by_email, normalize_email

# Hash argon2 "fantasma" precomputado: se verifica contra él cuando el email
# no existe, para que el login tarde lo mismo exista o no el usuario (mitiga
# enumeración por timing — AUDIT-2026-05).
_DUMMY_PASSWORD_HASH = hash_password("crisol-timing-equalizer-not-a-real-password")


def _absolute_session_days() -> int:
    """Vida ABSOLUTA de una sesión (familia de refresh tokens), en días.

    AUDIT-FIX (refresh-rotacion-sin-vida-absoluta-de-sesion): la rotación
    reinicia `expires_at` a `now + ttl` en cada uso → sesión deslizante que,
    con `remember_me`, nunca caduca mientras se use. Imponemos un límite duro
    medido desde el PRIMER login de la familia: pasado ese plazo el usuario
    debe re-autenticarse, refresque cuanto refresque.

    Configurable vía `AUTH_ABSOLUTE_SESSION_DAYS` (settings ignora env extra,
    así que no hace falta tocar `config.py`). Default: 3× el TTL extendido
    (90 días con los defaults) — holgado para no molestar a usuarios reales,
    pero acota un token robado a una ventana finita.
    """
    configured = getattr(settings, "auth_absolute_session_days", None)
    if isinstance(configured, int) and configured > 0:
        return configured
    return settings.jwt_refresh_token_remember_me_expire_days * 3


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
        email=normalize_email(email),
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
    if user is None:
        # Verify "fantasma" para igualar el tiempo con la rama de usuario
        # existente (anti-enumeración por timing — AUDIT-2026-05).
        verify_password(password, _DUMMY_PASSWORD_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )
    if not verify_password(password, user.password_hash):
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
    token_id = parse_refresh_token_id(refresh_token_plain)
    token_record = await get_refresh_token_by_token_id(db, token_id) if token_id else None
    if token_record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o revocado",
        )

    # Reuse detection (AUDIT-2026-05): un token YA revocado que se presenta
    # de nuevo es la señal clásica de robo (atacante y víctima ambos rotan).
    # Revocamos toda la familia para contener la brecha.
    if token_record.revoked:
        await revoke_family(db, token_record.family_id)
        # La contención de robo DEBE persistir aunque devolvamos 401: el
        # router sólo commitea tras un refresh exitoso, y aquí levantamos
        # excepción antes de llegar a ese commit (AUDIT-2026-05).
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reutilizado; sesión revocada por seguridad",
        )

    if token_record.expires_at < datetime.now(UTC):
        # AUDIT-FIX (refresh-revoke-expirado-se-revierte-por-falta-de-commit):
        # NO revocamos aquí. El chequeo de `expires_at` ya rechaza el token, y
        # `purge_expired_tokens` borra la fila por su cuenta. Antes se hacía un
        # `revoke_token` cuyo UPDATE el router NUNCA commitea (sólo commitea
        # tras un refresh exitoso), así que se revertía con un rollback
        # silencioso: un UPDATE inútil que además no persistía.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expirado",
        )

    # token_id coincide pero el secreto no → token forjado/corrupto.
    if not verify_refresh_token(refresh_token_plain, token_record.token_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o revocado",
        )

    user_id = token_record.user_id

    # AUDIT-FIX (refresh-rotacion-sin-vida-absoluta-de-sesion): límite duro
    # desde el PRIMER login de la familia. Como no hay columna `created_at`
    # heredada explícita, derivamos el origen de la sesión del `created_at`
    # más antiguo de la familia (el primer token, no rotado). Si la sesión ya
    # superó la vida absoluta, forzamos re-login revocando la familia entera.
    now = datetime.now(UTC)
    family_started_at = await _family_started_at(db, token_record.family_id)
    absolute_deadline = family_started_at + timedelta(days=_absolute_session_days())
    if now >= absolute_deadline:
        await revoke_family(db, token_record.family_id)
        # Igual que la rama de reuse: el router sólo commitea tras un refresh
        # exitoso, así que persistimos la revocación aquí antes del 401.
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión caducada por antigüedad; inicia sesión de nuevo",
        )

    original_ttl_days = (token_record.expires_at - token_record.created_at).days
    ttl_days = (
        settings.jwt_refresh_token_remember_me_expire_days
        if original_ttl_days >= settings.jwt_refresh_token_remember_me_expire_days
        else settings.jwt_refresh_token_expire_days
    )

    await revoke_token(db, token_record.id)

    access = create_access_token(user_id)
    new_plain, new_token_id, expires_at = create_refresh_token(ttl_days=ttl_days)
    # El nuevo token nunca vive más allá del límite absoluto de la sesión:
    # `expires_at = min(now + ttl, absolute_deadline)`.
    expires_at = min(expires_at, absolute_deadline)
    new_record = RefreshToken(
        user_id=user_id,
        token_id=new_token_id,
        token_hash=hash_refresh_token(new_plain),
        family_id=token_record.family_id,  # preserva el linaje
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
    token_id = parse_refresh_token_id(refresh_token_plain)
    token_record = await get_refresh_token_by_token_id(db, token_id) if token_id else None
    if token_record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido",
        )
    # AUDIT-2026-05: verifica el SECRETO, no sólo el `token_id` (que es
    # público/indexado). Sin esto, conocer el token_id bastaría para
    # revocar la sesión de cualquiera (mismo verify que hace `refresh`).
    if not verify_refresh_token(refresh_token_plain, token_record.token_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido",
        )
    await revoke_token(db, token_record.id)


async def _issue_tokens(
    db: AsyncSession, user: User, *, ttl_days: int | None = None
) -> IssuedSession:
    """Emite un par access + refresh token para el usuario (nueva familia)."""
    effective_ttl = ttl_days if ttl_days is not None else settings.jwt_refresh_token_expire_days
    access = create_access_token(user.id)
    plain, token_id, expires_at = create_refresh_token(ttl_days=effective_ttl)
    record = RefreshToken(
        user_id=user.id,
        token_id=token_id,
        token_hash=hash_refresh_token(plain),
        family_id=uuid.uuid4(),
        expires_at=expires_at,
    )
    await persist_refresh_token(db, record)
    tokens = TokenResponse(access_token=access, refresh_token=plain)
    return IssuedSession(tokens=tokens, refresh_ttl_days=effective_ttl)


async def _family_started_at(db: AsyncSession, family_id: uuid.UUID) -> datetime:
    """Momento del PRIMER login de una familia de refresh tokens.

    AUDIT-FIX (vida absoluta de sesión): es el `created_at` más antiguo de la
    familia — el token original emitido en login/register, antes de cualquier
    rotación. Se usa como ancla para el límite de vida absoluta de la sesión.

    Si la familia no tuviera filas (caso degenerado), se cae a `now` para no
    revocar de forma agresiva por un dato ausente.
    """
    result = await db.execute(
        select(func.min(RefreshToken.created_at)).where(RefreshToken.family_id == family_id)
    )
    started_at: datetime | None = result.scalar_one_or_none()
    if started_at is None:
        return datetime.now(UTC)
    # `created_at` es TIMESTAMPTZ → SQLAlchemy lo devuelve tz-aware; pero por
    # robustez (algunos drivers/SQLite-en-memoria devuelven naive), forzamos
    # UTC para que la resta con `datetime.now(UTC)` no lance TypeError.
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    return started_at
