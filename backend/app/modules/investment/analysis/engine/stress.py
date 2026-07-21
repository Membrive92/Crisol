"""Capa 3.5 — stress paramétrico (PHASE-44.5, DESIGN §5).

Escenarios hipotéticos sobre el ÚLTIMO ejercicio: ¿aguanta el dividendo un golpe?
Todos llevan la etiqueta fija "escenario hipotético" — no son datos, son
proyecciones deterministas de un supuesto explícito.

- **ST1 shock de ingresos**: las ventas caen un x%; el EBIT cae según el
  apalancamiento operativo estimado (margen de contribución proxy = mediana de
  Δebit/Δrevenue de la serie). El golpe se traslada a la caja neto de impuestos.
- **ST2 shock de tipos**: los tipos suben y pb sobre la fracción variable de la
  deuda; el mayor gasto financiero reduce la caja neto de impuestos.
- **ST3 breakeven del dividendo**: cuánto puede caer la caja libre antes de dejar
  de cubrir el dividendo (D3 = 1,0). Derivado, sin parámetros.

Cada escenario recalcula la cobertura FCF (D3) y produce la frase que la UI
muestra ("con ingresos −20%, la cobertura baja de 2,5× a 1,4×").

El módulo mantiene la pureza del engine: los parámetros entran por `StressParams`
(con los defaults del DESIGN), nunca de configuración externa.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.modules.investment.analysis.engine import derivations as dv
from app.modules.investment.analysis.engine.conventions import ZERO, median
from app.modules.investment.analysis.engine.types import StatementSeries
from app.modules.investment.fundamentals.canonical import CanonicalStatement

HYPOTHETICAL_LABEL = "escenario hipotético"

BPS = Decimal(10000)


@dataclass(frozen=True)
class StressParams:
    """Parámetros de los escenarios. Defaults del DESIGN §5, editables por el
    request del usuario (la UI los expone)."""

    revenue_drops: tuple[Decimal, ...] = (Decimal("0.10"), Decimal("0.20"), Decimal("0.30"))
    rate_shocks_bps: tuple[int, ...] = (100, 200, 300)
    pct_variable_debt: Decimal = Decimal("0.30")


@dataclass(frozen=True)
class StressScenario:
    """Resultado de UN escenario. `label` es siempre HYPOTHETICAL_LABEL."""

    key: str
    parameter: str
    coverage_before: Decimal | None
    coverage_after: Decimal | None
    sentence: str
    label: str = HYPOTHETICAL_LABEL


@dataclass(frozen=True)
class StressResult:
    scenarios: tuple[StressScenario, ...]
    contribution_margin: Decimal | None
    """El margen de contribución estimado (ST1). `None` si la serie no da para
    estimarlo — entonces ST1 no se calcula (no se inventa un apalancamiento)."""
    breakeven_fcf_drop: Decimal | None = None
    """ST3: fracción máxima de caída de la caja libre que mantiene D3 ≥ 1,0.
    `None` si no paga dividendo o falta la caja libre."""
    not_computable_reason: str | None = None

    def get(self, key: str) -> StressScenario | None:
        for scenario in self.scenarios:
            if scenario.key == key:
                return scenario
        return None

    def by_family(self, prefix: str) -> tuple[StressScenario, ...]:
        return tuple(s for s in self.scenarios if s.key.startswith(prefix))


# ── Estimaciones de base ──────────────────────────────────────────────


def estimate_contribution_margin(series: StatementSeries) -> Decimal | None:
    """Margen de contribución proxy = mediana de Δebit/Δrevenue en la serie.

    Cuánto EBIT se pierde por cada euro de ventas que desaparece — el
    apalancamiento operativo. Se toma la mediana (no la media) para que un año
    atípico no domine. Se ignoran los años sin variación de ventas (ratio
    indefinido) y se acota a [0, 1]: un margen de contribución fuera de ese rango
    es ruido de datos, no economía (un euro de ventas no destruye más de un euro
    de EBIT ni lo aumenta).
    """
    ratios: list[Decimal] = []
    previous: CanonicalStatement | None = None
    for statement in series.statements:
        if (
            previous is not None
            and previous.fiscal_year == statement.fiscal_year - 1
            and statement.ebit is not None
            and previous.ebit is not None
            and statement.revenue is not None
            and previous.revenue is not None
        ):
            delta_revenue = statement.revenue - previous.revenue
            if delta_revenue != ZERO:
                ratio = (statement.ebit - previous.ebit) / delta_revenue
                if ZERO <= ratio <= Decimal(1):
                    ratios.append(ratio)
        previous = statement
    if not ratios:
        return None
    return median(ratios)


def _effective_tax_shield(statement: CanonicalStatement) -> Decimal:
    """1 − tipo efectivo, acotado a [0, 1]. Sin ETR computable → 1 (sin escudo:
    el golpe pre-impuestos, más conservador)."""
    etr = dv.effective_tax_rate(statement).value
    if etr is None or etr < ZERO or etr > Decimal(1):
        return Decimal(1)
    return Decimal(1) - etr


def _coverage(fcf: Decimal | None, dividends: Decimal | None) -> Decimal | None:
    """Cobertura D3 = fcf / dividends, con el mismo criterio que la Capa 3."""
    if fcf is None or dividends is None or dividends == ZERO:
        return None
    return fcf / dividends


def _fmt(coverage: Decimal | None) -> str:
    return "no computable" if coverage is None else f"{coverage:.2f}×"


# ── Cálculo ───────────────────────────────────────────────────────────


def compute(series: StatementSeries, params: StressParams | None = None) -> StressResult:
    """Calcula los escenarios de stress sobre el último ejercicio."""
    config = params or StressParams()
    latest = series.latest
    if latest is None:
        return StressResult(
            scenarios=(),
            contribution_margin=None,
            not_computable_reason="la serie no tiene ejercicios",
        )

    fcf_base = dv.fcf_cfo(latest).value
    dividends = latest.dividends_paid
    coverage_base = _coverage(fcf_base, dividends)
    tax_shield = _effective_tax_shield(latest)
    margin = estimate_contribution_margin(series)

    scenarios: list[StressScenario] = []

    # ── ST1 — shock de ingresos ──
    if margin is not None and fcf_base is not None and latest.revenue is not None:
        for drop in config.revenue_drops:
            delta_ebit = margin * (-drop * latest.revenue)
            fcf_after = fcf_base + delta_ebit * tax_shield
            coverage_after = _coverage(fcf_after, dividends)
            scenarios.append(
                StressScenario(
                    key=f"ST1_revenue_-{int(drop * 100)}",
                    parameter=f"ventas −{drop:.0%}",
                    coverage_before=coverage_base,
                    coverage_after=coverage_after,
                    sentence=(
                        f"Con las ventas cayendo un {drop:.0%}, la cobertura del dividendo por "
                        f"caja libre pasa de {_fmt(coverage_base)} a {_fmt(coverage_after)}."
                    ),
                )
            )

    # ── ST2 — shock de tipos ──
    total_debt = dv.total_debt(latest).value
    if total_debt is not None and fcf_base is not None:
        variable_debt = config.pct_variable_debt * total_debt
        for shock in config.rate_shocks_bps:
            extra_interest = variable_debt * Decimal(shock) / BPS
            fcf_after = fcf_base - extra_interest * tax_shield
            coverage_after = _coverage(fcf_after, dividends)
            scenarios.append(
                StressScenario(
                    key=f"ST2_rates_+{shock}bps",
                    parameter=f"tipos +{shock} pb",
                    coverage_before=coverage_base,
                    coverage_after=coverage_after,
                    sentence=(
                        f"Con los tipos subiendo {shock} puntos básicos sobre la deuda variable "
                        f"({config.pct_variable_debt:.0%} del total), la cobertura del dividendo "
                        f"pasa de {_fmt(coverage_base)} a {_fmt(coverage_after)}."
                    ),
                )
            )

    # ── ST3 — breakeven del dividendo ──
    breakeven = _breakeven_drop(coverage_base)

    return StressResult(
        scenarios=tuple(scenarios),
        contribution_margin=margin,
        breakeven_fcf_drop=breakeven,
    )


def _breakeven_drop(coverage_base: Decimal | None) -> Decimal | None:
    """ST3 — máxima caída relativa de la caja libre que mantiene D3 ≥ 1,0.

    D3' = fcf·(1−d) / dividends = coverage_base·(1−d) ≥ 1 ⟺ d ≤ 1 − 1/coverage.
    Con la cobertura ya por debajo de 1 el resultado sale negativo: no hay margen
    de caída, la caja tendría que SUBIR — el signo lo dice.
    """
    if coverage_base is None or coverage_base <= ZERO:
        return None
    return Decimal(1) - Decimal(1) / coverage_base
