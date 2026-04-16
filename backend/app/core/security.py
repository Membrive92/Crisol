"""Funciones de seguridad: hashing de passwords y JWT.

Vive en core/ porque lo usan tanto el módulo auth como deps.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import argon2
import jwt

from app.core.config import settings

_password_hasher = argon2.PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
)

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hashea un password con argon2id."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica un password contra su hash argon2id."""
    try:
        return _password_hasher.verify(password_hash, password)
    except argon2.exceptions.VerifyMismatchError:
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    """Crea un JWT access token de corta duración."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, datetime]:
    """Crea un refresh token opaco (UUID) y su fecha de expiración.

    Retorna (token_plaintext, expires_at). El caller es responsable de
    hashear el token antes de persistirlo en BD.
    """
    token = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    return token, expires_at


def hash_refresh_token(token: str) -> str:
    """Hashea un refresh token para almacenarlo en BD.

    Usa argon2id igual que los passwords — un refresh token es un secreto.
    """
    return _password_hasher.hash(token)


def verify_refresh_token(token: str, token_hash: str) -> bool:
    """Verifica un refresh token contra su hash almacenado."""
    try:
        return _password_hasher.verify(token_hash, token)
    except argon2.exceptions.VerifyMismatchError:
        return False


def decode_access_token(token: str) -> dict[str, object]:
    """Decodifica y valida un JWT access token.

    Raises:
        jwt.InvalidTokenError: si el token es inválido o expirado.
    """
    payload: dict[str, object] = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[JWT_ALGORITHM],
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload
