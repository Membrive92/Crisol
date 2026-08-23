"""PHASE-47 — «El mes del usuario»: UNA declaración, para todo el dominio.

El usuario declara en Ajustes el día en que empieza su mes
(`users.cycle_start_day`). Hasta aquí eso era un PRESET que sólo entendían
cinco endpoints y que había que pedir con `cycle=true`; el resto del backend
seguía cortando por mes natural aunque el ajuste existiera. El usuario lo
resumió mejor que ninguna especificación: *«es muy raro»* — el ajuste estaba
puesto y media app le enseñaba otro mes.

Ahora el día REDEFINE qué es un mes. Este módulo es el único sitio donde se
responde «¿qué período contiene hoy?» y «¿dónde empieza y acaba?», para que los
agregados que derivan su propio mes —la proyección de fin de mes, el runway,
los presupuestos, la ventana de gasto estructural, el DTI— no puedan contestarlo
cada uno por su cuenta y acabar en cinco sitios distintos.

**Vive en la raíz de `personal_finance/` a propósito.** Lo consumen `analytics`,
`budgets`, `dashboard` y `debt`, y ponerlo dentro de cualquiera de ellos
obligaría a los otros tres a importar de un módulo hermano por una función de
calendario. No importa nada del dominio: sólo fechas.

**No duplica la aritmética SQL.** El bucketing de las series lo sigue
gobernando `dashboard.repository.cycle_shifted_occurred_at`, que desplaza la
columna dentro de la query. Aquí se resuelven BOUNDS en Python, que es lo que
necesitan los agregados que no agrupan sino que acotan. Las dos coinciden por
construcción —desplazar D−1 días y cortar por mes es lo mismo que cortar del
día D al D−1— y hay un test que lo ata.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

# El rango admitido por `users.cycle_start_day` (CHECK en la BD y `Field` del
# schema). El 1 se acepta y degenera EXACTAMENTE en el mes natural, así que no
# necesita un caso especial en ninguna parte.
MIN_CYCLE_START_DAY = 1
MAX_CYCLE_START_DAY = 28


def is_valid_cycle_start_day(value: int | None) -> bool:
    """¿Es un día de corte utilizable?

    Guarda por VALOR y no por `is not None`: un `0` o un `31` en la columna
    —imposibles hoy por el CHECK, posibles mañana por un backfill o una
    migración— producirían un mes que no existe, y es mejor caer al natural que
    inventar un período.
    """
    return value is not None and MIN_CYCLE_START_DAY <= value <= MAX_CYCLE_START_DAY


def user_month_bounds(today: date, cycle_start_day: int | None) -> tuple[date, date]:
    """Primer y último día del mes del usuario que CONTIENE `today`.

    Sin día declarado, el mes natural de siempre. Con día `D`, el período va del
    `D` de un mes al `D−1` del siguiente — ambos incluidos, que es la convención
    de los intervalos del backend.

    La pertenencia se decide por el día del mes: si `today.day >= D`, el período
    lo abre este mes; si no, lo abrió el anterior. Es la regla que hace que la
    nómina del 14 caiga en «su» mes con `D = 14`, que es el caso que motivó todo
    esto.
    """
    if not is_valid_cycle_start_day(cycle_start_day):
        last = calendar.monthrange(today.year, today.month)[1]
        return date(today.year, today.month, 1), date(today.year, today.month, last)

    assert cycle_start_day is not None  # ya validado; para mypy
    if today.day >= cycle_start_day:
        start = date(today.year, today.month, cycle_start_day)
    else:
        prev_year, prev_month = (
            (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
        )
        start = date(prev_year, prev_month, cycle_start_day)
    # El fin es el día ANTERIOR al mismo día del mes siguiente. Con `D <= 28` no
    # hay clamp de fin de mes posible, que es justo por lo que 29-31 no se
    # ofrecen: el clamp de febrero convierte el ciclo en una charca de bugs.
    next_year, next_month = (
        (start.year, start.month + 1) if start.month < 12 else (start.year + 1, 1)
    )
    return start, date(next_year, next_month, cycle_start_day) - timedelta(days=1)


def user_month_bounds_for_anchor(anchor: date, cycle_start_day: int | None) -> tuple[date, date]:
    """El período que ABRE en el mes de `anchor` (se ignora su día).

    Distinta de `user_month_bounds`, y la diferencia es exactamente donde se
    coló un fallo: aquélla responde «¿qué período CONTIENE este día?», ésta
    «¿qué período EMPIEZA en este mes?». Para un ancla `YYYY-MM` —que es como
    viajan los buckets de las series y las flechas del navegador— la pregunta
    correcta es la segunda.

    Confundirlas desplaza la serie entera un bucket: los buckets llegan como
    día 1, y con `D > 1` el día 1 pertenece al período que abrió el mes
    ANTERIOR, así que la ventana se queda corta por los dos extremos y el
    último bucket sale a 0,00 € siempre — sus movimientos se consultan y se
    tiran, mientras el KPI de la misma pantalla sí los cuenta.

    Sin día declarado devuelve el mes natural del ancla, como siempre.
    """
    if not is_valid_cycle_start_day(cycle_start_day):
        last = calendar.monthrange(anchor.year, anchor.month)[1]
        return date(anchor.year, anchor.month, 1), date(anchor.year, anchor.month, last)
    assert cycle_start_day is not None  # ya validado; para mypy
    # El día D de ese mes pertenece por definición al período que abre ahí.
    return user_month_bounds(date(anchor.year, anchor.month, cycle_start_day), cycle_start_day)


def user_month_start(today: date, cycle_start_day: int | None) -> date:
    """Primer día del mes del usuario que contiene `today`."""
    return user_month_bounds(today, cycle_start_day)[0]


def previous_user_month_bounds(today: date, cycle_start_day: int | None) -> tuple[date, date]:
    """El mes del usuario ANTERIOR al que contiene `today`.

    Se deriva retrocediendo un día desde el inicio del actual, en vez de restar
    un mes al ancla: así el cruce de año y los meses de distinta longitud los
    resuelve la misma función que todo lo demás, y no una aritmética paralela
    que pueda discrepar en enero.
    """
    start, _ = user_month_bounds(today, cycle_start_day)
    return user_month_bounds(start - timedelta(days=1), cycle_start_day)


def user_months_back(
    today: date, cycle_start_day: int | None, count: int
) -> list[tuple[date, date]]:
    """Los `count` meses del usuario COMPLETOS anteriores al que contiene `today`.

    Excluye el período en curso porque está a medias: mezclar un mes parcial con
    meses completos en una media es el fallo de [AUDIT-2026-08], que inventó un
    sobreendeudamiento a base de dividir por una ventana que incluía meses sin
    observar. Devuelve del más antiguo al más reciente.
    """
    out: list[tuple[date, date]] = []
    cursor = today
    for _ in range(count):
        start, end = previous_user_month_bounds(cursor, cycle_start_day)
        out.append((start, end))
        cursor = start
    return list(reversed(out))
