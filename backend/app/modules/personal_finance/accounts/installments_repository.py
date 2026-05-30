"""Repository del módulo `liability_installments` (PHASE-24.1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.amortization import build_schedule
from app.modules.personal_finance.accounts.installments_model import (
    LiabilityInstallment,
)
from app.modules.personal_finance.accounts.models import Account


async def generate_installments_for_account(
    db: AsyncSession,
    account: Account,
    *,
    principal_override: Decimal | None = None,
) -> list[LiabilityInstallment]:
    """Genera las cuotas (cuadro francés) para una liability y las
    persiste. Idempotente: si ya hay cuotas para la cuenta, no toca
    nada (el caller usa este helper sólo al crear/regenerar).

    `principal_override` permite forzar el principal en flujos donde
    la deuda no se modela vía `opening_balance` sino vía la tx
    paréada (PHASE-24: convert-to-debt). Si es None, se usa
    `account.opening_balance`.

    Devuelve la lista de cuotas resultantes (vacía si la cuenta no
    cumple las precondiciones — el caller no debe asumir generación).
    """
    if account.apr is None or account.term_months is None or account.start_date is None:
        return []
    principal = principal_override if principal_override is not None else account.opening_balance
    if principal is None or principal <= 0:
        return []

    existing = await db.execute(
        select(LiabilityInstallment).where(LiabilityInstallment.account_id == account.id)
    )
    if existing.first() is not None:
        return []

    rows = build_schedule(
        principal=principal,
        apr=account.apr,
        term_months=account.term_months,
        start_date=account.start_date,
    )
    persisted: list[LiabilityInstallment] = []
    for r in rows:
        inst = LiabilityInstallment(
            user_id=account.user_id,
            account_id=account.id,
            installment_index=r.month,
            due_date=r.due_date,
            payment=r.payment,
            interest=r.interest,
            principal=r.principal,
            remaining_balance=r.remaining_balance,
        )
        db.add(inst)
        persisted.append(inst)
    await db.flush()
    return persisted


async def list_installments(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID
) -> list[LiabilityInstallment]:
    """Lista las cuotas de una liability ordenadas por índice."""
    query = (
        select(LiabilityInstallment)
        .where(
            LiabilityInstallment.account_id == account_id,
            LiabilityInstallment.user_id == user_id,
        )
        .order_by(LiabilityInstallment.installment_index.asc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_installment(
    db: AsyncSession, installment_id: uuid.UUID, user_id: uuid.UUID
) -> LiabilityInstallment | None:
    """Obtiene una cuota por id, filtrada por user_id (aislamiento)."""
    query = select(LiabilityInstallment).where(
        LiabilityInstallment.id == installment_id,
        LiabilityInstallment.user_id == user_id,
    )
    return (await db.execute(query)).scalar_one_or_none()


async def update_installment_amount_and_date(
    db: AsyncSession,
    inst: LiabilityInstallment,
    *,
    payment: object | None = None,
    due_date: object | None = None,
) -> LiabilityInstallment:
    """Override puntual de importe / fecha. No recomputa intereses ni
    saldos restantes — la edición es un override puntual (PHASE-24.1
    decisión arquitectónica).
    """
    if payment is not None:
        inst.payment = payment  # type: ignore[assignment]
    if due_date is not None:
        inst.due_date = due_date  # type: ignore[assignment]
    await db.flush()
    await db.refresh(inst)
    return inst


async def mark_installment_paid(
    db: AsyncSession,
    inst: LiabilityInstallment,
    *,
    paid_at: datetime,
    paid_transaction_id: uuid.UUID | None,
) -> LiabilityInstallment:
    """Marca la cuota como pagada con timestamp + tx opcional."""
    inst.paid_at = paid_at
    inst.paid_transaction_id = paid_transaction_id
    await db.flush()
    await db.refresh(inst)
    return inst


async def unmark_installment_paid(
    db: AsyncSession, inst: LiabilityInstallment
) -> LiabilityInstallment:
    """Revierte el estado a pendiente (NULL ambos campos)."""
    inst.paid_at = None
    inst.paid_transaction_id = None
    await db.flush()
    await db.refresh(inst)
    return inst


async def delete_installments_for_account(db: AsyncSession, account_id: uuid.UUID) -> None:
    """Borra todas las cuotas de una cuenta (al regenerar el cuadro)."""
    await db.execute(
        delete(LiabilityInstallment).where(LiabilityInstallment.account_id == account_id)
    )
    await db.flush()
