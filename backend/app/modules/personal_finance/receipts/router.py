"""Router del módulo receipts."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.uploads import read_upload_capped
from app.modules.ai.schemas import ReceiptExtraction
from app.modules.personal_finance.receipts.repository import get_receipt_by_id, list_receipts
from app.modules.personal_finance.receipts.schemas import (
    ReceiptConfirmRequest,
    ReceiptExtractResponse,
    ReceiptListResponse,
    ReceiptResponse,
)
from app.modules.personal_finance.receipts.service import (
    confirm_receipt,
    extract_and_persist,
    reject_receipt,
)

router = APIRouter(prefix="/receipts", tags=["receipts"])

# 8 MB. Suficiente para fotos de móvil; evita imágenes RAW gigantes.
MAX_RECEIPT_BYTES = 8 * 1024 * 1024


@router.post(
    "/extract",
    response_model=ReceiptExtractResponse,
    status_code=status.HTTP_201_CREATED,
)
async def extract_receipt_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File(...)],
) -> ReceiptExtractResponse:
    """Sube una imagen de ticket, ejecuta extracción IA y devuelve el job."""
    # AUDIT-2026-07 (LOW): lee con tope acumulado (aborta 413 en cuanto se
    # supera el límite) en vez de cargar la imagen entera antes de medirla.
    payload = await read_upload_capped(
        file,
        MAX_RECEIPT_BYTES,
        detail=f"La imagen supera {MAX_RECEIPT_BYTES // (1024 * 1024)} MB",
    )
    if not payload:
        raise HTTPException(status_code=400, detail="La imagen está vacía")

    content_type = (file.content_type or "").lower() or "application/octet-stream"

    receipt, extraction = await extract_and_persist(
        db,
        user.id,
        payload=payload,
        content_type=content_type,
    )
    await db.commit()
    return ReceiptExtractResponse(
        receipt=ReceiptResponse.model_validate(receipt),
        extraction=extraction,
    )


@router.post(
    "/{receipt_id}/confirm",
    response_model=ReceiptResponse,
    status_code=status.HTTP_200_OK,
)
async def confirm_receipt_endpoint(
    receipt_id: uuid.UUID,
    payload: ReceiptConfirmRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReceiptResponse:
    """Confirma el recibo, crea la transacción asociada y devuelve el receipt."""
    receipt = await confirm_receipt(db, user.id, receipt_id, payload)
    await db.commit()
    return ReceiptResponse.model_validate(receipt)


@router.post(
    "/{receipt_id}/reject",
    response_model=ReceiptResponse,
    status_code=status.HTTP_200_OK,
)
async def reject_receipt_endpoint(
    receipt_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReceiptResponse:
    """Rechaza el recibo (no crea transacción)."""
    receipt = await reject_receipt(db, user.id, receipt_id)
    await db.commit()
    return ReceiptResponse.model_validate(receipt)


@router.get("", response_model=ReceiptListResponse)
async def list_receipts_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ReceiptListResponse:
    """Lista paginada de recibos del usuario, más recientes primero."""
    items, total = await list_receipts(db, user.id, limit=limit, offset=offset)
    return ReceiptListResponse(
        items=[ReceiptResponse.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{receipt_id}", response_model=ReceiptResponse)
async def get_receipt_endpoint(
    receipt_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReceiptResponse:
    """Detalle de un recibo concreto."""
    receipt = await get_receipt_by_id(db, receipt_id, user.id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Recibo no encontrado")
    return ReceiptResponse.model_validate(receipt)


@router.get("/{receipt_id}/blob")
async def get_receipt_blob_endpoint(
    receipt_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Devuelve el binario de la imagen del recibo desde MinIO.

    Aislamiento: el receipt se busca por `user_id`, así que un usuario
    nunca puede pedir el blob de otro. La descarga se hace en el backend
    (no presigned URL) para mantener el control de acceso vía JWT y
    evitar exponer credenciales de MinIO.
    """
    receipt = await get_receipt_by_id(db, receipt_id, user.id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Recibo no encontrado")
    try:
        payload = await storage.get_receipt(receipt.blob_key)
    except storage.StorageError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se pudo recuperar la imagen",
        ) from e
    return Response(
        content=payload,
        media_type=receipt.content_type or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"},
    )


# Para que el módulo `ai/schemas` cargue eager las dependencias del response model
_ = ReceiptExtraction
