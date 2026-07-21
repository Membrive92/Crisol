"""Capa 1.5 — evolutiva (PHASE-44.3, DESIGN §5).

Los ratios de la Capa 1 son una foto; esta capa mira la PELÍCULA. Su valor está
en las divergencias: no importa que el DSO sea 45 días, importa que llevaba dos
años en 30. Cuatro bloques:

- **E1 horizontal**: YoY, CAGR y base 100 de las 7 magnitudes que cuentan la
  historia del negocio.
- **E2 vertical (common-size)**: balance sobre activo total, P&L sobre ventas.
  Es la vista que revela cambios de MEZCLA que los importes absolutos esconden.
- **E3 estabilidad de márgenes** y **E4 crecimiento sostenible** (métricas con
  banda).
- **Reglas de coherencia C1-C8**: cruces entre dos series que, al separarse,
  delatan lo que ninguna de las dos dice por su cuenta (cobros que crecen más
  que las ventas, beneficio sin caja, dividendo pagado con deuda…).

Nada aquí levanta bandera por UN año salvo que la regla lo diga: casi todos los
cruces exigen 2 años consecutivos, porque un año suelto lo explica la
estacionalidad del circulante o un extraordinario.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.modules.investment.analysis.engine import derivations as dv
from app.modules.investment.analysis.engine.conventions import (
    ONE,
    ZERO,
    avg_balance,
    cagr,
    constant,
    divide,
    multiply,
    population_stdev,
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
    Severity,
    StatementSeries,
    ThresholdSpec,
)
from app.modules.investment.enums import ThresholdDirection
from app.modules.investment.fundamentals.canonical import (
    CANONICAL_BALANCE_ITEMS,
    CanonicalStatement,
    Provenance,
)

PP = Decimal(100)
"""Puntos porcentuales. E3 y varios cruces se expresan en pp, no en tanto por
uno, porque así los enuncia el DESIGN §5 ("<2 pp", ">15 pp")."""

MIN_YEARS_FOR_SIGMA = 3
"""σ con dos puntos es media distancia entre ellos, no dispersión. E3 dice medir
predictibilidad, así que exige tres ejercicios o sale `not_computable`."""


# ── Catálogo ──────────────────────────────────────────────────────────

METRIC_CATALOG: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        "E3",
        "Estabilidad del margen EBIT",
        "evolución",
        ThresholdDirection.LOWER_BETTER,
        high_ok=Decimal(2),
        high_alarm=Decimal(5),
        note=(
            "Desviación típica del margen EBIT limpio (R3) en la serie, en pp. "
            "La predictibilidad ES seguridad: un margen errático convierte "
            "cualquier cobertura de dividendo en una lotería."
        ),
    ),
    MetricDefinition(
        "E4",
        "Tasa de crecimiento sostenible",
        "evolución",
        note=(
            "g = ROE × (1 − payout): lo que la empresa puede crecer "
            "autofinanciándose. Sin banda absoluta — se juzga contra el "
            "crecimiento real de las ventas (ver bandera `growth_externally_funded`)."
        ),
    ),
)

METRIC_KEYS: tuple[str, ...] = tuple(definition.key for definition in METRIC_CATALOG)
DEFAULT_THRESHOLDS: Mapping[str, ThresholdSpec] = thresholds_from(METRIC_CATALOG)

EXTERNAL_FUNDING_GAP = Decimal("0.10")
"""CAGR de ventas por encima del crecimiento sostenible en más de 10 pp
sostenido → alguien está pagando ese crecimiento (dilución o deuda)."""


# ── E1 — horizontal ───────────────────────────────────────────────────

_Extractor = Callable[[CanonicalStatement], Amount]


def _item(name: str) -> _Extractor:
    def extract(statement: CanonicalStatement) -> Amount:
        return sourced(statement, name)

    return extract


HORIZONTAL_ITEMS: tuple[tuple[str, str, _Extractor], ...] = (
    ("revenue", "Ventas", _item("revenue")),
    ("ebit_clean", "EBIT limpio", dv.ebit_clean),
    ("net_income", "Resultado neto", _item("net_income")),
    ("cfo", "Flujo de explotación", _item("cfo")),
    ("fcf_cfo", "Caja libre", dv.fcf_cfo),
    ("dividends_paid", "Dividendos pagados", _item("dividends_paid")),
    ("shares_basic", "Acciones en circulación", _item("shares_basic")),
)
"""Las 7 magnitudes de E1. `shares_basic` está aquí porque la dilución es la vía
silenciosa por la que el accionista pierde sin que ninguna magnitud total caiga."""


@dataclass(frozen=True)
class HorizontalPoint:
    fiscal_year: int
    value: Decimal | None
    yoy: Decimal | None
    """Variación interanual en tanto por uno. `None` si falta un año o el
    anterior es cero."""
    index_100: Decimal | None
    """Base 100 = primer ejercicio de la serie con valor."""


@dataclass(frozen=True)
class HorizontalSeries:
    key: str
    label: str
    points: tuple[HorizontalPoint, ...]
    cagr: Decimal | None = None
    cagr_reason: str | None = None
    """Por qué no hay CAGR: un cambio de signo (de pérdidas a beneficios) hace
    que la tasa compuesta no exista, y devolver un número ahí sería inventarlo."""


def _growth(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    """Variación relativa. `abs` en el denominador para que el signo del
    resultado signifique "mejora/empeora" incluso partiendo de negativo."""
    if current is None or previous is None or previous == ZERO:
        return None
    return (current - previous) / abs(previous)


def compute_horizontal(series: StatementSeries) -> tuple[HorizontalSeries, ...]:
    """E1 — YoY, CAGR y base 100 de las 7 magnitudes."""
    result: list[HorizontalSeries] = []
    for key, label, extract in HORIZONTAL_ITEMS:
        values = [(s.fiscal_year, extract(s).value) for s in series.statements]
        base = next((v for _, v in values if v is not None and v != ZERO), None)

        points: list[HorizontalPoint] = []
        previous: Decimal | None = None
        for fiscal_year, value in values:
            points.append(
                HorizontalPoint(
                    fiscal_year=fiscal_year,
                    value=value,
                    yoy=_growth(value, previous),
                    index_100=(value / base * PP if value is not None and base else None),
                )
            )
            previous = value

        first = values[0][1] if values else None
        last = values[-1][1] if values else None
        cagr_value, reason = cagr(first, last, len(values) - 1)
        result.append(
            HorizontalSeries(
                key=key, label=label, points=tuple(points), cagr=cagr_value, cagr_reason=reason
            )
        )
    return tuple(result)


# ── E2 — vertical (common-size) ───────────────────────────────────────

VERTICAL_INCOME_ITEMS: tuple[str, ...] = (
    "revenue",
    "cogs",
    "sga_expense",
    "rd_expense",
    "depreciation_amortization",
    "impairments",
    "gains_on_sale_of_business",
    "ebit",
    "interest_expense",
    "taxes",
    "net_income",
    "sbc_expense",
)
"""Los recuentos de acciones se quedan fuera: "acciones sobre ventas" no
significa nada."""


@dataclass(frozen=True)
class VerticalPoint:
    fiscal_year: int
    item: str
    base: str
    """`total_assets` para el balance, `revenue` para el P&L."""
    weight: Decimal | None


def compute_vertical(series: StatementSeries) -> tuple[VerticalPoint, ...]:
    """E2 — cada partida como fracción de su base, por año."""
    points: list[VerticalPoint] = []
    for statement in series.statements:
        for base_item, items in (
            ("total_assets", CANONICAL_BALANCE_ITEMS),
            ("revenue", VERTICAL_INCOME_ITEMS),
        ):
            base = statement.get(base_item)
            usable_base = base if base is not None and base != ZERO else None
            for item in items:
                value = statement.get(item)
                weight = value / usable_base if value is not None and usable_base else None
                points.append(
                    VerticalPoint(
                        fiscal_year=statement.fiscal_year,
                        item=item,
                        base=base_item,
                        weight=weight,
                    )
                )
    return tuple(points)


# ── E3 / E4 — métricas ────────────────────────────────────────────────


def _ebit_margin(statement: CanonicalStatement) -> Decimal | None:
    ebit_clean = dv.ebit_clean(statement).value
    revenue = statement.get("revenue")
    if ebit_clean is None or revenue is None or revenue <= ZERO:
        return None
    return ebit_clean / revenue


def compute_margin_stability(series: StatementSeries) -> Amount:
    """E3 — σ poblacional del margen EBIT limpio, en pp.

    Poblacional (÷N) y no muestral (÷N−1): la serie NO es una muestra de una
    población mayor, son TODOS los años de los que hay datos. Con 3-5 puntos la
    diferencia es visible, así que conviene que esté escrito.
    """
    margins = [m for m in (_ebit_margin(s) for s in series.statements) if m is not None]
    if len(margins) < MIN_YEARS_FOR_SIGMA:
        return Amount(
            value=None,
            provenance=Provenance.DERIVED,
            status="not_computable",
            reason=(
                f"hacen falta al menos {MIN_YEARS_FOR_SIGMA} ejercicios con margen "
                f"calculable para medir su dispersión (hay {len(margins)})"
            ),
        )
    return Amount(value=population_stdev(margins) * PP, provenance=Provenance.DERIVED)


def payout_ratio(statement: CanonicalStatement) -> Amount:
    """`dividends_paid / net_income` — payout sobre beneficio.

    Es la definición de **D1** (Capa 3), que E4 necesita ya. Vive aquí una sola
    vez para que cuando llegue `dividend.py` la reutilice en vez de reescribirla:
    dos definiciones del mismo payout acabarían divergiendo en silencio.
    """
    return divide(
        sourced(statement, "dividends_paid"),
        sourced(statement, "net_income"),
        denominator_label="resultado neto",
        require_positive_denominator=True,
    )


def compute_sustainable_growth(series: StatementSeries, statement: CanonicalStatement) -> Amount:
    """E4 — `g = ROE × (1 − payout)`.

    ROE sobre patrimonio MEDIO, igual que R5: si aquí se usara el saldo final,
    E4 y R5 dirían cosas distintas sobre el mismo año.
    """
    roe = divide(
        sourced(statement, "net_income"),
        avg_balance(series, "equity", statement.fiscal_year),
        denominator_label="patrimonio medio",
        require_positive_denominator=True,
    )
    retention = subtract(constant(ONE), payout_ratio(statement))
    return multiply(roe, retention)


# ── Reglas de coherencia C1-C8 ────────────────────────────────────────


def _runs(years: Sequence[int], length: int) -> list[tuple[int, ...]]:
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


@dataclass(frozen=True)
class _YearPair:
    """Un año y su inmediato anterior, ya resueltos."""

    year: int
    current: CanonicalStatement
    previous: CanonicalStatement


def _pairs(series: StatementSeries) -> list[_YearPair]:
    pairs: list[_YearPair] = []
    for statement in series.statements:
        previous = series.prior(statement.fiscal_year)
        if previous is not None:
            pairs.append(
                _YearPair(year=statement.fiscal_year, current=statement, previous=previous)
            )
    return pairs


def _flag(key: str, severity: Severity, message: str, **evidence: object) -> Flag:
    return Flag(key=key, severity=severity, message=message, evidence=dict(evidence))


def _gap_rule(
    series: StatementSeries,
    *,
    key: str,
    numerator_item: str,
    reference_item: str,
    gap: Decimal,
    sustained: int,
    severity: Severity,
    message: str,
) -> tuple[Flag, ...]:
    """Cruce genérico "X crece más que Y en más de N pp".

    C1 (cobros vs ventas) y C3 (inventario vs coste de ventas) son la misma
    forma con distinto umbral, así que comparten implementación: si divergieran,
    divergirían por accidente.
    """
    marked: list[int] = []
    for pair in _pairs(series):
        growth_numerator = _growth(
            pair.current.get(numerator_item), pair.previous.get(numerator_item)
        )
        growth_reference = _growth(
            pair.current.get(reference_item), pair.previous.get(reference_item)
        )
        if growth_numerator is None or growth_reference is None:
            continue
        if growth_numerator - growth_reference > gap:
            marked.append(pair.year)
    return tuple(
        _flag(key, severity, message.format(years=f"{run[0]}-{run[-1]}"), years=list(run))
        for run in _runs(marked, sustained)
    )


def compute_coherence_flags(series: StatementSeries) -> tuple[Flag, ...]:
    """C1-C8 — los cruces que delatan divergencias (DESIGN §5, Capa 1.5)."""
    flags: list[Flag] = []
    pairs = _pairs(series)

    # C1 — cobros creciendo por encima de las ventas
    flags.extend(
        _gap_rule(
            series,
            key="C1_receivables_vs_revenue",
            numerator_item="receivables",
            reference_item="revenue",
            gap=Decimal("0.15"),
            sustained=2,
            severity="amber",
            message=(
                "Los saldos pendientes de cobro crecen más de 15 puntos por encima de "
                "las ventas dos años seguidos ({years}): puede que se esté vendiendo "
                "forzando el cobro a plazo o cargando producto al canal."
            ),
        )
    )

    # C3 — inventario creciendo por encima del coste de ventas
    flags.extend(
        _gap_rule(
            series,
            key="C3_inventory_vs_cogs",
            numerator_item="inventory",
            reference_item="cogs",
            gap=Decimal("0.20"),
            sustained=1,
            severity="amber",
            message=(
                "El inventario crece más de 20 puntos por encima del coste de ventas "
                "({years}): producto que entra y no sale."
            ),
        )
    )

    # C2 — beneficio que sube sin que suba la caja
    marked_c2 = [
        pair.year
        for pair in pairs
        if (ni := _growth(pair.current.net_income, pair.previous.net_income)) is not None
        and (cfo := _growth(pair.current.cfo, pair.previous.cfo)) is not None
        and ni > ZERO
        and cfo <= ZERO
    ]
    flags.extend(
        _flag(
            "C2_income_without_cash",
            "amber",
            f"El resultado neto sube mientras el flujo de explotación no acompaña "
            f"({run[0]}-{run[-1]}): beneficio contable que todavía no es caja.",
            years=list(run),
        )
        for run in _runs(marked_c2, 2)
    )

    # C4 — capex por debajo de la amortización (descapitalización).
    # Sobre TODOS los ejercicios, no solo los que tienen anterior: la regla
    # compara capex con D&A del mismo año, así que exigir un t−1 recortaría la
    # ventana y una serie de 3 años nunca llegaría a la racha de 3 que pide.
    marked_c4 = [
        statement.fiscal_year
        for statement in series.statements
        if (capex := statement.capex) is not None
        and (dna := statement.depreciation_amortization) is not None
        and dna > ZERO
        and capex / dna < Decimal("0.8")
    ]
    flags.extend(
        _flag(
            "C4_underinvestment",
            "info",
            f"La inversión lleva tres años por debajo del 80% de la amortización "
            f"({run[0]}-{run[-1]}): el activo se está consumiendo más rápido de lo que "
            "se repone.",
            years=list(run),
        )
        for run in _runs(marked_c4, 3)
    )

    # C5 — fondo de comercio que aparece sin compras
    for pair in pairs:
        goodwill_now = pair.current.goodwill
        goodwill_before = pair.previous.goodwill
        acquisitions = pair.current.acquisitions
        if goodwill_now is None or goodwill_before is None or acquisitions is None:
            continue
        if goodwill_now > goodwill_before and acquisitions == ZERO:
            flags.append(
                _flag(
                    "C5_goodwill_without_acquisitions",
                    "amber",
                    f"En {pair.year} sube el fondo de comercio sin que el flujo de caja "
                    "registre compras de empresas: conviene revisar de dónde sale.",
                    fiscal_year=pair.year,
                    goodwill_delta=str(goodwill_now - goodwill_before),
                )
            )

    # C6 — dilución
    diluting = [
        (pair.year, growth)
        for pair in pairs
        if (growth := _growth(pair.current.shares_basic, pair.previous.shares_basic)) is not None
        and growth > Decimal("0.02")
        and (pair.current.buybacks or ZERO) == ZERO
    ]
    severe = [year for year, growth in diluting if growth > Decimal("0.05")]
    for run in _runs([year for year, _ in diluting], 2):
        is_severe = any(year in severe for year in run)
        flags.append(
            _flag(
                "C6_dilution",
                "amber" if is_severe else "info",
                f"El número de acciones crece de forma sostenida sin recompras "
                f"({run[0]}-{run[-1]}): cada acción representa una porción menor del "
                "negocio.",
                years=list(run),
                severe=is_severe,
            )
        )

    # C7 — retorno al accionista financiado con deuda
    marked_c7 = [
        pair.year
        for pair in pairs
        if (fcf := dv.fcf_cfo(pair.current).value) is not None
        and (dividends := pair.current.dividends_paid) is not None
        and (debt_change := pair.current.debt_change) is not None
        and dividends + (pair.current.buybacks or ZERO) > fcf
        and debt_change > ZERO
    ]
    sustained_c7 = _runs(marked_c7, 2)
    if sustained_c7:
        run = sustained_c7[0]
        flags.append(
            _flag(
                "C7_shareholder_return_funded_by_debt",
                "red",
                f"Dos años seguidos ({run[0]}-{run[-1]}) se ha devuelto al accionista más "
                "de lo que genera el negocio, y a la vez ha aumentado la deuda: el "
                "dividendo se está sosteniendo pidiendo prestado.",
                years=list(run),
            )
        )
    elif marked_c7:
        flags.append(
            _flag(
                "C7_shareholder_return_funded_by_debt",
                "amber",
                f"En {marked_c7[0]} se devolvió al accionista más de lo que generó el "
                "negocio mientras subía la deuda.",
                years=marked_c7,
            )
        )

    # C8 — crecimiento comprado
    statements = series.statements
    if len(statements) >= 2:
        acquisitions_series = [s.acquisitions for s in statements]
        revenue_first = statements[0].revenue
        revenue_last = statements[-1].revenue
        if (
            all(a is not None for a in acquisitions_series)
            and revenue_first is not None
            and revenue_last is not None
            and revenue_last > revenue_first
        ):
            total_acquisitions = sum((a for a in acquisitions_series if a is not None), ZERO)
            if total_acquisitions / (revenue_last - revenue_first) > Decimal("0.5"):
                flags.append(
                    _flag(
                        "C8_acquired_growth",
                        "info",
                        "Buena parte del crecimiento de ventas del periodo viene "
                        "acompañado de compras de empresas: no es crecimiento repetible "
                        "sin seguir comprando.",
                        total_acquisitions=str(total_acquisitions),
                        revenue_growth=str(revenue_last - revenue_first),
                    )
                )
    return tuple(flags)


# ── Orquestación de la capa ───────────────────────────────────────────


@dataclass(frozen=True)
class EvolutionResult:
    metrics: tuple[MetricResult, ...]
    horizontal: tuple[HorizontalSeries, ...]
    vertical: tuple[VerticalPoint, ...]
    flags: tuple[Flag, ...]

    def get(self, key: str, fiscal_year: int) -> MetricResult | None:
        for metric in self.metrics:
            if metric.key == key and metric.fiscal_year == fiscal_year:
                return metric
        return None

    def by_key(self, key: str) -> tuple[MetricResult, ...]:
        return tuple(m for m in self.metrics if m.key == key)

    def series_for(self, key: str) -> HorizontalSeries | None:
        for horizontal in self.horizontal:
            if horizontal.key == key:
                return horizontal
        return None

    def weight_of(self, item: str, fiscal_year: int) -> Decimal | None:
        for point in self.vertical:
            if point.item == item and point.fiscal_year == fiscal_year:
                return point.weight
        return None


def compute(
    series: StatementSeries,
    thresholds: Mapping[str, ThresholdSpec] | None = None,
) -> EvolutionResult:
    """Calcula la capa 1.5 completa."""
    specs = DEFAULT_THRESHOLDS if thresholds is None else thresholds
    horizontal = compute_horizontal(series)
    vertical = compute_vertical(series)
    flags = list(compute_coherence_flags(series))

    metrics: list[MetricResult] = []
    stability = compute_margin_stability(series)
    growth_rates: dict[int, Decimal] = {}
    for statement in series.statements:
        year = statement.fiscal_year
        # E3 es una propiedad de la SERIE, no del año: se repite en cada
        # ejercicio para que el informe pueda mostrarla junto al resto sin
        # tratarla como un caso aparte.
        metrics.append(to_metric_result("E3", year, stability, specs))
        sustainable = compute_sustainable_growth(series, statement)
        metrics.append(to_metric_result("E4", year, sustainable, specs))
        if sustainable.value is not None:
            growth_rates[year] = sustainable.value

    flags.extend(_external_funding_flags(horizontal, growth_rates))
    return EvolutionResult(
        metrics=tuple(metrics),
        horizontal=horizontal,
        vertical=vertical,
        flags=tuple(flags),
    )


def _external_funding_flags(
    horizontal: Sequence[HorizontalSeries], growth_rates: Mapping[int, Decimal]
) -> tuple[Flag, ...]:
    """E4 vs crecimiento real: si las ventas corren más de 10 pp por encima de
    lo que la empresa puede autofinanciar, y de forma sostenida, alguien lo está
    pagando — cruzar con C6 (dilución) y C7 (deuda)."""
    revenue = next((h for h in horizontal if h.key == "revenue"), None)
    if revenue is None or revenue.cagr is None:
        return ()
    marked = [
        year
        for year, growth in growth_rates.items()
        if revenue.cagr - growth > EXTERNAL_FUNDING_GAP
    ]
    return tuple(
        _flag(
            "growth_externally_funded",
            "amber",
            f"Las ventas crecen bastante más deprisa de lo que la empresa puede "
            f"financiar con sus propios beneficios ({run[0]}-{run[-1]}): ese exceso sale "
            "de ampliar capital o de endeudarse.",
            years=list(run),
            revenue_cagr=str(revenue.cagr),
        )
        for run in _runs(marked, 2)
    )
