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
    """Body para `/authenticate-options`.

    `email` es opcional: si no viene, el flow es Conditional UI y el
    navegador descubrirá la credencial mediante autocompletado.
    """

    email: EmailStr | None = None


class PasskeyAuthenticationOptionsResponse(BaseModel):
    """Opciones para navigator.credentials.get."""

    options: dict[str, Any]


class PasskeyAuthenticationVerifyRequest(BaseModel):
    """El navegador devuelve la assertion tras firmar el challenge.

    `email` es opcional; en el flow Conditional UI no lo conocemos hasta
    que la credencial se identifica.
    """

    email: EmailStr | None = None
    credential: dict[str, Any]


class PasskeyRelabelRequest(BaseModel):
    """Renombrar la etiqueta de una passkey existente."""

    label: str = Field(min_length=1, max_length=100)


class PasskeyResponse(BaseModel):
    """Vista pública de una credencial registrada por el usuario."""

    id: str
    label: str | None
    transports: str | None
    created_at: str
    last_used_at: str | None
