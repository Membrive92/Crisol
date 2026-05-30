"""Lógica de negocio de WebAuthn / Passkeys.

Encapsula `py_webauthn` para que el router no toque la librería directamente.
Los flujos son cuatro: register-options, register-verify, authenticate-options
y authenticate-verify.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.exceptions import (
    InvalidAuthenticationResponse,
    InvalidRegistrationResponse,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.core.config import settings
from app.modules.auth.webauthn.models import WebAuthnChallenge, WebAuthnCredential
from app.modules.auth.webauthn.repository import (
    consume_authentication_challenge,
    consume_challenge,
    create_challenge,
    create_credential,
    get_credential_by_credential_id,
    list_user_credentials,
)
from app.modules.users.models import User
from app.modules.users.repository import get_user_by_email, get_user_by_id

PURPOSE_REGISTER = "register"
PURPOSE_AUTHENTICATE = "authenticate"


# ─────────────────────────────────────────────────────────────────────────────
# Registro (usuario logueado)
# ─────────────────────────────────────────────────────────────────────────────


async def build_registration_options(db: AsyncSession, user: User) -> dict[str, Any]:
    """Genera las options para `navigator.credentials.create` y persiste el challenge.

    Excluye las credenciales ya registradas del usuario para evitar
    re-registros del mismo dispositivo.
    """
    existing = await list_user_credentials(db, user.id)
    exclude_credentials = [PublicKeyCredentialDescriptor(id=c.credential_id) for c in existing]

    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=str(user.id).encode("utf-8"),
        user_name=user.email,
        user_display_name=user.display_name,
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )

    await _persist_challenge(
        db,
        user_id=user.id,
        challenge=options.challenge,
        purpose=PURPOSE_REGISTER,
    )

    return cast(dict[str, Any], json.loads(options_to_json(options)))


async def verify_and_store_credential(
    db: AsyncSession,
    user: User,
    *,
    credential: dict[str, Any],
    label: str | None,
) -> WebAuthnCredential:
    """Verifica la attestation devuelta por el navegador y guarda la credencial."""
    pending = await consume_challenge(db, user_id=user.id, purpose=PURPOSE_REGISTER)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Challenge de registro inválido o expirado",
        )

    try:
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=pending.challenge,
            expected_origin=settings.webauthn_origin,
            expected_rp_id=settings.webauthn_rp_id,
        )
    except InvalidRegistrationResponse as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registro de passkey inválido: {e}",
        ) from e

    transports_csv = _extract_transports(credential)

    record = WebAuthnCredential(
        user_id=user.id,
        credential_id=verification.credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        transports=transports_csv,
        label=label,
    )
    return await create_credential(db, record)


# ─────────────────────────────────────────────────────────────────────────────
# Autenticación (usuario NO logueado)
# ─────────────────────────────────────────────────────────────────────────────


async def build_authentication_options(
    db: AsyncSession, email: str | None = None
) -> dict[str, Any]:
    """Genera las options para `navigator.credentials.get`.

    Dos modos:
    - **Email-driven**: el cliente conoce el email; el backend incluye
      `allowCredentials` con las credenciales del usuario. Este es el
      flujo "Entrar con passkey" del botón.
    - **Discoverable / Conditional UI**: sin email, `allowCredentials`
      vacío, challenge guardado con `user_id=NULL`. El navegador ofrece
      passkeys en el autocompletado del input email; el usuario elige
      una y al verificar identificamos al usuario por `credential_id`.
    """
    user_id_for_challenge: uuid.UUID | None = None
    allow_credentials: list[PublicKeyCredentialDescriptor] | None = None

    if email is not None:
        user = await get_user_by_email(db, email)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No hay passkeys registradas para esta cuenta",
            )
        credentials = await list_user_credentials(db, user.id)
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No hay passkeys registradas para esta cuenta",
            )
        allow_credentials = [PublicKeyCredentialDescriptor(id=c.credential_id) for c in credentials]
        user_id_for_challenge = user.id

    options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    await _persist_challenge(
        db,
        user_id=user_id_for_challenge,
        challenge=options.challenge,
        purpose=PURPOSE_AUTHENTICATE,
    )

    return cast(dict[str, Any], json.loads(options_to_json(options)))


async def verify_authentication_and_get_user(
    db: AsyncSession,
    *,
    email: str | None,
    credential: dict[str, Any],
) -> User:
    """Verifica la assertion y devuelve el usuario autenticado.

    Funciona en dos modos:
    - Si `email` viene → flujo email-driven (el del botón "Entrar con
      passkey"). Validamos además que la credencial recibida pertenezca
      al usuario del email (defensa en profundidad).
    - Si `email` es None → flujo Conditional UI: el usuario sale de
      `credential_id`. Es seguro porque la firma sólo verifica si la
      `public_key` y la cuenta de firmas casan con la BD.

    Actualiza `sign_count` y `last_used_at` de la credencial usada.
    """
    raw_id = credential.get("rawId") or credential.get("id")
    if not isinstance(raw_id, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credential malformada",
        )
    credential_id_bytes = _decode_base64url(raw_id)

    stored = await get_credential_by_credential_id(db, credential_id_bytes)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencial desconocida",
        )

    user = await get_user_by_id(db, stored.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario asociado a la credencial no existe",
        )

    if email is not None and email.lower() != user.email.lower():
        # El cliente dijo un email pero la credencial es de otro usuario.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencial no coincide con la cuenta",
        )

    pending = await consume_authentication_challenge(db, user_id=user.id)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Challenge inválido o expirado",
        )

    try:
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=pending.challenge,
            expected_origin=settings.webauthn_origin,
            expected_rp_id=settings.webauthn_rp_id,
            credential_public_key=stored.public_key,
            credential_current_sign_count=stored.sign_count,
        )
    except InvalidAuthenticationResponse as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Autenticación inválida: {e}",
        ) from e

    stored.sign_count = verification.new_sign_count
    stored.last_used_at = datetime.now(UTC)
    await db.flush()

    return user


# ─────────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────────


async def _persist_challenge(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    challenge: bytes,
    purpose: str,
) -> None:
    record = WebAuthnChallenge(
        user_id=user_id,
        challenge=challenge,
        purpose=purpose,
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.webauthn_challenge_ttl_seconds),
    )
    await create_challenge(db, record)


def _extract_transports(credential: dict[str, Any]) -> str | None:
    """Extrae el array de transports del attestation response a CSV."""
    response = credential.get("response", {})
    if not isinstance(response, dict):
        return None
    transports = response.get("transports")
    if not isinstance(transports, list):
        return None
    cleaned = [t for t in transports if isinstance(t, str) and t]
    return ",".join(cleaned) if cleaned else None


def _decode_base64url(value: str) -> bytes:
    """Decodifica un string base64url (con o sin padding) a bytes."""
    import base64

    pad = (-len(value)) % 4
    return base64.urlsafe_b64decode(value + ("=" * pad))
