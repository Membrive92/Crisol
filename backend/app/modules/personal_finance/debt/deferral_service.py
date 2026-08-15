"""PHASE-47.E2 — Declarar qué gasto quedó aplazado por un recibo financiado.

El sistema INICIA (propone el ciclo, con su aritmética a la vista) y el usuario
DECLARA (confirma o no) — [ADR-0011](../../../../internal_docs/decisions/0011-system-initiated-debt-event-translation.md).
Aquí vive esa conversación: un previsualizador que enseña exactamente qué
compras se marcarían y por cuánto, y un aplicador que sólo escribe lo que el
previsualizador ya había enseñado.

Idempotente y reversible: aplicar dos veces deja lo mismo, y `clear` devuelve
las compras a contar como salida de caja.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.models import Account, AccountType
from app.modules.personal_finance.debt.deferral import (
    CyclePurchase,
    CycleSelection,
    select_deferred_cycle,
)
from app.modules.personal_finance.debt.installments_model import LiabilityInstallment
from app.modules.personal_finance.debt.reconciliation import is_card_settlement
from app.modules.personal_finance.transactions.models import Transaction, TransactionFlow


async def _load_liability(db: AsyncSession, user_id: uuid.UUID, liability_id: uuid.UUID) -> Account:
    account = await db.scalar(
        select(Account).where(Account.id == liability_id, Account.user_id == user_id)
    )
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Esa deuda no existe o no es tuya.",
        )
    return account


async def _schedule_principal(db: AsyncSession, liability_id: uuid.UUID) -> Decimal:
    """El capital del cuadro. Es lo que costó el recibo aplazado.

    Se usa el CUADRO y no el texto del movimiento por lo mismo que en PHASE-46:
    un aplazamiento y su cuadro nacen del mismo importe, así que coinciden al
    céntimo, y esa coincidencia no caduca cuando el banco cambia la redacción.
    """
    rows = await db.execute(
        select(LiabilityInstallment.principal).where(
            LiabilityInstallment.account_id == liability_id
        )
    )
    return sum((r[0] for r in rows.all()), Decimal(0))


async def _card_purchases(
    db: AsyncSession, user_id: uuid.UUID, card_id: uuid.UUID
) -> list[CyclePurchase]:
    """Las compras VIVAS de la tarjeta, sin las que ya están aplazadas.

    Se excluyen las liquidaciones: el recibo que salda el ciclo no forma parte
    del ciclo, y sumarlo lo duplicaría. Y se excluyen las ya marcadas por otro
    aplazamiento, para que dos recibos no se disputen la misma compra.
    """
    rows = await db.execute(
        select(
            Transaction.id,
            Transaction.occurred_at,
            Transaction.amount,
            Transaction.description,
        ).where(
            Transaction.user_id == user_id,
            Transaction.account_id == card_id,
            Transaction.deleted_at.is_(None),
            Transaction.flow == TransactionFlow.OUT,
            Transaction.deferred_by_account_id.is_(None),
        )
    )
    return [
        CyclePurchase(id=r[0], occurred_at=r[1], amount=r[2], description=r[3])
        for r in rows.all()
        if not is_card_settlement(r[3])
    ]


async def preview_deferred_cycle(
    db: AsyncSession, user_id: uuid.UUID, liability_id: uuid.UUID
) -> tuple[Account, Account | None, Decimal, CycleSelection]:
    """Qué compras cubriría este aplazamiento, sin escribir nada.

    Devuelve también el pasivo y la tarjeta para que el router pueda componer
    una respuesta que se explique sola — incluido el caso de que no haya
    tarjeta declarada, que es el más frecuente al empezar.
    """
    liability = await _load_liability(db, user_id, liability_id)
    if liability.parent_account_id is None:
        return (
            liability,
            None,
            Decimal(0),
            CycleSelection(
                (),
                Decimal(0),
                False,
                (
                    "Esta deuda no tiene declarada la tarjeta con la que se financió. "
                    "Sin saber qué tarjeta, no hay ciclo que buscar."
                ),
            ),
        )

    card = await db.scalar(
        select(Account).where(Account.id == liability.parent_account_id, Account.user_id == user_id)
    )
    if card is None or card.type != AccountType.CREDIT_CARD:
        return (
            liability,
            None,
            Decimal(0),
            CycleSelection(
                (),
                Decimal(0),
                False,
                "La cuenta declarada como tarjeta ya no existe o no es una tarjeta.",
            ),
        )

    target = await _schedule_principal(db, liability_id)
    if target <= 0:
        return (
            liability,
            card,
            target,
            CycleSelection(
                (),
                Decimal(0),
                False,
                (
                    "Esta deuda no tiene cuadro de amortización, así que no se sabe cuánto "
                    "se aplazó. Genera el cuadro y vuelve a intentarlo."
                ),
            ),
        )

    purchases = await _card_purchases(db, user_id, card.id)
    # El cierre del ciclo acota por arriba: una compra POSTERIOR pertenece al
    # recibo siguiente, que todavía no se ha facturado. Se toma el día entero
    # porque `start_date` es una fecha y las compras llevan hora.
    until = None
    if liability.start_date is not None:
        until = datetime.combine(liability.start_date, time.max, tzinfo=UTC)
    selection = select_deferred_cycle(purchases, target, until=until)
    return liability, card, target, selection


async def apply_deferred_cycle(
    db: AsyncSession, user_id: uuid.UUID, liability_id: uuid.UUID
) -> tuple[Account, Account | None, Decimal, CycleSelection]:
    """Marca las compras del ciclo. Sólo escribe lo que el preview enseñó."""
    liability, card, target, selection = await preview_deferred_cycle(db, user_id, liability_id)
    if not selection.closes_exactly:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=selection.reason)

    await db.execute(
        update(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.id.in_([p.id for p in selection.purchases]),
        )
        .values(deferred_by_account_id=liability_id)
    )
    return liability, card, target, selection


async def clear_deferred_cycle(
    db: AsyncSession, user_id: uuid.UUID, liability_id: uuid.UUID
) -> int:
    """Quita la marca. Las compras vuelven a contar como salida de caja."""
    await _load_liability(db, user_id, liability_id)
    result = await db.execute(
        update(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.deferred_by_account_id == liability_id,
        )
        .values(deferred_by_account_id=None)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
