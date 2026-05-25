"""Lógica de negocio del módulo accounts (PHASE-19.1, PHASE-19.4)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.models import (
    Account,
    AccountNature,
    AccountType,
)
from app.modules.personal_finance.accounts.repository import (
    count_transactions_for_account,
    create_account as persist_account,
    delete_account as remove_account,
    get_account_by_id,
    get_account_by_name,
    get_balances_for_user,
    list_accounts as list_all,
)
from app.modules.personal_finance.accounts.amortization import build_schedule
from app.modules.personal_finance.accounts.installments_model import (
    LiabilityInstallment,
)
from app.modules.personal_finance.accounts.installments_repository import (
    generate_installments_for_account,
    get_installment as repo_get_installment,
    list_installments as repo_list_installments,
    mark_installment_paid as repo_mark_paid,
    unmark_installment_paid as repo_unmark_paid,
    update_installment_amount_and_date as repo_update_installment,
)
from app.modules.personal_finance.accounts.schemas import (
    ASSET_ACCOUNT_TYPES,
    LIABILITY_ACCOUNT_TYPES,
    AccountBalance,
    AccountBalancesResponse,
    AccountCreate,
    AccountUpdate,
    AmortizationRowResponse,
    AmortizationScheduleResponse,
)


def _nature_for_type(account_type: AccountType) -> AccountNature:
    """Asigna `nature` automáticamente según el `type` (PHASE-22)."""
    if account_type in LIABILITY_ACCOUNT_TYPES:
        return AccountNature.LIABILITY
    return AccountNature.ASSET

DEFAULT_REFERENCE_CURRENCY = "EUR"

# PHASE-31.4 — tipos de cuenta cuya valoración real no se computa por
# `Σ(movimientos)` mientras no exista un módulo de inversión propio.
# Quedan visibles en `items` (display + destino de transferencias) pero
# fuera del agregado de patrimonio neto. Se reincorporarán cuando el
# módulo de inversiones (locked en el registry) llegue con valoración
# real (precio de mercado × cantidad).
_UNVALUED_ACCOUNT_TYPES = frozenset({AccountType.BROKERAGE, AccountType.CRYPTO})


async def list_accounts(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    include_archived: bool = False,
) -> list[Account]:
    """Lista las cuentas del usuario."""
    return await list_all(db, user_id, include_archived=include_archived)


async def get_account(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID
) -> Account:
    """Obtiene una cuenta o lanza 404."""
    account = await get_account_by_id(db, account_id, user_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cuenta no encontrada"
        )
    return account


async def ensure_account_exists(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID
) -> Account:
    """Igual que `get_account` — alias semántico para callers (transactions,
    imports) que sólo quieren validar pertenencia antes de asociar.
    """
    return await get_account(db, account_id, user_id)


async def create_account(
    db: AsyncSession, user_id: uuid.UUID, data: AccountCreate
) -> Account:
    """Crea una nueva cuenta para el usuario.

    Validaciones:
    - El nombre no puede repetirse (case-insensitive) entre cuentas
      del mismo usuario.
    - El tipo debe estar entre los soportados (assets o liabilities).
    - `nature` se asigna automáticamente según el tipo.
    - Los campos de amortización (`apr`, `term_months`, `start_date`)
      sólo aplican a `loan` / `mortgage`. Para otros tipos se ignoran.
    """
    valid_types = ASSET_ACCOUNT_TYPES | LIABILITY_ACCOUNT_TYPES
    if data.type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de cuenta no soportado.",
        )
    duplicate = await get_account_by_name(db, user_id, name=data.name)
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya tienes una cuenta con ese nombre.",
        )
    # Para loan/mortgage el principal es indispensable: sin él la
    # generación del cuadro silenciosamente devuelve 0 cuotas y queda
    # una cuenta en estado roto (saldo 0, sin cuadro, sin contribución
    # a debt-health). Rechazamos en el endpoint antes de persistir.
    # credit_card se permite con opening_balance=0 porque la deuda
    # puede modelarse vía la tx contraparte (flujo convert-to-debt).
    if data.type in {AccountType.LOAN, AccountType.MORTGAGE}:
        if data.opening_balance is None or data.opening_balance <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "El capital del préstamo o hipoteca es obligatorio "
                    "y debe ser mayor que 0."
                ),
            )
    accepts_amortization = data.type in {
        AccountType.LOAN,
        AccountType.MORTGAGE,
        AccountType.CREDIT_CARD,  # PHASE-24.2: tarjetas financiadas con plan fijo.
    }
    account = Account(
        user_id=user_id,
        name=data.name,
        type=data.type,
        nature=_nature_for_type(data.type),
        currency=data.currency.upper(),
        color=data.color,
        icon=data.icon,
        opening_balance=data.opening_balance,
        opening_balance_date=data.opening_balance_date,
        apr=data.apr if accepts_amortization else None,
        tae=data.tae if accepts_amortization else None,
        term_months=data.term_months if accepts_amortization else None,
        start_date=data.start_date if accepts_amortization else None,
        total_to_pay=data.total_to_pay if accepts_amortization else None,
        interest_only_first_payment=(
            data.interest_only_first_payment if accepts_amortization else None
        ),
        display_order=data.display_order,
    )
    persisted = await persist_account(db, account)
    # PHASE-24.1: si es loan/mortgage con todos los campos, generar las
    # cuotas persistidas inmediatamente para que el editor del cuadro
    # tenga datos desde el minuto cero. Idempotente.
    if accepts_amortization:
        await generate_installments_for_account(db, persisted)
    return persisted


async def update_account(
    db: AsyncSession,
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    data: AccountUpdate,
) -> Account:
    """Actualiza campos de la cuenta. `nature` se re-sincroniza si
    cambia el `type`.
    """
    account = await get_account(db, account_id, user_id)
    payload = data.model_dump(exclude_unset=True)
    valid_types = ASSET_ACCOUNT_TYPES | LIABILITY_ACCOUNT_TYPES
    if "type" in payload and payload["type"] is not None:
        new_type = payload["type"]
        if new_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tipo de cuenta no soportado.",
            )
        # Sincronizar nature con el nuevo type.
        account.nature = _nature_for_type(new_type)
    if "name" in payload and payload["name"] is not None:
        duplicate = await get_account_by_name(db, user_id, name=payload["name"])
        if duplicate is not None and duplicate.id != account.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya tienes una cuenta con ese nombre.",
            )
    if "currency" in payload and payload["currency"] is not None:
        payload["currency"] = payload["currency"].upper()
    for field, value in payload.items():
        setattr(account, field, value)
    await db.flush()
    await db.refresh(account)
    return account


async def delete_account(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Borra una cuenta sin transacciones; si tiene, fuerza al caller
    a archivarla en su lugar.

    `ON DELETE CASCADE` en `transactions.account_id` borraría también
    el histórico de la cuenta — no queremos que el usuario lo haga
    accidentalmente. La política aquí es: archivar si hay datos,
    DELETE real sólo si está completamente vacía.
    """
    account = await get_account(db, account_id, user_id)
    tx_count = await count_transactions_for_account(db, account_id, user_id)
    if tx_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"La cuenta tiene {tx_count} transacciones. "
                "Archívala en lugar de borrarla para conservar el histórico."
            ),
        )
    await remove_account(db, account)


async def get_balances(
    db: AsyncSession, user_id: uuid.UUID
) -> AccountBalancesResponse:
    """Saldo por cuenta + agregados de patrimonio (PHASE-19.4).

    Sólo cuentas no archivadas entran en los totales agregados, pero
    `items` incluye también las archivadas (display sólo). Si las
    monedas activas no son homogéneas, `mixed_currencies=True` y los
    totales son suma cruda — la UI debe avisarlo.
    """
    accounts = await list_all(db, user_id, include_archived=True)
    movements = await get_balances_for_user(db, user_id)

    items: list[AccountBalance] = []
    active_currencies: set[str] = set()
    total_assets = Decimal("0")
    total_liabilities = Decimal("0")

    for account in accounts:
        movements_balance = movements.get(account.id, Decimal("0"))
        current_balance = account.opening_balance + movements_balance
        is_unvalued = account.type in _UNVALUED_ACCOUNT_TYPES
        items.append(
            AccountBalance(
                account_id=account.id,
                name=account.name,
                type=account.type,
                nature=account.nature,
                currency=account.currency,
                color=account.color,
                icon=account.icon,
                opening_balance=account.opening_balance,
                movements_balance=movements_balance,
                current_balance=current_balance,
                is_unvalued=is_unvalued,
            )
        )
        if account.is_archived:
            continue
        active_currencies.add(account.currency)
        # PHASE-31.4 — brokerage/crypto no entran al agregado de
        # patrimonio: su valor real depende del mercado y `Σ(movimientos)`
        # no lo representa. Siguen visibles en `items` y siendo destino
        # válido de transferencias.
        if is_unvalued:
            continue
        if account.nature == AccountNature.LIABILITY:
            total_liabilities += current_balance
        else:
            total_assets += current_balance

    mixed_currencies = len(active_currencies) > 1
    if active_currencies:
        # Determinista: el primero por display_order/name de la lista
        # es la primera cuenta activa.
        for account in accounts:
            if not account.is_archived:
                reference_currency = account.currency
                break
        else:
            reference_currency = DEFAULT_REFERENCE_CURRENCY
    else:
        reference_currency = DEFAULT_REFERENCE_CURRENCY

    return AccountBalancesResponse(
        items=items,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        net_worth=total_assets - total_liabilities,
        mixed_currencies=mixed_currencies,
        reference_currency=reference_currency,
    )


def _compute_extra_charges(
    *,
    total_to_pay: Decimal | None,
    installments_total: Decimal,
    interest_only: Decimal | None,
) -> Decimal | None:
    """PHASE-24.3 — Calcula cargos extra dinámicamente como
    `total_to_pay − Σ(cuotas) − interest_only_first_payment`.

    Devuelve None si no hay `total_to_pay` declarado. 0 cuando el
    cuadro teórico cuadra exactamente con lo que el banco
    contractualiza. Positivo cuando hay comisiones ocultas (~1-2%
    del principal en el caso BBVA típico).

    No corregimos a negativo: si el banco contractualiza MENOS que
    nuestro cálculo, lo dejamos como diferencia negativa para que el
    usuario vea el desajuste y revise sus parámetros (ej. TIN
    incorrecto).
    """
    if total_to_pay is None:
        return None
    base = installments_total + (interest_only or Decimal("0"))
    return total_to_pay - base



async def get_amortization_schedule(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID
) -> AmortizationScheduleResponse:
    """PHASE-22.3 + PHASE-24.1: lee el cuadro de amortización desde
    `liability_installments` (persistido + editable). Fallback a cálculo
    on-the-fly desde `opening_balance` si no hay cuotas persistidas y
    los campos del cuadro están presentes (compat con cuentas legacy).

    Errores:
    - 404 si la cuenta no es del usuario.
    - 400 si la cuenta no es liability tipo `loan`/`mortgage`.
    - 400 si faltan APR/plazo/fecha o no hay cuotas.
    """
    account = await get_account(db, account_id, user_id)
    if account.type not in {
        AccountType.LOAN,
        AccountType.MORTGAGE,
        AccountType.CREDIT_CARD,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "El cuadro de amortización sólo aplica a préstamos, "
                "hipotecas y tarjetas financiadas con plan fijo."
            ),
        )
    if account.apr is None or account.term_months is None or account.start_date is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faltan APR, plazo o fecha de inicio para generar el cuadro.",
        )

    installments = await repo_list_installments(db, account_id, user_id)
    if installments:
        # Path PHASE-24.1: cuotas persistidas (con overrides y estado de pago).
        total_paid = sum((i.payment for i in installments), Decimal("0"))
        total_interest = sum((i.interest for i in installments), Decimal("0"))
        monthly_payment = installments[0].payment
        # `principal` para mostrar en cabecera: derivado de la primera cuota
        # (principal_1 + remaining_balance_1 = principal total).
        first = installments[0]
        principal_total = first.principal + first.remaining_balance
        extra = _compute_extra_charges(
            total_to_pay=account.total_to_pay,
            installments_total=total_paid,
            interest_only=account.interest_only_first_payment,
        )
        return AmortizationScheduleResponse(
            account_id=account.id,
            principal=principal_total,
            apr=account.apr,
            tae=account.tae,
            term_months=account.term_months,
            start_date=account.start_date,
            monthly_payment=monthly_payment,
            total_interest=total_interest,
            total_paid=total_paid,
            interest_only_first_payment=account.interest_only_first_payment,
            total_to_pay=account.total_to_pay,
            extra_charges=extra,
            rows=[
                AmortizationRowResponse(
                    id=i.id,
                    month=i.installment_index,
                    due_date=i.due_date,
                    payment=i.payment,
                    interest=i.interest,
                    principal=i.principal,
                    remaining_balance=i.remaining_balance,
                    paid_at=i.paid_at,
                    paid_transaction_id=i.paid_transaction_id,
                )
                for i in installments
            ],
        )

    # Fallback PHASE-22.3 (cuentas legacy sin cuotas persistidas).
    if account.opening_balance <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El saldo inicial debe ser positivo para generar el cuadro.",
        )
    rows = build_schedule(
        principal=account.opening_balance,
        apr=account.apr,
        term_months=account.term_months,
        start_date=account.start_date,
    )
    total_paid = sum((r.payment for r in rows), Decimal("0"))
    total_interest = sum((r.interest for r in rows), Decimal("0"))
    monthly_payment = rows[0].payment if rows else Decimal("0")
    extra = _compute_extra_charges(
        total_to_pay=account.total_to_pay,
        installments_total=total_paid,
        interest_only=account.interest_only_first_payment,
    )
    return AmortizationScheduleResponse(
        account_id=account.id,
        principal=account.opening_balance,
        apr=account.apr,
        tae=account.tae,
        term_months=account.term_months,
        start_date=account.start_date,
        interest_only_first_payment=account.interest_only_first_payment,
        total_to_pay=account.total_to_pay,
        extra_charges=extra,
        monthly_payment=monthly_payment,
        total_interest=total_interest,
        total_paid=total_paid,
        rows=[
            AmortizationRowResponse(
                month=r.month,
                due_date=r.due_date,
                payment=r.payment,
                interest=r.interest,
                principal=r.principal,
                remaining_balance=r.remaining_balance,
            )
            for r in rows
        ],
    )


# ---------------------------------------------------------------------------
# PHASE-24.1 — CRUD individual de cuotas (override + estado de pago)
# ---------------------------------------------------------------------------


async def _get_installment_or_404(
    db: AsyncSession, installment_id: uuid.UUID, user_id: uuid.UUID
) -> LiabilityInstallment:
    inst = await repo_get_installment(db, installment_id, user_id)
    if inst is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cuota no encontrada"
        )
    return inst


async def regenerate_amortization_schedule(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID
) -> AmortizationScheduleResponse:
    """PHASE-24.3 — Borra las cuotas persistidas (si las hay) y las
    regenera con los datos actuales de la cuenta.

    Determina el `principal` así (en orden de preferencia):
    1. Si la cuenta tiene una tx pareada (counterpart de
       convert-to-debt), usa su `amount` — refleja el importe
       financiado real.
    2. Si no, `opening_balance` (cuentas creadas manualmente).

    Casos de uso típicos:
    - Cuenta creada vía convert-to-debt antes de PHASE-24.2 (sin
      cuotas porque tarjetas no eran amortizables). Tras añadir
      APR/plazo, el usuario llama a este endpoint y aparecen las
      cuotas reales.
    - El usuario cambió APR o plazo y quiere refrescar el cuadro
      perdiendo el estado de pago.

    Requiere `accepts_amortization` y los tres campos del cuadro
    informados.
    """
    from decimal import Decimal as _Decimal  # noqa: PLC0415

    from sqlalchemy import select  # noqa: PLC0415

    from app.modules.personal_finance.accounts.installments_repository import (  # noqa: PLC0415
        delete_installments_for_account,
    )
    from app.modules.personal_finance.transactions.models import (  # noqa: PLC0415
        Transaction,
    )

    account = await get_account(db, account_id, user_id)
    if account.type not in {
        AccountType.LOAN,
        AccountType.MORTGAGE,
        AccountType.CREDIT_CARD,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sólo loan/mortgage/credit_card aceptan cuadro.",
        )
    if account.apr is None or account.term_months is None or account.start_date is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faltan APR, plazo o fecha de inicio.",
        )

    # Buscar counterpart tx pareada (sólo aplica si convert-to-debt):
    # cualquier tx activa con `transfer_pair_id IS NOT NULL` cuyo
    # account_id sea el actual.
    counterpart_q = await db.execute(
        select(Transaction)
        .where(Transaction.account_id == account_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_not(None))
        .order_by(Transaction.created_at.asc())
        .limit(1)
    )
    counterpart = counterpart_q.scalar_one_or_none()

    principal_override: _Decimal | None = None
    if counterpart is not None:
        principal_override = counterpart.amount
    elif account.opening_balance <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No se puede generar el cuadro: el `opening_balance` "
                "es 0 y no hay transacción pareada de la que derivar "
                "el principal."
            ),
        )

    await delete_installments_for_account(db, account_id)
    await generate_installments_for_account(
        db, account, principal_override=principal_override
    )
    await db.flush()
    return await get_amortization_schedule(db, account_id, user_id)


async def update_installment(
    db: AsyncSession,
    installment_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    payment: Decimal | None,
    due_date: object | None,
) -> LiabilityInstallment:
    """Override puntual: importe y/o fecha. NO recomputa el resto."""
    inst = await _get_installment_or_404(db, installment_id, user_id)
    if payment is not None and payment < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El importe de la cuota no puede ser negativo.",
        )
    return await repo_update_installment(
        db, inst, payment=payment, due_date=due_date
    )


async def mark_installment_paid(
    db: AsyncSession,
    installment_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    paid_at: object | None,
    paid_transaction_id: uuid.UUID | None,
) -> LiabilityInstallment:
    """Marca como pagada — `paid_at=None` → now()."""
    from datetime import datetime, timezone  # noqa: PLC0415

    inst = await _get_installment_or_404(db, installment_id, user_id)
    when = paid_at if paid_at is not None else datetime.now(timezone.utc)
    return await repo_mark_paid(
        db,
        inst,
        paid_at=when,  # type: ignore[arg-type]
        paid_transaction_id=paid_transaction_id,
    )


async def unmark_installment_paid(
    db: AsyncSession, installment_id: uuid.UUID, user_id: uuid.UUID
) -> LiabilityInstallment:
    """Revierte a pendiente."""
    inst = await _get_installment_or_404(db, installment_id, user_id)
    return await repo_unmark_paid(db, inst)
