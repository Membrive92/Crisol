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

from app.modules.personal_finance.accounts.models import Account, AccountNature, AccountType
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
    # Sin esta comprobación, pasar el id de una cuenta corriente devolvía 200 y
    # le pedía al usuario que declarase con qué tarjeta financió su nómina.
    if account.nature is not AccountNature.LIABILITY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"«{account.name}» no es una cuenta de deuda.",
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
    """Los movimientos VIVOS de la tarjeta que componen un ciclo.

    Compras (`OUT`) **y devoluciones** (`IN`, con importe negativo): el banco
    liquida el NETO, así que un ciclo con una devolución dentro no puede sumar
    el recibo si sólo se cuentan las compras. Medido contra los datos reales
    del usuario, netarlas es exactamente lo que separa «cierra al céntimo» de
    «no cierra» en dos de sus cuatro ciclos.

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
            Transaction.flow,
        ).where(
            Transaction.user_id == user_id,
            Transaction.account_id == card_id,
            Transaction.deleted_at.is_(None),
            Transaction.flow.in_([TransactionFlow.OUT, TransactionFlow.IN]),
            Transaction.deferred_by_account_id.is_(None),
        )
    )
    return [
        CyclePurchase(
            id=r[0],
            occurred_at=r[1],
            amount=-r[2] if r[4] is TransactionFlow.IN else r[2],
            description=r[3],
        )
        for r in rows.all()
        if not is_card_settlement(r[3])
    ]


async def _declared_cycle(
    db: AsyncSession, user_id: uuid.UUID, liability_id: uuid.UUID
) -> list[CyclePurchase]:
    """Las compras que YA están marcadas como aplazadas por este pasivo."""
    rows = await db.execute(
        select(
            Transaction.id,
            Transaction.occurred_at,
            Transaction.amount,
            Transaction.description,
        ).where(
            Transaction.user_id == user_id,
            Transaction.deferred_by_account_id == liability_id,
            Transaction.deleted_at.is_(None),
        )
    )
    return [
        CyclePurchase(id=r[0], occurred_at=r[1], amount=r[2], description=r[3]) for r in rows.all()
    ]


async def has_declared_cycle(db: AsyncSession, user_id: uuid.UUID, liability_id: uuid.UUID) -> bool:
    """¿Este pasivo tiene ya un ciclo marcado?"""
    return bool(await _declared_cycle(db, user_id, liability_id))


async def _parent_card(db: AsyncSession, user_id: uuid.UUID, liability: Account) -> Account | None:
    """La tarjeta con la que se financió este pasivo, si está declarada."""
    if liability.parent_account_id is None:
        return None
    card: Account | None = await db.scalar(
        select(Account).where(Account.id == liability.parent_account_id, Account.user_id == user_id)
    )
    return card


async def preview_deferred_cycle(
    db: AsyncSession, user_id: uuid.UUID, liability_id: uuid.UUID
) -> tuple[Account, Account | None, Decimal, CycleSelection]:
    """Qué compras cubriría este aplazamiento, sin escribir nada.

    Devuelve también el pasivo y la tarjeta para que el router pueda componer
    una respuesta que se explique sola — incluido el caso de que no haya
    tarjeta declarada, que es el más frecuente al empezar.
    """
    liability = await _load_liability(db, user_id, liability_id)

    # Idempotencia. `_card_purchases` excluye lo YA marcado, así que una segunda
    # llamada buscaría en un pool FRESCO y podría cerrar sobre un conjunto
    # completamente distinto —las compras del ciclo anterior, si dan la misma
    # suma— y estamparle el mismo pasivo. Un doble clic bastaba. Si ya hay
    # ciclo declarado, se devuelve ESE y no se busca nada.
    declared = await _declared_cycle(db, user_id, liability_id)
    if declared:
        total = sum((p.amount for p in declared), Decimal(0))
        # El recibo sigue siendo el capital del cuadro, NO la suma de lo que
        # haya marcado ahora mismo. Si se devolviera esa suma como importe del
        # recibo, `closes_exactly` sería cierto por construcción y el atajo
        # afirmaría un cierre al céntimo aunque el usuario hubiera mandado una
        # de las compras a la papelera — justo lo que «cierre exacto o nada»
        # existe para impedir.
        receipt = await _schedule_principal(db, liability_id)
        closes = receipt > 0 and total == receipt
        reason = (
            f"Ya declarado: {len(declared)} compras marcadas como aplazadas por esta deuda."
            if closes
            else (
                f"Las {len(declared)} compras marcadas suman {total}, que ya no coincide con el "
                f"recibo ({receipt}). Alguna se ha borrado o cambiado de importe: retira la "
                "marca y vuelve a declararla."
            )
        )
        return (
            liability,
            await _parent_card(db, user_id, liability),
            receipt if receipt > 0 else total,
            CycleSelection(tuple(declared), total, closes, reason),
        )

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
    until = await _cycle_close(db, user_id, card.id, target, liability)
    selection = select_deferred_cycle(purchases, target, until=until)
    return liability, card, target, selection


async def _cycle_close(
    db: AsyncSession,
    user_id: uuid.UUID,
    card_id: uuid.UUID,
    target: Decimal,
    liability: Account,
) -> datetime | None:
    """Cuándo cerró el ciclo que este recibo salda. Acota el ciclo por arriba.

    `start_date` es cuando se CONTRATÓ la financiación, no cuando el banco
    cortó la facturación, y entre las dos fechas caben compras del ciclo
    SIGUIENTE. Como el recorrido va de más reciente a más antigua, esas
    entrarían las primeras — y si los importes se alinean, el ciclo cerraría
    sobre compras que no son.

    La señal buena ya está en los datos: el extracto de la tarjeta trae la
    propia liquidación (`Recibo mes anterior` / `Adeudo mensual`) por el importe
    exacto del recibo. Esa fila ES el corte. Se busca en la tarjeta y, sólo si
    no aparece, se cae a `start_date` — que sigue siendo mejor que nada, pero
    es una aproximación y por eso se prefiere la otra.
    """
    rows = await db.execute(
        select(Transaction.occurred_at, Transaction.amount, Transaction.description).where(
            Transaction.user_id == user_id,
            Transaction.account_id == card_id,
            Transaction.deleted_at.is_(None),
            Transaction.amount == target,
        )
    )
    settlements = [r[0] for r in rows.all() if is_card_settlement(r[2])]

    # Cuándo se contrató ESTA financiación. Acota la búsqueda: el mismo importe
    # se liquida dos meses seguidos más a menudo de lo que parece —577,16 € en
    # marzo y en abril de 2026, en los datos reales—, y quedarse con la más
    # reciente sin más anclaría el ciclo de marzo en el cierre de abril.
    contracted = (
        datetime.combine(liability.start_date, time.max, tzinfo=UTC)
        if liability.start_date is not None
        else None
    )
    if settlements:
        candidates = (
            [s for s in settlements if s <= contracted] if contracted is not None else settlements
        )
        if candidates:
            # La más reciente de las ANTERIORES al contrato: es el ciclo que
            # esta financiación salda.
            latest: datetime = max(candidates)
            return latest
    return contracted


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
