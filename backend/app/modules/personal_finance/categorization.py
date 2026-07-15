"""Resolución de categoría compartida (PHASE-41).

Cascada canónica de la app para asignar categoría a un movimiento a partir
de su texto (concepto/comercio + descripción), en el mismo orden que usa el
pipeline de imports (`imports/service.py::_parse_row`):

    equivalencia aprendida (bank_mapping exacta)
      > nombre de categoría exacto
      > motor de reglas (contains/regex por prioridad)
      > categoría por defecto (la que pase el caller)

El *override* del usuario (una categoría elegida a mano) NO se resuelve aquí:
es responsabilidad del caller cortocircuitar la cascada cuando el usuario ya
eligió. Se extrae como helper para que receipts (y en el futuro el alta manual)
hereden exactamente la misma inteligencia que imports, sin duplicarla ni
divergir. La dirección del dinero (`flow`) NUNCA se deriva de la categoría
resuelta (ADR-0004): es descriptiva, no la verdad del dinero.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.bank_mappings.repository import (
    get_mappings_for_concepts,
    normalize_concept,
)
from app.modules.personal_finance.categories.models import Category
from app.modules.personal_finance.category_rules.repository import (
    find_first_matching_rule,
    list_rules_for_user,
)


async def resolve_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    concept: str | None,
    description: str | None = None,
    default_category_id: uuid.UUID | None = None,
) -> uuid.UUID | None:
    """Resuelve la categoría de un movimiento por su texto.

    `concept` es el "quién" (comercio del ticket, concepto del banco);
    `description` el texto secundario que también evalúan las reglas. Devuelve
    el `category_id` resuelto, o `default_category_id` si nada matchea. Todas
    las consultas filtran por `user_id`.
    """
    if concept:
        normalized = normalize_concept(concept)
        if normalized:
            # 1) equivalencia aprendida exacta (bank_mapping).
            mappings = await get_mappings_for_concepts(db, user_id, [concept])
            if normalized in mappings:
                return mappings[normalized]
            # 2) nombre de categoría exacto (normalizado igual que el concepto,
            #    sin acentos, para no fragmentar por tildes).
            result = await db.execute(select(Category).where(Category.user_id == user_id))
            for category in result.scalars():
                if normalize_concept(category.name) == normalized:
                    return category.id
    # 3) motor de reglas (contains/regex, ya ordenado por prioridad).
    rules = await list_rules_for_user(db, user_id, enabled_only=True)
    rule = find_first_matching_rule(rules, concept=concept, description=description)
    if rule is not None:
        return rule.category_id
    # 4) por defecto.
    return default_category_id
