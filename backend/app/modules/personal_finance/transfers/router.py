"""Router del módulo transfers (PHASE-19.3).

PHASE-41 (ADR-0005) — retirado el emparejado heurístico (GET /transfers,
/candidates, /match, /suspects, /mark). La verdad del dinero vive en
`transactions.flow`, así que esa maquinaria ya no corrige nada. Se conserva:
- `link`/`unlink`: load-bearing del asistente de pago de deuda y del "deshacer"
  desde la lista de transacciones.
- `from-source`/`from-source-debt`: convertir una tx en transferencia/deuda
  desde el detalle de transacción.
- `misclassified`/`reclassify-bulk`: data-hygiene de dirección, ahora
  embebida en la pestaña Transacciones.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.transfers.schemas import (
    MisclassifiedTransfer,
    ReclassifyBulkRequest,
    ReclassifyBulkResponse,
    TransferFromSourceDebtRequest,
    TransferFromSourceRequest,
    TransferLinkRequest,
    TransferPairResponse,
)
from app.modules.personal_finance.transfers.service import (
    convert_to_debt_operation,
    convert_to_internal_transfer,
    link_manually,
    list_misclassified,
    reclassify_bulk,
    unlink,
)

router = APIRouter(prefix="/transfers", tags=["transfers"])


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


@router.delete("/{transaction_id}", status_code=204, response_class=Response)
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


@router.get("/misclassified", response_model=list[MisclassifiedTransfer])
async def misclassified_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[MisclassifiedTransfer]:
    """PHASE-31.2: tx con categoría is_transfer cuyo kind no encaja
    con la dirección de la descripción (ej. RECIBIDA en categoría
    EXPENSE). Candidatas a recategorización en bloque desde la UI."""
    return await list_misclassified(db, user.id)


@router.post("/reclassify-bulk", response_model=ReclassifyBulkResponse)
async def reclassify_bulk_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    body: ReclassifyBulkRequest,
) -> ReclassifyBulkResponse:
    """PHASE-31.2: recategoriza en bloque tx mal direccionadas. Sin
    `target_category_id` el service asigna a cada tx la categoría
    is_transfer del kind opuesto al actual (el caso típico tras
    detectar bulk: las inbounds van a INCOME, las outbounds a
    EXPENSE)."""
    response = await reclassify_bulk(
        db,
        user.id,
        transaction_ids=body.transaction_ids,
        target_category_id=body.target_category_id,
    )
    await db.commit()
    return response


@router.post("/from-source", response_model=TransferPairResponse, status_code=201)
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
