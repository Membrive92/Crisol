"""Lógica de negocio del módulo budgets (PHASE-12.1)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.budgets.models import Budget
from app.modules.personal_finance.budgets.repository import (
    create_budget as persist_budget,
)
from app.modules.personal_finance.budgets.repository import (
    delete_budget as remove_budget,
)
from app.modules.personal_finance.budgets.repository import (
    get_active_budget_for_category,
    get_budget_by_id,
    list_active_budgets,
    sum_expenses_in_period,
)
from app.modules.personal_finance.budgets.schemas import (
    BudgetCreate,
    BudgetStatusItem,
    BudgetStatusResponse,
    BudgetUpdate,
)
from app.modules.personal_finance.dashboard.service import ensure_rates_for_user_scope

WARNING_THRESHOLD = 80.0
OVER_THRESHOLD = 100.0


def _today_utc() -> date:
    """`date.today()` usa la TZ local; el cálculo del mes para budgets
    debe ser determinista, así que usamos UTC.
    """
    return datetime.now(UTC).date()


def _month_bounds_utc(today: date) -> tuple[datetime, datetime]:
    """Inicio y fin del mes calendario que contiene `today`, en UTC.

    `month_start = YYYY-MM-01 00:00:00+00`,
    `month_end = último-día-del-mes 23:59:59.999999+00`.
    """
    month_start = datetime(today.year, today.month, 1, tzinfo=UTC)
    if today.month == 12:
        next_month_start = datetime(today.year + 1, 1, 1, tzinfo=UTC)
    else:
        next_month_start = datetime(today.year, today.month + 1, 1, tzinfo=UTC)
    month_end = next_month_start - timedelta(microseconds=1)
    return month_start, month_end


def _classify_status(percent_used: float) -> str:
    """Clasifica `percent_used` en `ok|warning|over`."""
    if percent_used > OVER_THRESHOLD:
        return "over"
    if percent_used >= WARNING_THRESHOLD:
        return "warning"
    return "ok"


async def list_budgets(db: AsyncSession, user_id: uuid.UUID) -> list[Budget]:
    """Presupuestos activos del usuario."""
    return await list_active_budgets(db, user_id, today=_today_utc())


async def get_budget(
    db: AsyncSession, budget_id: uuid.UUID, user_id: uuid.UUID
) -> Budget:
    """Obtiene un presupuesto o 404."""
    budget = await get_budget_by_id(db, budget_id, user_id)
    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Presupuesto no encontrado"
        )
    return budget


async def create_budget(
    db: AsyncSession, user_id: uuid.UUID, data: BudgetCreate
) -> Budget:
    """Crea un nuevo presupuesto.

    Política: un solo presupuesto activo por (user, category) a la
    vez. Si ya hay uno activo para esa categoría (o global), 409.
    Para reemplazar: DELETE el actual y crear el nuevo.
    """
    today = _today_utc()
    existing = await get_active_budget_for_category(
        db, user_id, category_id=data.category_id, today=today
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Ya existe un presupuesto activo para esta categoría. "
                "Cierra el actual antes de crear uno nuevo."
            ),
        )

    budget = Budget(
        user_id=user_id,
        category_id=data.category_id,
        amount=data.amount,
        currency=data.currency.upper(),
        effective_from=data.effective_from,
        convert_other_currencies=data.convert_other_currencies,
    )
    return await persist_budget(db, budget)


async def update_budget(
    db: AsyncSession,
    budget_id: uuid.UUID,
    user_id: uuid.UUID,
    data: BudgetUpdate,
) -> Budget:
    """Actualiza amount o currency del presupuesto.

    `effective_from`/`category_id` no se pueden cambiar — para eso,
    cerrar y crear nuevo (preserva histórico real).
    """
    budget = await get_budget(db, budget_id, user_id)
    payload = data.model_dump(exclude_unset=True)
    if "currency" in payload and payload["currency"] is not None:
        payload["currency"] = payload["currency"].upper()
    for field, value in payload.items():
        setattr(budget, field, value)
    await db.flush()
    await db.refresh(budget)
    return budget


async def close_budget(
    db: AsyncSession, budget_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Cierra un presupuesto poniendo `effective_to = today`.

    Mantiene el row para histórico — DELETE real sería destructivo y
    rompería la trazabilidad de "qué presupuesto estuvo vigente
    cuándo". Si efectivamente se quiere borrar (por ejemplo budget
    creado por error inmediatamente), el frontend puede llamar a
    DELETE dos veces — la segunda no encuentra activo y devuelve
    404 (idempotente desde el lado del usuario).
    """
    budget = await get_budget(db, budget_id, user_id)
    if budget.effective_to is not None and budget.effective_to < _today_utc():
        # Ya está cerrado en el pasado — DELETE real para limpiar.
        await remove_budget(db, budget)
        return
    budget.effective_to = _today_utc()
    await db.flush()
    await db.refresh(budget)


async def get_alert_for_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    category_id: uuid.UUID | None,
) -> BudgetStatusItem | None:
    """Devuelve `BudgetStatusItem` para el budget activo de una
    categoría sólo si está en `warning|over`. `None` en `ok` o sin
    budget. PHASE-14.5 — usado tras crear una transacción para
    notificar proactivamente.

    Búsqueda: primero el budget de la categoría exacta (si tx tiene
    categoría); si no encuentra, prueba el global. Si la tx no tiene
    categoría, sólo el global.
    """
    today = _today_utc()
    candidates: list[uuid.UUID | None] = []
    if category_id is not None:
        candidates.append(category_id)
    candidates.append(None)

    for candidate_cat in candidates:
        budget = await get_active_budget_for_category(
            db, user_id, category_id=candidate_cat, today=today
        )
        if budget is None:
            continue
        month_start, month_end = _month_bounds_utc(today)
        # PHASE-16: si el budget tiene cross-currency on, asegura
        # que las tasas de las fechas relevantes están en BD antes
        # de hacer la SUM convertida.
        if budget.convert_other_currencies:
            await ensure_rates_for_user_scope(
                db,
                user_id,
                target_currency=budget.currency,
                date_from=month_start,
                date_to=month_end,
            )
        spent, unconv = await sum_expenses_in_period(
            db,
            user_id,
            currency=budget.currency,
            month_start=month_start,
            month_end=month_end,
            category_id=budget.category_id,
            convert_other_currencies=budget.convert_other_currencies,
        )
        amount = Decimal(budget.amount)
        if amount <= 0:
            continue
        percent_used = float(spent / amount * Decimal("100"))
        status = _classify_status(percent_used)
        if status == "ok":
            continue
        return BudgetStatusItem(
            budget=budget,
            spent_this_month=spent,
            remaining=amount - spent,
            percent_used=round(percent_used, 2),
            status=status,
            unconvertible_count=unconv,
        )
    return None


async def get_budgets_status(
    db: AsyncSession, user_id: uuid.UUID
) -> BudgetStatusResponse:
    """Para cada presupuesto activo, calcula gasto del mes y status.

    El "mes" es el calendario UTC actual (1 a último día). Reusa el
    helper `sum_expenses_in_period` del repository — query única por
    presupuesto. Para usuarios con muchos budgets esto se podría
    optimizar a una sola query con GROUP BY, pero para los volúmenes
    esperados (< 20 categorías) cada query es ~ms.
    """
    today = _today_utc()
    month_start, month_end = _month_bounds_utc(today)

    budgets = await list_active_budgets(db, user_id, today=today)
    # PHASE-16: si algún budget tiene cross-currency on, backfilleamos
    # las tasas para el rango del mes — single call cubre todos los
    # budgets cross-currency del usuario en este request.
    for currency in {b.currency for b in budgets if b.convert_other_currencies}:
        await ensure_rates_for_user_scope(
            db,
            user_id,
            target_currency=currency,
            date_from=month_start,
            date_to=month_end,
        )

    items: list[BudgetStatusItem] = []
    for budget in budgets:
        spent, unconv = await sum_expenses_in_period(
            db,
            user_id,
            currency=budget.currency,
            month_start=month_start,
            month_end=month_end,
            category_id=budget.category_id,
            convert_other_currencies=budget.convert_other_currencies,
        )
        amount = Decimal(budget.amount)
        remaining = amount - spent
        percent_used = float(spent / amount * Decimal("100")) if amount > 0 else 0.0
        items.append(
            BudgetStatusItem(
                budget=budget,
                spent_this_month=spent,
                remaining=remaining,
                percent_used=round(percent_used, 2),
                status=_classify_status(percent_used),
                unconvertible_count=unconv,
            )
        )
    return BudgetStatusResponse(
        items=items,
        month_start=month_start.date(),
        month_end=month_end.date(),
    )
