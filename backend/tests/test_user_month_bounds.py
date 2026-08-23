"""PHASE-47 — «el mes del usuario» como única declaración del período.

Estos tests son la red del cambio que hace que el ciclo REEMPLACE al mes
natural en todo el backend. Lo que protegen no es una fórmula: es que el mes
del usuario y el bucketing SQL de las series no puedan discrepar, porque cuando
discrepan el usuario ve dos cifras distintas del mismo dinero y ninguna avisa.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.personal_finance.user_month import (
    previous_user_month_bounds,
    user_month_bounds,
    user_months_back,
)


@pytest.mark.parametrize("dia", [None, 0, 29, 31, -1])
def test_sin_dia_valido_es_el_mes_natural(dia: int | None) -> None:
    """Un día imposible cae al mes natural en vez de inventar un período.

    Hoy el CHECK de la BD lo impide, pero un backfill o una migración futura
    podrían colar un 0 o un 31, y `date(y, m, 31)` reventaría en febrero. Es
    mejor el mes de siempre que un 500.
    """
    assert user_month_bounds(date(2026, 7, 20), dia) == (date(2026, 7, 1), date(2026, 7, 31))


def test_el_dia_uno_degenera_exactamente_en_el_mes_natural() -> None:
    """La propiedad que verifica la aritmética entera.

    Si `D = 1` no diera el mes natural byte a byte, habría dos caminos para el
    mismo período y en algún borde discreparían.
    """
    for mes in range(1, 13):
        hoy = date(2026, mes, 15)
        assert user_month_bounds(hoy, 1) == user_month_bounds(hoy, None)


def test_el_dia_del_corte_pertenece_al_periodo_que_abre() -> None:
    """El caso que motivó la feature: la nómina del 14 cae en «su» mes.

    Con D=14, el 14 de julio abre el período; el 13 todavía pertenece al que
    abrió el 14 de junio. Un corte al revés dejaría la nómina fuera del mes que
    ella misma paga, que es exactamente de lo que el usuario se quejaba.
    """
    assert user_month_bounds(date(2026, 7, 14), 14) == (date(2026, 7, 14), date(2026, 8, 13))
    assert user_month_bounds(date(2026, 7, 13), 14) == (date(2026, 6, 14), date(2026, 7, 13))


def test_el_periodo_cruza_el_ano_sin_partirse() -> None:
    """Enero es donde la aritmética de meses se rompe si se escribe dos veces."""
    assert user_month_bounds(date(2026, 1, 5), 14) == (date(2025, 12, 14), date(2026, 1, 13))
    assert user_month_bounds(date(2026, 12, 20), 14) == (date(2026, 12, 14), date(2027, 1, 13))


def test_los_periodos_son_contiguos_y_no_se_solapan() -> None:
    """Ni un día huérfano ni un día contado dos veces.

    Es la propiedad que garantiza que la suma de los períodos sea la suma del
    dinero: un hueco esconde movimientos y un solape los cuenta dos veces, y
    las dos cosas son invisibles mirando un solo período.
    """
    for dia in (1, 5, 14, 28):
        hoy = date(2026, 6, 20)
        actual_ini, actual_fin = user_month_bounds(hoy, dia)
        prev_ini, prev_fin = previous_user_month_bounds(hoy, dia)
        assert prev_fin.toordinal() + 1 == actual_ini.toordinal(), dia
        assert prev_ini < prev_fin < actual_ini < actual_fin


def test_la_ventana_hacia_atras_excluye_el_periodo_en_curso() -> None:
    """Mezclar un período a medias con períodos completos infla o desinfla una
    media sin que se note — es el fallo de [AUDIT-2026-08], que inventó un
    sobreendeudamiento dividiendo por meses sin observar."""
    ventana = user_months_back(date(2026, 7, 20), 14, 3)

    assert len(ventana) == 3
    assert ventana == [
        (date(2026, 4, 14), date(2026, 5, 13)),
        (date(2026, 5, 14), date(2026, 6, 13)),
        (date(2026, 6, 14), date(2026, 7, 13)),
    ]
    # El que contiene hoy (14-jul → 13-ago) NO está.
    assert all(fin < date(2026, 7, 14) for _, fin in ventana)


def test_coincide_con_el_bucketing_sql_de_las_series() -> None:
    """El invariante que ata las dos aritméticas.

    Las series agrupan desplazando la columna `D−1` días y cortando por mes
    (`cycle_shifted_occurred_at`); los agregados acotan con estos bounds. Son
    dos implementaciones de la misma regla, y si divergen el usuario ve dos
    cifras del mismo dinero. Aquí se comprueba que un día pertenece al mismo
    período por las dos vías.
    """
    from datetime import timedelta

    dia = 14
    for offset in range(0, 400, 7):
        d = date(2026, 1, 1) + timedelta(days=offset)
        inicio, _ = user_month_bounds(d, dia)
        # La vía SQL: restar D−1 días y quedarse con (año, mes).
        desplazado = d - timedelta(days=dia - 1)
        assert (inicio.year, inicio.month) == (desplazado.year, desplazado.month), d


def test_el_periodo_que_abre_en_un_mes_no_es_el_que_contiene_su_dia_1() -> None:
    """La distinción que se coló como fallo en la serie de deuda.

    Los buckets de las series y las flechas del navegador viajan como anclas
    `YYYY-MM`, o sea con día 1. Preguntar «¿qué período contiene el día 1?»
    devuelve el que abrió el mes ANTERIOR, así que usar esa respuesta para
    acotar una serie la desplaza un bucket entero: el último sale a 0,00 €
    siempre y sus movimientos se consultan y se tiran.
    """
    from app.modules.personal_finance.user_month import user_month_bounds_for_anchor

    ancla = date(2026, 8, 1)
    # El que CONTIENE el día 1 de agosto abrió en julio.
    assert user_month_bounds(ancla, 13) == (date(2026, 7, 13), date(2026, 8, 12))
    # El que ABRE en agosto es el de agosto.
    assert user_month_bounds_for_anchor(ancla, 13) == (date(2026, 8, 13), date(2026, 9, 12))
    # El día del ancla es irrelevante: lo que manda es su mes.
    assert user_month_bounds_for_anchor(date(2026, 8, 27), 13) == (
        date(2026, 8, 13),
        date(2026, 9, 12),
    )


def test_el_periodo_que_abre_degenera_en_el_mes_natural_sin_dia() -> None:
    from app.modules.personal_finance.user_month import user_month_bounds_for_anchor

    for dia in (None, 1):
        assert user_month_bounds_for_anchor(date(2026, 2, 1), dia) == (
            date(2026, 2, 1),
            date(2026, 2, 28),
        )
