"""Schemas Pydantic del módulo category_rules."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.modules.personal_finance.category_rules.models import (
    RuleField,
    RuleMatchType,
)


class CategoryRuleCreate(BaseModel):
    """Crea una regla nueva. El backend valida que la categoría
    pertenezca al usuario antes de persistir."""

    pattern: str = Field(min_length=1, max_length=255)
    match_type: RuleMatchType
    field: RuleField = RuleField.BOTH
    category_id: uuid.UUID
    priority: int = Field(default=100, ge=0, le=10_000)
    enabled: bool = True

    @model_validator(mode="after")
    def _validate_regex_compiles(self) -> CategoryRuleCreate:
        """Si `match_type=regex`, asegurar que el pattern compila."""
        if self.match_type == RuleMatchType.REGEX:
            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f"regex inválida: {e}") from e
        return self


class CategoryRuleUpdate(BaseModel):
    """Actualización parcial de una regla."""

    pattern: str | None = Field(default=None, min_length=1, max_length=255)
    match_type: RuleMatchType | None = None
    field: RuleField | None = None
    category_id: uuid.UUID | None = None
    priority: int | None = Field(default=None, ge=0, le=10_000)
    enabled: bool | None = None

    @model_validator(mode="after")
    def _validate_regex_compiles(self) -> CategoryRuleUpdate:
        if self.match_type == RuleMatchType.REGEX and self.pattern is not None:
            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f"regex inválida: {e}") from e
        return self


class CategoryRuleResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    pattern: str
    match_type: RuleMatchType
    field: RuleField
    category_id: uuid.UUID
    priority: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CategoryRuleListResponse(BaseModel):
    items: list[CategoryRuleResponse]
