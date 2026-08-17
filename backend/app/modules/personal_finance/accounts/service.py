"""Lógica de negocio del módulo accounts (PHASE-19.1, PHASE-19.4)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.accounts.models import (
    UNVALUED_ACCOUNT_TYPES,
    Account,
    AccountNature,
    AccountType,
)
from app.modules.personal_finance.accounts.repository import (
    clear_default_accounts,
    clear_settlement_references_to,
    count_child_accounts,
    count_transactions_for_account,
    find_statement_seams,
    get_account_by_id,
    get_account_by_name,
    get_account_movement_until,
    get_balances_for_user,
)
from app.modules.personal_finance.accounts.repository import (
    create_account as persist_account,
)
from app.modules.personal_finance.accounts.repository import (
    delete_account as remove_account,
)
from app.modules.personal_finance.accounts.repository import (
    list_accounts as list_all,
)
from app.modules.personal_finance.accounts.schemas import (
    ASSET_ACCOUNT_TYPES,
    LIABILITY_ACCOUNT_TYPES,
    AccountBalance,
    AccountBalancesResponse,
    AccountCreate,
    AccountUpdate,
    StatementSeamOut,
)
from app.modules.personal_finance.debt.amortization import build_schedule
from app.modules.personal_finance.debt.installments_model import (
    LiabilityInstallment,
)
from app.modules.personal_finance.debt.installments_repository import (
    generate_installments_for_account,
    installments_by_account,
    plan_installments_covering_principal,
    resolve_liability_outstanding,
    schedule_outstanding,
)
from app.modules.personal_finance.debt.installments_repository import (
    get_installment as repo_get_installment,
)
from app.modules.personal_finance.debt.installments_repository import (
    list_installments as repo_list_installments,
)
from app.modules.personal_finance.debt.installments_repository import (
    mark_installment_paid as repo_mark_paid,
)
from app.modules.personal_finance.debt.installments_repository import (
    unmark_installment_paid as repo_unmark_paid,
)
from app.modules.personal_finance.debt.installments_repository import (
    update_installment_amount_and_date as repo_update_installment,
)
from app.modules.personal_finance.debt.schemas import (
    AmortizationRowResponse,
    AmortizationScheduleResponse,
)


def _nature_for_type(account_type: AccountType) -> AccountNature:
    """Asigna `nature` automáticamente según el `type` (PHASE-22)."""
    if account_type in LIABILITY_ACCOUNT_TYPES:
        return AccountNature.LIABILITY
    return AccountNature.ASSET


async def _validate_debt_category_link(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    account_type: AccountType,
    category_id: uuid.UUID | None,
) -> None:
    """PHASE-30.4 — Verifica que el `category_id` propuesto se puede
    asociar a esta cuenta.

    Reglas:
    - `None` se acepta siempre (desvincular).
    - La cuenta debe ser liability (no tiene sentido para assets).
    - La categoría debe existir y pertenecer al usuario.
    - La categoría debe tener `role IN (DEBT_PAYMENT, DEBT_INTEREST)`.

    Lanza 400 con mensaje claro en cualquier violación; nunca 404 para
    no filtrar existencia de categorías ajenas.
    """
    if category_id is None:
        return
    if account_type not in LIABILITY_ACCOUNT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("Sólo las cuentas de deuda pueden vincularse a una " "categoría de pagos."),
        )
    from sqlalchemy import select

    from app.modules.personal_finance.categories.models import (
        Category,
        CategoryRole,
    )

    result = await db.execute(
        select(Category).where(Category.id == category_id).where(Category.user_id == user_id)
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La categoría seleccionada no existe.",
        )
    if category.role not in {CategoryRole.DEBT_PAYMENT, CategoryRole.DEBT_INTEREST}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "La categoría vinculada debe tener rol de deuda " "(DEBT_PAYMENT o DEBT_INTEREST)."
            ),
        )


async def _validate_settlement_account(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    account_id: uuid.UUID | None,
    account_type: AccountType,
    settlement_account_id: uuid.UUID | None,
) -> None:
    """PHASE-47.A — Verifica que la cuenta de cargo declarada tiene sentido.

    Reglas:
    - `None` se acepta siempre (no declarado / desvincular).
    - Sólo un pasivo se cobra desde otra cuenta.
    - La cuenta apuntada existe, es del usuario y es de ACTIVO — apuntar a otra
      deuda no describe de dónde sale el dinero, sólo mueve la pregunta.
    - No puede apuntarse a sí misma.

    Lanza 400 con mensaje claro; nunca 404, para no filtrar la existencia de
    cuentas ajenas (mismo criterio que `_validate_debt_category_link`).
    """
    if settlement_account_id is None:
        return
    if account_type not in LIABILITY_ACCOUNT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sólo una cuenta de deuda declara desde qué cuenta se cobra.",
        )
    if account_id is not None and settlement_account_id == account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Una cuenta no puede cobrarse a sí misma.",
        )
    target = await get_account_by_id(db, settlement_account_id, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La cuenta de cargo seleccionada no existe.",
        )
    if target.nature != AccountNature.ASSET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "La cuenta de cargo debe ser una cuenta de activo "
                "(banco, ahorro, efectivo): es de donde sale el dinero."
            ),
        )


async def _validate_parent_card(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    account_id: uuid.UUID | None,
    account_type: AccountType,
    parent_account_id: uuid.UUID | None,
    has_own_plan: bool,
) -> None:
    """PHASE-35 — Colgar un pasivo financiado de la tarjeta con la que se financió.

    Fuente ÚNICA de esta validación, usada al crear y al declarar el vínculo
    después. Estaba escrita sólo en `create_account`; duplicarla para el update
    es exactamente el patrón que costó la lección de [PHASE-46] (dos listas que
    describen lo mismo y divergen).

    PHASE-47.E4 — el hijo ya NO tiene que ser de tipo `credit_card`. La regla
    original valía cuando el único caso era «compra a plazos en tienda», pero un
    RECIBO de la tarjeta aplazado es igual de financiado-en-esa-tarjeta y el
    usuario lo da de alta como préstamo. Lo que define a una hija es de dónde se
    cobra, no cómo se tipó: el banco las cobra a todas dentro de la misma línea
    agregada, y esa línea es la que reparte la reconciliación.
    """
    if parent_account_id is None:
        return
    if account_id is not None and parent_account_id == account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Una cuenta no puede colgar de sí misma.",
        )
    parent = await get_account_by_id(db, parent_account_id, user_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La tarjeta a la que asociar la financiación no existe.",
        )
    if parent.is_archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La tarjeta indicada está archivada; no puedes anidar financiaciones en ella.",
        )
    if parent.type != AccountType.CREDIT_CARD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sólo se pueden colgar financiaciones de una tarjeta de crédito.",
        )
    if parent.parent_account_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede anidar: la tarjeta indicada ya es una financiación.",
        )
    if account_type not in LIABILITY_ACCOUNT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sólo una cuenta de deuda puede colgar de una tarjeta.",
        )
    if not has_own_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Una financiación necesita su importe, TIN, plazo (meses) "
                "y fecha de inicio para generar el cuadro."
            ),
        )


DEFAULT_REFERENCE_CURRENCY = "EUR"


async def list_accounts(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    include_archived: bool = False,
) -> list[Account]:
    """Lista las cuentas del usuario."""
    return await list_all(db, user_id, include_archived=include_archived)


async def get_account(db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID) -> Account:
    """Obtiene una cuenta o lanza 404."""
    account = await get_account_by_id(db, account_id, user_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cuenta no encontrada")
    return account


async def ensure_account_exists(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID
) -> Account:
    """Igual que `get_account` — alias semántico para callers (transactions,
    imports) que sólo quieren validar pertenencia antes de asociar.
    """
    return await get_account(db, account_id, user_id)


async def create_account(db: AsyncSession, user_id: uuid.UUID, data: AccountCreate) -> Account:
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
    if data.type in {AccountType.LOAN, AccountType.MORTGAGE} and (
        data.opening_balance is None or data.opening_balance <= 0
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("El capital del préstamo o hipoteca es obligatorio " "y debe ser mayor que 0."),
        )
    accepts_amortization = data.type in {
        AccountType.LOAN,
        AccountType.MORTGAGE,
        AccountType.CREDIT_CARD,  # PHASE-24.2: tarjetas financiadas con plan fijo.
    }
    await _validate_debt_category_link(
        db, user_id, account_type=data.type, category_id=data.category_id
    )
    await _validate_settlement_account(
        db,
        user_id,
        account_id=None,
        account_type=data.type,
        settlement_account_id=data.settlement_account_id,
    )
    # PHASE-32 (HIGH#2) — la cuenta principal refleja ahorro neto y SÓLO
    # tiene sentido sobre un activo. Una cuenta de pasivo no puede ser
    # principal: su carve-out de transferencias no aplica y su saldo es
    # deuda, no ahorro. La UI ya oculta el botón; lo reforzamos en backend.
    if data.is_default and _nature_for_type(data.type) == AccountNature.LIABILITY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Una cuenta de pasivo no puede ser la cuenta principal.",
        )
    await _validate_parent_card(
        db,
        user_id,
        account_id=None,
        account_type=data.type,
        parent_account_id=data.parent_account_id,
        has_own_plan=(
            data.opening_balance is not None
            and data.opening_balance > 0
            and data.apr is not None
            and data.term_months is not None
            and data.start_date is not None
        ),
    )
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
        is_default=data.is_default,
        counts_as_debt=data.counts_as_debt,
        category_id=data.category_id,
        parent_account_id=data.parent_account_id,
        settlement_account_id=data.settlement_account_id,
    )
    persisted = await persist_account(db, account)
    # PHASE-32: si se crea como principal, desmarcar cualquier otra.
    if data.is_default:
        await clear_default_accounts(db, user_id, except_id=persisted.id)
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
    # Se captura ANTES de re-sincronizar `nature` con el nuevo `type`.
    was_asset = account.nature == AccountNature.ASSET
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
    if "category_id" in payload:
        effective_type = payload.get("type") or account.type
        await _validate_debt_category_link(
            db,
            user_id,
            account_type=effective_type,
            category_id=payload["category_id"],
        )
    if "parent_account_id" in payload:
        effective_type = payload.get("type") or account.type
        # El cuadro ya existe: se comprueba contra las cuotas persistidas, no
        # contra el payload — exigir apr/plazo/fecha en un PATCH obligaría a
        # reenviar datos que ya están, y el cuadro es lo que de verdad importa.
        existing_rows = await repo_list_installments(db, account.id, user_id)
        await _validate_parent_card(
            db,
            user_id,
            account_id=account.id,
            account_type=effective_type,
            parent_account_id=payload["parent_account_id"],
            has_own_plan=bool(existing_rows)
            or (
                (payload.get("apr") or account.apr) is not None
                and (payload.get("term_months") or account.term_months) is not None
                and (payload.get("start_date") or account.start_date) is not None
            ),
        )
    if "settlement_account_id" in payload:
        effective_type = payload.get("type") or account.type
        await _validate_settlement_account(
            db,
            user_id,
            account_id=account.id,
            account_type=effective_type,
            settlement_account_id=payload["settlement_account_id"],
        )
    # AUDIT MEDIUM#6 — archivar una cuenta la saca de la pre-selección (los
    # formularios sólo cargan cuentas activas). Si era la principal, limpiamos
    # is_default para no dejar un puntero colgante a una cuenta invisible. El
    # archivado gana sobre cualquier is_default que venga en el payload.
    if payload.get("is_archived") is True:
        payload["is_default"] = False
    # PHASE-32 (HIGH#2 + fix-review) — una cuenta de pasivo no puede ser la
    # cuenta principal. Cubre DOS caminos: (a) marcar is_default en un
    # pasivo, y (b) convertir a pasivo (cambio de `type`) una cuenta que YA
    # es principal sin tocar is_default en el payload — el guard antiguo sólo
    # miraba `payload["is_default"]` y se saltaba este caso. `account.nature`
    # ya está re-sincronizada arriba si el payload cambió el `type`.
    effective_is_default = payload.get("is_default", account.is_default)
    if effective_is_default and account.nature == AccountNature.LIABILITY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Una cuenta de pasivo no puede ser la cuenta principal. "
                "Desmarca la principal antes de cambiarla a un tipo de deuda."
            ),
        )
    # Marcar como principal desmarca el resto (única por usuario).
    if payload.get("is_default") is True:
        await clear_default_accounts(db, user_id, except_id=account.id)
    # PHASE-47.A — si esta cuenta deja de ser un ACTIVO, los pasivos que
    # declaraban cobrarse desde ella se quedan apuntando a algo que el propio
    # validador rechaza. Nadie revalida las referencias ENTRANTES, así que se
    # limpian aquí: es la única forma de que no quede un estado inalcanzable
    # desde la interfaz (la siguiente edición de esos pasivos daría 400 sobre
    # un campo que el formulario pinta como válido).
    if was_asset and account.nature != AccountNature.ASSET:
        await clear_settlement_references_to(db, user_id, account.id)
    for field, value in payload.items():
        setattr(account, field, value)
    # PHASE-47.A — y el reverso, después del setattr para que gane sobre el
    # payload: una cuenta que deja de ser pasivo no se cobra desde ningún sitio.
    # Sin esto, convertir una tarjeta en cuenta de ahorro dejaba el vínculo
    # persistido e invisible, y volver a convertirla en pasivo lo resucitaba.
    if account.nature != AccountNature.LIABILITY:
        account.settlement_account_id = None
    await db.flush()
    await db.refresh(account)
    return account


async def reconcile_account_balance(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    current_balance: Decimal,
) -> Account:
    """PHASE-34 — 'Cuadrar saldo'. Ancla el saldo de una cuenta de ACTIVO al
    valor real que declara el usuario (lo que dice su banco hoy), ajustando
    `opening_balance = saldo_real − Σmovimientos`. Así el saldo mostrado pasa
    a ser exactamente el declarado, SIN reconstruir el histórico ni emparejar
    transferencias.

    Sirve para dos cosas con el mismo gesto:
    - Fijar el saldo inicial de una cuenta recién creada (no hay que recordar
      el saldo de hace meses).
    - Re-cuadrar cuando el saldo se desvía de la realidad (catch de
      descuadres por un movimiento olvidado o mal categorizado).

    Solo activos: la deuda (loan/mortgage/credit_card) tiene su saldo dirigido
    por el cuadro de amortización / las tx de deuda → 400 si no es ASSET.
    """
    account = await get_account_by_id(db, account_id, user_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cuenta no encontrada")
    if account.nature != AccountNature.ASSET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Solo se puede cuadrar el saldo de cuentas de activo. La deuda "
                "se gestiona en su módulo (cuadro de amortización / operaciones)."
            ),
        )
    # Σmovimientos de ESTA cuenta, en su moneda nativa (mismo cálculo que el
    # saldo mostrado). `get_balances_for_user` devuelve el movimiento por
    # cuenta sin el opening; el saldo es `opening + movimiento`.
    movements = await get_balances_for_user(db, user_id)
    movement = movements.get(account_id, Decimal("0"))
    account.opening_balance = (current_balance - movement).quantize(Decimal("0.01"))
    account.opening_balance_date = datetime.now(UTC).date()
    # PHASE-39 — persistir el saldo declarado como ancla: si luego se
    # importa historia anterior a hoy, `re_anchor_from_stored` re-deriva
    # el opening preservando `saldo(hoy) == current_balance`.
    account.anchored_statement_balance = current_balance.quantize(Decimal("0.01"))
    await db.flush()
    await db.refresh(account)
    return account


async def anchor_account_balance_at(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    *,
    balance: Decimal,
    at: datetime,
    currency: str | None = None,
) -> dict[str, str] | None:
    """PHASE-39 — ancla el saldo de una cuenta ASSET al declarado por el
    EXTRACTO en una fecha (pasada): `opening_balance = saldo(D) − Σmov(≤D)`.

    Es la variante automática de `reconcile_account_balance` ("Cuadrar
    saldo"): misma semántica (ajustar `opening_balance`, sellar
    `opening_balance_date`), pero anclada a la fecha del último movimiento
    del extracto en lugar de a hoy. La invoca el commit de imports cuando
    el fichero trae columna Saldo.

    Guardas (devuelve `None` sin tocar nada si alguna falla):
    - Sólo cuentas de ACTIVO (la deuda la gobierna su cuadro).
    - `currency` (si se pasa) debe coincidir con la de la cuenta.
    - Un ancla existente MÁS RECIENTE nunca se pisa con una más vieja:
      si `opening_balance_date > fecha del extracto`, se salta. Así un
      import de un extracto antiguo (backfill) no degrada un anclaje
      fresco (manual o de un extracto posterior).

    A diferencia del reconcile manual, NO lanza HTTPException: el anclaje
    es un efecto secundario best-effort del import — si no procede, el
    import sigue siendo válido.
    """
    account = await get_account_by_id(db, account_id, user_id)
    if account is None or account.nature != AccountNature.ASSET:
        return None
    if currency is not None and account.currency != currency.upper():
        return None
    anchor_date = at.date()
    if account.opening_balance_date is not None and account.opening_balance_date > anchor_date:
        return None
    # Σmov hasta el FIN del día del ancla (las tx de import se guardan a
    # las 00:00): incluye todos los movimientos de ese día, que es lo que
    # el saldo del extracto ya refleja.
    at_utc = at if at.tzinfo is not None else at.replace(tzinfo=UTC)
    until = at_utc.replace(hour=23, minute=59, second=59, microsecond=999999)
    movement = await get_account_movement_until(db, user_id, account_id, until=until)
    account.opening_balance = (balance - movement).quantize(Decimal("0.01"))
    account.opening_balance_date = anchor_date
    account.anchored_statement_balance = balance.quantize(Decimal("0.01"))
    await db.flush()
    return {"balance": str(balance), "date": anchor_date.isoformat()}


async def re_anchor_from_stored(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
) -> bool:
    """PHASE-39 — re-deriva `opening_balance` desde el ancla PERSISTIDA.

    Cuando un import añade movimientos ANTERIORES a la fecha del ancla
    (reimportar extractos viejos, backfill de historia), la Σmov(≤ancla)
    cambia y el `opening_balance` calculado en el anclaje original dejaría
    el saldo desviado exactamente en la suma de las filas nuevas. Este
    helper restaura el invariante `saldo(fecha_ancla) ==
    anchored_statement_balance` recalculando el opening con la Σ actual.

    No-op (False) si la cuenta no existe, no es ASSET o nunca fue anclada
    (sin `opening_balance_date` o sin `anchored_statement_balance`).
    Idempotente: recalcular dos veces seguidas da el mismo opening.
    """
    account = await get_account_by_id(db, account_id, user_id)
    if (
        account is None
        or account.nature != AccountNature.ASSET
        or account.opening_balance_date is None
        or account.anchored_statement_balance is None
    ):
        return False
    until = datetime(
        account.opening_balance_date.year,
        account.opening_balance_date.month,
        account.opening_balance_date.day,
        23,
        59,
        59,
        999999,
        tzinfo=UTC,
    )
    movement = await get_account_movement_until(db, user_id, account_id, until=until)
    account.opening_balance = (account.anchored_statement_balance - movement).quantize(
        Decimal("0.01")
    )
    await db.flush()
    return True


async def delete_account(db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID) -> None:
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
    # PHASE-35 — `parent_account_id` es ON DELETE CASCADE: borrar una tarjeta
    # con compras a plazos anidadas arrastraría cada hija Y su tx de deuda
    # emparejada (via CASCADE en transactions.account_id), resucitando el
    # activo fantasma en la cuenta origen y perdiendo la deuda. Se archiva.
    child_count = await count_child_accounts(db, account_id, user_id)
    if child_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"La cuenta tiene {child_count} compra(s) a plazos asociada(s). "
                "Archívala en lugar de borrarla para no perder su deuda."
            ),
        )
    await remove_account(db, account)


async def _convert_at_today(
    db: AsyncSession,
    amount: Decimal,
    *,
    from_currency: str,
    target_currency: str,
) -> Decimal | None:
    """Convierte `amount` con la tasa de HOY o devuelve `None` si no hay
    tasa.

    AUDIT-FIX (finding 5): se replica aquí el mismo helper que ya existe
    en `debt/health.py` y `debt/service.py` (cada uno con su
    copia para evitar dependencias circulares con `currency.service`).
    La lógica real vive en `currency.service.convert`; aquí sólo
    decidimos "snapshot a hoy" + señalización de tasa ausente.
    """
    from datetime import UTC, datetime

    from app.modules.currency.service import convert as currency_convert

    result = await currency_convert(
        db,
        amount=amount,
        from_currency=from_currency,
        to_currency=target_currency,
        at_date=datetime.now(UTC).date(),
    )
    if result.fallback == "missing":
        return None
    return result.amount


async def get_balances(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    target_currency: str | None = None,
) -> AccountBalancesResponse:
    """Saldo por cuenta + agregados de patrimonio (PHASE-19.4).

    Sólo cuentas no archivadas entran en los totales agregados, pero
    `items` incluye también las archivadas (display sólo).

    Dos modos (AUDIT-FIX finding 5):

    - **Crudo (por defecto, `target_currency=None`)**: comportamiento
      histórico intacto. Si las monedas activas no son homogéneas,
      `mixed_currencies=True` y los totales son suma cruda en monedas
      mezcladas — la UI debe avisarlo. NO se rompe ningún consumidor
      existente del flag.
    - **Convertido (`target_currency="USD"`, etc.)**: cada saldo se
      convierte a `target_currency` con la tasa de HOY (snapshot
      simple, igual que `/debt-health` y `/debt-history`). Las cuentas
      cuya moneda no tiene tasa quedan EXCLUIDAS del agregado (mismo
      contrato que el modo crudo con `mixed_currencies`) pero siguen en
      `items` con su saldo nativo. En este modo `net_worth` ya es una
      cifra con sentido y `mixed_currencies` se reporta `False` (todo
      viene homogeneizado a `reference_currency`).

    AUDIT-2026-06 — En modo convertido, `items[*]` también se reexpresa
    en `target_currency` (no sólo los agregados). Antes los items se
    quedaban nativos, así que la DebtList y los tiles del hero salían en
    divisa distinta a los KPIs/charts de la misma pantalla. La cuenta
    sin tasa es la única excepción: se queda nativa (y fuera del
    agregado). Se preserva `opening + movements == current`.
    """
    accounts = await list_all(db, user_id, include_archived=True)
    movements = await get_balances_for_user(db, user_id)
    # PHASE-36 — "el cuadro manda": para las liabilities CON cuadro, la deuda
    # viva sale de las cuotas no pagadas (no de los movimientos). Así las
    # aportaciones (que marcan cuotas pagadas) bajan la deuda, y el saldo
    # cuadra con el cuadro de amortización mostrado en /schedule.
    liability_ids = [a.id for a in accounts if a.nature == AccountNature.LIABILITY]
    insts_by_account = await installments_by_account(db, user_id, liability_ids)

    # PHASE-34 — La lista de cuentas muestra la CAJA REAL de cada cuenta (lo
    # que de verdad hay en ella), incluida la principal. Antes (PHASE-32) la
    # principal mostraba "ahorro neto" (excluía transferencias internas), lo
    # que daba un saldo que NO coincidía con la caja real y confundía (la
    # principal salía igual que el cashflow del mes). El ahorro neto / tasa de
    # ahorro siguen en el dashboard como métricas propias. El agregado de
    # patrimonio ya usaba caja, así que esto no cambia el net_worth (HIGH#1).
    effective_target = target_currency.upper() if target_currency else None

    seams_by_account = await find_statement_seams(db, user_id)

    items: list[AccountBalance] = []
    active_currencies: set[str] = set()
    total_assets = Decimal("0")
    total_liabilities = Decimal("0")

    for account in accounts:
        cash_movement = movements.get(account.id, Decimal("0"))
        cash_balance = account.opening_balance + cash_movement
        # PHASE-34: la caja real, igual para todas las cuentas (ver nota arriba).
        display_movement = cash_movement
        display_balance = cash_balance
        # PHASE-36: liability con cuadro → la deuda viva la manda el cuadro
        # (Σ principal de cuotas no pagadas), no los movimientos. El
        # `movements_balance` se reexpresa para conservar la invariante
        # `opening + movements == current`.
        resolved = (
            resolve_liability_outstanding(
                opening_balance=account.opening_balance,
                movements_balance=cash_movement,
                installments=insts_by_account.get(account.id, []),
            )
            if account.nature == AccountNature.LIABILITY
            else None
        )
        if resolved is not None and resolved.from_schedule:
            display_balance = resolved.value
            cash_balance = resolved.value
            display_movement = resolved.value - account.opening_balance
        is_unvalued = account.type in UNVALUED_ACCOUNT_TYPES

        # AUDIT-2026-06 — Modo convertido: además del agregado, cada item
        # se reexpresa en la divisa destino (tasa de hoy) para que la
        # DebtList y los tiles del hero cuadren con los agregados y con el
        # resto de la pantalla. Sin tasa, el item se queda nativo y la
        # cuenta queda fuera del agregado (mismo contrato que el modo
        # crudo). `cash_balance == display_balance` siempre, así que una
        # sola conversión sirve para item y agregado; `opening + movements
        # == current` se conserva reconstruyendo movements del converted.
        item_currency = account.currency
        item_opening = account.opening_balance
        item_movements = display_movement
        item_balance = display_balance
        aggregable_balance: Decimal | None = cash_balance
        if effective_target is not None and account.currency.upper() != effective_target:
            conv_balance = await _convert_at_today(
                db,
                display_balance,
                from_currency=account.currency,
                target_currency=effective_target,
            )
            # AUDIT-2026-07 (LOW): el opening convertido se DERIVA del mismo
            # ratio en lugar de una segunda conversión (evita duplicar el N+1
            # de tasas). La conversión es lineal, así que
            # `conv_opening = opening · conv_balance / display_balance`. Con
            # `display_balance == 0` no hay ratio: caemos a la segunda conversión.
            conv_opening: Decimal | None
            if conv_balance is None:
                conv_opening = None
            elif display_balance != 0:
                conv_opening = (account.opening_balance * conv_balance / display_balance).quantize(
                    Decimal("0.01")
                )
            else:
                conv_opening = await _convert_at_today(
                    db,
                    account.opening_balance,
                    from_currency=account.currency,
                    target_currency=effective_target,
                )
            if conv_balance is None or conv_opening is None:
                aggregable_balance = None  # sin tasa → fuera del agregado
            else:
                item_currency = effective_target
                item_opening = conv_opening
                item_balance = conv_balance
                item_movements = conv_balance - conv_opening
                aggregable_balance = conv_balance

        # PHASE-37 — cuota del cuadro (para la "Cuota est." de la lista de
        # deuda). Las tarjetas financiadas tienen `opening_balance=0`, así que
        # la cuota francesa no se puede recomputar en el cliente: la servimos
        # persistida. Nativa (misma aproximación que la estimación previa).
        _insts = insts_by_account.get(account.id, [])
        item_monthly_payment = Decimal(_insts[0].payment) if _insts else None

        # PHASE-47.G — la app se compara con el banco por su cuenta. El testigo
        # (`anchored_statement_balance`) lleva desde PHASE-39 en la BD y sólo se
        # escribía; con eso, un desvío de 700,26 € vivió semanas sin que nada lo
        # dijera. Se compara la CAJA nativa, no el saldo mostrado: un pasivo con
        # cuadro reexpresa su saldo desde las cuotas y no tiene extracto.
        item_statement_gap: Decimal | None = None
        if account.anchored_statement_balance is not None and account.nature == AccountNature.ASSET:
            item_statement_gap = (
                account.opening_balance + cash_movement
            ) - account.anchored_statement_balance
        item_seams = [
            StatementSeamOut(after=s.after, before=s.before, amount=s.amount)
            for s in seams_by_account.get(account.id, [])
        ]

        items.append(
            AccountBalance(
                statement_gap=item_statement_gap,
                statement_seams=item_seams,
                account_id=account.id,
                name=account.name,
                type=account.type,
                nature=account.nature,
                currency=item_currency,
                color=account.color,
                icon=account.icon,
                opening_balance=item_opening,
                movements_balance=item_movements,
                current_balance=item_balance,
                monthly_payment=item_monthly_payment,
                is_unvalued=is_unvalued,
                parent_account_id=account.parent_account_id,
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
        # Sin tasa para convertir → fuera del agregado (mismo contrato que
        # el modo crudo con `mixed_currencies`). El agregado se calcula con
        # el saldo cash convertido para que las dos patas de una
        # transferencia interna se cancelen entre cuentas (HIGH#1).
        if aggregable_balance is None:
            continue
        if account.nature == AccountNature.LIABILITY:
            total_liabilities += aggregable_balance
        else:
            total_assets += aggregable_balance

    if effective_target is not None:
        # Modo convertido: todo homogeneizado al target → no hay mezcla.
        reference_currency = effective_target
        mixed_currencies = False
    else:
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
        rows_payment = sum((i.payment for i in installments), Decimal("0"))
        rows_interest = sum((i.interest for i in installments), Decimal("0"))
        monthly_payment = installments[0].payment
        # `principal` para mostrar en cabecera: derivado de la primera cuota
        # (principal_1 + remaining_balance_1 = principal total).
        first = installments[0]
        principal_total = first.principal + first.remaining_balance
        # AUDIT-FIX (finding 3): el primer pago sólo-intereses, si existe,
        # es 100% interés. Se incorpora a `total_interest` Y a `total_paid`
        # con la MISMA fórmula que usa la base de `extra_charges`, de modo
        # que se preserva la identidad global
        #   total_paid == principal_total + total_interest
        # Por construcción del cuadro (finding 1): rows_payment ==
        # rows_interest + principal_total. Sumando interest_only a ambos
        # lados (es interés puro): total_paid == principal_total +
        # total_interest.
        interest_only = account.interest_only_first_payment or Decimal("0")
        total_paid = rows_payment + interest_only
        total_interest = rows_interest + interest_only
        # AUDIT-FIX (finding 2): `extra_charges` se calcula contra
        # `Σ(payments)` reales (no `n × payment`), por lo que el ajuste de
        # la última cuota no propaga residuo a los cargos derivados. La
        # base (rows_payment + interest_only) == total_paid, manteniendo
        # `extra_charges == total_to_pay − total_paid`.
        extra = _compute_extra_charges(
            total_to_pay=account.total_to_pay,
            installments_total=rows_payment,
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
    rows_payment = sum((r.payment for r in rows), Decimal("0"))
    rows_interest = sum((r.interest for r in rows), Decimal("0"))
    monthly_payment = rows[0].payment if rows else Decimal("0")
    # AUDIT-FIX (findings 2+3): misma coherencia que en el path persistido.
    # `total_paid`/`total_interest` incorporan el primer pago sólo-intereses;
    # `extra_charges` se mide contra Σ(payments) reales del cuadro.
    interest_only = account.interest_only_first_payment or Decimal("0")
    total_paid = rows_payment + interest_only
    total_interest = rows_interest + interest_only
    extra = _compute_extra_charges(
        total_to_pay=account.total_to_pay,
        installments_total=rows_payment,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cuota no encontrada")
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
    from decimal import Decimal as _Decimal

    from sqlalchemy import select

    from app.modules.personal_finance.debt.installments_repository import (
        delete_installments_for_account,
    )
    from app.modules.personal_finance.transactions.models import (
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
    await generate_installments_for_account(db, account, principal_override=principal_override)
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
    return await repo_update_installment(db, inst, payment=payment, due_date=due_date)


async def mark_installment_paid(
    db: AsyncSession,
    installment_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    paid_at: object | None,
    paid_transaction_id: uuid.UUID | None,
) -> LiabilityInstallment:
    """Marca como pagada — `paid_at=None` → now()."""
    from datetime import datetime

    inst = await _get_installment_or_404(db, installment_id, user_id)
    # AUDIT-2026-05: validar pertenencia del `paid_transaction_id` para no
    # persistir una referencia a una tx ajena en la cuota propia.
    if paid_transaction_id is not None:
        from sqlalchemy import select

        from app.modules.personal_finance.transactions.models import Transaction

        owned = await db.execute(
            select(Transaction.id).where(
                Transaction.id == paid_transaction_id,
                Transaction.user_id == user_id,
            )
        )
        if owned.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La transacción indicada no existe o no es tuya.",
            )
    when = paid_at if paid_at is not None else datetime.now(UTC)
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


async def pay_installments_by_principal(
    db: AsyncSession,
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    principal_amount: Decimal,
    paid_at: datetime | None,
    paid_transaction_id: uuid.UUID | None,
) -> tuple[int, Decimal, Decimal, Decimal | None]:
    """AUDIT-2026-07 (H-05) — Marca las cuotas que un pago de principal cubre.

    Con PHASE-36 el saldo de una liability con cuadro lo manda
    `schedule_outstanding` (Σ principal de cuotas NO pagadas). El asistente
    "Pagar cuota" mueve el dinero como transferencia, pero sin marcar cuotas
    el saldo mostrado no bajaba (H-05). Aquí marcamos, de la cuota más antigua
    pendiente hacia adelante, tantas como el principal cubra (greedy: se marca
    la cuota k mientras el principal acumulado ≤ importe pagado + 1 cts de
    holgura), enlazándolas a la transacción del pago.

    Un pago menor que la cuota más antigua pendiente no marca ninguna: el
    caller lo detecta por `uncovered_principal == principal_amount` para avisar.
    Asume que el cuadro está anclado (las cuotas ya vencidas y pagadas están
    marcadas — lo hace la reconciliación), así que la cuota más antigua
    pendiente es la del pago en curso.

    NO crea transacciones (eso lo hace el asistente aparte). Devuelve
    (marcadas, principal_cubierto, principal_no_cubierto, saldo_del_cuadro).
    """
    account = await get_account(db, account_id, user_id)
    if account.nature != AccountNature.LIABILITY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sólo las cuentas de deuda tienen cuotas que marcar.",
        )
    # Misma defensa que mark_installment_paid: la tx del pago debe ser del
    # usuario para no enlazar una cuota propia a una tx ajena.
    if paid_transaction_id is not None:
        from sqlalchemy import select

        from app.modules.personal_finance.transactions.models import Transaction

        owned = await db.execute(
            select(Transaction.id).where(
                Transaction.id == paid_transaction_id,
                Transaction.user_id == user_id,
            )
        )
        if owned.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La transacción indicada no existe o no es tuya.",
            )

    installments = await repo_list_installments(db, account_id, user_id)
    when = paid_at if paid_at is not None else datetime.now(UTC)
    # PHASE-45: el greedy vive en `plan_installments_covering_principal` (puro)
    # para que el previsualizador del panel de amortización y este aplicador
    # compartan UNA definición y no puedan divergir.
    plan = plan_installments_covering_principal(installments, principal_amount)
    for inst in plan:
        await repo_mark_paid(db, inst, paid_at=when, paid_transaction_id=paid_transaction_id)
    marked = len(plan)
    covered = sum((i.principal for i in plan), Decimal("0"))

    outstanding = schedule_outstanding(await repo_list_installments(db, account_id, user_id))
    uncovered = principal_amount - covered
    if uncovered < 0:
        uncovered = Decimal("0")
    return marked, covered, uncovered, outstanding
