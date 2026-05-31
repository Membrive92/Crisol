"""Router del submódulo WebAuthn / Passkeys."""

from __future__ import annotations

import base64
import uuid
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.rate_limit import rate_limit
from app.modules.auth.schemas import TokenResponse
from app.modules.auth.service import _issue_tokens
from app.modules.auth.webauthn.repository import (
    delete_credential,
    get_user_credential,
    list_user_credentials,
)
from app.modules.auth.webauthn.schemas import (
    PasskeyAuthenticationOptionsRequest,
    PasskeyAuthenticationOptionsResponse,
    PasskeyAuthenticationVerifyRequest,
    PasskeyRegistrationOptionsResponse,
    PasskeyRegistrationVerifyRequest,
    PasskeyRelabelRequest,
    PasskeyResponse,
)
from app.modules.auth.webauthn.service import (
    build_authentication_options,
    build_registration_options,
    verify_and_store_credential,
    verify_authentication_and_get_user,
)

router = APIRouter(prefix="/auth/webauthn", tags=["auth"])


def _set_refresh_cookie(response: Response, refresh_token: str, ttl_days: int) -> None:
    """Setea la cookie httpOnly. Replica la del router auth principal — la
    duplicamos aquí para no crear una dependencia entre módulos hermanos.
    Si crece más, mover a `core/cookies.py`."""
    samesite = cast(Literal["lax", "strict", "none"], settings.auth_cookie_samesite.lower())
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=refresh_token,
        max_age=ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=samesite,
        path="/",
    )


@router.post(
    "/register-options",
    response_model=PasskeyRegistrationOptionsResponse,
)
async def register_options_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PasskeyRegistrationOptionsResponse:
    """Devuelve las opciones para que el navegador cree una passkey.

    El usuario debe estar autenticado (con password o sesión activa). El
    flujo típico: el frontend llama tras el login para registrar el
    dispositivo actual como passkey de futuro.
    """
    options = await build_registration_options(db, user)
    await db.commit()
    return PasskeyRegistrationOptionsResponse(options=options)


@router.post(
    "/register-verify",
    response_model=PasskeyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_verify_endpoint(
    body: PasskeyRegistrationVerifyRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PasskeyResponse:
    """Verifica la attestation devuelta por el navegador y persiste la passkey."""
    record = await verify_and_store_credential(
        db, user, credential=body.credential, label=body.label
    )
    await db.commit()
    return PasskeyResponse(
        id=str(record.id),
        label=record.label,
        transports=record.transports,
        created_at=record.created_at.isoformat(),
        last_used_at=None,
    )


@router.post(
    "/authenticate-options",
    response_model=PasskeyAuthenticationOptionsResponse,
    dependencies=[Depends(rate_limit(10, 60))],
)
async def authenticate_options_endpoint(
    body: PasskeyAuthenticationOptionsRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PasskeyAuthenticationOptionsResponse:
    """Genera options para autenticación. No requiere auth previa."""
    options = await build_authentication_options(db, body.email)
    await db.commit()
    return PasskeyAuthenticationOptionsResponse(options=options)


@router.post(
    "/authenticate-verify",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(20, 60))],
)
async def authenticate_verify_endpoint(
    body: PasskeyAuthenticationVerifyRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    _refresh_cookie: Annotated[str | None, Cookie(alias=settings.auth_cookie_name)] = None,
) -> TokenResponse:
    """Verifica la assertion y emite los tokens normales (access + refresh).

    El refresh token y la cookie usan el TTL default — si el usuario quiere
    "Recordarme 30 días" puede marcarlo en login normal; passkey ya implica
    confianza en el dispositivo, así que el TTL extendido se podría aplicar
    aquí también, pero se deja conservador hasta que tengamos UX explícita.
    """
    user = await verify_authentication_and_get_user(
        db, email=body.email, credential=body.credential
    )
    session = await _issue_tokens(db, user)
    await db.commit()
    _set_refresh_cookie(response, session.tokens.refresh_token, session.refresh_ttl_days)
    return session.tokens


@router.get("", response_model=list[PasskeyResponse])
async def list_passkeys_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PasskeyResponse]:
    """Lista las passkeys del usuario para que pueda gestionarlas."""
    items = await list_user_credentials(db, user.id)
    return [
        PasskeyResponse(
            id=str(c.id),
            label=c.label,
            transports=c.transports,
            created_at=c.created_at.isoformat(),
            last_used_at=c.last_used_at.isoformat() if c.last_used_at else None,
        )
        for c in items
    ]


@router.patch("/{credential_id}", response_model=PasskeyResponse)
async def relabel_passkey_endpoint(
    credential_id: uuid.UUID,
    body: PasskeyRelabelRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PasskeyResponse:
    """Renombra la etiqueta de una passkey del usuario."""
    record = await get_user_credential(db, user_id=user.id, credential_pk=credential_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Passkey no encontrada")
    record.label = body.label.strip()
    await db.flush()
    await db.refresh(record)
    await db.commit()
    return PasskeyResponse(
        id=str(record.id),
        label=record.label,
        transports=record.transports,
        created_at=record.created_at.isoformat(),
        last_used_at=record.last_used_at.isoformat() if record.last_used_at else None,
    )


@router.delete("/{credential_id}", status_code=204, response_class=Response)
async def delete_passkey_endpoint(
    credential_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Elimina una passkey del usuario."""
    deleted = await delete_credential(db, user_id=user.id, credential_pk=credential_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Passkey no encontrada")
    await db.commit()
    return Response(status_code=204)


# Re-export para que mypy no se queje del helper privado importado del padre.
__all__ = ["router"]
_ = base64  # imported pero no usado directamente; mantener si añadimos algo
