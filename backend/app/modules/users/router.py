"""Router del módulo users — preferencias del perfil autenticado.

La LECTURA del perfil vive en `GET /auth/me`, que ya serializa `UserResponse`;
este router sólo aporta la escritura. Duplicar aquí un `GET /users/me` daría
dos rutas para el mismo dato y, antes o después, dos formas distintas de la
misma respuesta.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.users.schemas import UserResponse, UserUpdate
from app.modules.users.service import update_me

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserResponse)
async def update_me_endpoint(
    body: UserUpdate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Actualiza las preferencias del usuario autenticado.

    `cycle_start_day` (1-28) es el día en que empieza SU mes a efectos de
    presentación; `null` lo devuelve al mes natural. Fuera de rango → `422`.

    No lleva identificador de usuario en la ruta ni en el body a propósito: el
    único perfil que este endpoint puede tocar es el del token, así que no hay
    superficie para pedir el de otro.
    """
    updated = await update_me(db, user, body)
    await db.commit()
    return UserResponse.model_validate(updated)
