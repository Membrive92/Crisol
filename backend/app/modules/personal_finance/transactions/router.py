"""Router del módulo transactions."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.budgets.service import get_alert_for_category
from app.modules.personal_finance.categories.repository import (
    get_category_by_id,
)
from app.modules.personal_finance.transactions.models import Transaction
from app.modules.personal_finance.transactions.schemas import (
    BudgetAlertSchema,
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdate,
)
from app.modules.personal_finance.transactions.service import (
    bulk_delete_transactions,
    bulk_purge_trashed_transactions,
    bulk_restore_trashed_transactions,
    create_transaction,
    delete_transaction,
    get_transaction,
    list_available_periods,
    list_transactions,
    list_trashed_transactions,
    purge_transaction,
    restore_transaction,
    update_transaction,
)


class BulkDeleteResponse(BaseModel):
    """Respuesta del endpoint DELETE /transactions (bulk)."""

    deleted_count: int


class BulkRestoreResponse(BaseModel):
    """Respuesta del endpoint POST /transactions/trash/restore (bulk)."""

    restored_count: int


class BulkPurgeResponse(BaseModel):
    """Respuesta del endpoint DELETE /transactions/trash (bulk)."""

    purged_count: int


class AvailablePeriodItem(BaseModel):
    """Un año con la lista de meses (1-12) que tienen transacciones."""

    year: int
    months: list[int]


class AvailablePeriodsResponse(BaseModel):
    """Años + meses con al menos una transacción activa para el usuario.

    Sirve para construir filtros rápidos en la UI sin tener que pedir
    al usuario que adivine qué rango introducir, y para no mostrar
    botones de meses que no tienen datos. Excluye papelera.
    """

    periods: list[AvailablePeriodItem]


router = APIRouter(prefix="/transactions", tags=["transactions"])


def _build_response(
    tx: Transaction, converted: Decimal | None, target_currency: str | None
) -> TransactionResponse:
    """Construye la respuesta enriqueciendo con la conversión per-row."""
    payload = TransactionResponse.model_validate(tx)
    if target_currency is not None and converted is not None:
        payload = payload.model_copy(
            update={
                "converted_amount": converted,
                "converted_currency": target_currency.upper(),
            }
        )
    return payload


@router.get("", response_model=TransactionListResponse)
async def list_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TransactionListResponse:
    """Lista transacciones activas con filtros opcionales.

    PHASE-19.4: `account_id` permite filtrar por cuenta. Las
    soft-deleted (PHASE-10.1) NO aparecen aquí — usar `/trash`.

    Si se pasa `target_currency`, cada fila incluye `converted_amount`
    + `converted_currency` (PHASE-8.4) — la UI puede pintar el
    equivalente en moneda activa sin lanzar fetches por fecha.
    """
    items, total = await list_transactions(
        db,
        user.id,
        account_id=account_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        target_currency=target_currency,
        limit=limit,
        offset=offset,
    )
    return TransactionListResponse(
        items=[_build_response(tx, conv, target_currency) for tx, conv in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/trash", response_model=TransactionListResponse)
async def list_trash_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TransactionListResponse:
    """Lista las transacciones en papelera del usuario, ordenadas por
    `deleted_at DESC`. PHASE-10.1.

    Cada fila trae `deleted_at` no-NULL para que la UI pueda pintar
    "borrada hace X días". Sin filtros adicionales — la papelera es
    una vista plana de "qué he borrado recientemente".
    """
    items, total = await list_trashed_transactions(
        db, user.id, limit=limit, offset=offset
    )
    return TransactionListResponse(
        items=[TransactionResponse.model_validate(tx) for tx in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/trash/restore", response_model=BulkRestoreResponse)
async def bulk_restore_trash_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BulkRestoreResponse:
    """Restaura todas las transacciones del usuario que estén en papelera.

    Idempotente: si la papelera está vacía, devuelve 0. Las transacciones
    vuelven al listado activo y al dashboard.
    """
    count = await bulk_restore_trashed_transactions(db, user.id)
    await db.commit()
    return BulkRestoreResponse(restored_count=count)


@router.delete("/trash", response_model=BulkPurgeResponse)
async def bulk_purge_trash_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BulkPurgeResponse:
    """Elimina permanente (DELETE real) todas las transacciones del
    usuario que estén en papelera. Operación IRREVERSIBLE.

    Idempotente: si la papelera está vacía, devuelve 0.
    """
    count = await bulk_purge_trashed_transactions(db, user.id)
    await db.commit()
    return BulkPurgeResponse(purged_count=count)


@router.get("/available-periods", response_model=AvailablePeriodsResponse)
async def available_periods_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AvailablePeriodsResponse:
    """Años + meses con transacciones activas del usuario.

    Lo usa el filtro rápido del listado para mostrar sólo los años
    y los meses que tienen datos, en lugar de listar todos los años
    o forzar los 12 meses fijos. Importante: esta ruta estática debe
    declararse ANTES de `/{transaction_id}` — si no, FastAPI matchea
    "available-periods" como un UUID y devuelve 422.
    """
    periods = await list_available_periods(db, user.id)
    return AvailablePeriodsResponse(
        periods=[
            AvailablePeriodItem(year=year, months=months)
            for year, months in periods
        ]
    )


class UncategorizedSummaryResponse(BaseModel):
    """PHASE-31.3 — Conteo + suma de tx sin categoría para el banner UX."""

    count: int
    total_amount: Decimal
    currency: str


@router.get("/uncategorized-summary", response_model=UncategorizedSummaryResponse)
async def uncategorized_summary_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UncategorizedSummaryResponse:
    """Cuántas tx activas (no papelera) tiene el usuario sin categoría
    y por qué importe total. Alimenta el banner que invita a
    categorizar — tras PHASE-31.3 estas tx ya no contaminan el saldo,
    así que conviene que el usuario las vea explícitamente."""
    from sqlalchemy import func as sql_func

    rows = (
        await db.execute(
            sa_select(
                sql_func.count(Transaction.id),
                sql_func.coalesce(sql_func.sum(Transaction.amount), 0),
                Transaction.currency,
            )
            .where(Transaction.user_id == user.id)
            .where(Transaction.deleted_at.is_(None))
            .where(Transaction.category_id.is_(None))
            .group_by(Transaction.currency)
        )
    ).all()
    # Si el usuario tiene tx sin categoría en varias monedas, devolvemos
    # la moneda mayoritaria (más tx) y el total en esa moneda. Es
    # razonable para el banner — un caso bordes que no debería pasar
    # con un usuario disciplinado.
    if not rows:
        return UncategorizedSummaryResponse(
            count=0, total_amount=Decimal("0"), currency="EUR"
        )
    rows_sorted = sorted(rows, key=lambda r: r[0], reverse=True)
    count, amount, currency = rows_sorted[0]
    total_count = sum(int(r[0]) for r in rows)
    _ = count  # noqa: F841 — kept for clarity above; total_count wins
    return UncategorizedSummaryResponse(
        count=total_count,
        total_amount=Decimal(amount or 0),
        currency=currency,
    )


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_endpoint(
    transaction_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TransactionResponse:
    """Obtiene una transacción activa por ID."""
    transaction = await get_transaction(db, transaction_id, user.id)
    return TransactionResponse.model_validate(transaction)


@router.post("", response_model=TransactionResponse, status_code=201)
async def create_endpoint(
    body: TransactionCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TransactionResponse:
    """Crea una nueva transacción.

    PHASE-14.5: si la nueva tx empuja la categoría afectada (o el
    budget global) a warning/over, la respuesta lleva
    `budget_alert: BudgetAlertSchema` para que el cliente lance una
    notificación proactiva. `None` cuando no hay budget activo o el
    estado sigue en `ok`.
    """
    transaction = await create_transaction(db, user.id, body)
    await db.flush()
    alert = await get_alert_for_category(
        db, user.id, category_id=transaction.category_id
    )
    await db.commit()

    payload = TransactionResponse.model_validate(transaction)
    if alert is not None:
        cat_label: str
        if alert.budget.category_id is None:
            cat_label = "Presupuesto global"
        else:
            cat = await get_category_by_id(
                db, alert.budget.category_id, user.id
            )
            cat_label = cat.name if cat is not None else "Categoría"
        message = (
            f"{cat_label} está al {alert.percent_used:.0f}% del presupuesto."
        )
        payload = payload.model_copy(
            update={
                "budget_alert": BudgetAlertSchema(
                    budget_id=alert.budget.id,
                    category_id=alert.budget.category_id,
                    status=alert.status,
                    percent_used=alert.percent_used,
                    spent_this_month=alert.spent_this_month,
                    amount=alert.budget.amount,
                    currency=alert.budget.currency,
                    next_due_label=message,
                )
            }
        )
    return payload


@router.put("/{transaction_id}", response_model=TransactionResponse)
async def update_endpoint(
    transaction_id: uuid.UUID,
    body: TransactionUpdate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TransactionResponse:
    """Actualiza una transacción existente."""
    transaction = await update_transaction(db, transaction_id, user.id, body)
    await db.commit()
    return TransactionResponse.model_validate(transaction)


@router.delete("", response_model=BulkDeleteResponse)
async def bulk_delete_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    category_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
) -> BulkDeleteResponse:
    """Mueve a papelera todas las transacciones que matcheen los filtros.

    Acepta los mismos filtros que `GET /transactions` para que "borrar
    todo lo que veo" sea exacto. Sin filtros, mueve todas las activas del
    usuario. Idempotente — si ya no hay nada que matchee, devuelve 0.

    Las transacciones se pueden recuperar individualmente desde
    `/transactions/trash`. No hay endpoint de undo masivo: el caller
    puede recordar los IDs antes y restaurarlos uno a uno si lo necesita.
    """
    count = await bulk_delete_transactions(
        db,
        user.id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    await db.commit()
    return BulkDeleteResponse(deleted_count=count)


@router.delete("/{transaction_id}", status_code=204, response_class=Response)
async def delete_endpoint(
    transaction_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Mueve la transacción a papelera (soft-delete, PHASE-10.1).

    Cambio de comportamiento respecto a pre-PHASE-10.1: ya no destruye.
    Para borrar definitivamente, usar `DELETE /transactions/{id}/purge`
    sobre una tx que ya esté en papelera.
    """
    await delete_transaction(db, transaction_id, user.id)
    await db.commit()
    return Response(status_code=204)


@router.post("/{transaction_id}/restore", response_model=TransactionResponse)
async def restore_endpoint(
    transaction_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TransactionResponse:
    """Saca una transacción de la papelera. PHASE-10.1.

    404 si la transacción no existe o no está en papelera.
    """
    transaction = await restore_transaction(db, transaction_id, user.id)
    await db.commit()
    return TransactionResponse.model_validate(transaction)


@router.delete(
    "/{transaction_id}/purge", status_code=204, response_class=Response
)
async def purge_endpoint(
    transaction_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Elimina permanente (DELETE real) una transacción que esté EN
    papelera. PHASE-10.1.

    404 si la transacción no existe o no está en papelera. Para purgar
    una activa primero hacer `DELETE /transactions/{id}` (soft) y luego
    purgar.
    """
    await purge_transaction(db, transaction_id, user.id)
    await db.commit()
    return Response(status_code=204)
