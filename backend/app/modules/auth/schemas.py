"""Schemas Pydantic del módulo auth."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Datos de registro de un nuevo usuario."""

    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    """Credenciales de login."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Petición de refresh de token."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Respuesta con tokens de acceso y refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
