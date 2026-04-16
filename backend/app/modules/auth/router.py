"""Router del módulo auth."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.modules.auth.service import login, logout, refresh, register
from app.modules.users.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register_endpoint(
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Registra un nuevo usuario y devuelve tokens."""
    result = await register(db, body.email, body.password, body.display_name)
    await db.commit()
    return result


@router.post("/login", response_model=TokenResponse)
async def login_endpoint(
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Autentica un usuario y devuelve tokens."""
    result = await login(db, body.email, body.password)
    await db.commit()
    return result


@router.post("/refresh", response_model=TokenResponse)
async def refresh_endpoint(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Rota el refresh token y devuelve nuevos tokens."""
    result = await refresh(db, body.refresh_token)
    await db.commit()
    return result


@router.post("/logout", status_code=204)
async def logout_endpoint(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: CurrentUser,
) -> None:
    """Revoca el refresh token."""
    await logout(db, body.refresh_token)
    await db.commit()


@router.get("/me", response_model=UserResponse)
async def me_endpoint(user: CurrentUser) -> UserResponse:
    """Devuelve los datos del usuario autenticado."""
    return UserResponse.model_validate(user)
