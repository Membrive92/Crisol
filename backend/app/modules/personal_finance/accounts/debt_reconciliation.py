"""PHASE-36 — Reconciliación de aportaciones contra el cuadro de deuda.

ADR-0004 / decisión del usuario: las aportaciones (amortización de
préstamo, cuotas de "operación financiada con tarjeta") deben DESCONTAR
la deuda. "El cuadro manda": el saldo vivo de una liability con plan sale
de las cuotas no pagadas (`schedule_outstanding`); este módulo es quien
las marca pagadas a partir de los movimientos reales del extracto.

Mecánica (sin patas sintéticas ni tocar el cashflow):

1. **Generar el cuadro que falte** (préstamo dado de alta sin cuotas).
2. **Ancla temporal**: las cuotas con `due_date` anterior a la ventana de
   datos del usuario se marcan pagadas (sin tx) → el saldo de arranque es
   el saldo económico real a la primera fecha de datos, no el principal
   original.
3. **Match aportación → cuota**:
   - *Préstamo/hipoteca*: cada cargo de amortización marca la siguiente
     cuota pendiente de su liability (FIFO), enlazando `paid_transaction_id`.
   - *Tarjeta (PHASE-36.1)*: el cargo `OPERACIÓN FINANCIADA CON TARJETA` es
     AGREGADO (engloba varias compras a plazos de la misma tarjeta), así que
     un cargo paga la siguiente cuota pendiente de CADA tarjeta con cuadro
     ya iniciada — mes del cargo ≥ mes de inicio del plan, para no adelantar
     cuotas de un plan que aún no existía.
4. **Exceso asumido**: el sobrante de un cargo de tarjeta sobre las cuotas
   que cubre (compras de años previos no registradas) NO toca el saldo — se
   reporta como `assumed_unregistered_debt` (línea informativa), imputado al
   plan vinculado por categoría (o al primero que casó cuota).

Idempotente: re-ejecutar no duplica (cuotas ya pagadas / ya enlazadas se
respetan). Reversible: las marcas se pueden deshacer (unmark) y el cuadro
generado borrar; las contrapartidas no existen (no se crean tx).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.amortization import build_schedule
from app.modules.personal_finance.accounts.installments_model import LiabilityInstallment
from app.modules.personal_finance.accounts.installments_repository import (
    generate_installments_for_account,
    list_installments,
    mark_installment_paid,
)
from app.modules.personal_finance.accounts.models import Account, AccountNature, AccountType
from app.modules.personal_finance.transactions.models import Transaction


# ── Clasificación de la descripción del movimiento ──────────────────────
def is_loan_amortization(description: str | None) -> bool:
    """Cargo de amortización de un préstamo/hipoteca."""
    return description is not None and "amortizac" in description.lower()


def is_card_financed_op(description: str | None) -> bool:
    """Cuota de una compra financiada con TARJETA.

    Exige "operaci...financiada" + "tarjeta" para casar "OPERACIÓN
    FINANCIADA CON TARJETA" y EXCLUIR tanto el evento de financiación
    entrante ("OPERACION FINANCIADA" a secas) como la liquidación normal
    ("ADEUDO MENSUAL DE TARJETA").
    """
    if not description:
        return False
    d = description.lower()
    return "operaci" in d and "financiada" in d and "tarjeta" in d


@dataclass
class _ScheduleRow:
    """Proyección en memoria de una cuota (existente o por generar)."""

    index: int
    due: date
    payment: Decimal
    principal: Decimal
    paid: bool
    synthetic_anchor: bool = False
    existing: LiabilityInstallment | None = None


@dataclass
class InstallmentAction:
    account_name: str
    installment_index: int
    due_date: date
    principal: Decimal
    payment: Decimal
    reason: str  # "anchor" | "matched"
    paid_transaction_id: uuid.UUID | None = None
    payment_description: str | None = None
    payment_amount: Decimal | None = None


@dataclass
class LiabilityPlan:
    account_id: uuid.UUID
    name: str
    type: str
    generate_schedule: bool = False
    schedule_rows: int = 0
    anchored: int = 0
    matched: int = 0
    actions: list[InstallmentAction] = field(default_factory=list)
    assumed_unregistered_debt: Decimal = Decimal("0")
    outstanding_before: Decimal | None = None
    outstanding_after: Decimal | None = None


@dataclass
class ReconcilePlan:
    data_window_start: date | None
    liabilities: list[LiabilityPlan] = field(default_factory=list)
    skipped_payments: list[str] = field(default_factory=list)
    # Estado interno para el apply (no se serializa).
    anchor_at: datetime = field(
        default_factory=lambda: datetime(2000, 1, 1, tzinfo=UTC), repr=False
    )
    schedules: dict[uuid.UUID, list[_ScheduleRow]] = field(default_factory=dict, repr=False)
    accounts_by_id: dict[uuid.UUID, Account] = field(default_factory=dict, repr=False)
    plan_by_id: dict[uuid.UUID, LiabilityPlan] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "data_window_start": (
                self.data_window_start.isoformat() if self.data_window_start else None
            ),
            "liabilities": [
                {
                    "name": lp.name,
                    "type": lp.type,
                    "generate_schedule": lp.generate_schedule,
                    "schedule_rows": lp.schedule_rows,
                    "anchored": lp.anchored,
                    "matched": lp.matched,
                    "assumed_unregistered_debt": str(lp.assumed_unregistered_debt),
                    "outstanding_before": (
                        str(lp.outstanding_before) if lp.outstanding_before is not None else None
                    ),
                    "outstanding_after": (
                        str(lp.outstanding_after) if lp.outstanding_after is not None else None
                    ),
                    "actions": [
                        {
                            "ix": a.installment_index,
                            "due": a.due_date.isoformat(),
                            "principal": str(a.principal),
                            "payment": str(a.payment),
                            "reason": a.reason,
                            "tx": str(a.paid_transaction_id) if a.paid_transaction_id else None,
                            "tx_desc": a.payment_description,
                            "tx_amount": (
                                str(a.payment_amount) if a.payment_amount is not None else None
                            ),
                        }
                        for a in lp.actions
                    ],
                }
                for lp in self.liabilities
            ],
            "skipped_payments": self.skipped_payments,
        }


async def _data_window_start(db: AsyncSession, user_id: uuid.UUID) -> date | None:
    """Primera fecha con transacciones activas del usuario (corte del ancla)."""
    result = await db.execute(
        select(func.min(Transaction.occurred_at))
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
    )
    earliest = result.scalar_one_or_none()
    return earliest.date() if earliest is not None else None


async def _load_aportaciones(db: AsyncSession, user_id: uuid.UUID) -> list[Transaction]:
    """Movimientos candidatos a aportación de deuda (amortización / cuota
    de tarjeta financiada), ordenados cronológicamente. Excluye papelera."""
    rows = (
        (
            await db.execute(
                select(Transaction)
                .where(Transaction.user_id == user_id)
                .where(Transaction.deleted_at.is_(None))
                .order_by(Transaction.occurred_at.asc(), Transaction.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return [
        t for t in rows if is_loan_amortization(t.description) or is_card_financed_op(t.description)
    ]


def _resolve_target(
    tx: Transaction,
    loans: list[Account],
    cards_with_schedule: list[Account],
) -> Account | None:
    """Resuelve la liability destino de una aportación.

    Determinista cuando hay una sola candidata; si hay varias, usa el
    vínculo explícito `accounts.category_id == tx.category_id` (PHASE-30.4);
    si sigue ambiguo, devuelve None (el caller lo reporta, no adivina).
    """
    if is_loan_amortization(tx.description):
        pool = loans
    elif is_card_financed_op(tx.description):
        pool = cards_with_schedule
    else:
        return None
    if len(pool) == 1:
        return pool[0]
    if tx.category_id is not None:
        linked = [a for a in pool if a.category_id == tx.category_id]
        if len(linked) == 1:
            return linked[0]
    return None


def _excess_bucket(
    tx: Transaction,
    cards: list[Account],
    plan_by_id: dict[uuid.UUID, LiabilityPlan],
    first_matched: LiabilityPlan | None,
) -> LiabilityPlan | None:
    """Plan al que imputar el EXCESO de un cargo agregado de tarjeta (deuda
    previa no registrada, informativa). Preferencia: el plan vinculado por
    categoría (PHASE-30.4); si no, el primero que casó una cuota en este
    cargo; si no, la primera tarjeta con cuadro. `None` si no hay ninguna."""
    if tx.category_id is not None:
        linked = [c for c in cards if c.category_id == tx.category_id]
        if len(linked) == 1:
            return plan_by_id[linked[0].id]
    if first_matched is not None:
        return first_matched
    if cards:
        return plan_by_id[cards[0].id]
    return None


async def build_reconcile_plan(db: AsyncSession, user_id: uuid.UUID) -> ReconcilePlan:
    """Calcula (sin escribir) el plan completo de reconciliación.

    El mismo plan alimenta el dry-run (que sólo lo reporta) y el apply
    (que lo materializa). Trabaja sobre una proyección en memoria de los
    cuadros, generando in-memory los que faltan, para que el dry-run
    muestre exactamente lo que pasaría sin tocar la BD.
    """
    window_start = await _data_window_start(db, user_id)

    liabilities = list(
        (
            await db.execute(
                select(Account)
                .where(Account.user_id == user_id)
                .where(Account.nature == AccountNature.LIABILITY)
                .where(Account.is_archived.is_(False))
            )
        )
        .scalars()
        .all()
    )

    plan = ReconcilePlan(data_window_start=window_start)
    plan.accounts_by_id = {a.id: a for a in liabilities}
    schedules = plan.schedules
    plan_by_id = plan.plan_by_id

    for liab in liabilities:
        lp = LiabilityPlan(account_id=liab.id, name=liab.name, type=liab.type.value)
        plan_by_id[liab.id] = lp
        plan.liabilities.append(lp)
        existing = await list_installments(db, liab.id, user_id)
        if existing:
            schedules[liab.id] = [
                _ScheduleRow(
                    index=i.installment_index,
                    due=i.due_date,
                    payment=i.payment,
                    principal=i.principal,
                    paid=i.paid_at is not None,
                    existing=i,
                )
                for i in existing
            ]
        elif (
            liab.apr is not None
            and liab.term_months is not None
            and liab.start_date is not None
            and liab.opening_balance is not None
            and liab.opening_balance > 0
        ):
            # Cuadro a generar (préstamo sin plan): proyectarlo in-memory.
            built_rows = build_schedule(
                principal=liab.opening_balance,
                apr=liab.apr,
                term_months=liab.term_months,
                start_date=liab.start_date,
            )
            schedules[liab.id] = [
                _ScheduleRow(
                    index=br.month,
                    due=br.due_date,
                    payment=br.payment,
                    principal=br.principal,
                    paid=False,
                )
                for br in built_rows
            ]
            lp.generate_schedule = True
            lp.schedule_rows = len(built_rows)
        else:
            schedules[liab.id] = []

        # Ancla: cuotas con due_date < ventana de datos → pagadas (sin tx).
        if window_start is not None:
            for row in schedules[liab.id]:
                if not row.paid and row.due < window_start:
                    row.paid = True
                    row.synthetic_anchor = True
                    lp.anchored += 1
                    lp.actions.append(
                        InstallmentAction(
                            account_name=liab.name,
                            installment_index=row.index,
                            due_date=row.due,
                            principal=row.principal,
                            payment=row.payment,
                            reason="anchor",
                        )
                    )

    loans = [a for a in liabilities if a.type in {AccountType.LOAN, AccountType.MORTGAGE}]
    cards_with_schedule = [
        a for a in liabilities if a.type == AccountType.CREDIT_CARD and schedules.get(a.id)
    ]
    # Orden estable para el reparto de cargos agregados (por inicio, luego nombre).
    cards_with_schedule.sort(key=lambda a: (a.start_date or date.max, a.name))

    # Match aportación → cuota(s):
    #   - Préstamo/hipoteca: 1 cargo → 1 cuota de la liability resuelta (única
    #     o por vínculo de categoría), FIFO por índice.
    #   - Tarjeta (PHASE-36.1): el cargo `OPERACIÓN FINANCIADA CON TARJETA` es
    #     AGREGADO (engloba varias compras a plazos de la MISMA tarjeta). Un
    #     cargo paga la siguiente cuota pendiente de CADA tarjeta con cuadro ya
    #     iniciada (mes del cargo ≥ mes de inicio del plan, para no adelantar
    #     cuotas de un plan que aún no existía). El exceso sobre las cuotas
    #     cubiertas es deuda previa no registrada (informativa).
    aportaciones = await _load_aportaciones(db, user_id)
    for tx in aportaciones:
        # ── Préstamo/hipoteca: 1 cargo → 1 cuota (target único o por categoría).
        if is_loan_amortization(tx.description):
            target = _resolve_target(tx, loans, cards_with_schedule)
            if target is None:
                plan.skipped_payments.append(
                    f"{tx.occurred_at.date()} {tx.amount} «{(tx.description or '')[:40]}» "
                    "(no se pudo resolver la deuda destino)"
                )
                continue
            rows = schedules.get(target.id, [])
            if any(
                r.existing is not None and r.existing.paid_transaction_id == tx.id for r in rows
            ):
                continue
            nxt = next((r for r in rows if not r.paid), None)
            lp = plan_by_id[target.id]
            if nxt is None:
                plan.skipped_payments.append(
                    f"{tx.occurred_at.date()} {tx.amount} «{(tx.description or '')[:40]}» "
                    f"(cuadro de «{target.name}» ya completo)"
                )
                continue
            nxt.paid = True
            lp.matched += 1
            lp.actions.append(
                InstallmentAction(
                    account_name=target.name,
                    installment_index=nxt.index,
                    due_date=nxt.due,
                    principal=nxt.principal,
                    payment=nxt.payment,
                    reason="matched",
                    paid_transaction_id=tx.id,
                    payment_description=tx.description,
                    payment_amount=tx.amount,
                )
            )
            continue

        if not is_card_financed_op(tx.description):
            continue

        # ── Tarjeta: cargo agregado → 1 cuota de CADA plan iniciado (PHASE-36.1).
        charge_ym = (tx.occurred_at.year, tx.occurred_at.month)
        covered = Decimal("0")
        first_matched: LiabilityPlan | None = None
        for card in cards_with_schedule:
            start = card.start_date
            if start is None or (start.year, start.month) > charge_ym:
                continue  # el plan aún no había arrancado en el mes del cargo
            rows = schedules.get(card.id, [])
            # Idempotencia: si YA hay una cuota de este plan enlazada a esta tx,
            # cuéntala como cubierta pero no la re-marques (exceso idéntico
            # entre ejecuciones).
            linked = next(
                (
                    r
                    for r in rows
                    if r.existing is not None and r.existing.paid_transaction_id == tx.id
                ),
                None,
            )
            if linked is not None:
                covered += linked.payment
                # first_matched debe reflejar el MISMO plan en cada ejecución
                # (idempotencia del exceso): en re-runs la cuota ya está
                # enlazada, así que sin esto first_matched quedaría None y el
                # exceso se imputaría a cards[0] en vez de al que casó primero.
                if first_matched is None:
                    first_matched = plan_by_id[card.id]
                continue
            nxt = next((r for r in rows if not r.paid), None)
            if nxt is None:
                continue  # cuadro de este plan ya completo
            nxt.paid = True
            lp = plan_by_id[card.id]
            lp.matched += 1
            lp.actions.append(
                InstallmentAction(
                    account_name=card.name,
                    installment_index=nxt.index,
                    due_date=nxt.due,
                    principal=nxt.principal,
                    payment=nxt.payment,
                    reason="matched",
                    paid_transaction_id=tx.id,
                    payment_description=tx.description,
                    payment_amount=tx.amount,
                )
            )
            covered += nxt.payment
            if first_matched is None:
                first_matched = lp
        # Exceso del cargo agregado sobre las cuotas cubiertas = deuda previa.
        excess = tx.amount - covered
        if excess > 0:
            bucket = _excess_bucket(tx, cards_with_schedule, plan_by_id, first_matched)
            if bucket is not None:
                bucket.assumed_unregistered_debt += excess
            else:
                plan.skipped_payments.append(
                    f"{tx.occurred_at.date()} {tx.amount} «{(tx.description or '')[:40]}» "
                    "(sin cuadro de tarjeta al que imputar)"
                )

    # Saldos antes/después (Σ principal no pagado) para el reporte.
    for liab in liabilities:
        rows = schedules.get(liab.id, [])
        if not rows:
            continue
        lp = plan_by_id[liab.id]
        # "before" = como estaba en BD (sólo cuotas ya pagadas en BD);
        # "after" = tras ancla + match de este plan.
        before_paid_principal = sum(
            (
                r.principal
                for r in rows
                if r.existing is not None and r.existing.paid_at is not None
            ),
            Decimal("0"),
        )
        total_principal = sum((r.principal for r in rows), Decimal("0"))
        lp.outstanding_before = total_principal - before_paid_principal
        lp.outstanding_after = sum((r.principal for r in rows if not r.paid), Decimal("0"))

    return plan


async def apply_reconcile_plan(db: AsyncSession, user_id: uuid.UUID, plan: ReconcilePlan) -> None:
    """Materializa el plan: genera cuadros faltantes, marca ancla y matches.

    Idempotente. No crea ni borra transacciones (sólo marca cuotas).
    """
    anchor_at = plan.anchor_at

    for lp in plan.liabilities:
        liab = plan.accounts_by_id[lp.account_id]
        # 1. Generar el cuadro que falte (idempotente en el repo).
        if lp.generate_schedule:
            await generate_installments_for_account(db, liab)
        # Recargar las cuotas reales (ya persistidas) por índice.
        persisted = {i.installment_index: i for i in await list_installments(db, liab.id, user_id)}
        for action in lp.actions:
            inst = persisted.get(action.installment_index)
            if inst is None or inst.paid_at is not None:
                continue  # idempotencia: ya pagada o inexistente
            paid_at = action_paid_at(action) if action.reason == "matched" else anchor_at
            await mark_installment_paid(
                db,
                inst,
                paid_at=paid_at,
                paid_transaction_id=action.paid_transaction_id,
            )


def action_paid_at(action: InstallmentAction) -> datetime:
    """Timestamp de pago de una cuota matcheada (la marca estable del ancla
    no aplica). Usa el corte de la cuota; el día exacto no es crítico."""
    return datetime(action.due_date.year, action.due_date.month, action.due_date.day, tzinfo=UTC)


async def reconcile_debt_payments(
    db: AsyncSession, user_id: uuid.UUID, *, dry_run: bool = True
) -> dict[str, object]:
    """Construye el plan y, si `dry_run` es False, lo aplica. Devuelve el
    plan serializado para que el caller lo muestre/auditе."""
    plan = await build_reconcile_plan(db, user_id)
    if not dry_run:
        await apply_reconcile_plan(db, user_id, plan)
    result = plan.to_dict()
    result["dry_run"] = dry_run
    return result
