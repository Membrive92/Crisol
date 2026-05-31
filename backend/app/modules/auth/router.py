"""Router del módulo auth."""

from __future__ import annotations

from typing import Annotated, Literal, cast

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.rate_limit import rate_limit
from app.modules.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.modules.auth.service import login, logout, refresh, register
from app.modules.users.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(
    response: Response, refresh_token: str, *, ttl_days: int | None = None
) -> None:
    """Setea la cookie httpOnly con el refresh token.

    `ttl_days` permite usar el TTL extendido cuando el cliente pide
    "Recordarme". Si no se pasa, se usa el default de settings.
    `httponly=True` la oculta de JS (XSS no puede leerla).
    """
    samesite = cast(Literal["lax", "strict", "none"], settings.auth_cookie_samesite.lower())
    days = ttl_days if ttl_days is not None else settings.jwt_refresh_token_expire_days
    # Path="/" para que la cookie viaje también cuando el frontend usa el
    # rewrite `/api/auth/...` de Next.js: la cookie la setea el browser con
    # el path que ve, y el browser ve `/api/auth/...`, no `/auth`. Con `/`
    # nos cubrimos sea cual sea el prefijo. La protección XSRF la da
    # SameSite + httpOnly + el access token Bearer que sigue siendo el que
    # autoriza acciones reales (refresh por sí solo no muta dominio).
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=refresh_token,
        max_age=days * 24 * 60 * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=samesite,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Borra la cookie del refresh token (mismo path que el set)."""
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
    )


def _resolve_refresh_token(body_token: str | None, cookie_token: str | None) -> str:
    """Devuelve el refresh token efectivo. Cookie tiene prioridad sobre body.

    Si no hay ninguno → 401 (es lo que expone el caller cuando no recibe
    una sesión válida).
    """
    token = cookie_token or body_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token ausente (ni cookie ni body)",
        )
    return token


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    dependencies=[Depends(rate_limit(5, 60))],
)
async def register_endpoint(
    body: RegisterRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Registra un nuevo usuario, devuelve tokens y setea la cookie.

    PHASE-20: tras crear el usuario, se siembran automáticamente
    categorías y reglas recomendadas para bancos españoles, para que
    el primer import ya venga mayoritariamente categorizado.
    """
    from app.modules.personal_finance.seed.service import seed_recommended
    from app.modules.users.repository import get_user_by_email

    session = await register(db, body.email, body.password, body.display_name)
    user = await get_user_by_email(db, body.email)
    if user is not None:
        await seed_recommended(db, user.id)
    await db.commit()
    _set_refresh_cookie(response, session.tokens.refresh_token, ttl_days=session.refresh_ttl_days)
    return session.tokens


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(10, 60))],
)
async def login_endpoint(
    body: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Autentica un usuario, devuelve tokens y setea la cookie.

    Si `body.remember_me` es true, la cookie y el refresh usan el TTL
    extendido de settings.
    """
    session = await login(db, body.email, body.password, remember_me=body.remember_me)
    await db.commit()
    _set_refresh_cookie(response, session.tokens.refresh_token, ttl_days=session.refresh_ttl_days)
    return session.tokens


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(30, 60))],
)
async def refresh_endpoint(
    body: RefreshRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_cookie: Annotated[str | None, Cookie(alias=settings.auth_cookie_name)] = None,
) -> TokenResponse:
    """Rota el refresh token y setea la cookie nueva.

    Acepta el refresh por cookie (web) o por body (mobile); cookie tiene
    prioridad. La nueva cookie hereda el TTL del token rotado: si era
    extendido (remember_me), sigue siéndolo.
    """
    token = _resolve_refresh_token(body.refresh_token, refresh_cookie)
    session = await refresh(db, token)
    await db.commit()
    _set_refresh_cookie(response, session.tokens.refresh_token, ttl_days=session.refresh_ttl_days)
    return session.tokens


@router.post("/logout", status_code=204, response_class=Response)
async def logout_endpoint(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: CurrentUser,
    refresh_cookie: Annotated[str | None, Cookie(alias=settings.auth_cookie_name)] = None,
) -> Response:
    """Revoca el refresh token y limpia la cookie."""
    token = _resolve_refresh_token(body.refresh_token, refresh_cookie)
    await logout(db, token)
    await db.commit()
    # Construimos la response final aquí: devolver una Response nueva en un
    # endpoint con `response_class=Response` reemplaza la inyectada, así que
    # las cookies hay que setearlas en la que efectivamente se devuelve.
    resp = Response(status_code=204)
    _clear_refresh_cookie(resp)
    return resp


@router.get("/me", response_model=UserResponse)
async def me_endpoint(user: CurrentUser) -> UserResponse:
    """Devuelve los datos del usuario autenticado."""
    return UserResponse.model_validate(user)
