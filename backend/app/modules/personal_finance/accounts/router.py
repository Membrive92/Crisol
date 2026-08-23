"""Router del módulo accounts (PHASE-19.1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.accounts.position_history import (
    compute_position_as_of,
    compute_position_history,
)
from app.modules.personal_finance.accounts.schemas import (
    AccountBalancesResponse,
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    PositionAsOfResponse,
    PositionHistoryResponse,
    ReconcileBalanceRequest,
    SettlementCandidateResponse,
)
from app.modules.personal_finance.accounts.service import (
    create_account,
    delete_account,
    get_account,
    get_amortization_schedule,
    get_balances,
    list_accounts,
    mark_installment_paid,
    pay_installments_by_principal,
    reconcile_account_balance,
    regenerate_amortization_schedule,
    unmark_installment_paid,
    update_account,
    update_installment,
)
from app.modules.personal_finance.debt.attribution import suggest_settlement_account
from app.modules.personal_finance.debt.health import compute_debt_health
from app.modules.personal_finance.debt.history import compute_debt_history
from app.modules.personal_finance.debt.reconciliation import reconcile_debt_payments
from app.modules.personal_finance.debt.schemas import (
    AmortizationRowResponse,
    AmortizationScheduleResponse,
    DebtHealthKpis,
    DebtHistoryResponse,
    InstallmentBulkPayRequest,
    InstallmentBulkPayResponse,
    InstallmentPayRequest,
    InstallmentUpdateRequest,
    ReconcilePlanResponse,
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
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> AccountBalancesResponse:
    """Saldo actual de cada cuenta + agregado de patrimonio (PHASE-19.4).

    Cada cuenta devuelve `opening_balance + Σ(income − expense)` en su
    moneda nativa. Sólo cuentas activas suman a los totales. Si las
    monedas activas no son homogéneas, `mixed_currencies=true`.

    AUDIT-2026-06 (#net-worth-mixed-currencies) — `?target_currency=`
    convierte cada saldo a esa moneda con la tasa de hoy y excluye las
    cuentas sin tasa, devolviendo un agregado con sentido en vez de una
    suma cruda de monedas mezcladas. Sin el parámetro, modo crudo + flag.
    """
    return await get_balances(db, user.id, target_currency=target_currency)


@router.get("/debt-health", response_model=DebtHealthKpis)
async def debt_health_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> DebtHealthKpis:
    """KPIs de salud financiera (PHASE-22.4): DTI, debt-to-assets,
    intereses YTD, APR medio ponderado, proyección de tiempo hasta
    saldar la deuda al ritmo actual.

    PHASE-30.6 — `?target_currency=` convierte saldos a esa moneda
    (snapshot today) y aplica per-tx conversion al income e
    intereses YTD. Saldos sin tasa quedan excluidos del agregado.
    """
    return await compute_debt_health(
        db,
        user.id,
        target_currency=target_currency,
        # PHASE-47 — el DTI divide por el ingreso medio mensual, y «mes» es el
        # del usuario: con corte a mitad, el mes natural le mete dos nóminas en
        # unos meses y ninguna en otros.
        cycle_start_day=user.cycle_start_day,
    )


@router.get("/debt-history", response_model=DebtHistoryResponse)
async def debt_history_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    months_back: Annotated[int, Query(ge=1, le=36)] = 12,
    months_ahead: Annotated[int, Query(ge=0, le=36)] = 12,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> DebtHistoryResponse:
    """Serie temporal de evolución de deuda (PHASE-22.1).

    Devuelve un array contiguo con `months_back` puntos históricos
    (meses cerrados) + `months_ahead` puntos proyectados (a partir
    del mes en curso) usando cuadros de amortización y cuota teórica
    de tarjetas. `months_ahead=0` desactiva la proyección.

    PHASE-30.6 — `?target_currency=` aplica per-tx conversion al
    histórico (intereses + principal) y convierte cada saldo / cuota
    proyectada al target con la tasa de hoy.
    """
    return await compute_debt_history(
        db,
        user.id,
        months_back=months_back,
        months_ahead=months_ahead,
        target_currency=target_currency,
    )


@router.get("/position-history", response_model=PositionHistoryResponse)
async def position_history_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    months_back: Annotated[int, Query(ge=1, le=36)] = 12,
    months_forward: Annotated[int, Query(ge=0, le=36)] = 0,
) -> PositionHistoryResponse:
    """PHASE-37.1 — Serie temporal de patrimonio (activos / pasivos / neto).

    `months_back` puntos históricos (meses cerrados) + `months_forward`
    proyectados (activos planos + deuda por cuadro teórico). Mono-divisa
    (divisa de referencia), misma limitación que `/accounts/balances`.
    """
    return await compute_position_history(
        db,
        user.id,
        months_back=months_back,
        months_forward=months_forward,
    )


@router.get("/position-as-of", response_model=PositionAsOfResponse)
async def position_as_of_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: Annotated[datetime, Query()],
    date_to: Annotated[datetime, Query()],
) -> PositionAsOfResponse:
    """PHASE-41 — Patrimonio a fecha `date_to` + Δ del patrimonio durante
    `[date_from, date_to]`. Para que las cards de patrimonio del Análisis
    reflejen el período elegido (no una foto de hoy). Mono-divisa."""
    return await compute_position_as_of(db, user.id, date_from=date_from, date_to=date_to)


@router.post("/reconcile-debt", response_model=ReconcilePlanResponse)
async def reconcile_debt_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    dry_run: Annotated[bool, Query()] = True,
) -> ReconcilePlanResponse:
    """PHASE-36 — Reconcilia las aportaciones (amortización de préstamo,
    cuotas de operación financiada con tarjeta) contra el cuadro de cada
    deuda: genera el cuadro que falte, ancla las cuotas previas a los datos
    y marca pagada la cuota que cada aportación liquida, de modo que la
    deuda baje de forma realista ("el cuadro manda").

    `dry_run=true` (por defecto) sólo devuelve el plan sin escribir nada.
    `dry_run=false` lo aplica (idempotente). Devuelve el plan/serializado.
    """
    plan = await reconcile_debt_payments(db, user.id, dry_run=dry_run)
    if not dry_run:
        await db.commit()
    return ReconcilePlanResponse.model_validate(plan)


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


@router.patch("/installments/{installment_id}", response_model=AmortizationRowResponse)
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


@router.post(
    "/{account_id}/pay-installments",
    response_model=InstallmentBulkPayResponse,
)
async def pay_installments_endpoint(
    account_id: uuid.UUID,
    body: InstallmentBulkPayRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InstallmentBulkPayResponse:
    """AUDIT-2026-07 (H-05): marca las cuotas que un pago de principal cubre.

    Lo llama el asistente "Pagar cuota" tras crear la transferencia del
    principal, para que el saldo dirigido por el cuadro (PHASE-36) baje.
    """
    marked, covered, uncovered, outstanding = await pay_installments_by_principal(
        db,
        account_id,
        user.id,
        principal_amount=body.principal_amount,
        paid_at=body.paid_at,
        paid_transaction_id=body.paid_transaction_id,
    )
    await db.commit()
    return InstallmentBulkPayResponse(
        marked_count=marked,
        covered_principal=covered,
        uncovered_principal=uncovered,
        schedule_outstanding=outstanding,
    )


@router.get(
    "/{account_id}/settlement-candidate",
    response_model=SettlementCandidateResponse,
)
async def settlement_candidate_endpoint(
    account_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SettlementCandidateResponse:
    """PHASE-47.A — Desde qué cuenta de activo parece cobrarse este pasivo.

    Cuenta los cargos que el usuario ya enlazó a mano (PHASE-45) y devuelve la
    cuenta mayoritaria con su recuento. Sin evidencia —o con empate— devuelve
    una propuesta vacía: el sistema propone, no adivina (ADR-0011). No escribe
    nada; declararlo sigue siendo un `PUT` del usuario.
    """
    await get_account(db, account_id, user.id)  # 404 y pertenencia
    suggestion = await suggest_settlement_account(db, user.id, account_id)
    return SettlementCandidateResponse(
        account_id=suggestion.account_id,
        account_name=suggestion.account_name,
        reason=suggestion.reason,
        matches=suggestion.matches,
        total=suggestion.total,
    )


# ── Rutas paramétricas de un solo segmento, AL FINAL ────────────────────────
# PHASE-47.A (D13) — FastAPI resuelve por orden de declaración, así que
# `/{account_id}` a secas tiene que ir DESPUÉS de todas las rutas nombradas
# (`/balances`, `/debt-health`, `/position-as-of`…): declarada antes, se
# tragaría cada una de ellas intentando parsear su nombre como UUID. Cualquier
# ruta nombrada nueva va ARRIBA de esta línea.
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


@router.post("/{account_id}/reconcile", response_model=AccountResponse)
async def reconcile_endpoint(
    account_id: uuid.UUID,
    body: ReconcileBalanceRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountResponse:
    """PHASE-34 'Cuadrar saldo' — fija el saldo de la cuenta (de activo) al
    valor real que declara el usuario, ajustando `opening_balance`. Sirve para
    el saldo inicial y para re-cuadrar. 400 si la cuenta no es de activo."""
    account = await reconcile_account_balance(db, user.id, account_id, body.current_balance)
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
