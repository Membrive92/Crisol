"""Lógica de negocio del módulo receipts.

Flujo principal:

    extract: subir imagen → MinIO → ai.service.extract_receipt →
             persist Receipt(status=pending).
    confirm: leer Receipt(pending) → crear Transaction → marcar
             status=confirmed y enlazar transaction_id.
    reject : marcar status=rejected (no se crea transacción).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.modules.ai import service as ai_service
from app.modules.ai.exceptions import AiError
from app.modules.ai.schemas import ReceiptExtraction
from app.modules.personal_finance.accounts.service import ensure_account_exists
from app.modules.personal_finance.categories.repository import get_category_by_id
from app.modules.personal_finance.receipts.models import Receipt, ReceiptStatus
from app.modules.personal_finance.receipts.repository import create_receipt, get_receipt_by_id
from app.modules.personal_finance.receipts.schemas import ReceiptConfirmRequest
from app.modules.personal_finance.transactions.models import Transaction, TransactionSource

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}


async def extract_and_persist(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    payload: bytes,
    content_type: str,
) -> tuple[Receipt, ReceiptExtraction]:
    """Sube la imagen, llama al modelo y guarda el receipt en `pending`."""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de imagen no soportado: {content_type}",
        )

    blob_key = storage.put_receipt(user_id, payload, content_type)

    try:
        extraction = await ai_service.extract_receipt(payload)
    except AiError as e:
        # Limpiamos el blob si la IA falla — no queremos huérfanos.
        storage.delete_receipt(blob_key)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Extracción fallida: {e}",
        ) from e

    receipt = Receipt(
        user_id=user_id,
        status=ReceiptStatus.PENDING,
        blob_key=blob_key,
        content_type=content_type,
        extraction=_serialize_extraction(extraction),
    )
    receipt = await create_receipt(db, receipt)
    return receipt, extraction


async def confirm_receipt(
    db: AsyncSession,
    user_id: uuid.UUID,
    receipt_id: uuid.UUID,
    payload: ReceiptConfirmRequest,
) -> Receipt:
    """Crea la transacción asociada y marca el recibo `confirmed`."""
    receipt = await get_receipt_by_id(db, receipt_id, user_id)
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recibo no encontrado")
    if receipt.status != ReceiptStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El recibo está en estado {receipt.status}, no pendiente",
        )

    if payload.category_id is not None:
        cat = await get_category_by_id(db, payload.category_id, user_id)
        if cat is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="category_id no pertenece al usuario",
            )

    await ensure_account_exists(db, payload.account_id, user_id)

    transaction = Transaction(
        user_id=user_id,
        account_id=payload.account_id,
        category_id=payload.category_id,
        amount=payload.amount,
        currency=payload.currency.upper(),
        occurred_at=payload.occurred_at,
        description=payload.description,
        source=TransactionSource.RECEIPT,
        receipt_id=receipt.id,
    )
    db.add(transaction)
    await db.flush()
    await db.refresh(transaction)

    receipt.status = ReceiptStatus.CONFIRMED
    receipt.transaction_id = transaction.id
    await db.flush()
    await db.refresh(receipt)
    return receipt


async def reject_receipt(
    db: AsyncSession,
    user_id: uuid.UUID,
    receipt_id: uuid.UUID,
) -> Receipt:
    """Marca el recibo `rejected` (irreversible). No crea transacción."""
    receipt = await get_receipt_by_id(db, receipt_id, user_id)
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recibo no encontrado")
    if receipt.status != ReceiptStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El recibo está en estado {receipt.status}, no pendiente",
        )
    receipt.status = ReceiptStatus.REJECTED
    await db.flush()
    await db.refresh(receipt)
    return receipt


def _serialize_extraction(extraction: ReceiptExtraction) -> dict[str, Any]:
    """Serializa la extracción a dict JSON-friendly (Decimal → str)."""
    return extraction.model_dump(mode="json")
