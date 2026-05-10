"""Reglas de categorización pattern → categoría.

PHASE-20: rules engine para autocategorizar transacciones importadas
sin que el usuario tenga que mapear concepto-a-concepto. Las reglas
evalúan un patrón contra el `concept` (concept del banco extraído por
el smart parser, lo que va al `category_name` de la fila) y/o el
`description` de la transacción.

Orden de prioridad de la asignación de categoría en imports:

1. Override explícito del usuario en preview → se persiste como
   `bank_category_mapping` (match exacto del concepto).
2. `bank_category_mappings` previos del usuario (match exacto).
3. `category_rules` evaluadas en orden de `priority` ascendente
   (menor primero) — primer match gana.
4. `default_category_id` del import o `NULL`.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RuleMatchType(enum.StrEnum):
    """Cómo se evalúa el `pattern` contra el campo objetivo."""

    EXACT = "exact"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    REGEX = "regex"


class RuleField(enum.StrEnum):
    """Sobre qué campo de la fila se evalúa el patrón.

    `concept` → el concepto del banco (`category_name` extraído del
    extracto). Útil para reglas tipo "PAGO TARJETA - RESTAURANTES".

    `description` → la descripción de la transacción (comercio /
    detalle). Útil para reglas tipo "AMAZON" o "MERCADONA".

    `both` → evalúa contra ambos; matchea si cualquiera de los dos
    cumple. Default razonable.
    """

    CONCEPT = "concept"
    DESCRIPTION = "description"
    BOTH = "both"


class CategoryRule(Base):
    """Regla de categorización del usuario.

    El matching se hace case+acento-insensible (normalize en service).
    `priority` ordena la evaluación: a menor número, antes se evalúa.
    Empate por `created_at` ascendente como fallback determinista.
    """

    __tablename__ = "category_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    match_type: Mapped[RuleMatchType] = mapped_column(nullable=False)
    field: Mapped[RuleField] = mapped_column(
        nullable=False, default=RuleField.BOTH, server_default="BOTH"
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Menor = antes. Default 100 para que los seeds (priority<100) y
    # las reglas del usuario (priority=100) puedan convivir.
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default="100"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        # Misma combinación pattern+match_type+field+category no debería
        # duplicarse para el mismo usuario. Permite reordenar (cambiar
        # priority) sin chocar.
        UniqueConstraint(
            "user_id",
            "pattern",
            "match_type",
            "field",
            "category_id",
            name="uq_category_rules_user_pattern",
        ),
    )
