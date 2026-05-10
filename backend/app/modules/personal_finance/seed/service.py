"""Servicio de seeding: crea categorías recomendadas + reglas para
bancos españoles. Idempotente.

- Categorías: UPSERT por (user_id, nombre lowercase). Si el usuario
  ya tiene una categoría con el mismo nombre, se reutiliza (no se
  duplica).
- Reglas: UPSERT por (pattern, match_type, field, category_id). Si
  ya existe la combinación exacta no se inserta.

Uso:
- Hook en `POST /auth/register` para nuevos usuarios.
- Endpoint `POST /seed/recommended` para usuarios existentes que
  quieran añadir las recomendadas (idempotente).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.categories.models import Category
from app.modules.personal_finance.category_rules.models import CategoryRule
from app.modules.personal_finance.category_rules.repository import find_existing
from app.modules.personal_finance.seed.dataset import (
    SEED_CATEGORIES,
    SeedCategoryDef,
)


class SeedResult:
    """Resumen del seeding para que el caller pueda mostrarlo en la UI."""

    def __init__(self) -> None:
        self.categories_created = 0
        self.categories_existed = 0
        self.rules_created = 0
        self.rules_existed = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "categories_created": self.categories_created,
            "categories_existed": self.categories_existed,
            "rules_created": self.rules_created,
            "rules_existed": self.rules_existed,
        }


async def _upsert_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    spec: SeedCategoryDef,
) -> tuple[Category, bool]:
    """Devuelve `(categoría, creada_bool)`. Match por nombre case-insensible.

    Si la categoría ya existe pero le faltan `color` o `icon` (NULL),
    se rellenan con los del seed — útil para usuarios cuyas categorías
    fueron creadas antes de que el seed asignase color/emoji. Lo que
    el usuario haya puesto a mano nunca se sobrescribe.
    """
    existing_q = await db.execute(
        select(Category).where(
            Category.user_id == user_id,
            # Postgres: lower() simétrico — case-insensitive sin instalar
            # citext. Para el volumen esperado (~20 categorías por user)
            # el seq scan es trivial.
        )
    )
    existing_list = list(existing_q.scalars().all())
    target = spec["name"].casefold()
    for c in existing_list:
        if c.name.casefold() == target:
            mutated = False
            if c.color is None:
                c.color = spec["color"]
                mutated = True
            if c.icon is None:
                c.icon = spec["icon"]
                mutated = True
            if mutated:
                await db.flush()
                await db.refresh(c)
            return c, False
    cat = Category(
        user_id=user_id,
        name=spec["name"],
        kind=spec["kind"],
        color=spec["color"],
        icon=spec["icon"],
    )
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return cat, True


async def seed_recommended(
    db: AsyncSession, user_id: uuid.UUID
) -> SeedResult:
    """Crea categorías y reglas recomendadas. Idempotente.

    Si el usuario ya tiene la categoría con ese nombre, se reutiliza.
    Si la regla con la misma (pattern, match_type, field, category_id)
    ya existe, se omite. El resultado indica cuántas se crearon vs
    cuántas ya existían.
    """
    result = SeedResult()

    for spec in SEED_CATEGORIES:
        category, created = await _upsert_category(db, user_id, spec=spec)
        if created:
            result.categories_created += 1
        else:
            result.categories_existed += 1

        for rule_spec in spec["rules"]:
            existing = await find_existing(
                db,
                user_id,
                pattern=rule_spec["pattern"],
                match_type=rule_spec["match_type"],
                field=rule_spec["field"],
                category_id=category.id,
            )
            if existing is not None:
                result.rules_existed += 1
                continue
            rule = CategoryRule(
                user_id=user_id,
                pattern=rule_spec["pattern"],
                match_type=rule_spec["match_type"],
                field=rule_spec["field"],
                category_id=category.id,
                priority=rule_spec["priority"],
                enabled=True,
            )
            db.add(rule)
            await db.flush()
            result.rules_created += 1

    return result
