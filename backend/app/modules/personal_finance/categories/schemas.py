"""Schemas Pydantic del módulo categories."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.personal_finance.categories.models import CategoryKind, CategoryRole


class CategoryCreate(BaseModel):
    """Datos para crear una categoría."""

    name: str = Field(min_length=1, max_length=100)
    icon: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=7)
    kind: CategoryKind
    is_transfer: bool = False
    """PHASE-23.1: marca la categoría como transferencia interna —
    sus txs quedan fuera del cashflow agregado pero conservan el
    signo de `kind` al sumar al saldo de la cuenta."""
    role: CategoryRole = CategoryRole.GENERIC
    """PHASE-30.1 — rol semántico. Default GENERIC. Cuando
    `is_transfer=True` el service lo fuerza a TRANSFER por
    consistencia (transición segura mientras `is_transfer` siga vivo)."""


class CategoryUpdate(BaseModel):
    """Datos para actualizar una categoría (parcial)."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    icon: str | None = None
    color: str | None = None
    kind: CategoryKind | None = None
    is_transfer: bool | None = None
    role: CategoryRole | None = None


class CategoryResponse(BaseModel):
    """Respuesta pública de una categoría."""

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    icon: str | None
    color: str | None
    kind: CategoryKind
    is_transfer: bool
    role: CategoryRole
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
