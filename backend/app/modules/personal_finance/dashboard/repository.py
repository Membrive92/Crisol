"""Queries de agregación del módulo dashboard.

Todas las queries filtran por `user_id` (aislamiento multi-tenant). El
modo de moneda es explícito vía dos parámetros mutuamente excluyentes:

- `currency` (legacy): filtra por esa moneda y agrega importes crudos.
  Equivalente al comportamiento pre-PHASE-8.3.
- `target_currency` (PHASE-8.3): no filtra por moneda. Convierte cada
  transacción a `target_currency` con la tasa **del día de su
  `occurred_at`** (vía `conversion.converted_amount_expr`) antes de
  agregar. Las transacciones sin tasa disponible quedan excluidas
  (NULL → SUM ignora). El service expone `missing_count` para que el
  caller sepa cuántas se quedaron fuera.

El service decide cuál usar según los parámetros que recibe el router.
Aquí ofrecemos ambos modos vía las flags `currency`/`target_currency`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, Select, case, extract, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.categories.models import Category, CategoryKind
from app.modules.personal_finance.dashboard.conversion import (
    amount_is_convertible_expr,
    converted_amount_expr,
)
from app.modules.personal_finance.transactions.models import Transaction, TransactionFlow


# PHASE-34 (ADR-0004): la clasificación gasto/ingreso/transferencia la manda
# `transactions.flow`. Durante la transición, las filas sin flow (heredadas /
# write path aún sin migrar) caen a `category.kind`/`is_transfer` como antes.
# Los tres helpers son NULL-safe: un row sin flow ni categoría no rompe el
# WHERE. Se elimina el fallback (y el join a Category de la clasificación) en
# 34.6. Equivalente por construcción al backfill de 34.1.
def _is_refund() -> ColumnElement[bool]:
    """PHASE-47.H — una DEVOLUCIÓN: dinero que entra en una categoría de gasto.

    Un reembolso de Amazon no es un ingreso, es una compra que se deshace. Con
    `flow=IN` a secas se contaba como ingreso, y en julio de 2026 los ingresos
    del usuario salían 2.664 € con una nómina de 2.520 €.

    Cada señal responde a lo que sabe, que es la regla que costó nueve
    lecciones: la DIRECCIÓN la manda `flow` —probada contra la cadena de saldos
    del extracto (PHASE-47.G)— y la categoría sólo responde «¿esto es una
    categoría de compras?». Si un ingreso real estuviera mal categorizado,
    pasaría a contar como gasto negativo en vez de como ingreso: cambia la
    etiqueta, **nunca el neto ni el saldo**. Ese es el modo de fallo que hace
    aceptable apoyarse aquí en la categoría.

    Sólo con `flow` explícito: una fila heredada sin flow no tiene dirección
    probada, y adivinarla desde la categoría es justo lo que no se hace.

    **NULL-safe, y no es cosmético.** Sin el `coalesce`, una entrada SIN
    categoría da `TRUE AND NULL` = NULL, y ese NULL envenena el `AND NOT` de
    `_is_income()`: la fila deja de ser ingreso y desaparece del cashflow. Se
    midió — una nómina sin categorizar dejaba la tasa de ahorro en `None` y el
    titular del mes en −1.500 € en vez de +500. Los otros tres helpers de este
    fichero ya lo declaraban arriba; éste nació sin ello.
    """
    return (Transaction.flow == TransactionFlow.IN) & func.coalesce(
        Category.kind == CategoryKind.EXPENSE, literal(False)
    )


def _is_income() -> ColumnElement[bool]:
    return case(
        (
            Transaction.flow.is_not(None),
            (Transaction.flow == TransactionFlow.IN) & ~_is_refund(),
        ),
        else_=(Category.kind == CategoryKind.INCOME),
    )


def _is_expense() -> ColumnElement[bool]:
    """Pertenece al cubo de GASTO — incluidas las devoluciones.

    Una devolución entra aquí a propósito: es gasto de su categoría, con signo
    contrario. Por eso todo sitio que SUME bajo este predicado tiene que usar
    `expense_amount_expr`, o estaría sumando el reembolso en vez de restarlo.
    """
    return case(
        (
            Transaction.flow.is_not(None),
            (Transaction.flow == TransactionFlow.OUT) | _is_refund(),
        ),
        else_=(Category.kind == CategoryKind.EXPENSE),
    )


def expense_amount_expr(amount: Any) -> ColumnElement[Decimal]:
    """El importe con el que una fila cuenta COMO GASTO: negativo si devuelve.

    Existe como helper explícito en vez de meter el signo en `_amount_expr`
    porque esa expresión la comparten 39 sitios, entre ellos los SALDOS y los
    presupuestos, donde una devolución no lleva signo invertido — ahí es una
    entrada normal. Firmar allí habría movido el saldo, que es lo único que en
    esta app no puede moverse por un cambio de etiqueta.
    """
    return case((_is_refund(), -amount), else_=amount)


def bucketed_amount_expr(amount: Any) -> ColumnElement[Decimal]:
    """El importe de una fila para una agregación que MEZCLA los dos cubos.

    Las series por mes agrupan por `kind_label` y suman una sola columna, así
    que la misma expresión tiene que valer para el cubo de ingreso (importe tal
    cual) y para el de gasto (negativo si es devolución). Aplicar
    `expense_amount_expr` en el `else_` sería inofensivo hoy pero mentiría en el
    nombre; así la condición dice exactamente lo que hace.

    Existe porque el docstring de `_is_expense` fija la regla —«todo sitio que
    SUME bajo este predicado tiene que usar `expense_amount_expr`»— y esa regla
    se cumplía en las cuatro agregaciones de un solo cubo y NO en las cuatro que
    bucketizan por mes o por categoría. Con datos reales, julio de 2026 daba
    3.213,69 € de gasto en el KPI y 3.485,79 € en la barra del chart del mismo
    mes: 272,10 € de diferencia, que son las cuatro devoluciones de julio
    sumadas en vez de restadas (dos veces su importe). Y el donut decía 1.267,06
    € en una categoría donde el drill-down decía 1.704,84 € para los MISMOS 56
    movimientos. Ninguna de las dos cifras avisaba de nada: las dos son
    plausibles y sólo se contradicen si las miras juntas.
    """
    return case((_is_expense(), expense_amount_expr(amount)), else_=amount)


def _is_internal_transfer() -> ColumnElement[bool]:
    """True sólo si la fila es una transferencia interna (excluir del cashflow).

    NULL-safe: cuando `flow` es NULL cae a `coalesce(is_transfer, false)`, así
    que una tx normal sin flow NO se descarta por error.
    """
    return case(
        (
            Transaction.flow.is_not(None),
            Transaction.flow.in_([TransactionFlow.TRANSFER_IN, TransactionFlow.TRANSFER_OUT]),
        ),
        else_=func.coalesce(Category.is_transfer, literal(False)),
    )


async def list_user_currencies(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[str]:
    """Devuelve las monedas distintas en las transacciones del usuario.

    Excluye soft-deleted (PHASE-10.1) y movimientos marcados como
    transferencia interna (PHASE-19.3 pares + PHASE-23.1 is_transfer)
    — una moneda que sólo aparece en transferencias no representa
    cashflow real y no debe inundar el selector.
    """
    query = (
        select(Transaction.currency)
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        # ADR-0005: la exclusión la gobierna `flow` (`_is_internal_transfer`,
        # NULL-safe). El filtro por `transfer_pair_id` era un cinturón extra del
        # caso legacy `flow NULL` — redundante una vez `flow` está poblado
        # (verificado: 0 filas `flow NULL AND transfer_pair_id NOT NULL`).
        .where(_is_internal_transfer().is_(False))
        .distinct()
        .order_by(Transaction.currency)
    )
    result = await db.execute(query)
    return [row[0] for row in result.all()]


def cycle_shifted_occurred_at(cycle_start_day: int | None) -> ColumnElement[Any]:
    """C4 — El instante de la tx DESPLAZADO para que truncar a mes dé el ciclo.

    El usuario declara el día `D` en que empieza su mes (`users.cycle_start_day`,
    1-28). El ciclo con ancla `M` es el intervalo `[día D de M, día D de M+1)`, y
    el ancla es SIEMPRE el mes que lo **abre** — no el que aporta más días. Con
    esa convención, agrupar por ciclo es agrupar por mes de una fecha corrida:

        restar (D − 1) días  →  truncar a mes  =  ancla del ciclo

    Comprobado ejecutándolo contra PostgreSQL, no razonándolo: con `D = 14`, una
    tx del **14-ago** cae en `2026-08-01` → ancla `2026-08`; una del **13-ago**
    cae en `2026-07-31` → ancla `2026-07`. La nómina del 14, que es el caso
    motivador de la fase, abre su ciclo. Y con `D = 28`, el 1-mar cae en el ciclo
    que abrió el 28-feb — sin un solo clamp de fin de mes, porque `D ≤ 28`
    garantiza que ese día existe en todos los meses.

    **`D = 1` (y `None`) devuelven la expresión SIN desplazar**: es literalmente
    el mismo objeto SQL que usaban estas queries antes de C4, así que el mes
    natural no puede divergir del ciclo degenerado por un cambio aquí. El
    `not cycle_start_day` cubre `None`, `0` y el `1` por la misma puerta.

    **Ésta es la ÚNICA declaración de la aritmética** (lección PHASE-46: dos
    declaraciones del mismo hecho no fallan el día que las escribes, sino el día
    que sólo actualizas una). Todo consumidor —`extract`, `to_char`, `min/max`—
    la recibe de aquí; ninguno resta días por su cuenta.

    Se resta con `make_interval` y BIND PARAMS, nunca interpolando el día en la
    cadena SQL.

    Vive en `dashboard/repository` y sólo la consumen queries de **flujos**
    (series de P&G, bounds y chips de períodos). Ninguna query de SALDO la toca;
    `tests/test_user_cycle.py::test_el_ciclo_no_mueve_ni_un_centimo` lo vigila.
    """
    # AUDIT-2026-07 (LOW): truncar en UTC (`func.timezone`) para que el mes no
    # dependa de la TZ de la sesión de PostgreSQL, igual que
    # debt_history/debt_health. Sin esto, un bucket cerca de la frontera de mes
    # podía caer en el mes contiguo según la TZ del servidor.
    occurred_utc = func.timezone("UTC", Transaction.occurred_at)
    if not cycle_start_day or cycle_start_day == 1:
        return occurred_utc
    return occurred_utc - func.make_interval(0, 0, 0, cycle_start_day - 1)


async def get_transaction_month_bounds(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    cycle_start_day: int | None = None,
) -> tuple[str | None, str | None]:
    """PHASE-34 — Mes mínimo y máximo (`YYYY-MM`) con transacciones activas
    del usuario, INDEPENDIENTE de cualquier filtro de período.

    Lo usa el navegador de período del Análisis para acotar las flechas ◀▶ a
    los meses con datos (mismo papel que `available_from/to` en deuda).
    Devuelve `(None, None)` si el usuario aún no tiene transacciones.

    C4 — con `cycle_start_day` los extremos son **anclas de ciclo**, no meses
    naturales: las flechas tienen que aterrizar en ciclos con datos reales, y un
    ancla fuera de datos con el ciclo activo ya no es cosmética (pinta un período
    vacío). Sin él, mes natural exacto como siempre.
    """
    occurred = cycle_shifted_occurred_at(cycle_start_day)
    result = await db.execute(
        select(
            func.to_char(func.min(occurred), "YYYY-MM"),
            func.to_char(func.max(occurred), "YYYY-MM"),
        )
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
    )
    row = result.one()
    return row[0], row[1]


def _apply_scope[Q: Select[Any]](
    query: Q,
    *,
    user_id: uuid.UUID,
    currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Q:
    """Filtros comunes (user_id, opcional currency legacy, rango de fechas).

    Siempre excluye soft-deleted (PHASE-10.1) — todas las agregaciones
    del dashboard ignoran transacciones en papelera. Cuando `currency`
    es None la query NO filtra por moneda — el caller está usando
    modo `target_currency` y agrega cross-currency.

    PHASE-19.3: excluye las txs con `transfer_pair_id IS NOT NULL`
    — son movimientos internos entre cuentas del usuario y no afectan
    al flujo neto (sí al saldo individual de cada cuenta).
    """
    query = query.where(Transaction.user_id == user_id)
    query = query.where(Transaction.deleted_at.is_(None))
    query = query.where(Transaction.transfer_pair_id.is_(None))
    if currency is not None:
        query = query.where(Transaction.currency == currency)
    if date_from is not None:
        query = query.where(Transaction.occurred_at >= date_from)
    if date_to is not None:
        query = query.where(Transaction.occurred_at <= date_to)
    return query


def _exclude_transfer_kind(query: Any) -> Any:
    """Excluye transferencias internas del cashflow agregado.

    PHASE-34: la exclusión la manda `flow` (TRANSFER_*), con fallback a
    `category.is_transfer` para filas sin flow vía `_is_internal_transfer()`.
    Es NULL-safe, así que da igual que el JOIN a `categories` sea inner u
    outer (de ahí que ya no haga falta el antiguo parámetro `outer_join`).
    La exclusión por `transfer_pair_id` (pares emparejados, señal ortogonal)
    sigue viva en `_apply_scope`.
    """
    return query.where(_is_internal_transfer().is_(False))


def _exclude_deferred(query: Any) -> Any:
    """Quita del CASHFLOW las compras de un ciclo aplazado (PHASE-47.E2).

    El banco financió el recibo de la tarjeta, así que ese dinero NO salió de
    la cuenta ese mes: sale como cuota durante los años siguientes, y esa sí
    cuenta entera cuando llega.

    Se aplica SÓLO a las lecturas de caja —el resultado del mes, que responde
    a «¿he ahorrado?»—. El desglose por categorías las mantiene a propósito,
    porque el gasto se hizo: preguntarle en qué se gastó el dinero y esconderle
    700 € de compras sería mentir por omisión.

    Consecuencia deliberada: los meses con aplazamiento, el resultado mensual y
    la suma del desglose dejan de coincidir. Quien enseñe el desglose tiene que
    decir la diferencia en voz alta (`deferred_expense`).
    """
    return query.where(Transaction.deferred_by_account_id.is_(None))


def _amount_expr(target_currency: str | None) -> Any:
    """Devuelve la columna a sumar — convertida si target, cruda si no."""
    if target_currency is None:
        return Transaction.amount
    return converted_amount_expr(target_currency)


async def get_totals_by_kind(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[CategoryKind, Decimal]:
    """Suma `amount` clasificando income/expense por `flow` (PHASE-34).

    Devuelve siempre ambas claves (0 si no hay). En modo `target_currency`,
    las transacciones sin tasa disponible quedan fuera.
    """
    amount = _amount_expr(target_currency)
    income_amount = case((_is_income(), amount), else_=Decimal("0"))
    expense_amount = case((_is_expense(), expense_amount_expr(amount)), else_=Decimal("0"))
    query = (
        select(
            func.coalesce(func.sum(income_amount), Decimal("0")),
            func.coalesce(func.sum(expense_amount), Decimal("0")),
        )
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
    )
    query = _apply_scope(
        query,
        user_id=user_id,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
    )
    query = _exclude_transfer_kind(query)
    query = _exclude_deferred(query)

    row = (await db.execute(query)).one()
    return {CategoryKind.INCOME: Decimal(row[0]), CategoryKind.EXPENSE: Decimal(row[1])}


async def get_summary_aggregates(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[Decimal, Decimal, int, int]:
    """Una sola query con income, expense, total_count y unconvertible.

    Reemplaza las 3 queries serial pre-PHASE-8.4 (totals_by_kind +
    count_transactions + count_unconvertible). Las sumas income/expense
    se computan con `CASE` por categoría sobre el outerjoin (las
    transacciones sin categoría no contribuyen pero sí se cuentan).
    El `unconvertible_count` viene como **subquery escalar** dentro
    del mismo SELECT — sólo consulta cuando hay `target_currency`,
    en modo legacy es literal `0`.
    """
    amount = _amount_expr(target_currency)
    income_amount = case((_is_income(), amount), else_=Decimal("0"))
    expense_amount = case((_is_expense(), expense_amount_expr(amount)), else_=Decimal("0"))

    if target_currency is not None:
        unconv_subq = (
            select(func.count())
            .select_from(Transaction)
            .outerjoin(Category, Category.id == Transaction.category_id)
            .where(~amount_is_convertible_expr(target_currency))
        )
        unconv_subq = _apply_scope(
            unconv_subq,
            user_id=user_id,
            currency=None,
            date_from=date_from,
            date_to=date_to,
        )
        unconv_subq = _exclude_transfer_kind(unconv_subq)
        unconv_col = unconv_subq.scalar_subquery().label("unconvertible_count")
    else:
        unconv_col = literal(0).label("unconvertible_count")

    query = (
        select(
            func.coalesce(func.sum(income_amount), Decimal("0")).label("income"),
            func.coalesce(func.sum(expense_amount), Decimal("0")).label("expense"),
            func.count(Transaction.id).label("total_count"),
            unconv_col,
        )
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
    )
    query = _apply_scope(
        query,
        user_id=user_id,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
    )
    query = _exclude_transfer_kind(query)
    query = _exclude_deferred(query)

    row = (await db.execute(query)).one()
    return (
        Decimal(row.income),
        Decimal(row.expense),
        int(row.total_count),
        int(row.unconvertible_count),
    )


async def get_deferred_expense_total(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Decimal:
    """Cuánto del gasto del periodo está APLAZADO (PHASE-47.E2).

    Es la diferencia, dicha en voz alta, entre las dos lecturas: el resultado
    del mes no lo cuenta —no salió de la cuenta— y el desglose por categorías
    sí. Sin este número, quien intente cuadrar las dos cifras a mano no puede,
    y la pantalla estaría mintiendo por omisión.
    """
    amount = _amount_expr(target_currency)
    query = (
        select(
            func.coalesce(
                func.sum(case((_is_expense(), expense_amount_expr(amount)), else_=Decimal("0"))),
                Decimal("0"),
            )
        )
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.deferred_by_account_id.is_not(None))
    )
    query = _apply_scope(
        query, user_id=user_id, currency=currency, date_from=date_from, date_to=date_to
    )
    query = _exclude_transfer_kind(query)
    return Decimal((await db.execute(query)).scalar_one())


async def get_breakdown_by_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    kind: CategoryKind | None = None,
) -> list[
    tuple[
        uuid.UUID | None,
        str | None,
        CategoryKind | None,
        str | None,
        str | None,
        Decimal,
        int,
        Decimal,
    ]
]:
    """Totales por categoría. Incluye bucket con `category_id=None`.

    Devuelve tuplas con `(id, name, kind, color, icon, total, count,
    deferred)` — color/icon llegan al frontend para que la UI (donut, chips,
    breakdowns) pinte cada categoría con su personalización, y `deferred` es
    la parte de `total` que quedó aplazada por un recibo financiado.
    """
    amount = _amount_expr(target_currency)
    query = (
        select(
            Category.id,
            Category.name,
            Category.kind,
            Category.color,
            Category.icon,
            func.coalesce(func.sum(expense_amount_expr(amount)), 0),
            func.count(Transaction.id),
            # PHASE-47.E4 — la parte APLAZADA del total de esta categoría. El
            # aviso del desglose decía cuánto hay aplazado en el periodo pero
            # no DÓNDE, así que no había forma de saber qué fila lo explica —
            # y bajo el filtro Fijo/Variable el número ni siquiera describía lo
            # que estaba en pantalla. Mismo `expense_amount_expr` que el total
            # para que la parte no pueda ser mayor que el todo por una
            # devolución aplazada.
            func.coalesce(
                func.sum(
                    case(
                        (
                            Transaction.deferred_by_account_id.is_not(None),
                            expense_amount_expr(amount),
                        ),
                        else_=Decimal("0"),
                    )
                ),
                0,
            ),
        )
        .outerjoin(Category, Category.id == Transaction.category_id)
        .group_by(
            Category.id,
            Category.name,
            Category.kind,
            Category.color,
            Category.icon,
        )
    )
    query = _apply_scope(
        query,
        user_id=user_id,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
    )
    query = _exclude_transfer_kind(query)
    # AUDIT-2026-06 — La cara income/expense del donut se decide por `flow`
    # (igual que el KPI "Gastos" y la barra roja), NO por `Category.kind`.
    # Antes filtraba `Category.kind == kind`, así que cuando flow y la
    # categoría discrepaban (lo que PHASE-34/ADR-0004 permite a propósito)
    # el donut sumaba distinto que el resto de la pantalla: un OUT aparcado
    # en categoría de ingreso se le escapaba, y un TRANSFER_OUT en categoría
    # de gasto lo inflaba. Con `_is_expense()/_is_income()` el donut
    # reconcilia con summary + barras. Bonus: los OUT sin categoría caen al
    # bucket `category_id=None` en vez de desaparecer.
    if kind == CategoryKind.EXPENSE:
        query = query.where(_is_expense())
    elif kind == CategoryKind.INCOME:
        query = query.where(_is_income())

    result = await db.execute(query)
    return [
        (
            cat_id,
            cat_name,
            cat_kind,
            cat_color,
            cat_icon,
            Decimal(total),
            int(count),
            Decimal(deferred),
        )
        for cat_id, cat_name, cat_kind, cat_color, cat_icon, total, count, deferred in result.all()
    ]


async def get_totals_by_month(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    year: int,
    currency: str | None = None,
    target_currency: str | None = None,
    cycle_start_day: int | None = None,
) -> list[tuple[int, int, CategoryKind, Decimal]]:
    """Totales income/expense por bucket para el año pedido (PHASE-34: por flow).

    C4 — con `cycle_start_day`, los buckets dejan de ser meses naturales y pasan
    a ser **ciclos**: el bucket `08` es «el ciclo del 14 de agosto» (14-ago →
    13-sep), no «agosto». El año también se lee del instante desplazado, o el
    ciclo del 14-dic se partiría en dos años.

    **Y por eso son TRECE y no doce.** Los días 1..D−1 de enero no pertenecen a
    ningún ciclo que abra en este año: pertenecen al que abrió el D de diciembre
    del año ANTERIOR. Devolver sólo los doce que abren en el año pedido los
    dejaba fuera de la serie — medido en la base real con D=13: **30
    movimientos, 69,62 € de entradas y 698,70 € de salidas** que no aparecían en
    ninguna barra, y la suma del histórico en ciclos no cuadraba con la del año
    natural. Ese cuadre es el criterio de aceptación de la fase, no un detalle:
    el ciclo cambia CÓMO se reparte el dinero, nunca cuánto hay.

    Devuelve `(año, mes, kind, total)`: con trece buckets el mes ya no basta
    para identificarlos, porque diciembre aparece dos veces.
    """
    _occurred = cycle_shifted_occurred_at(cycle_start_day)
    month_col = extract("month", _occurred)
    year_col = extract("year", _occurred)
    amount = _amount_expr(target_currency)
    # Etiqueta income/expense por flow (fallback kind). Transferencias y
    # movimientos sin clasificar quedan en NULL y se descartan.
    kind_label = case(
        (_is_income(), literal(CategoryKind.INCOME.value)),
        (_is_expense(), literal(CategoryKind.EXPENSE.value)),
    )

    query = (
        select(
            year_col,
            month_col,
            kind_label.label("kind"),
            func.coalesce(func.sum(bucketed_amount_expr(amount)), 0),
        )
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        # ADR-0005: la exclusión del cashflow la gobierna `flow`
        # (`_is_internal_transfer`, NULL-safe). El filtro por `transfer_pair_id`
        # era redundante (belt-and-suspenders del caso legacy `flow NULL`); las
        # txs siguen impactando al saldo individual de su cuenta vía `flow`.
        .where(_is_internal_transfer().is_(False))
        # PHASE-47.E2 — un ciclo aplazado no salió de la cuenta ese mes.
        .where(Transaction.deferred_by_account_id.is_(None))
        # PHASE-47 — los períodos que ABREN en el año pedido, y sólo esos.
        #
        # Aquí hubo una rama extra que traía además el que abre en diciembre del
        # año anterior, para no perder los días 1..D−1 de enero. Sobra desde que
        # el AÑO del usuario también se desplaza (12-ene → 11-ene): sus doce
        # períodos lo cubren entero, y esos días caen en su año anterior, donde
        # les toca.
        .where(year_col == year)
        .where(kind_label.is_not(None))
        .group_by(year_col, month_col, kind_label)
    )
    if currency is not None:
        query = query.where(Transaction.currency == currency)

    result = await db.execute(query)
    return [
        (int(yr), int(month), CategoryKind(kind), Decimal(total))
        for yr, month, kind, total in result.all()
    ]


async def get_totals_by_month_in_range(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    date_from: datetime,
    date_to: datetime,
    currency: str | None = None,
    target_currency: str | None = None,
    cycle_start_day: int | None = None,
) -> list[tuple[int, int, CategoryKind, Decimal]]:
    """PHASE-41 — Totales income/expense por (año, mes) dentro de
    `[date_from, date_to]`, con los meses de borde PARCIALES (sólo las tx del
    rango). Para el período `custom`: así las barras del chart mensual cuadran
    con los KPIs de flujo del mismo rango. Misma semántica `flow` que
    `get_totals_by_month`.

    C4 — con `cycle_start_day`, el `(año, mes)` que agrupa es el **ancla del
    ciclo**. El filtro del rango sigue sobre el `occurred_at` REAL: el
    desplazamiento decide en qué barra cae cada tx, nunca qué transacciones
    entran en el período.
    """
    _occurred = cycle_shifted_occurred_at(cycle_start_day)
    month_col = extract("month", _occurred)
    year_col = extract("year", _occurred)
    amount = _amount_expr(target_currency)
    kind_label = case(
        (_is_income(), literal(CategoryKind.INCOME.value)),
        (_is_expense(), literal(CategoryKind.EXPENSE.value)),
    )
    query = (
        select(
            year_col,
            month_col,
            kind_label.label("kind"),
            func.coalesce(func.sum(bucketed_amount_expr(amount)), 0),
        )
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(_is_internal_transfer().is_(False))
        # PHASE-47.E2 — un ciclo aplazado no salió de la cuenta ese mes.
        .where(Transaction.deferred_by_account_id.is_(None))
        .where(Transaction.occurred_at >= date_from)
        .where(Transaction.occurred_at <= date_to)
        .where(kind_label.is_not(None))
        .group_by(year_col, month_col, kind_label)
    )
    if currency is not None:
        query = query.where(Transaction.currency == currency)

    result = await db.execute(query)
    return [
        (int(y), int(m), CategoryKind(kind), Decimal(total)) for y, m, kind, total in result.all()
    ]


async def get_top_expenses(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 10,
) -> list[tuple[Transaction, str | None, Decimal | None]]:
    """Top N gastos ordenados por importe convertido desc.

    Devuelve `(transaction, category_name, converted_amount)` — el
    importe convertido se devuelve para que el caller pueda exponerlo
    además del original. En modo legacy `converted_amount` es igual al
    `amount` de la transacción.
    """
    amount = _amount_expr(target_currency)
    query = (
        select(Transaction, Category.name, amount.label("converted_amount"))
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(_is_expense())
    )
    query = _apply_scope(
        query,
        user_id=user_id,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
    )
    # Ordenamos por el importe convertido — los gastos en moneda débil
    # no deben aparecer artificialmente arriba sólo por número grande.
    query = query.order_by(amount.desc().nulls_last()).limit(limit)

    result = await db.execute(query)
    return [
        (tx, name, Decimal(converted) if converted is not None else None)
        for tx, name, converted in result.all()
    ]


# ─────────────────────────────────────────────────────────────────────
# PHASE-25 — Drill-down de categoría (KPIs + evolución + top tx)
# ─────────────────────────────────────────────────────────────────────


async def get_category_kpis(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    category_id: uuid.UUID,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[Decimal, int]:
    """Total + count para UNA categoría en el rango pedido. Mantiene
    las exclusiones estándar (papelera, transferencias).

    Suma con `bucketed_amount_expr`, igual que el donut del que se llega aquí
    (`get_breakdown_by_category`). Sin eso, las dos pantallas daban cifras
    distintas para los MISMOS movimientos: en los datos reales, «Compras
    online» decía 1.267,06 € en el donut y 1.704,84 € al pinchar, con los
    mismos 56 movimientos — la diferencia eran cinco devoluciones de Amazon
    sumadas en vez de restadas.
    """
    amount = _amount_expr(target_currency)
    query = (
        select(
            func.coalesce(func.sum(bucketed_amount_expr(amount)), Decimal("0")),
            func.count(Transaction.id),
        )
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.category_id == category_id)
    )
    query = _apply_scope(
        query,
        user_id=user_id,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
    )
    query = _exclude_transfer_kind(query)
    row = (await db.execute(query)).one()
    return Decimal(row[0]), int(row[1])


async def get_category_monthly_evolution(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    category_id: uuid.UUID,
    currency: str | None = None,
    target_currency: str | None = None,
    months_back: int = 12,
    cycle_start_day: int | None = None,
) -> list[tuple[str, Decimal]]:
    """Evolución mensual de UNA categoría: últimos `months_back` meses
    cerrados + el mes en curso (inclusivo). Devuelve `(YYYY-MM, total)`
    ordenado cronológicamente. Meses sin actividad se omiten — el
    frontend rellena gaps si lo necesita.

    C4 — con `cycle_start_day`, cada `YYYY-MM` es el **ancla del ciclo** que
    abre ese mes, y `months_back` recorta los últimos N ciclos. La etiqueta no
    cambia de forma a propósito: el frontend la traduce a «Ciclo del 14 ago» con
    la misma función que usa el navegador de período.
    """
    month_col = func.to_char(cycle_shifted_occurred_at(cycle_start_day), "YYYY-MM").label("month")
    amount = _amount_expr(target_currency)
    query = (
        select(month_col, func.coalesce(func.sum(bucketed_amount_expr(amount)), Decimal("0")))
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.category_id == category_id)
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.transfer_pair_id.is_(None))
        .where(_is_internal_transfer().is_(False))
        .group_by(month_col)
        .order_by(month_col)
    )
    if currency is not None:
        query = query.where(Transaction.currency == currency)
    rows = (await db.execute(query)).all()
    # Recortamos a los últimos `months_back` meses para evitar series
    # gigantes en cuentas con histórico largo.
    return [(month, Decimal(total)) for month, total in rows[-months_back:]]


async def get_category_top_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    category_id: uuid.UUID,
    currency: str | None = None,
    target_currency: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 10,
) -> list[tuple[Transaction, str | None, Decimal | None]]:
    """Top N tx de la categoría en el rango, ordenadas por importe."""
    amount = _amount_expr(target_currency)
    query = (
        select(Transaction, Category.name, amount.label("converted_amount"))
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.category_id == category_id)
    )
    query = _apply_scope(
        query,
        user_id=user_id,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
    )
    query = _exclude_transfer_kind(query)
    query = query.order_by(amount.desc().nulls_last()).limit(limit)
    result = await db.execute(query)
    return [
        (tx, name, Decimal(converted) if converted is not None else None)
        for tx, name, converted in result.all()
    ]
