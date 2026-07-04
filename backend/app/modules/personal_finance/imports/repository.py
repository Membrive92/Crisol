"""Queries a DB del módulo imports."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.imports.models import ImportJob
from app.modules.personal_finance.transactions.models import Transaction


async def create_job(db: AsyncSession, job: ImportJob) -> ImportJob:
    """Persiste un job nuevo."""
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


async def get_job_by_id(
    db: AsyncSession, job_id: uuid.UUID, user_id: uuid.UUID
) -> ImportJob | None:
    """Obtiene un job filtrando por user_id."""
    result = await db.execute(
        select(ImportJob).where(ImportJob.id == job_id, ImportJob.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_jobs(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ImportJob], int]:
    """Lista jobs del usuario ordenados por fecha desc + total."""
    base = select(ImportJob).where(ImportJob.user_id == user_id)
    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar_one()

    result = await db.execute(
        base.order_by(ImportJob.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def find_existing_hashes(db: AsyncSession, user_id: uuid.UUID, hashes: list[str]) -> set[str]:
    """Devuelve los hashes que YA existen en transactions activas del usuario.

    Filtra soft-deleted (PHASE-10.1) para coherencia con el partial
    unique index `uq_transactions_user_import_hash`, que también
    excluye `deleted_at IS NOT NULL`. Re-importar una fila cuya
    versión previa fue trasheada por el USUARIO produce una nueva — si
    después la restaura, asume el riesgo de duplicado.

    AUDIT-2026-07 (H-04): EXCEPCIÓN — los "cargos espejo" que el sistema
    absorbió (`absorbed_as_mirror=True`) están soft-deleted pero SÍ cuentan
    como existentes. Así reimportar el mismo extracto no resucita el −X que
    ya se absorbió al convertir una compra en deuda (que dejaría el saldo
    descuadrado en silencio). No es papelera de usuario: fue un borrado de
    sistema con contrapartida ya creada.
    """
    if not hashes:
        return set()
    result = await db.execute(
        select(Transaction.import_hash).where(
            Transaction.user_id == user_id,
            Transaction.import_hash.in_(hashes),
            or_(
                Transaction.deleted_at.is_(None),
                Transaction.absorbed_as_mirror.is_(True),
            ),
        )
    )
    return {h for h in result.scalars().all() if h is not None}
