"""Hooks de ciclo de vida del dominio (AUDIT-2026-05).

Permite que un módulo de infraestructura (`auth`) dispare efectos de
dominio (sembrar categorías/reglas recomendadas) **sin importar** el
módulo de dominio directamente. `auth/router.py` sólo llama a
`dispatch_user_created`; el cableado concreto vive en `main.py`, que es
el único sitio que conoce ambos lados.

Antes, `auth/router.py` importaba `personal_finance.seed.service` dentro
del handler — la única inversión de dependencia infra→dominio del repo.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

# Un hook recibe la sesión + el id del usuario recién creado. El valor de
# retorno se ignora (los seeders devuelven su propio resumen).
UserCreatedHook = Callable[[AsyncSession, uuid.UUID], Awaitable[object]]

_user_created_hooks: list[UserCreatedHook] = []


def register_user_created_hook(hook: UserCreatedHook) -> None:
    """Registra un efecto a ejecutar tras crear un usuario. Idempotente
    por proceso: `main.py` lo llama una vez al cargar."""
    if hook not in _user_created_hooks:
        _user_created_hooks.append(hook)


async def dispatch_user_created(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Ejecuta en orden los hooks registrados. Comparte la sesión del
    request — el caller controla el commit."""
    for hook in _user_created_hooks:
        await hook(db, user_id)
