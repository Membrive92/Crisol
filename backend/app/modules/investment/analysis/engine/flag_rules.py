"""Evaluabilidad de las reglas de bandera (PHASE-44.17).

Una `Flag` sólo existe cuando salta, así que preguntar «¿hay bandera con esta
clave?» tiene tres respuestas posibles y sólo distinguía dos: encendida, y todo
lo demás. La síntesis traducía ese «todo lo demás» a **«no se ha encendido»**,
que se lee como *comprobado y limpio* — también cuando la regla no llegó a
ejecutarse ni una vez por falta de un dato (sin coste de ventas, C3 nunca corre).

Aquí vive la decisión, una sola vez, en dos formas según la ventana de la regla:

- **De serie** (`evaluate_windowed_rule`): las que exigen una racha («dos años
  seguidos»). Su unidad de decisión es la serie entera, no el año.
- **De último ejercicio** (`evaluate_single_year_rule`): los cruces de balance
  B1/B2/B4, que miran la foto del cierre más reciente.

Lo que NO se centraliza es el UMBRAL. C7 salta con un solo año y C4 exige tres;
meterlos en un criterio común rompería las dos. Cada regla trae el suyo.

Este módulo es **hoja** del grafo de imports del engine (sólo depende de
`types`) para que lo puedan usar la capa evolutiva y la de dividendo sin
importarse entre ellas.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.modules.investment.analysis.engine.types import Flag, FlagEvaluation
from app.modules.investment.enums import SectorInternal

# ── Aplicabilidad por sector ──────────────────────────────────────────
#
# Vive aquí, en la hoja del grafo de imports, y no en `sector_profiles`: las
# capas que EVALÚAN las reglas (evolutiva y dividendo) necesitan consultarla, y
# `sector_profiles` importa el catálogo del engine, que a su vez importa esas
# capas. Los motivos se comparten con los perfiles de umbral —los importa
# `sector_profiles` desde aquí— para que la misma empresa no lea dos
# explicaciones distintas de la misma ausencia.

NO_INVENTORY_REASON = (
    "sin inventario material en este sector: la regla mide una rotación que "
    "este negocio no tiene"
)
FIN_WORKING_CAPITAL_REASON = (
    "el circulante de un banco no es capital de trabajo: sus vaivenes SON el negocio"
)
FIN_CASH_REASON = (
    "el esquema de caja libre (CFO − capex) no describe a una financiera: "
    "su negocio ES mover dinero, así que el cociente sale y no significa nada"
)
FIN_COVERAGE_REASON = (
    "el interés es la materia prima de un banco, no una carga: leerlo como "
    "cobertura invierte lo que la métrica quiere decir"
)

NO_MATERIAL_INVENTORY: frozenset[SectorInternal] = frozenset(
    {
        SectorInternal.UTILITIES,
        SectorInternal.COMMUNICATION,
        SectorInternal.TECHNOLOGY,
        SectorInternal.REAL_ESTATE,
        SectorInternal.FINANCIALS,
    }
)
"""Sectores sin inventario material.

Lo consumen la regla de coherencia C3, el check de inventario del C-Score (F7) y
—vía `sector_profiles`— la aplicabilidad de A2 (días de inventario). Una sola
lista: si hubiera dos, la misma empresa podría decir que no tiene inventario en
una pantalla y medirle la rotación en otra."""

_FINANCIAL_FLAGS_NOT_APPLICABLE: Mapping[str, str] = {
    "C1_receivables_vs_revenue": FIN_WORKING_CAPITAL_REASON,
    "C3_inventory_vs_cogs": FIN_WORKING_CAPITAL_REASON,
    "B1_debt_competes_with_dividend": FIN_CASH_REASON,
    "B2_interest_priority": FIN_COVERAGE_REASON,
}


def flag_applicability(sector: SectorInternal, *, is_financial: bool = False) -> Mapping[str, str]:
    """Qué reglas de bandera NO aplican a un valor, y por qué.

    `is_financial` es del valor y no del sector: un holding clasificado fuera del
    sector financiero sigue siendo un banco para estas reglas.
    """
    not_applicable: dict[str, str] = {}
    if sector in NO_MATERIAL_INVENTORY:
        not_applicable["C3_inventory_vs_cogs"] = NO_INVENTORY_REASON
    if is_financial or sector is SectorInternal.FINANCIALS:
        not_applicable.update(_FINANCIAL_FLAGS_NOT_APPLICABLE)
    return not_applicable


@dataclass(frozen=True)
class FlagRuleResult:
    """Lo que salta y lo que se ha podido comprobar.

    Las dos cosas juntas, porque por separado se confunden: una bandera apagada y
    una regla que no llegó a ejecutarse se ven igual desde fuera y significan lo
    contrario.
    """

    flags: tuple[Flag, ...]
    evaluations: tuple[FlagEvaluation, ...]


def runs(years: Sequence[int], length: int) -> list[tuple[int, ...]]:
    """Rachas de `length` años CONSECUTIVOS dentro de los años marcados.

    "Sostenido 2 años" significa 2024 y 2025, no 2021 y 2024: dos años sueltos
    son dos casualidades, dos seguidos son una tendencia.
    """
    ordered = sorted(years)
    found: list[tuple[int, ...]] = []
    for index in range(len(ordered) - length + 1):
        window = ordered[index : index + length]
        if window[-1] - window[0] == length - 1:
            found.append(tuple(window))
    return found


def evaluate_windowed_rule(
    key: str,
    *,
    fired: bool,
    evaluable: Sequence[int],
    unevaluable: Mapping[int, str],
    sustained: int,
) -> FlagEvaluation:
    """¿Se ha podido comprobar una regla que exige una racha?

    El criterio NO es un cardinal de años evaluables: `runs` busca ventanas
    CONSECUTIVAS, así que con años evaluables {2016, 2018, 2020} y `sustained=2`
    la regla **no puede encenderse jamás**, y decir «comprobado y limpio» sería
    afirmar una comprobación imposible.
    """
    evaluated = tuple(sorted(evaluable))
    unevaluated = tuple(sorted(unevaluable))
    if fired:
        return FlagEvaluation(
            key=key, outcome="fired", years_evaluated=evaluated, years_unevaluable=unevaluated
        )
    if runs(list(evaluable), sustained):
        return FlagEvaluation(
            key=key, outcome="clear", years_evaluated=evaluated, years_unevaluable=unevaluated
        )
    return FlagEvaluation(
        key=key,
        outcome="not_computable",
        reason=unevaluable_reason(unevaluable, sustained=sustained, evaluable=evaluable),
        years_evaluated=evaluated,
        years_unevaluable=unevaluated,
    )


def not_applicable_rule(key: str, reason: str) -> FlagEvaluation:
    """La regla no se plantea en este sector, que no es «no se pudo comprobar».

    La diferencia importa en pantalla: «no se ha podido comprobar» invita a
    ingerir más datos, y aquí no hay nada que ingerir — el inventario de una
    eléctrica no va a aparecer.
    """
    return FlagEvaluation(key=key, outcome="not_applicable", reason=reason)


def evaluate_single_year_rule(
    key: str, *, fired: bool, year: int, missing: str | None
) -> FlagEvaluation:
    """¿Se ha podido comprobar una regla de un solo ejercicio?

    `missing` es el motivo cuando falta algún input; `None` significa que estaban
    todos. Una regla que SALTA se declara encendida aunque falte algún input
    secundario: ya ha demostrado lo que tenía que demostrar.
    """
    if fired:
        return FlagEvaluation(key=key, outcome="fired", years_evaluated=(year,))
    if missing:
        return FlagEvaluation(
            key=key, outcome="not_computable", reason=missing, years_unevaluable=(year,)
        )
    return FlagEvaluation(key=key, outcome="clear", years_evaluated=(year,))


def unevaluable_reason(
    unevaluable: Mapping[int, str], *, sustained: int, evaluable: Sequence[int]
) -> str:
    """Por qué no se pudo comprobar, con el motivo del ejercicio MÁS RECIENTE.

    El del primer año suele ser «no hay ejercicio anterior», que es cierto y no
    sirve de nada: se arregla solo mirando el año siguiente, así que como
    explicación manda a ingerir historia que no cambia el resultado. Es la misma
    regla que aplica la pantalla al elegir qué motivo enseñar de una serie.
    """
    if unevaluable:
        latest = max(unevaluable)
        detail = unevaluable[latest]
        if len(set(unevaluable.values())) > 1:
            return f"{detail} (y otros ejercicios, por otro motivo)"
        return detail
    return (
        f"la serie no tiene {sustained} ejercicios consecutivos comparables "
        f"(hay {len(evaluable)})"
    )
