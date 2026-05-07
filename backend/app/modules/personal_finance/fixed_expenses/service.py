"""Lógica de negocio del módulo fixed_expenses (PHASE-13.1,
renombrado en PHASE-17.1)."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.fixed_expenses import detector
from app.modules.personal_finance.fixed_expenses.models import (
    FixedExpense,
    FixedExpenseStatus,
)
from app.modules.personal_finance.fixed_expenses.repository import (
    create_fixed_expense as persist_fixed_expense,
)
from app.modules.personal_finance.fixed_expenses.repository import (
    delete_fixed_expense as remove_fixed_expense,
)
from app.modules.personal_finance.fixed_expenses.repository import (
    find_by_fingerprint,
    get_fixed_expense_by_id,
)
from app.modules.personal_finance.fixed_expenses.repository import (
    list_fixed_expenses as list_in_db,
)
from app.modules.personal_finance.fixed_expenses.schemas import ScanResponse


async def list_fixed_expenses(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: FixedExpenseStatus | None = None,
) -> list[FixedExpense]:
    """Lista del usuario, ordenada por `next_due`."""
    return await list_in_db(db, user_id, status=status)


async def get_fixed_expense(
    db: AsyncSession, fixed_expense_id: uuid.UUID, user_id: uuid.UUID
) -> FixedExpense:
    """Obtiene un gasto fijo o 404."""
    item = await get_fixed_expense_by_id(db, fixed_expense_id, user_id)
    if item is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Gasto fijo no encontrado",
        )
    return item


async def confirm_fixed_expense(
    db: AsyncSession, fixed_expense_id: uuid.UUID, user_id: uuid.UUID
) -> FixedExpense:
    """`pending` → `confirmed`."""
    item = await get_fixed_expense(db, fixed_expense_id, user_id)
    if item.status == FixedExpenseStatus.DISMISSED:
        # Confirmar uno dismissed lo reactiva — útil si el usuario se
        # arrepintió. Pasa por pending como audit trail mínimo.
        item.status = FixedExpenseStatus.PENDING
    item.status = FixedExpenseStatus.CONFIRMED
    await db.flush()
    await db.refresh(item)
    return item


async def dismiss_fixed_expense(
    db: AsyncSession, fixed_expense_id: uuid.UUID, user_id: uuid.UUID
) -> FixedExpense:
    """Marca como dismissed; el detector NO lo volverá a sugerir."""
    item = await get_fixed_expense(db, fixed_expense_id, user_id)
    item.status = FixedExpenseStatus.DISMISSED
    await db.flush()
    await db.refresh(item)
    return item


async def pause_fixed_expense(
    db: AsyncSession, fixed_expense_id: uuid.UUID, user_id: uuid.UUID
) -> FixedExpense:
    """Marca como paused (PHASE-15.2). Sólo desde confirmed; otros
    estados producen 409 — pausar uno pending o dismissed no tiene
    semántica clara."""
    item = await get_fixed_expense(db, fixed_expense_id, user_id)
    if item.status != FixedExpenseStatus.CONFIRMED:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=(
                "Sólo se puede pausar un gasto fijo confirmado. "
                f"Estado actual: {item.status}."
            ),
        )
    item.status = FixedExpenseStatus.PAUSED
    await db.flush()
    await db.refresh(item)
    return item


async def resume_fixed_expense(
    db: AsyncSession, fixed_expense_id: uuid.UUID, user_id: uuid.UUID
) -> FixedExpense:
    """Reanuda paused → confirmed (PHASE-15.2)."""
    item = await get_fixed_expense(db, fixed_expense_id, user_id)
    if item.status != FixedExpenseStatus.PAUSED:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=(
                "Sólo se puede reanudar un gasto fijo pausado. "
                f"Estado actual: {item.status}."
            ),
        )
    item.status = FixedExpenseStatus.CONFIRMED
    await db.flush()
    await db.refresh(item)
    return item


async def cancel_fixed_expense(
    db: AsyncSession, fixed_expense_id: uuid.UUID, user_id: uuid.UUID
) -> FixedExpense:
    """Marca como cancelled (PHASE-15.2). Aceptable desde
    pending/confirmed/paused. Uno dismissed no se cancela — ya está
    fuera del flujo. cancelled bloquea re-sugestion igual que
    dismissed (find_by_fingerprint matchea sin tocar status)."""
    item = await get_fixed_expense(db, fixed_expense_id, user_id)
    if item.status == FixedExpenseStatus.DISMISSED:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Un gasto fijo descartado no se puede cancelar.",
        )
    item.status = FixedExpenseStatus.CANCELLED
    await db.flush()
    await db.refresh(item)
    return item


async def delete_fixed_expense(
    db: AsyncSession, fixed_expense_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Borra permanente. Un gasto fijo borrado y luego re-detectado
    en el siguiente scan re-aparecerá como `pending` — coherente con
    "borrar = empezar de cero".
    """
    item = await get_fixed_expense(db, fixed_expense_id, user_id)
    await remove_fixed_expense(db, item)


async def scan_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> ScanResponse:
    """Ejecuta el detector y persiste/refresca gastos fijos.

    Política:
    - Patrones que ya tienen un row (mismo fingerprint): se refrescan
      `last_seen_at`, `next_due`, `occurrence_count` y `confidence`.
      `status` y `category_id` NO se tocan — respetan la decisión del
      usuario.
    - Patrones nuevos sin fingerprint match: se crean como `pending`.
    - Patrones que matchean a un gasto fijo `dismissed`: NO se
      crea fila nueva (la `dismissed` ya existe; sólo se refresca).
      Resultado: el usuario que descartó algo no lo vuelve a ver.
    """
    candidates = await detector.detect_for_user(db, user_id)

    created = 0
    updated = 0
    for cand in candidates:
        existing = await find_by_fingerprint(
            db,
            user_id,
            merchant=cand.merchant,
            amount=cand.amount,
            currency=cand.currency,
            cadence_days=cand.cadence_days,
        )
        if existing is not None:
            existing.last_seen_at = cand.last_seen_at
            existing.next_due = cand.next_due
            existing.occurrence_count = cand.occurrence_count
            existing.confidence = cand.confidence
            existing.raw_description = cand.raw_description
            updated += 1
        else:
            item = FixedExpense(
                user_id=user_id,
                merchant=cand.merchant,
                raw_description=cand.raw_description,
                amount=cand.amount,
                currency=cand.currency,
                cadence_days=cand.cadence_days,
                next_due=cand.next_due,
                status=FixedExpenseStatus.PENDING,
                category_id=cand.category_id,
                first_seen_at=cand.first_seen_at,
                last_seen_at=cand.last_seen_at,
                occurrence_count=cand.occurrence_count,
                confidence=cand.confidence,
            )
            await persist_fixed_expense(db, item)
            created += 1

    await db.flush()

    # Activos = todo lo que no esté dismissed (pending + confirmed).
    pending = await list_in_db(db, user_id, status=FixedExpenseStatus.PENDING)
    confirmed = await list_in_db(db, user_id, status=FixedExpenseStatus.CONFIRMED)
    return ScanResponse(
        created=created,
        updated=updated,
        total_active_after=len(pending) + len(confirmed),
    )
