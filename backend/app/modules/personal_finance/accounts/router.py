"""Router del módulo accounts (PHASE-19.1)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.accounts.debt_health import compute_debt_health
from app.modules.personal_finance.accounts.debt_history import compute_debt_history
from app.modules.personal_finance.accounts.schemas import (
    AccountBalancesResponse,
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    AmortizationRowResponse,
    AmortizationScheduleResponse,
    DebtHealthKpis,
    DebtHistoryResponse,
    InstallmentPayRequest,
    InstallmentUpdateRequest,
)
from app.modules.personal_finance.accounts.service import (
    create_account,
    delete_account,
    get_account,
    get_amortization_schedule,
    get_balances,
    list_accounts,
    mark_installment_paid,
    regenerate_amortization_schedule,
    unmark_installment_paid,
    update_account,
    update_installment,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountResponse])
async def list_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    include_archived: Annotated[bool, Query()] = False,
) -> list[AccountResponse]:
    """Lista las cuentas del usuario.

    Por defecto excluye archivadas. Pasa `?include_archived=true`
    para verlas todas (útil en pantallas de gestión).
    """
    accounts = await list_accounts(db, user.id, include_archived=include_archived)
    return [AccountResponse.model_validate(a) for a in accounts]


@router.get("/balances", response_model=AccountBalancesResponse)
async def balances_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountBalancesResponse:
    """Saldo actual de cada cuenta + agregado de patrimonio (PHASE-19.4).

    Cada cuenta devuelve `opening_balance + Σ(income − expense)` en su
    moneda nativa. Sólo cuentas activas suman a los totales. Si las
    monedas activas no son homogéneas, `mixed_currencies=true`.
    """
    return await get_balances(db, user.id)


@router.get("/debt-health", response_model=DebtHealthKpis)
async def debt_health_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DebtHealthKpis:
    """KPIs de salud financiera (PHASE-22.4): DTI, debt-to-assets,
    intereses YTD, APR medio ponderado, proyección de tiempo hasta
    saldar la deuda al ritmo actual.
    """
    return await compute_debt_health(db, user.id)


@router.get("/debt-history", response_model=DebtHistoryResponse)
async def debt_history_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    months_back: Annotated[int, Query(ge=1, le=36)] = 12,
    months_ahead: Annotated[int, Query(ge=0, le=36)] = 12,
) -> DebtHistoryResponse:
    """Serie temporal de evolución de deuda (PHASE-22.1).

    Devuelve un array contiguo con `months_back` puntos históricos
    (meses cerrados) + `months_ahead` puntos proyectados (a partir
    del mes en curso) usando cuadros de amortización y cuota teórica
    de tarjetas. `months_ahead=0` desactiva la proyección.
    """
    return await compute_debt_history(
        db, user.id, months_back=months_back, months_ahead=months_ahead
    )


@router.get(
    "/{account_id}/amortization-schedule",
    response_model=AmortizationScheduleResponse,
)
async def amortization_schedule_endpoint(
    account_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AmortizationScheduleResponse:
    """Cuadro francés de amortización para una liability `loan`/`mortgage`.

    Devuelve la cuota mensual constante, el desglose de cada mes
    (principal vs intereses) y los totales (intereses pagados durante
    todo el plazo, total a pagar). 400 si la cuenta no es liability
    apta o si faltan APR/plazo/fecha de inicio.
    """
    return await get_amortization_schedule(db, account_id, user.id)


@router.post(
    "/{account_id}/amortization-schedule/regenerate",
    response_model=AmortizationScheduleResponse,
)
async def regenerate_amortization_endpoint(
    account_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AmortizationScheduleResponse:
    """PHASE-24.3 — Borra y regenera el cuadro de amortización con
    los datos actuales (apr/term/start). Usa el counterpart tx como
    principal si existe (caso convert-to-debt); si no, opening_balance.
    PIERDE el estado de pago (paid_at) de las cuotas anteriores."""
    schedule = await regenerate_amortization_schedule(db, account_id, user.id)
    await db.commit()
    return schedule


@router.patch(
    "/installments/{installment_id}", response_model=AmortizationRowResponse
)
async def update_installment_endpoint(
    installment_id: uuid.UUID,
    body: InstallmentUpdateRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AmortizationRowResponse:
    """PHASE-24.1: override puntual de importe / fecha de una cuota.
    No recomputa las siguientes."""
    inst = await update_installment(
        db,
        installment_id,
        user.id,
        payment=body.payment,
        due_date=body.due_date,
    )
    await db.commit()
    return AmortizationRowResponse(
        id=inst.id,
        month=inst.installment_index,
        due_date=inst.due_date,
        payment=inst.payment,
        interest=inst.interest,
        principal=inst.principal,
        remaining_balance=inst.remaining_balance,
        paid_at=inst.paid_at,
        paid_transaction_id=inst.paid_transaction_id,
    )


@router.post(
    "/installments/{installment_id}/pay",
    response_model=AmortizationRowResponse,
)
async def pay_installment_endpoint(
    installment_id: uuid.UUID,
    body: InstallmentPayRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AmortizationRowResponse:
    """PHASE-24.1: marca cuota como pagada (timestamp + tx opcional)."""
    inst = await mark_installment_paid(
        db,
        installment_id,
        user.id,
        paid_at=body.paid_at,
        paid_transaction_id=body.paid_transaction_id,
    )
    await db.commit()
    return AmortizationRowResponse(
        id=inst.id,
        month=inst.installment_index,
        due_date=inst.due_date,
        payment=inst.payment,
        interest=inst.interest,
        principal=inst.principal,
        remaining_balance=inst.remaining_balance,
        paid_at=inst.paid_at,
        paid_transaction_id=inst.paid_transaction_id,
    )


@router.delete(
    "/installments/{installment_id}/pay",
    response_model=AmortizationRowResponse,
)
async def unpay_installment_endpoint(
    installment_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AmortizationRowResponse:
    """PHASE-24.1: revierte el estado de la cuota a pendiente."""
    inst = await unmark_installment_paid(db, installment_id, user.id)
    await db.commit()
    return AmortizationRowResponse(
        id=inst.id,
        month=inst.installment_index,
        due_date=inst.due_date,
        payment=inst.payment,
        interest=inst.interest,
        principal=inst.principal,
        remaining_balance=inst.remaining_balance,
        paid_at=inst.paid_at,
        paid_transaction_id=inst.paid_transaction_id,
    )


@router.get("/{account_id}", response_model=AccountResponse)
async def get_endpoint(
    account_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountResponse:
    """Obtiene una cuenta por ID."""
    account = await get_account(db, account_id, user.id)
    return AccountResponse.model_validate(account)


@router.post("", response_model=AccountResponse, status_code=201)
async def create_endpoint(
    body: AccountCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountResponse:
    """Crea una nueva cuenta. 409 si el nombre ya existe para el usuario."""
    account = await create_account(db, user.id, body)
    await db.commit()
    return AccountResponse.model_validate(account)


@router.put("/{account_id}", response_model=AccountResponse)
async def update_endpoint(
    account_id: uuid.UUID,
    body: AccountUpdate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountResponse:
    """Actualiza una cuenta (parcial). Permite archivar via `is_archived=true`."""
    account = await update_account(db, account_id, user.id, body)
    await db.commit()
    return AccountResponse.model_validate(account)


@router.delete("/{account_id}", status_code=204, response_class=Response)
async def delete_endpoint(
    account_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Borra una cuenta sin transacciones. Si tiene histórico, 409 —
    el usuario debe archivarla en su lugar.
    """
    await delete_account(db, account_id, user.id)
    await db.commit()
    return Response(status_code=204)
