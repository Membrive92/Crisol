"""Lógica de negocio del módulo users."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.users.repository import update_user
from app.modules.users.schemas import UserUpdate


async def update_me(db: AsyncSession, user: User, body: UserUpdate) -> User:
    """Actualiza las preferencias del usuario autenticado.

    Hoy sólo `cycle_start_day` (el día que abre su «mes»). El rango 1-28 lo
    valida el schema y lo reafirma un CHECK en la BD; aquí no se repite la
    comprobación, se documenta dónde vive: la validación duplicada en dos capas
    con posibilidad de divergir es exactamente lo que costó PHASE-46.

    Es una preferencia de PRESENTACIÓN: no dispara ningún recálculo ni toca
    ninguna tabla de dinero. Cambiarla no puede mover un céntimo de ningún
    saldo, y por eso este service no tiene nada más que hacer que persistirla.
    """
    return await update_user(db, user, cycle_start_day=body.cycle_start_day)
