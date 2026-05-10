"""Lógica de negocio del módulo transfers (PHASE-19.3)."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.transactions.models import Transaction
from app.modules.personal_finance.transfers.repository import (
    filter_unambiguous,
    find_candidate_pairs,
    get_pair as repo_get_pair,
    get_transaction as repo_get_tx,
    link_pair as repo_link_pair,
    list_pairs as repo_list_pairs,
    list_unmatched_active_transactions,
    unlink_pair as repo_unlink_pair,
)
from app.modules.personal_finance.transfers.schemas import (
    TransferCandidate,
    TransferMatchResponse,
    TransferPairResponse,
)


def _delta_days(tx_a: Transaction, tx_b: Transaction) -> int:
    return abs((tx_a.occurred_at - tx_b.occurred_at).days)


def _candidate_to_schema(
    out_tx: Transaction, in_tx: Transaction, delta: int
) -> TransferCandidate:
    return TransferCandidate(
        out_transaction_id=out_tx.id,
        in_transaction_id=in_tx.id,
        amount=out_tx.amount,
        currency=out_tx.currency,
        out_account_id=out_tx.account_id,
        in_account_id=in_tx.account_id,
        out_occurred_at=out_tx.occurred_at,
        in_occurred_at=in_tx.occurred_at,
        delta_days=delta,
    )


def _pair_to_schema(
    out_tx: Transaction, in_tx: Transaction
) -> TransferPairResponse:
    return TransferPairResponse(
        out_transaction_id=out_tx.id,
        in_transaction_id=in_tx.id,
        amount=out_tx.amount,
        currency=out_tx.currency,
        out_account_id=out_tx.account_id,
        in_account_id=in_tx.account_id,
        out_occurred_at=out_tx.occurred_at,
        in_occurred_at=in_tx.occurred_at,
        delta_days=_delta_days(out_tx, in_tx),
    )


async def list_pairs(
    db: AsyncSession, user_id: uuid.UUID
) -> list[TransferPairResponse]:
    """Pares emparejados activos del usuario, en orden cronológico."""
    pairs = await repo_list_pairs(db, user_id)
    return [_pair_to_schema(out_tx, in_tx) for out_tx, in_tx in pairs]


async def detect_candidates(
    db: AsyncSession, user_id: uuid.UUID, *, window_days: int = 3
) -> list[TransferCandidate]:
    """Devuelve TODOS los pares candidatos del matcher sin enlazar nada.

    Útil para previsualizar antes de un match automático, o para que la
    UI muestre sólo "sugerencias" sin escribir en BD.
    """
    items = await list_unmatched_active_transactions(db, user_id)
    pairs = find_candidate_pairs(items, window_days=window_days)
    return [_candidate_to_schema(out_tx, in_tx, d) for out_tx, in_tx, d in pairs]


async def auto_match(
    db: AsyncSession, user_id: uuid.UUID, *, window_days: int = 3
) -> TransferMatchResponse:
    """Ejecuta el matcher: enlaza los pares sin ambigüedad y devuelve
    los ambiguos para que el usuario decida.

    Política conservadora: si hay >1 par con la misma huella
    (amount + currency + cuentas), NO enlaza ninguno automáticamente
    — el usuario revisa y resuelve. Esto evita emparejar mal cuando
    hay varios cargos del mismo importe entre las mismas dos cuentas.
    """
    items = await list_unmatched_active_transactions(db, user_id)
    pairs = find_candidate_pairs(items, window_days=window_days)
    unambiguous, ambiguous = filter_unambiguous(pairs)

    for out_tx, in_tx, _ in unambiguous:
        await repo_link_pair(db, out_tx, in_tx)

    return TransferMatchResponse(
        linked_count=len(unambiguous),
        pending_candidates=[
            _candidate_to_schema(out_tx, in_tx, d)
            for out_tx, in_tx, d in ambiguous
        ],
    )


async def link_manually(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    out_transaction_id: uuid.UUID,
    in_transaction_id: uuid.UUID,
) -> TransferPairResponse:
    """Enlaza dos transacciones explícitamente como par de transferencia.

    Validaciones (todas → 400/409):
    - Las dos pertenecen al usuario y están activas.
    - Son distintas.
    - Cuentas distintas.
    - Mismo amount + currency.
    - Ninguna está ya emparejada (si lo está, primero hay que desenlazar).
    """
    if out_transaction_id == in_transaction_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes enlazar una transacción consigo misma.",
        )
    out_tx = await repo_get_tx(db, out_transaction_id, user_id)
    in_tx = await repo_get_tx(db, in_transaction_id, user_id)
    if out_tx is None or in_tx is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Una de las transacciones no existe o no es tuya.",
        )
    if out_tx.transfer_pair_id is not None or in_tx.transfer_pair_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Alguna de las transacciones ya forma parte de otra "
                "transferencia. Deshaz ese enlace antes de crear uno nuevo."
            ),
        )
    if out_tx.account_id == in_tx.account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Una transferencia interna requiere dos cuentas distintas.",
        )
    if out_tx.amount != in_tx.amount or out_tx.currency != in_tx.currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "El importe y la moneda deben coincidir entre las dos "
                "transacciones del par."
            ),
        )
    await repo_link_pair(db, out_tx, in_tx)
    return _pair_to_schema(out_tx, in_tx)


async def unlink(
    db: AsyncSession,
    user_id: uuid.UUID,
    transaction_id: uuid.UUID,
) -> None:
    """Deshace el par del que `transaction_id` forma parte. 404 si no
    pertenece al usuario o no está emparejada."""
    pair = await repo_get_pair(db, transaction_id, user_id)
    if pair is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La transacción no existe o no está emparejada.",
        )
    tx_a, tx_b = pair
    await repo_unlink_pair(db, tx_a, tx_b)
