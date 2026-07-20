"""Capa 1 — métricas base (PHASE-44.2, DESIGN §5).

27 métricas en cuatro familias: liquidez (L), actividad (A), solvencia (S) y
rentabilidad (R). Cada una se calcula para CADA ejercicio de la serie, de modo
que el informe pueda enseñar la evolución y no solo la foto del último año.

`METRIC_CATALOG` es la **fuente única** de las `metric_key` y de sus bandas por
defecto (US-GAAP genérico, §5). El seed de `scoring_thresholds` se construye a
partir de él [Dec.8]: así las claves sembradas en BD no pueden divergir de las
que el engine calcula — que era justo el riesgo por el que el seed se difirió de
PHASE-44.1 a esta fase.

Las claves (L1, S4b, R9b…) son estables y se citan en umbrales, UI y docstrings.
No inventar métricas fuera del catálogo (ARCHITECTURE §4.2).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from app.modules.investment.analysis.engine import derivations as dv
from app.modules.investment.analysis.engine.conventions import (
    DAY_COUNT,
    ZERO,
    add,
    avg_balance,
    avg_derived,
    constant,
    divide,
    multiply,
    sourced,
    subtract,
)
from app.modules.investment.analysis.engine.metrics import (
    MetricDefinition,
    thresholds_from,
    to_metric_result,
)
from app.modules.investment.analysis.engine.types import (
    Amount,
    Flag,
    MetricResult,
    StatementSeries,
    ThresholdSpec,
)
from app.modules.investment.enums import ThresholdDirection
from app.modules.investment.fundamentals.canonical import CanonicalStatement, Provenance


def _d(value: str) -> Decimal:
    return Decimal(value)


_HIGHER = ThresholdDirection.HIGHER_BETTER
_LOWER = ThresholdDirection.LOWER_BETTER

METRIC_CATALOG: tuple[MetricDefinition, ...] = (
    # ── Liquidez ──────────────────────────────────────────────────
    MetricDefinition("L1", "Ratio corriente", "liquidez", _HIGHER, _d("1.0"), _d("1.5")),
    MetricDefinition("L2", "Prueba ácida", "liquidez", _HIGHER, _d("0.7"), _d("1.0")),
    MetricDefinition("L3", "Ratio de caja", "liquidez", _HIGHER, _d("0.15"), _d("0.3")),
    MetricDefinition(
        "L4",
        "Muro de vencimientos",
        "liquidez",
        _HIGHER,
        _d("1.0"),
        _d("1.5"),
        note=(
            "La deuda que vence en 12 meses contra la liquidez más la caja libre del año: "
            "el mecanismo por el que las empresas quiebran de verdad (no poder refinanciar), "
            "y que L1-L3 no miran."
        ),
    ),
    # ── Actividad (medias [Dec.3]; sin banda absoluta) ────────────
    MetricDefinition("A1", "Días de cobro (DSO)", "actividad"),
    MetricDefinition("A2", "Días de inventario (DIO)", "actividad"),
    MetricDefinition("A3", "Días de pago (DPO)", "actividad"),
    MetricDefinition("A4", "Rotación de activos", "actividad"),
    MetricDefinition(
        "A5",
        "Ciclo de conversión de caja",
        "actividad",
        note="Su deriva (>15 días vs mediana de 3 años) se evalúa en la capa 1.5.",
    ),
    # ── Solvencia ─────────────────────────────────────────────────
    MetricDefinition(
        "S1", "Apalancamiento", "solvencia", _LOWER, high_ok=_d("0.6"), high_alarm=_d("0.75")
    ),
    MetricDefinition("S2", "Cobertura de intereses", "solvencia", _HIGHER, _d("3"), _d("6")),
    MetricDefinition("S3", "Autonomía financiera", "solvencia", _HIGHER, _d("0.2"), _d("0.35")),
    MetricDefinition(
        "S4", "Deuda neta / EBITDA", "solvencia", _LOWER, high_ok=_d("2"), high_alarm=_d("3.5")
    ),
    MetricDefinition(
        "S4b",
        "Deuda neta / EBIT",
        "solvencia",
        _LOWER,
        high_ok=_d("3"),
        high_alarm=_d("5"),
        note=(
            "Complementa S4: en negocios con amortización alta (mucho capex), el EBITDA "
            "infla la capacidad de repago aparente."
        ),
    ),
    MetricDefinition(
        "S5",
        "Años de repago",
        "solvencia",
        _LOWER,
        high_ok=_d("4"),
        high_alarm=_d("8"),
        note="Años de caja libre real que costaría devolver la deuda neta.",
    ),
    MetricDefinition(
        "S6",
        "Cobertura de intereses por caja",
        "solvencia",
        _HIGHER,
        _d("4"),
        _d("8"),
        note=(
            "S2 usa EBIT (devengo, maquillable); esta usa caja generada. "
            "Si S2 sale verde y S6 rojo, el devengo está mintiendo."
        ),
    ),
    # ── Rentabilidad ──────────────────────────────────────────────
    MetricDefinition("R1", "Margen bruto", "rentabilidad"),
    MetricDefinition("R2", "Margen EBITDA", "rentabilidad"),
    MetricDefinition("R3", "Margen EBIT", "rentabilidad"),
    MetricDefinition("R4", "Margen neto", "rentabilidad"),
    MetricDefinition("R5", "ROE", "rentabilidad", _HIGHER, _d("0.08"), _d("0.12")),
    MetricDefinition("R6", "ROA", "rentabilidad", _HIGHER, _d("0.02"), _d("0.05")),
    MetricDefinition(
        "R7",
        "Margen FCF",
        "rentabilidad",
        _HIGHER,
        _d("0.03"),
        _d("0.08"),
        note="Cuánta venta acaba siendo caja libre; su estabilidad es proxy de foso.",
    ),
    MetricDefinition(
        "R8",
        "FCF por acción",
        "rentabilidad",
        note=(
            "Sin banda: es serie. Contrapartida por acción de la dilución — el FCF total "
            "puede crecer mientras el FCF por acción cae."
        ),
    ),
    MetricDefinition(
        "R9",
        "ROIC",
        "rentabilidad",
        _HIGHER,
        _d("0.06"),
        _d("0.10"),
        note="La métrica de creación de valor: separa negocio de apalancamiento (vs ROE).",
    ),
    MetricDefinition(
        "R9b",
        "CROIC",
        "rentabilidad",
        _HIGHER,
        _d("0.04"),
        _d("0.08"),
        note="El ROIC medido en caja: si R9 sale verde y R9b rojo, el retorno es contable.",
    ),
    MetricDefinition(
        "R10",
        "Rentabilidad bruta sobre activos",
        "rentabilidad",
        _HIGHER,
        _d("0.18"),
        _d("0.33"),
        note=(
            "Novy-Marx: el factor de calidad con mejor respaldo empírico. Margen bruto por "
            "unidad de activo, difícil de manipular por estar arriba de la cascada contable."
        ),
    ),
)

METRIC_KEYS: tuple[str, ...] = tuple(definition.key for definition in METRIC_CATALOG)

METRIC_DEFINITIONS: Mapping[str, MetricDefinition] = {
    definition.key: definition for definition in METRIC_CATALOG
}

DEFAULT_THRESHOLDS: Mapping[str, ThresholdSpec] = thresholds_from(METRIC_CATALOG)
"""Bandas por defecto para US-GAAP genérico (§5). El servicio las sustituye por
las de BD calibradas por (sector × norma) cuando existan [Dec.8]."""


# ── Resultado ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DuPontDecomposition:
    """`ROE = margen neto × rotación de activos × multiplicador de patrimonio`.

    Explicativa, sin banda propia: dice QUÉ movió el ROE. Un ROE que sube solo
    por el multiplicador no es mejora del negocio, es deuda.
    """

    fiscal_year: int
    net_margin: MetricResult
    asset_turnover: MetricResult
    equity_multiplier: MetricResult


@dataclass(frozen=True)
class BaseRatiosResult:
    metrics: tuple[MetricResult, ...]
    flags: tuple[Flag, ...] = ()
    dupont: tuple[DuPontDecomposition, ...] = ()

    def get(self, key: str, fiscal_year: int) -> MetricResult | None:
        for metric in self.metrics:
            if metric.key == key and metric.fiscal_year == fiscal_year:
                return metric
        return None

    def by_key(self, key: str) -> tuple[MetricResult, ...]:
        return tuple(m for m in self.metrics if m.key == key)

    def by_year(self, fiscal_year: int) -> tuple[MetricResult, ...]:
        return tuple(m for m in self.metrics if m.fiscal_year == fiscal_year)


# ── Ensamblado de una métrica ─────────────────────────────────────────

_result = to_metric_result


# ── Cálculo ───────────────────────────────────────────────────────────


def compute(
    series: StatementSeries,
    thresholds: Mapping[str, ThresholdSpec] | None = None,
) -> BaseRatiosResult:
    """Calcula las 27 métricas de la Capa 1 para todos los ejercicios.

    `thresholds=None` usa las bandas por defecto del catálogo (US-GAAP
    genérico). Una métrica sin umbral sale con `band=None` — que NO significa
    "sana", sino "no hay banda que aplicar".
    """
    specs = DEFAULT_THRESHOLDS if thresholds is None else thresholds
    metrics: list[MetricResult] = []
    dupont: list[DuPontDecomposition] = []
    flags: list[Flag] = []

    for statement in series.statements:
        year = statement.fiscal_year
        year_metrics = {metric.key: metric for metric in _compute_year(series, statement, specs)}
        metrics.extend(year_metrics.values())

        equity_multiplier = _result(
            "DUPONT_EM",
            year,
            divide(
                avg_balance(series, "total_assets", year),
                avg_balance(series, "equity", year),
                denominator_label="patrimonio medio",
                require_positive_denominator=True,
            ),
            specs,
        )
        dupont.append(
            DuPontDecomposition(
                fiscal_year=year,
                net_margin=year_metrics["R4"],
                asset_turnover=year_metrics["A4"],
                equity_multiplier=equity_multiplier,
            )
        )

        ebt_flag = dv.ebt_divergence_flag(statement)
        if ebt_flag is not None:
            flags.append(ebt_flag)

    flags.extend(dv.fcf_divergence_flags(series))
    return BaseRatiosResult(metrics=tuple(metrics), flags=tuple(flags), dupont=tuple(dupont))


def _compute_year(
    series: StatementSeries,
    statement: CanonicalStatement,
    specs: Mapping[str, ThresholdSpec],
) -> list[MetricResult]:
    year = statement.fiscal_year

    def metric(key: str, amount: Amount) -> MetricResult:
        return _result(key, year, amount, specs)

    # Magnitudes reutilizadas
    current_liabilities = sourced(statement, "current_liabilities")
    revenue = sourced(statement, "revenue")
    cogs = sourced(statement, "cogs")
    total_assets = sourced(statement, "total_assets")
    interest_expense = sourced(statement, "interest_expense")
    liquid_assets = add(sourced(statement, "cash"), sourced(statement, "current_financial_assets"))
    gross_profit = subtract(revenue, cogs)
    net_income = sourced(statement, "net_income")

    ebitda = dv.ebitda(statement)
    ebit_clean = dv.ebit_clean(statement)
    net_debt = dv.net_debt(statement)
    fcf = dv.fcf_cfo(statement)

    total_assets_avg = avg_balance(series, "total_assets", year)
    equity_avg = avg_balance(series, "equity", year)
    invested_capital_avg = avg_derived(series, year, dv.invested_capital, label="capital invertido")

    return [
        # ── Liquidez ──────────────────────────────────────────────
        metric(
            "L1",
            divide(
                sourced(statement, "current_assets"),
                current_liabilities,
                denominator_label="pasivo corriente",
            ),
        ),
        metric(
            "L2",
            divide(
                subtract(sourced(statement, "current_assets"), sourced(statement, "inventory")),
                current_liabilities,
                denominator_label="pasivo corriente",
            ),
        ),
        metric(
            "L3",
            divide(liquid_assets, current_liabilities, denominator_label="pasivo corriente"),
        ),
        metric(
            "L4",
            divide(
                add(liquid_assets, fcf),
                add(
                    sourced(statement, "short_term_debt"),
                    sourced(statement, "ltd_current_portion"),
                ),
                denominator_label="deuda que vence en 12 meses",
            ),
        ),
        # ── Actividad ─────────────────────────────────────────────
        metric(
            "A1",
            multiply(
                divide(
                    avg_balance(series, "receivables", year),
                    revenue,
                    denominator_label="ventas",
                    require_positive_denominator=True,
                ),
                constant(DAY_COUNT),
            ),
        ),
        metric(
            "A2",
            multiply(
                divide(
                    avg_balance(series, "inventory", year),
                    cogs,
                    denominator_label="coste de ventas",
                    require_positive_denominator=True,
                ),
                constant(DAY_COUNT),
            ),
        ),
        metric(
            "A3",
            multiply(
                divide(
                    avg_balance(series, "accounts_payable", year),
                    cogs,
                    denominator_label="coste de ventas",
                    require_positive_denominator=True,
                ),
                constant(DAY_COUNT),
            ),
        ),
        metric(
            "A4",
            divide(revenue, total_assets_avg, denominator_label="activo total medio"),
        ),
        metric("A5", _cash_conversion_cycle(series, statement)),
        # ── Solvencia ─────────────────────────────────────────────
        metric(
            "S1",
            divide(
                sourced(statement, "total_liabilities"),
                total_assets,
                denominator_label="activo total",
            ),
        ),
        metric(
            "S2",
            divide(ebit_clean, interest_expense, denominator_label="gasto financiero"),
        ),
        metric(
            "S3",
            divide(sourced(statement, "equity"), total_assets, denominator_label="activo total"),
        ),
        metric("S4", divide(net_debt, ebitda, denominator_label="EBITDA")),
        metric("S4b", divide(net_debt, ebit_clean, denominator_label="EBIT limpio")),
        metric("S5", _years_to_repay(statement)),
        metric(
            "S6",
            divide(
                add(sourced(statement, "cfo"), interest_expense, sourced(statement, "taxes_paid")),
                interest_expense,
                denominator_label="gasto financiero",
            ),
        ),
        # ── Rentabilidad ──────────────────────────────────────────
        metric(
            "R1",
            divide(
                gross_profit, revenue, denominator_label="ventas", require_positive_denominator=True
            ),
        ),
        metric(
            "R2",
            divide(ebitda, revenue, denominator_label="ventas", require_positive_denominator=True),
        ),
        metric(
            "R3",
            divide(
                ebit_clean, revenue, denominator_label="ventas", require_positive_denominator=True
            ),
        ),
        metric(
            "R4",
            divide(
                net_income, revenue, denominator_label="ventas", require_positive_denominator=True
            ),
        ),
        metric(
            "R5",
            divide(
                net_income,
                equity_avg,
                denominator_label="patrimonio medio",
                require_positive_denominator=True,
            ),
        ),
        metric(
            "R6",
            divide(net_income, total_assets_avg, denominator_label="activo total medio"),
        ),
        metric(
            "R7",
            divide(fcf, revenue, denominator_label="ventas", require_positive_denominator=True),
        ),
        metric(
            "R8",
            divide(
                fcf,
                sourced(statement, "shares_basic"),
                denominator_label="acciones básicas",
                require_positive_denominator=True,
            ),
        ),
        metric(
            "R9",
            divide(
                dv.nopat(statement),
                invested_capital_avg,
                denominator_label="capital invertido medio",
                require_positive_denominator=True,
            ),
        ),
        metric(
            "R9b",
            divide(
                fcf,
                invested_capital_avg,
                denominator_label="capital invertido medio",
                require_positive_denominator=True,
            ),
        ),
        metric(
            "R10",
            divide(gross_profit, total_assets_avg, denominator_label="activo total medio"),
        ),
    ]


def _cash_conversion_cycle(series: StatementSeries, statement: CanonicalStatement) -> Amount:
    """A5 = A1 + A2 − A3 (días de cobro + inventario − pago).

    Se recalculan los tres componentes en vez de reutilizar sus `MetricResult`
    para que el estado degradado (`approximation` del primer año) se propague
    entero: un ciclo que mezcla una media real con un saldo final no es un
    ciclo comparable.
    """
    year = statement.fiscal_year
    revenue = sourced(statement, "revenue")
    cogs = sourced(statement, "cogs")
    dso = multiply(
        divide(
            avg_balance(series, "receivables", year),
            revenue,
            denominator_label="ventas",
            require_positive_denominator=True,
        ),
        constant(DAY_COUNT),
    )
    dio = multiply(
        divide(
            avg_balance(series, "inventory", year),
            cogs,
            denominator_label="coste de ventas",
            require_positive_denominator=True,
        ),
        constant(DAY_COUNT),
    )
    dpo = multiply(
        divide(
            avg_balance(series, "accounts_payable", year),
            cogs,
            denominator_label="coste de ventas",
            require_positive_denominator=True,
        ),
        constant(DAY_COUNT),
    )
    return subtract(add(dso, dio), dpo)


def _years_to_repay(statement: CanonicalStatement) -> Amount:
    """S5 = `net_debt / fcf_cfo`, con los dos casos especiales del §5.

    - `net_debt < 0` (caja neta): no hay deuda que repagar. El cociente sería
      un número negativo sin significado, así que se devuelve 0 años — el
      umbral `lower_better` lo pinta verde, que es la lectura correcta.
    - `fcf ≤ 0` con deuda positiva: no computable. Y su razón es, en la
      práctica, la peor señal posible: la empresa no genera caja con la que
      amortizar.
    """
    net_debt = dv.net_debt(statement)
    fcf = dv.fcf_cfo(statement)
    if net_debt.is_missing:
        return net_debt
    if fcf.is_missing:
        return fcf
    assert net_debt.value is not None and fcf.value is not None
    if net_debt.value < ZERO:
        return Amount(
            value=ZERO,
            provenance=Provenance.DERIVED,
            reason="caja neta: la liquidez supera a la deuda, no hay nada que repagar",
        )
    if fcf.value <= ZERO:
        return Amount(
            value=None,
            provenance=Provenance.DERIVED,
            status="not_computable",
            reason=(
                "la caja libre no es positiva: con deuda neta positiva, no hay flujo con "
                "el que amortizarla"
            ),
        )
    return divide(net_debt, fcf, denominator_label="caja libre")
