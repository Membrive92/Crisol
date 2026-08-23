"""Router del módulo transactions."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.budgets.service import get_alert_for_category
from app.modules.personal_finance.categories.repository import (
    get_category_by_id,
)

# C4 — el portero del ciclo se declara UNA vez en `dashboard.service` y lo
# consumen los dos routers que ganan `cycle`. Duplicarlo aquí dejaría dos
# mensajes de 422 y dos formas de decidir si el ajuste está puesto.
from app.modules.personal_finance.dashboard.service import resolve_cycle_start_day
from app.modules.personal_finance.transactions.models import Transaction

# `ListOrder` es un vocabulario (`Literal`), no lógica: se toma de donde está
# declarado en vez de reexportarlo desde el service, que exigiría un alias
# explícito por `no_implicit_reexport` y crearía un segundo sitio donde puede
# divergir. Mismo patrón que el import de `categories.repository` de arriba.
from app.modules.personal_finance.transactions.repository import ListOrder
from app.modules.personal_finance.transactions.schemas import (
    BudgetAlertSchema,
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdate,
)
from app.modules.personal_finance.transactions.service import (
    bulk_categorize_transactions,
    bulk_delete_transactions,
    bulk_purge_trashed_transactions,
    bulk_reassign_transactions,
    bulk_restore_trashed_transactions,
    create_transaction,
    delete_transaction,
    get_transaction,
    list_available_periods,
    list_transactions,
    list_trashed_transactions,
    purge_transaction,
    restore_transaction,
    uncategorized_summary,
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


class ReassignAccountRequest(BaseModel):
    """PHASE-32 — Reasigna en bloque a `target_account_id` las tx activas
    que matcheen los filtros (mismos que el listado). Útil para consolidar
    un mes en la cuenta principal. Sin filtros, mueve todas las activas
    (excepto transferencias internas)."""

    target_account_id: uuid.UUID
    account_id: uuid.UUID | None = None
    """Filtro: sólo las de esta cuenta origen. NULL = de cualquiera."""
    category_id: uuid.UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    search: str | None = None


class ReassignAccountResponse(BaseModel):
    reassigned_count: int
    # HIGH#3 — tx que matchean los filtros pero NO se movieron por tener una
    # divisa distinta a la de la cuenta destino (se las dejó donde estaban
    # para no sacarlas del saldo). La UI lo informa.
    skipped_other_currency: int = 0


class BulkCategorizeRequest(BaseModel):
    """PHASE-34 — Cambia en bloque la categoría de un conjunto EXPLÍCITO de tx
    (selección por checkbox en la lista), para no recategorizar una a una.
    `category_id=None` quita la categoría."""

    transaction_ids: list[uuid.UUID] = Field(min_length=1, max_length=1000)
    category_id: uuid.UUID | None = None


class BulkCategorizeResponse(BaseModel):
    updated: int


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
    tx: Transaction,
    converted: Decimal | None,
    is_debt_pair: bool,
    target_currency: str | None,
) -> TransactionResponse:
    """Construye la respuesta enriqueciendo con la conversión per-row y
    la señal `is_debt_pair` (que el ORM no lleva como columna).

    AUDIT: `converted` llega de SQL con precisión `Numeric(20, 8)` (8
    decimales). Si se devolviera tal cual, la UI sumaría filas con 8
    decimales y el total no cuadraría con un total cuantizado a
    céntimos. Se cuantiza cada fila a 2 decimales — misma política que
    `dashboard.get_category_detail`/`get_summary` — para que
    `sum(filas) == total` a nivel de presentación.
    """
    update: dict[str, object] = {"is_debt_pair": is_debt_pair}
    if target_currency is not None and converted is not None:
        update["converted_amount"] = converted.quantize(Decimal("0.01"))
        update["converted_currency"] = target_currency.upper()
    return TransactionResponse.model_validate(tx).model_copy(update=update)


@router.get("", response_model=TransactionListResponse)
async def list_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    uncategorized: bool = False,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    debt_only: bool = False,
    order: ListOrder = "desc",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TransactionListResponse:
    """Lista transacciones activas con filtros opcionales.

    PHASE-19.4: `account_id` permite filtrar por cuenta. Las
    soft-deleted (PHASE-10.1) NO aparecen aquí — usar `/trash`.

    `uncategorized=true` filtra las tx sin categoría (atajo "Ver y
    categorizar" del banner); ignora `category_id` si llegan ambos.

    Si se pasa `target_currency`, cada fila incluye `converted_amount`
    + `converted_currency` (PHASE-8.4) — la UI puede pintar el
    equivalente en moneda activa sin lanzar fetches por fecha.

    `order` (`asc | desc`, default `desc`) invierte el sentido por
    `occurred_at`. `asc` sirve para ver las PRIMERAS filas de una ventana
    —la previsualización del ciclo del usuario en Ajustes— sin paginar hasta
    el final. No cambia `total` ni qué filas entran: sólo su orden.
    """
    items, total = await list_transactions(
        db,
        user.id,
        account_id=account_id,
        category_id=category_id,
        uncategorized=uncategorized,
        date_from=date_from,
        date_to=date_to,
        search=search,
        target_currency=target_currency,
        debt_only=debt_only,
        order=order,
        limit=limit,
        offset=offset,
    )
    return TransactionListResponse(
        items=[
            _build_response(tx, conv, is_debt_pair, target_currency)
            for tx, conv, is_debt_pair in items
        ],
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
    items, total = await list_trashed_transactions(db, user.id, limit=limit, offset=offset)
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
    cycle: Annotated[
        bool,
        Query(
            description=(
                "Agrupa por el ciclo del usuario (users.cycle_start_day) en vez "
                "de por mes natural. El día sale del perfil; sin ajuste "
                "configurado, 422."
            )
        ),
    ] = False,
) -> AvailablePeriodsResponse:
    """Años + meses con transacciones activas del usuario.

    Lo usa el filtro rápido del listado para mostrar sólo los años
    y los meses que tienen datos, en lugar de listar todos los años
    o forzar los 12 meses fijos. Importante: esta ruta estática debe
    declararse ANTES de `/{transaction_id}` — si no, FastAPI matchea
    "available-periods" como un UUID y devuelve 422.

    C4 — con `cycle=true` los períodos son anclas de ciclo. El día lo pone el
    perfil, nunca el cliente; `resolve_cycle_start_day` es la MISMA puerta que
    usa el dashboard, para que los dos selectores no puedan responder distinto.
    """
    periods = await list_available_periods(
        db, user.id, cycle_start_day=resolve_cycle_start_day(user.cycle_start_day, cycle)
    )
    return AvailablePeriodsResponse(
        periods=[AvailablePeriodItem(year=year, months=months) for year, months in periods]
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
    así que conviene que el usuario las vea explícitamente.

    AUDIT-2026-05: la agregación vive ahora en service/repository."""
    count, total_amount, currency = await uncategorized_summary(db, user.id)
    return UncategorizedSummaryResponse(
        count=count,
        total_amount=total_amount,
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
        db,
        user.id,
        category_id=transaction.category_id,
        cycle_start_day=user.cycle_start_day,
    )
    await db.commit()

    payload = TransactionResponse.model_validate(transaction)
    if alert is not None:
        cat_label: str
        if alert.budget.category_id is None:
            cat_label = "Presupuesto global"
        else:
            cat = await get_category_by_id(db, alert.budget.category_id, user.id)
            cat_label = cat.name if cat is not None else "Categoría"
        message = f"{cat_label} está al {alert.percent_used:.0f}% del presupuesto."
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
    account_id: uuid.UUID | None = None,
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
        account_id=account_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    await db.commit()
    return BulkDeleteResponse(deleted_count=count)


@router.post("/reassign-account", response_model=ReassignAccountResponse)
async def reassign_account_endpoint(
    body: ReassignAccountRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReassignAccountResponse:
    """PHASE-32 — Mueve en bloque a la cuenta destino las transacciones
    activas que matcheen los filtros (mismos que `GET /transactions`).

    Pensado para consolidar "el mes en mi cuenta principal (BBVA)": el
    saldo de la cuenta destino pasa a reflejar esos movimientos. Excluye
    transferencias internas (mover una pata rompería el par) y las que ya
    están en la cuenta destino. 404 si la cuenta destino no es del usuario.

    HIGH#3 — sólo mueve tx de la MISMA divisa que la cuenta destino; las de
    otra divisa se quedan donde están (moverlas las sacaría del saldo) y se
    reportan en `skipped_other_currency`.
    """
    count, skipped = await bulk_reassign_transactions(
        db,
        user.id,
        target_account_id=body.target_account_id,
        account_id=body.account_id,
        category_id=body.category_id,
        date_from=body.date_from,
        date_to=body.date_to,
        search=body.search,
    )
    await db.commit()
    return ReassignAccountResponse(reassigned_count=count, skipped_other_currency=skipped)


@router.post("/bulk-categorize", response_model=BulkCategorizeResponse)
async def bulk_categorize_endpoint(
    body: BulkCategorizeRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BulkCategorizeResponse:
    """PHASE-34 — Cambia la categoría de las tx seleccionadas (checkbox) de una
    vez. Relabel puro: no toca el dinero (flow / par de transferencia), sólo la
    etiqueta. 400 si `category_id` no es del usuario."""
    updated = await bulk_categorize_transactions(
        db,
        user.id,
        transaction_ids=body.transaction_ids,
        category_id=body.category_id,
    )
    await db.commit()
    return BulkCategorizeResponse(updated=updated)


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


@router.delete("/{transaction_id}/purge", status_code=204, response_class=Response)
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
