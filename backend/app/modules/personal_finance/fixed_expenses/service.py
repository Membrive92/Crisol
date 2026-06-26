"""Lógica de negocio del módulo fixed_expenses (PHASE-13.1,
renombrado en PHASE-17.1, autopost en PHASE-17.2)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.service import ensure_account_exists
from app.modules.personal_finance.fixed_expenses import detector
from app.modules.personal_finance.fixed_expenses.models import (
    FixedExpense,
    FixedExpenseStatus,
)
from app.modules.personal_finance.fixed_expenses.repository import (
    create_fixed_expense as persist_fixed_expense,
)
from app.modules.personal_finance.fixed_expenses.repository import (
    delete_fixed_expense as remove_fixed_expense,
)
from app.modules.personal_finance.fixed_expenses.repository import (
    find_by_fingerprint,
    get_fixed_expense_by_id,
    list_due_for_autopost,
)
from app.modules.personal_finance.fixed_expenses.repository import (
    list_fixed_expenses as list_in_db,
)
from app.modules.personal_finance.fixed_expenses.schemas import (
    AutopostResponse,
    FixedExpenseUpdate,
    ScanResponse,
)
from app.modules.personal_finance.transactions.models import (
    Transaction,
    TransactionSource,
)


async def list_fixed_expenses(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: FixedExpenseStatus | None = None,
) -> list[FixedExpense]:
    """Lista del usuario, ordenada por `next_due`."""
    return await list_in_db(db, user_id, status=status)


async def get_fixed_expense(
    db: AsyncSession, fixed_expense_id: uuid.UUID, user_id: uuid.UUID
) -> FixedExpense:
    """Obtiene un gasto fijo o 404."""
    item = await get_fixed_expense_by_id(db, fixed_expense_id, user_id)
    if item is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Gasto fijo no encontrado",
        )
    return item


async def confirm_fixed_expense(
    db: AsyncSession, fixed_expense_id: uuid.UUID, user_id: uuid.UUID
) -> FixedExpense:
    """`pending` (o cualquier estado, incl. `dismissed`) → `confirmed`.

    AUDIT-fix: la antigua rama que ponía `PENDING` antes de `CONFIRMED`
    para un item `dismissed` era código muerto — la asignación
    siguiente la sobrescribía en la misma transacción sin emitir un
    estado intermedio observable (sin tabla de audit/eventos, el paso
    por `pending` no dejaba traza). Confirmar reactiva directamente a
    `confirmed`, que es el efecto pretendido.
    """
    item = await get_fixed_expense(db, fixed_expense_id, user_id)
    item.status = FixedExpenseStatus.CONFIRMED
    await db.flush()
    await db.refresh(item)
    return item


async def dismiss_fixed_expense(
    db: AsyncSession, fixed_expense_id: uuid.UUID, user_id: uuid.UUID
) -> FixedExpense:
    """Marca como dismissed; el detector NO lo volverá a sugerir."""
    item = await get_fixed_expense(db, fixed_expense_id, user_id)
    item.status = FixedExpenseStatus.DISMISSED
    await db.flush()
    await db.refresh(item)
    return item


async def pause_fixed_expense(
    db: AsyncSession, fixed_expense_id: uuid.UUID, user_id: uuid.UUID
) -> FixedExpense:
    """Marca como paused (PHASE-15.2). Sólo desde confirmed; otros
    estados producen 409 — pausar uno pending o dismissed no tiene
    semántica clara."""
    item = await get_fixed_expense(db, fixed_expense_id, user_id)
    if item.status != FixedExpenseStatus.CONFIRMED:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=(
                "Sólo se puede pausar un gasto fijo confirmado. " f"Estado actual: {item.status}."
            ),
        )
    item.status = FixedExpenseStatus.PAUSED
    await db.flush()
    await db.refresh(item)
    return item


async def resume_fixed_expense(
    db: AsyncSession, fixed_expense_id: uuid.UUID, user_id: uuid.UUID
) -> FixedExpense:
    """Reanuda paused → confirmed (PHASE-15.2)."""
    item = await get_fixed_expense(db, fixed_expense_id, user_id)
    if item.status != FixedExpenseStatus.PAUSED:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=(
                "Sólo se puede reanudar un gasto fijo pausado. " f"Estado actual: {item.status}."
            ),
        )
    item.status = FixedExpenseStatus.CONFIRMED
    await db.flush()
    await db.refresh(item)
    return item


async def cancel_fixed_expense(
    db: AsyncSession, fixed_expense_id: uuid.UUID, user_id: uuid.UUID
) -> FixedExpense:
    """Marca como cancelled (PHASE-15.2). Aceptable desde
    pending/confirmed/paused. Uno dismissed no se cancela — ya está
    fuera del flujo. cancelled bloquea re-sugestion igual que
    dismissed (find_by_fingerprint matchea sin tocar status)."""
    item = await get_fixed_expense(db, fixed_expense_id, user_id)
    if item.status == FixedExpenseStatus.DISMISSED:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Un gasto fijo descartado no se puede cancelar.",
        )
    item.status = FixedExpenseStatus.CANCELLED
    await db.flush()
    await db.refresh(item)
    return item


async def update_fixed_expense(
    db: AsyncSession,
    fixed_expense_id: uuid.UUID,
    user_id: uuid.UUID,
    data: FixedExpenseUpdate,
) -> FixedExpense:
    """Actualiza campos editables (`auto_post`, `account_id`).

    Si se incluye `account_id` no nulo, valida que pertenece al
    usuario antes de asignarlo.
    """
    item = await get_fixed_expense(db, fixed_expense_id, user_id)
    payload = data.model_dump(exclude_unset=True)
    if "account_id" in payload and payload["account_id"] is not None:
        await ensure_account_exists(db, payload["account_id"], user_id)
    for field, value in payload.items():
        setattr(item, field, value)
    await db.flush()
    await db.refresh(item)
    return item


async def delete_fixed_expense(
    db: AsyncSession, fixed_expense_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Borra permanente. Un gasto fijo borrado y luego re-detectado
    en el siguiente scan re-aparecerá como `pending` — coherente con
    "borrar = empezar de cero".
    """
    item = await get_fixed_expense(db, fixed_expense_id, user_id)
    await remove_fixed_expense(db, item)


def _today_utc() -> date:
    """Hoy en UTC (coherente con el cron y con `next_due` que es un
    `DATE` sin timezone)."""
    return datetime.now(UTC).date()


# AUDIT-fix (drift mensual/anual): mapa de cadencia canónica (días) a
# número de meses de calendario. Las cadencias que son "naturalmente"
# múltiplos de semana (7, 14) NO están aquí — para ellas avanzar por
# días fijos es exacto. Para mensual (30) / trimestral (90) /
# semestral (180) / anual (365), avanzar +30/+90/+180/+365 días deriva:
# un cargo el día 31 de enero saltaría al 2 de marzo, luego al 1 de
# abril… El avance por calendario ancla siempre al mismo día del mes.
_CADENCE_MONTHS: dict[int, int] = {
    30: 1,  # mensual
    90: 3,  # trimestral
    180: 6,  # semestral
    365: 12,  # anual
}


def _add_months(anchor: date, months: int) -> date:
    """Suma `months` meses de calendario a `anchor` conservando el día.

    Robusto frente a fin de mes: si el día de `anchor` no existe en el
    mes destino (ej. 31 de enero + 1 mes → febrero no tiene 31), se
    acota al último día válido de ese mes (28/29 de febrero). No
    depende de `python-dateutil` (no es dependencia declarada en
    `pyproject.toml`); la aritmética manual evita introducir un import
    no documentado.
    """
    # Mes 0-indexado para que la aritmética de overflow sea limpia.
    zero_based = anchor.month - 1 + months
    year = anchor.year + zero_based // 12
    month = zero_based % 12 + 1
    # Último día del mes destino sin importar `calendar`: el día 1 del
    # mes siguiente menos un día.
    first_of_next = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last_day = (first_of_next - timedelta(days=1)).day
    return date(year, month, min(anchor.day, last_day))


def _advance_due(current_due: date, cadence_days: int, *, anchor_day: int) -> date:
    """Avanza un ciclo el `next_due` de un gasto fijo.

    AUDIT-fix: para cadencias mensuales/anuales avanza por calendario
    (`_add_months`) anclando al día original (`anchor_day`, derivado de
    `first_seen_at`) para que no derive con los meses de 28/30/31 días.
    Para semanal/quincenal (y cualquier cadencia no mapeada) mantiene
    el avance por días fijos, que para múltiplos de semana es exacto.

    `anchor_day` se aplica sobre el resultado del avance de meses para
    re-anclar el día: si en febrero se acotó al 28, el siguiente avance
    vuelve a intentar el día original (ej. 31) en lugar de arrastrar el
    28. Así el patrón "día 31 de cada mes" no se degrada a "día 28".
    """
    months = _CADENCE_MONTHS.get(cadence_days)
    if months is None:
        return current_due + timedelta(days=cadence_days)
    # Calcular el primer día del mes DESTINO (independiente del día
    # actual, que pudo haberse recortado a fin de mes en un ciclo
    # previo). Luego aplicar el `anchor_day` original acotándolo al
    # último día válido de ese mes. Así "día 31" produce 28/30/31 según
    # el mes SIN degradarse: cada ciclo parte del anchor, no del día
    # recortado anterior.
    target_first = _add_months(current_due.replace(day=1), months)
    if target_first.month == 12:
        first_of_next = date(target_first.year + 1, 1, 1)
    else:
        first_of_next = date(target_first.year, target_first.month + 1, 1)
    last_day_target = (first_of_next - timedelta(days=1)).day
    return target_first.replace(day=min(anchor_day, last_day_target))


async def autopost_due_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    today: date | None = None,
) -> AutopostResponse:
    """Crea transacciones `source=expected` para todos los gastos
    fijos `auto_post=True confirmed` cuyo `next_due` ya llegó (o
    pasó) y avanza su `next_due` un ciclo (PHASE-17.2).

    Si la fecha de hoy ya está varios ciclos por delante de
    `next_due` (caso: el usuario activó autopost hace meses pero
    sin transacciones reales en medio), avanzamos paso a paso
    creando una tx por cada ciclo perdido — coherente con la
    semántica "cada ciclo posteo una". Cap a 12 ciclos por
    seguridad para evitar avalanchas si los datos vienen mal.

    `today` se pasa explícitamente para tests deterministas; en
    runtime usa UTC.
    """
    today = today or _today_utc()
    items = await list_due_for_autopost(db, user_id, today=today)

    created = 0
    advanced = 0
    max_backfill_cycles = 12
    for item in items:
        # PHASE-19.1: el autopost necesita una cuenta para imputar la
        # tx. Si el gasto fijo no la tiene asignada, lo saltamos
        # silenciosamente — el frontend pinta un aviso para que el
        # usuario lo configure.
        if item.account_id is None:
            continue
        cycles = 0
        # AUDIT-fix: ancla del día de cargo para el avance por
        # calendario. `first_seen_at` es la primera ocurrencia real del
        # patrón, así que su día es el "día de cargo" canónico (ej.
        # "día 31 de cada mes"). Si por algún dato legacy faltara, el
        # día del `next_due` actual sirve de respaldo.
        anchor_day = (item.first_seen_at or item.next_due).day
        while item.next_due <= today and cycles < max_backfill_cycles:
            tx = Transaction(
                user_id=user_id,
                account_id=item.account_id,
                category_id=item.category_id,
                amount=item.amount,
                currency=item.currency,
                # Se postea como datetime UTC al inicio del día para que
                # caiga en el calendario del mes correcto independientemente
                # de la TZ del cliente.
                occurred_at=datetime.combine(item.next_due, datetime.min.time()).replace(
                    tzinfo=UTC,
                ),
                description=item.raw_description,
                source=TransactionSource.EXPECTED,
            )
            db.add(tx)
            # AUDIT-fix: avance por calendario para mensual/trimestral/
            # semestral/anual (evita la deriva de usar 30/90/180/365
            # días fijos); por días para semanal/quincenal.
            item.next_due = _advance_due(item.next_due, item.cadence_days, anchor_day=anchor_day)
            created += 1
            cycles += 1
        if cycles > 0:
            advanced += 1

    await db.flush()
    return AutopostResponse(created=created, advanced=advanced)


async def scan_for_user(db: AsyncSession, user_id: uuid.UUID) -> ScanResponse:
    """Ejecuta el detector y persiste/refresca gastos fijos.

    Política:
    - Patrones que ya tienen un row (mismo fingerprint): se refrescan
      `last_seen_at`, `next_due`, `occurrence_count` y `confidence`.
      `status` y `category_id` NO se tocan — respetan la decisión del
      usuario.
    - Patrones nuevos sin fingerprint match: se crean como `pending`.
    - Patrones que matchean a un gasto fijo `dismissed`: NO se
      crea fila nueva (la `dismissed` ya existe; sólo se refresca).
      Resultado: el usuario que descartó algo no lo vuelve a ver.
    """
    candidates = await detector.detect_for_user(db, user_id)

    created = 0
    updated = 0
    for cand in candidates:
        existing = await find_by_fingerprint(
            db,
            user_id,
            merchant=cand.merchant,
            amount=cand.amount,
            currency=cand.currency,
            cadence_days=cand.cadence_days,
        )
        if existing is not None:
            existing.last_seen_at = cand.last_seen_at
            existing.next_due = cand.next_due
            existing.occurrence_count = cand.occurrence_count
            existing.confidence = cand.confidence
            existing.raw_description = cand.raw_description
            updated += 1
        else:
            item = FixedExpense(
                user_id=user_id,
                merchant=cand.merchant,
                raw_description=cand.raw_description,
                amount=cand.amount,
                currency=cand.currency,
                cadence_days=cand.cadence_days,
                next_due=cand.next_due,
                status=FixedExpenseStatus.PENDING,
                category_id=cand.category_id,
                first_seen_at=cand.first_seen_at,
                last_seen_at=cand.last_seen_at,
                occurrence_count=cand.occurrence_count,
                confidence=cand.confidence,
            )
            await persist_fixed_expense(db, item)
            created += 1

    await db.flush()

    # Activos = todo lo que no esté dismissed (pending + confirmed).
    pending = await list_in_db(db, user_id, status=FixedExpenseStatus.PENDING)
    confirmed = await list_in_db(db, user_id, status=FixedExpenseStatus.CONFIRMED)
    return ScanResponse(
        created=created,
        updated=updated,
        total_active_after=len(pending) + len(confirmed),
    )
