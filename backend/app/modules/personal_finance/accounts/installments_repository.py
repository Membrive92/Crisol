"""Repository del módulo `liability_installments` (PHASE-24.1)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.amortization import build_schedule
from app.modules.personal_finance.accounts.installments_model import (
    LiabilityInstallment,
)
from app.modules.personal_finance.accounts.models import Account


async def generate_installments_for_account(
    db: AsyncSession,
    account: Account,
    *,
    principal_override: Decimal | None = None,
) -> list[LiabilityInstallment]:
    """Genera las cuotas (cuadro francés) para una liability y las
    persiste. Idempotente: si ya hay cuotas para la cuenta, no toca
    nada (el caller usa este helper sólo al crear/regenerar).

    `principal_override` permite forzar el principal en flujos donde
    la deuda no se modela vía `opening_balance` sino vía la tx
    paréada (PHASE-24: convert-to-debt). Si es None, se usa
    `account.opening_balance`.

    Devuelve la lista de cuotas resultantes (vacía si la cuenta no
    cumple las precondiciones — el caller no debe asumir generación).
    """
    if account.apr is None or account.term_months is None or account.start_date is None:
        return []
    principal = principal_override if principal_override is not None else account.opening_balance
    if principal is None or principal <= 0:
        return []

    existing = await db.execute(
        select(LiabilityInstallment).where(LiabilityInstallment.account_id == account.id)
    )
    if existing.first() is not None:
        return []

    rows = build_schedule(
        principal=principal,
        apr=account.apr,
        term_months=account.term_months,
        start_date=account.start_date,
    )
    persisted: list[LiabilityInstallment] = []
    for r in rows:
        inst = LiabilityInstallment(
            user_id=account.user_id,
            account_id=account.id,
            installment_index=r.month,
            due_date=r.due_date,
            payment=r.payment,
            interest=r.interest,
            principal=r.principal,
            remaining_balance=r.remaining_balance,
        )
        db.add(inst)
        persisted.append(inst)
    await db.flush()
    return persisted


def schedule_outstanding(installments: list[LiabilityInstallment]) -> Decimal | None:
    """PHASE-36 — Saldo pendiente de una liability DIRIGIDO POR EL CUADRO.

    "El cuadro manda": la deuda viva = Σ del `principal` de las cuotas
    NO pagadas (`paid_at IS NULL`). Cada aportación que marca una cuota
    como pagada reduce este saldo exactamente por el principal francés de
    esa cuota; las cuotas previas a la ventana de datos se marcan pagadas
    (ancla) y por tanto no inflan el saldo.

    Devuelve `None` si la cuenta no tiene cuadro (no es una liability con
    plan): el caller cae entonces al saldo por movimientos
    (`opening_balance + Σ movimientos`), comportamiento previo.
    """
    if not installments:
        return None
    return sum(
        (i.principal for i in installments if i.paid_at is None),
        Decimal("0"),
    )


@dataclass(frozen=True)
class LiabilityOutstanding:
    """Deuda viva de un pasivo + de dónde ha salido el número."""

    value: Decimal
    from_schedule: bool
    """True si la manda el cuadro (Σ principal no pagado); False si sale de
    `opening_balance + Σ movimientos`."""


def resolve_liability_outstanding(
    *,
    opening_balance: Decimal,
    movements_balance: Decimal,
    installments: list[LiabilityInstallment],
) -> LiabilityOutstanding:
    """PHASE-36 — el MUX «el cuadro manda», en un solo sitio.

    Un pasivo CON cuadro deriva su deuda viva de las cuotas no pagadas y sus
    movimientos se ignoran; uno SIN cuadro la deriva de `opening_balance + Σ
    movimientos`. Nunca la suma de ambos: eso reintroduciría el doble conteo de
    [PHASE-34] «dos fuentes de verdad».
    """
    sched = schedule_outstanding(installments)
    if sched is not None:
        return LiabilityOutstanding(value=sched, from_schedule=True)
    return LiabilityOutstanding(value=opening_balance + movements_balance, from_schedule=False)


# Holgura de un céntimo al comparar un pago contra el principal de una cuota:
# el banco redondea distinto que el cuadro francés ideal.
PRINCIPAL_MATCH_TOLERANCE = Decimal("0.01")


def plan_installments_covering_principal(
    installments: list[LiabilityInstallment], principal_amount: Decimal
) -> list[LiabilityInstallment]:
    """Qué cuotas cubriría un pago de `principal_amount`, sin tocar nada.

    Greedy desde la cuota pendiente MÁS ANTIGUA hacia adelante: se cubre la
    cuota k mientras su `principal` quepa en lo que resta (con un céntimo de
    holgura). Devuelve la lista en orden; vacía si el pago no llega ni a la
    primera pendiente — el caller lo usa para avisar de que el saldo no bajará.

    Es PURA a propósito: así el "previsualiza el efecto" (`dry_run`) y el
    "aplícalo" usan LA MISMA definición y no pueden divergir. Asume el cuadro
    anclado (las cuotas ya pagadas están marcadas), así que la más antigua
    pendiente es la del pago en curso.

    `installments` debe venir ordenada por `installment_index` ascendente —
    es lo que devuelve `list_installments`.
    """
    remaining = principal_amount
    covered: list[LiabilityInstallment] = []
    for inst in installments:
        if inst.paid_at is not None:
            continue
        if inst.principal > remaining + PRINCIPAL_MATCH_TOLERANCE:
            break
        remaining -= inst.principal
        covered.append(inst)
    return covered


# ─────────────────────────────────────────────────────────────────────
# PHASE-37 — Agregación de interés/capital DIRIGIDA POR EL CUADRO.
# El interés no se registra como movimiento aparte (va dentro de la cuota),
# así que estas funciones puras son la fuente ÚNICA del interés/capital
# "real" para debt-health y para la Capa 1 (/debt/category-summary). Se
# comparan fechas por `.date()` para no depender de la tz del `paid_at`
# (las cuotas-ancla llevan año 2000 y quedan fuera de cualquier ventana).
# ─────────────────────────────────────────────────────────────────────


def _paid_in_window(inst: LiabilityInstallment, start: date, end: date) -> bool:
    return inst.paid_at is not None and start <= inst.paid_at.date() <= end


def interest_paid_in_window(
    installments: list[LiabilityInstallment], *, start: date, end: date
) -> Decimal:
    """Σ interés de las cuotas cuyo `paid_at` cae en `[start, end]`."""
    return sum(
        (i.interest for i in installments if _paid_in_window(i, start, end)),
        Decimal("0"),
    )


def principal_paid_in_window(
    installments: list[LiabilityInstallment], *, start: date, end: date
) -> Decimal:
    """Σ principal amortizado de las cuotas pagadas en `[start, end]`."""
    return sum(
        (i.principal for i in installments if _paid_in_window(i, start, end)),
        Decimal("0"),
    )


def interest_total(
    installments: list[LiabilityInstallment], *, unpaid_only: bool = False
) -> Decimal:
    """Σ interés del cuadro: contractual total, o el que queda por pagar
    (`unpaid_only=True`, cuotas con `paid_at IS NULL`)."""
    return sum(
        (i.interest for i in installments if not unpaid_only or i.paid_at is None),
        Decimal("0"),
    )


async def list_installments(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID
) -> list[LiabilityInstallment]:
    """Lista las cuotas de una liability ordenadas por índice."""
    query = (
        select(LiabilityInstallment)
        .where(
            LiabilityInstallment.account_id == account_id,
            LiabilityInstallment.user_id == user_id,
        )
        .order_by(LiabilityInstallment.installment_index.asc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def list_installments_paid_by_transaction(
    db: AsyncSession, user_id: uuid.UUID, transaction_id: uuid.UUID
) -> list[LiabilityInstallment]:
    """PHASE-45 — cuotas que una transacción concreta marcó como pagadas.

    Es la huella que deja una amortización sobre un pasivo CON cuadro (ahí no
    se crea ningún movimiento: manda el cuadro), así que es también la forma de
    saber si esa transacción ya está registrada y qué deshacer.
    """
    query = (
        select(LiabilityInstallment)
        .where(
            LiabilityInstallment.user_id == user_id,
            LiabilityInstallment.paid_transaction_id == transaction_id,
        )
        .order_by(LiabilityInstallment.installment_index.asc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def installments_by_account(
    db: AsyncSession, user_id: uuid.UUID, account_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[LiabilityInstallment]]:
    """Carga las cuotas de varias cuentas de una vez, ordenadas por índice
    y agrupadas por `account_id`. Una sola query (PHASE-36, reutilizado por
    saldos dirigidos por cuadro, debt-health y reconciliación)."""
    if not account_ids:
        return {}
    rows = (
        (
            await db.execute(
                select(LiabilityInstallment)
                .where(LiabilityInstallment.user_id == user_id)
                .where(LiabilityInstallment.account_id.in_(account_ids))
                .order_by(
                    LiabilityInstallment.account_id,
                    LiabilityInstallment.installment_index.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    by_account: dict[uuid.UUID, list[LiabilityInstallment]] = {}
    for inst in rows:
        by_account.setdefault(inst.account_id, []).append(inst)
    return by_account


async def get_installment(
    db: AsyncSession, installment_id: uuid.UUID, user_id: uuid.UUID
) -> LiabilityInstallment | None:
    """Obtiene una cuota por id, filtrada por user_id (aislamiento)."""
    query = select(LiabilityInstallment).where(
        LiabilityInstallment.id == installment_id,
        LiabilityInstallment.user_id == user_id,
    )
    return (await db.execute(query)).scalar_one_or_none()


async def update_installment_amount_and_date(
    db: AsyncSession,
    inst: LiabilityInstallment,
    *,
    payment: object | None = None,
    due_date: object | None = None,
) -> LiabilityInstallment:
    """Override puntual de importe / fecha.

    AUDIT-FIX (finding 4): al editar el `payment` de una cuota, se
    recalcula el split de ESA fila para que siga cumpliendo la
    identidad `payment == interest + principal`. Antes el override
    cambiaba sólo `payment` y dejaba `interest`/`principal` sin tocar,
    rompiendo la identidad de la fila y desligando el cuadro de los
    totales.

    Decisión deliberadamente mínima (no recompone las cuotas
    siguientes): el `interest` de la cuota se mantiene (es el interés
    devengado sobre el saldo de entrada de ese mes, que no cambia
    porque las filas previas no se tocan), y el `principal` absorbe la
    diferencia: `principal = payment − interest`. NO se recalcula
    `remaining_balance` ni las cuotas posteriores — el override sigue
    siendo puntual, pero internamente coherente fila a fila. Si el
    nuevo `payment` es menor que el interés del mes, el principal
    resultante sería negativo: en ese caso se deja `principal = 0` y el
    `interest` se ajusta a `payment` para no fabricar amortización
    negativa (caso degenerado de cuota inferior al interés).
    """
    if payment is not None:
        new_payment: Decimal = payment  # type: ignore[assignment]
        inst.payment = new_payment
        # Recalcular el split manteniendo el interés devengado del mes.
        if new_payment >= inst.interest:
            inst.principal = new_payment - inst.interest
        else:
            # Cuota inferior al interés del mes: no hay amortización de
            # principal; toda la cuota es interés.
            inst.interest = new_payment
            inst.principal = Decimal("0")
    if due_date is not None:
        inst.due_date = due_date  # type: ignore[assignment]
    await db.flush()
    await db.refresh(inst)
    return inst


async def mark_installment_paid(
    db: AsyncSession,
    inst: LiabilityInstallment,
    *,
    paid_at: datetime,
    paid_transaction_id: uuid.UUID | None,
) -> LiabilityInstallment:
    """Marca la cuota como pagada con timestamp + tx opcional."""
    inst.paid_at = paid_at
    inst.paid_transaction_id = paid_transaction_id
    await db.flush()
    await db.refresh(inst)
    return inst


async def unmark_installment_paid(
    db: AsyncSession, inst: LiabilityInstallment
) -> LiabilityInstallment:
    """Revierte el estado a pendiente (NULL ambos campos)."""
    inst.paid_at = None
    inst.paid_transaction_id = None
    await db.flush()
    await db.refresh(inst)
    return inst


async def delete_installments_for_account(db: AsyncSession, account_id: uuid.UUID) -> None:
    """Borra todas las cuotas de una cuenta (al regenerar el cuadro)."""
    await db.execute(
        delete(LiabilityInstallment).where(LiabilityInstallment.account_id == account_id)
    )
    await db.flush()
