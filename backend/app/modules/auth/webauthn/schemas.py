"""Schemas Pydantic del módulo WebAuthn.

Los tipos de los `options` y `credential` se mantienen como `dict[str, Any]`
porque son objetos definidos por la spec de WebAuthn (no por nosotros) y la
librería `webauthn` ya los serializa correctamente. Validar campo a campo
sería duplicar trabajo.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, EmailStr, Field


class PasskeyRegistrationOptionsResponse(BaseModel):
    """Opciones para que el navegador llame a navigator.credentials.create."""

    options: dict[str, Any]


class PasskeyRegistrationVerifyRequest(BaseModel):
    """El navegador devuelve la attestation tras crear la credencial."""

    credential: dict[str, Any]
    label: str | None = Field(default=None, max_length=100)


class PasskeyAuthenticationOptionsRequest(BaseModel):
    """Para arrancar el flujo el cliente nos dice qué email autentica."""

    email: EmailStr


class PasskeyAuthenticationOptionsResponse(BaseModel):
    """Opciones para navigator.credentials.get."""

    options: dict[str, Any]


class PasskeyAuthenticationVerifyRequest(BaseModel):
    """El navegador devuelve la assertion tras firmar el challenge."""

    email: EmailStr
    credential: dict[str, Any]


class PasskeyResponse(BaseModel):
    """Vista pública de una credencial registrada por el usuario."""

    id: str
    label: str | None
    transports: str | None
    created_at: str
    last_used_at: str | None
