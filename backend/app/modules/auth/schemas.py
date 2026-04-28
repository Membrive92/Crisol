"""Schemas Pydantic del módulo auth."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Datos de registro de un nuevo usuario."""

    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    """Credenciales de login.

    `remember_me` extiende el TTL del refresh token (y la cookie en web)
    al valor de `jwt_refresh_token_remember_me_expire_days`. Útil para
    "Recordarme 30 días". Default `False`.
    """

    email: EmailStr
    password: str
    remember_me: bool = False


class RefreshRequest(BaseModel):
    """Petición de refresh de token.

    `refresh_token` es opcional: si la petición trae cookie `finanzas_refresh`
    (flujo web), no hace falta. Mobile envía el token en el body.
    """

    refresh_token: str | None = None


class TokenResponse(BaseModel):
    """Respuesta con tokens de acceso y refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
