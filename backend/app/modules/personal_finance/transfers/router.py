"""Router del módulo transfers (PHASE-19.3)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.transfers.schemas import (
    TransferCandidate,
    TransferFromSourceDebtRequest,
    TransferFromSourceRequest,
    TransferLinkRequest,
    TransferMarkRequest,
    TransferMarkResponse,
    TransferMatchOptions,
    TransferMatchResponse,
    TransferPairResponse,
    TransferSuspect,
)
from app.modules.personal_finance.transfers.service import (
    auto_match,
    convert_to_debt_operation,
    convert_to_internal_transfer,
    detect_candidates,
    link_manually,
    list_pairs,
    list_suspects,
    mark_as_transfer,
    unlink,
)

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.get("", response_model=list[TransferPairResponse])
async def list_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TransferPairResponse]:
    """Lista los pares emparejados activos del usuario."""
    return await list_pairs(db, user.id)


@router.get("/candidates", response_model=list[TransferCandidate])
async def candidates_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    window_days: Annotated[int, Query(ge=0, le=14)] = 3,
) -> list[TransferCandidate]:
    """Sugerencias de pares aún no emparejados, sin escribir nada en BD.

    El frontend muestra esta lista para que el usuario confirme uno a
    uno (vía POST /transfers/link) o dispare el match automático
    completo (POST /transfers/match).
    """
    return await detect_candidates(db, user.id, window_days=window_days)


@router.post("/match", response_model=TransferMatchResponse)
async def match_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    body: TransferMatchOptions | None = None,
) -> TransferMatchResponse:
    """Ejecuta el matcher: enlaza los pares no ambiguos y devuelve
    los ambiguos para que el usuario los resuelva manualmente.
    """
    options = body or TransferMatchOptions()
    response = await auto_match(db, user.id, window_days=options.window_days)
    await db.commit()
    return response


@router.post("/link", response_model=TransferPairResponse, status_code=201)
async def link_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    body: TransferLinkRequest,
) -> TransferPairResponse:
    """Enlaza dos transacciones explícitamente como par de transferencia."""
    pair = await link_manually(
        db,
        user.id,
        out_transaction_id=body.out_transaction_id,
        in_transaction_id=body.in_transaction_id,
    )
    await db.commit()
    return pair


@router.delete(
    "/{transaction_id}", status_code=204, response_class=Response
)
async def unlink_endpoint(
    transaction_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Deshace el par del que `transaction_id` forma parte (cualquiera
    de las dos mitades sirve)."""
    await unlink(db, user.id, transaction_id)
    await db.commit()
    return Response(status_code=204)


@router.get("/suspects", response_model=list[TransferSuspect])
async def suspects_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TransferSuspect]:
    """PHASE-23: txs candidatas a transferencia interna sin pareja —
    cuya descripción contiene "transfer" y todavía no están marcadas
    como transferencia (categoría kind=transfer)."""
    return await list_suspects(db, user.id)


@router.post("/mark", response_model=TransferMarkResponse, status_code=201)
async def mark_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    body: TransferMarkRequest,
) -> TransferMarkResponse:
    """PHASE-23.1: marca una tx como transferencia interna asignándole
    una categoría con `is_transfer=true` (creándola por defecto si
    no existe). La tx sale del cashflow agregado pero su signo sigue
    impactando al saldo de la cuenta."""
    response = await mark_as_transfer(
        db, user.id, transaction_id=body.transaction_id
    )
    await db.commit()
    return response


@router.post(
    "/from-source", response_model=TransferPairResponse, status_code=201
)
async def from_source_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    body: TransferFromSourceRequest,
) -> TransferPairResponse:
    """PHASE-23.1: convierte una tx existente en una transferencia
    interna creando automáticamente la contraparte en la cuenta destino
    y emparejando ambas vía `transfer_pair_id`. Ambas cuentas reflejan
    el movimiento en sus saldos individuales y el par queda fuera del
    cashflow agregado."""
    pair = await convert_to_internal_transfer(
        db,
        user.id,
        source_transaction_id=body.source_transaction_id,
        originating_account_id=body.originating_account_id,
        beneficiary_account_id=body.beneficiary_account_id,
    )
    await db.commit()
    return pair


@router.post(
    "/from-source-debt",
    response_model=TransferPairResponse,
    status_code=201,
)
async def from_source_debt_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    body: TransferFromSourceDebtRequest,
) -> TransferPairResponse:
    """PHASE-24: convierte una tx en operación financiada (deuda con
    plan de pago). Crea la contraparte en una cuenta liability —
    existente o nueva al vuelo — y empareja ambas. El saldo de la
    liability sube por el importe (deuda contraída) y el par queda
    fuera del cashflow agregado."""
    pair = await convert_to_debt_operation(
        db,
        user.id,
        source_transaction_id=body.source_transaction_id,
        destination_account_id=body.destination_account_id,
        new_liability=body.new_liability,
    )
    await db.commit()
    return pair
