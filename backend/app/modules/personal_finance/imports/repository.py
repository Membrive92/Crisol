"""Queries a DB del módulo imports."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.debt.reconciliation import (
    CARD_SETTLEMENT_SEQUENCES,
    sql_like_patterns,
)
from app.modules.personal_finance.imports.models import ImportJob, ImportJobStatus
from app.modules.personal_finance.transactions.models import Transaction

# Derivados de la ÚNICA declaración de qué es una liquidación (PHASE-46). Un
# gate falla si alguien vuelve a enumerarlas por separado.
_CARD_SETTLEMENT_LIKE = sql_like_patterns(CARD_SETTLEMENT_SEQUENCES)


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


async def fingerprint_accounts(
    db: AsyncSession, user_id: uuid.UUID, fingerprint: str
) -> list[uuid.UUID]:
    """PHASE-47.A — Cuentas donde ya se importó un fichero con esta cabecera.

    Sólo jobs COMPLETADOS: un preview abandonado no prueba nada sobre a qué
    cuenta pertenece un formato, y contarlo haría saltar el aviso por el
    intento fallido del propio usuario dos minutos antes.
    """
    result = await db.execute(
        select(ImportJob.account_id)
        .where(
            ImportJob.user_id == user_id,
            ImportJob.header_fingerprint == fingerprint,
            ImportJob.status == ImportJobStatus.COMPLETED,
            ImportJob.account_id.is_not(None),
        )
        .distinct()
    )
    return [a for a in result.scalars().all() if a is not None]


async def account_fingerprints(
    db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID
) -> list[str]:
    """PHASE-47.A — Formatos ya importados con éxito EN esta cuenta.

    Si el formato del fichero ya entró aquí antes, no hay nada que avisar: es
    el extracto mensual de siempre. Sin esta comprobación el guardarraíl
    saltaría cada mes en cuanto dos cuentas compartieran formato, y un aviso
    que salta siempre se aprende a ignorar — con él, el que sí importa.
    """
    result = await db.execute(
        select(ImportJob.header_fingerprint)
        .where(
            ImportJob.user_id == user_id,
            ImportJob.account_id == account_id,
            ImportJob.status == ImportJobStatus.COMPLETED,
            ImportJob.header_fingerprint.is_not(None),
        )
        .distinct()
    )
    return [f for f in result.scalars().all() if f is not None]


async def accounts_holding_hashes(
    db: AsyncSession,
    user_id: uuid.UUID,
    hashes: list[str],
    *,
    exclude_account_id: uuid.UUID,
) -> list[tuple[uuid.UUID, int]]:
    """PHASE-47.A — Cuántas de estas filas ya existen en OTRAS cuentas.

    `_compute_hash` **no incluye `account_id`** (el índice único es
    `(user_id, import_hash)`), así que el mismo fichero produce los mismos
    hashes lo importes donde lo importes. Eso, que como dedup es un problema
    conocido —un fichero metido en la cuenta equivocada bloquea su
    reimportación en la correcta—, aquí es justo la señal que hace falta.

    Devuelve `(account_id, filas)` ordenado de más a menos, excluyendo la
    cuenta elegida (donde el solape significa «ya lo importaste», que es el
    dedup normal y no un error de cuenta).
    """
    if not hashes:
        return []
    result = await db.execute(
        select(Transaction.account_id, func.count())
        .where(
            Transaction.user_id == user_id,
            Transaction.import_hash.in_(hashes),
            Transaction.account_id != exclude_account_id,
            Transaction.deleted_at.is_(None),
        )
        .group_by(Transaction.account_id)
        .order_by(func.count().desc())
    )
    return [(row[0], row[1]) for row in result.all() if row[0] is not None]


async def find_live_card_settlements(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    *,
    since: datetime,
    until: datetime,
) -> list[tuple[datetime, Decimal]]:
    """Liquidaciones de tarjeta VIVAS de una cuenta dentro de un rango.

    Sirve para no volver a insertar un recibo que ya está registrado con otra
    redacción (PHASE-47.E1). Devuelve sólo fecha e importe porque es lo único
    que compara la regla de duplicado; el texto ya lo filtra la query.

    Se excluye lo soft-deleted A PROPÓSITO, y en las dos direcciones: si el
    usuario mandó una copia a la papelera, la que quede viva sigue tapando a la
    siguiente; y si las borró TODAS, reimportar vuelve a traer una — que es lo
    que él esperaría de una papelera.
    """
    patterns = [Transaction.description.ilike(p) for p in _CARD_SETTLEMENT_LIKE]
    result = await db.execute(
        select(Transaction.occurred_at, Transaction.amount).where(
            Transaction.user_id == user_id,
            Transaction.account_id == account_id,
            Transaction.deleted_at.is_(None),
            Transaction.occurred_at >= since,
            Transaction.occurred_at <= until,
            or_(*patterns),
        )
    )
    return [(row[0], row[1]) for row in result.all()]


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
