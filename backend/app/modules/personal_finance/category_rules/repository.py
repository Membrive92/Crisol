"""Queries a DB del módulo category_rules."""

from __future__ import annotations

import re
import unicodedata
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.category_rules.models import (
    CategoryRule,
    RuleField,
    RuleMatchType,
)


def normalize(value: str) -> str:
    """Lowercase + sin acentos + trim. Mismo helper para el matching
    de reglas y para la normalización de bank concepts.
    """
    if not value:
        return ""
    nfd = unicodedata.normalize("NFD", value)
    no_accents = "".join(ch for ch in nfd if not unicodedata.combining(ch))
    return no_accents.lower().strip()


async def list_rules_for_user(
    db: AsyncSession, user_id: uuid.UUID, *, enabled_only: bool = False
) -> list[CategoryRule]:
    """Lista reglas del usuario ordenadas por `priority` ascendente.

    `enabled_only=True` filtra a las habilitadas — usado en el
    pipeline de imports. La UI las muestra todas.
    """
    query = (
        select(CategoryRule)
        .where(CategoryRule.user_id == user_id)
        .order_by(CategoryRule.priority.asc(), CategoryRule.created_at.asc())
    )
    if enabled_only:
        query = query.where(CategoryRule.enabled.is_(True))
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_rule_by_id(
    db: AsyncSession, rule_id: uuid.UUID, user_id: uuid.UUID
) -> CategoryRule | None:
    result = await db.execute(
        select(CategoryRule).where(CategoryRule.id == rule_id, CategoryRule.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def find_existing(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    pattern: str,
    match_type: RuleMatchType,
    field: RuleField,
    category_id: uuid.UUID,
) -> CategoryRule | None:
    """Busca una regla con la misma combinación (para idempotencia
    del seed)."""
    result = await db.execute(
        select(CategoryRule).where(
            CategoryRule.user_id == user_id,
            CategoryRule.pattern == pattern,
            CategoryRule.match_type == match_type,
            CategoryRule.field == field,
            CategoryRule.category_id == category_id,
        )
    )
    return result.scalar_one_or_none()


async def add_rule(db: AsyncSession, rule: CategoryRule) -> CategoryRule:
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return rule


async def remove_rule(db: AsyncSession, rule: CategoryRule) -> None:
    await db.delete(rule)
    await db.flush()


def rule_matches(
    rule: CategoryRule,
    *,
    concept: str | None,
    description: str | None,
) -> bool:
    """Evalúa una regla contra los campos disponibles.

    Normaliza ambos lados (lowercase + sin acentos) antes de comparar.
    Para `match_type=regex`, las reglas mal-formadas no matchean (se
    capturan al crear, así que en runtime no debería ocurrir).
    """
    if not rule.enabled:
        return False

    targets: list[str] = []
    if rule.field in (RuleField.CONCEPT, RuleField.BOTH) and concept:
        targets.append(concept)
    if rule.field in (RuleField.DESCRIPTION, RuleField.BOTH) and description:
        targets.append(description)
    if not targets:
        return False

    pattern_norm = normalize(rule.pattern)
    if not pattern_norm:
        return False

    for raw in targets:
        target_norm = normalize(raw)
        if rule.match_type == RuleMatchType.EXACT:
            if pattern_norm == target_norm:
                return True
        elif rule.match_type == RuleMatchType.CONTAINS:
            if pattern_norm in target_norm:
                return True
        elif rule.match_type == RuleMatchType.STARTS_WITH:
            if target_norm.startswith(pattern_norm):
                return True
        elif rule.match_type == RuleMatchType.REGEX:
            try:
                if re.search(pattern_norm, target_norm):
                    return True
            except re.error:
                return False
    return False


def find_first_matching_rule(
    rules: list[CategoryRule],
    *,
    concept: str | None,
    description: str | None,
) -> CategoryRule | None:
    """Devuelve la primera regla que matchea (orden de prioridad). Las
    reglas vienen ya ordenadas por el repository."""
    for rule in rules:
        if rule_matches(rule, concept=concept, description=description):
            return rule
    return None
