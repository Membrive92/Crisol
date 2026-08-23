"""Schemas Pydantic del módulo users."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field

from app.modules.users.models import CYCLE_START_DAY_MAX, CYCLE_START_DAY_MIN

CycleStartDay = Annotated[int, Field(ge=CYCLE_START_DAY_MIN, le=CYCLE_START_DAY_MAX)]
"""Día que abre el ciclo del usuario, con su rango.

Va en `Annotated[...]` y no como `int | None = Field(ge=…, le=…)` porque la
restricción tiene que aplicarse al `int`, no al union nullable — es la forma
que se comprobó ejecutando Pydantic 2.13, no leyendo la documentación.
"""


class UserResponse(BaseModel):
    """Datos públicos de un usuario."""

    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    cycle_start_day: int | None
    """Día en que empieza el mes del usuario; `null` = mes natural.

    Viaja en `GET /auth/me`, que serializa este mismo schema. El cliente debe
    tratarlo como POSIBLEMENTE AUSENTE mientras exista un backend anterior a
    esta fase, y decidir por verdad (`cycle_start_day ? … : …`) y no comparando
    con `null` (lección PHASE-47.E).
    """
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Body de `PATCH /users/me` — hoy, sólo el ciclo del usuario.

    El campo es **requerido en el body** aunque acepte `null`: enviar `null`
    significa «vuelvo al mes natural». Así el endpoint no necesita distinguir
    ausente-vs-None, que es justo el tri-estado que convierte un PATCH en una
    fuente de ambigüedad. Cuando entre una segunda preferencia habrá que
    reabrir esa decisión, no heredarla por inercia.
    """

    cycle_start_day: CycleStartDay | None


class UserCreate(BaseModel):
    """Datos para crear un usuario (uso interno)."""

    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)
