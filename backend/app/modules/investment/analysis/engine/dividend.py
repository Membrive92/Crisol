"""Capa 3 — dividendo (PHASE-44.4, DESIGN §5).

El TARGET del módulo: todo el análisis existe para responder si un dividendo es
sostenible. Cuatro bloques:

- **Cobertura (D)**: ¿cuánto del beneficio / de la caja se va en el dividendo?
- **Calidad de la caja (Q)**: ¿la caja que cubre el dividendo es de fiar?
- **Soporte del balance (B)**: ¿la deuda deja sitio al dividendo?
- **Trayectoria (T)**: ¿qué ha hecho el dividendo a lo largo de la serie?

Ajuste REIT (D6): en una socimi la amortización del inmueble es un apunte
contable que no refleja deterioro económico, así que el resultado neto y el FCF
infravaloran la caja repartible. Para `is_reit`, D1/D2/D3/D8 se calculan sobre
**FFO** en lugar de NI/FCF, y D6 (payout sobre FFO) es la métrica canónica.

La Capa 3 calcula mecánicamente aunque la empresa no reparta dividendo (payout
0%, coberturas no computables por divisor cero): la decisión de marcar el
análisis como `not_applicable` es de la Capa 4 (síntesis), no de aquí.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from app.modules.investment.analysis.engine import derivations as dv
from app.modules.investment.analysis.engine.conventions import (
    ONE,
    ZERO,
    add,
    cagr,
    divide,
    median,
    population_stdev,
    sourced,
    subtract,
)
from app.modules.investment.analysis.engine.flag_rules import (
    FlagRuleResult,
    evaluate_single_year_rule,
    evaluate_windowed_rule,
    flag_applicability,
    not_applicable_rule,
    unevaluable_reason,
)
from app.modules.investment.analysis.engine.metrics import (
    MetricDefinition,
    MetricUnit,
    thresholds_from,
    to_metric_result,
)
from app.modules.investment.analysis.engine.types import (
    Amount,
    Band,
    Flag,
    FlagEvaluation,
    MetricResult,
    StatementSeries,
    ThresholdSpec,
)
from app.modules.investment.enums import SectorInternal, ThresholdDirection
from app.modules.investment.fundamentals.canonical import CanonicalStatement, Provenance

PP = Decimal(100)

_LOWER = ThresholdDirection.LOWER_BETTER
_HIGHER = ThresholdDirection.HIGHER_BETTER

MIN_YEARS_FOR_PAYOUT_STABILITY = 3
"""T3 mide dispersión del payout: σ de dos puntos es media distancia, no
dispersión (misma razón que E3)."""

EXTRAORDINARY_WEIGHT_LIMIT = Decimal("0.20")
"""Q5: peso de extraordinarios sobre EBT por encima del cual el beneficio
"normal" es otro."""

ETR_ANOMALY_DROP = Decimal("0.10")
"""Q4: caída del tipo efectivo vs la mediana de la serie que enciende la señal."""

ETR_LOW_LEVEL = Decimal("0.10")
"""Q4: tipo efectivo por debajo del cual, sostenido, el beneficio se apoya en
partidas fiscales."""

PAYOUT_STABILITY_LIMIT_PP = Decimal(20)
"""T3: σ del payout (en pp) que delata una política de dividendo no creíble."""

MOMENTUM_SLOWDOWN = Decimal("0.5")
"""T4: el crecimiento reciente del dividendo cae por debajo de la mitad del CAGR
de la serie → posible techo."""


# ── Catálogo (solo las métricas con banda simple) ─────────────────────

METRIC_CATALOG: tuple[MetricDefinition, ...] = (
    # Cobertura (D)
    MetricDefinition(
        "D1",
        "Payout sobre beneficio",
        "dividendo",
        MetricUnit.PERCENT,
        _LOWER,
        high_ok=Decimal("0.60"),
        high_alarm=Decimal("0.80"),
    ),
    MetricDefinition(
        "D2",
        "Payout sobre FCF",
        "dividendo",
        MetricUnit.PERCENT,
        _LOWER,
        high_ok=Decimal("0.60"),
        high_alarm=Decimal("0.85"),
        note="Primaria: la caja, no el beneficio, es lo que paga el dividendo.",
    ),
    MetricDefinition(
        "D3",
        "Cobertura FCF",
        "dividendo",
        MetricUnit.TIMES,
        _HIGHER,
        low_alarm=Decimal("1.15"),
        low_ok=Decimal("1.6"),
    ),
    MetricDefinition(
        "D4",
        "Payout FCF ajustado por SBC",
        "dividendo",
        MetricUnit.PERCENT,
        _LOWER,
        high_ok=Decimal("0.60"),
        high_alarm=Decimal("0.85"),
        note="La retribución en acciones es coste real que el CFO esconde; si D4 ≫ D2 el dividendo se paga diluyendo.",
    ),
    MetricDefinition(
        "D5",
        "Retorno total sobre FCF",
        "dividendo",
        MetricUnit.PERCENT,
        _LOWER,
        high_ok=Decimal("0.90"),
        high_alarm=Decimal("1.10"),
        note="Dividendo + recompras sobre caja libre. >100% sostenido = se devuelve más de lo que se genera.",
    ),
    MetricDefinition(
        "D6",
        "Payout REIT",
        "dividendo",
        MetricUnit.PERCENT,
        _LOWER,
        high_ok=Decimal("0.75"),
        high_alarm=Decimal("0.90"),
        note="Solo socimis: payout sobre FFO. En no-REIT sale not_computable.",
    ),
    MetricDefinition(
        "D8",
        "Margen de seguridad",
        "dividendo",
        MetricUnit.PERCENT,
        _HIGHER,
        low_alarm=Decimal("0.02"),
        low_ok=Decimal("0.05"),
    ),
    # Calidad de la caja (Q)
    MetricDefinition(
        "Q1",
        "Conversión CFO/beneficio",
        "dividendo",
        MetricUnit.PERCENT,
        _HIGHER,
        low_alarm=Decimal("0.8"),
        low_ok=ONE,
    ),
    MetricDefinition(
        "Q2",
        "Conversión FCF/EBITDA",
        "dividendo",
        MetricUnit.PERCENT,
        _HIGHER,
        low_alarm=Decimal("0.30"),
        low_ok=Decimal("0.50"),
    ),
    MetricDefinition(
        "Q3",
        "Divergencia FCF dual",
        "dividendo",
        MetricUnit.PERCENT,
        _LOWER,
        high_ok=Decimal("0.15"),
        high_alarm=Decimal("0.20"),
        note="|fcf_cfo − fcf_ebitda| / fcf_cfo: las dos formas de medir la caja no cuadran.",
    ),
    MetricDefinition(
        "Q5",
        "Peso de extraordinarios",
        "dividendo",
        MetricUnit.PERCENT,
        _LOWER,
        high_ok=EXTRAORDINARY_WEIGHT_LIMIT,
        high_alarm=EXTRAORDINARY_WEIGHT_LIMIT,
        note="|plusvalías − deterioros| / |EBT|: si el beneficio depende de vender o de no deteriorar, el beneficio normal es otro.",
    ),
    # Soporte del balance (B)
    MetricDefinition(
        "B3",
        "Años de dividendo en caja",
        "dividendo",
        MetricUnit.YEARS,
        _HIGHER,
        low_alarm=ONE,
        low_ok=Decimal(2),
    ),
    # Trayectoria (T)
    MetricDefinition(
        "T2",
        "CAGR del dividendo",
        "dividendo",
        MetricUnit.PERCENT,
        _HIGHER,
        low_alarm=ZERO,
        low_ok=ZERO,
        note="Crecimiento compuesto del dividendo por acción. Negativo → rojo directo.",
    ),
    MetricDefinition(
        "T3",
        "Estabilidad del payout",
        "dividendo",
        MetricUnit.PP,
        _LOWER,
        high_ok=PAYOUT_STABILITY_LIMIT_PP,
        high_alarm=PAYOUT_STABILITY_LIMIT_PP,
        note="σ del payout sobre FCF en la serie (pp): un payout errático es una política no creíble.",
    ),
)

METRIC_KEYS: tuple[str, ...] = tuple(definition.key for definition in METRIC_CATALOG)
DEFAULT_THRESHOLDS: Mapping[str, ThresholdSpec] = thresholds_from(METRIC_CATALOG)


# ── Bases de cálculo (con ajuste REIT) ────────────────────────────────


def profit_base(statement: CanonicalStatement, *, is_reit: bool) -> Amount:
    """La magnitud contra la que se mide el payout de beneficio (D1).

    REIT → FFO; resto → resultado neto (D6/§5)."""
    return dv.ffo(statement) if is_reit else sourced(statement, "net_income")


def cash_base(statement: CanonicalStatement, *, is_reit: bool) -> Amount:
    """La caja repartible contra la que se miden D2/D3/D8.

    REIT → FFO; resto → caja libre `fcf_cfo`."""
    return dv.ffo(statement) if is_reit else dv.fcf_cfo(statement)


# ── DPS: la serie que alimenta la trayectoria (D7) ────────────────────


@dataclass(frozen=True)
class DpsPoint:
    fiscal_year: int
    dps: Decimal | None


def compute_dps_series(series: StatementSeries) -> tuple[DpsPoint, ...]:
    """D7 — dividendo por acción por año. Sin banda: alimenta T1-T4."""
    return tuple(
        DpsPoint(fiscal_year=s.fiscal_year, dps=dv.dividend_per_share(s).value)
        for s in series.statements
    )


# ── Trayectoria (T1, T4: no bandeables; T2, T3: bandeables) ───────────


@dataclass(frozen=True)
class DividendTrajectory:
    """Los resultados de trayectoria que no son métricas con banda simple."""

    streak_no_cut: int
    """T1 — años consecutivos (desde el más reciente) sin recorte del DPS. Es
    una COTA INFERIOR: la serie es la ingerida, no la histórica completa."""
    momentum_slowdown: bool
    """T4 — el crecimiento reciente del dividendo es menos de la mitad del CAGR
    de la serie: posible techo."""


def compute_streak_no_cut(dps_points: tuple[DpsPoint, ...]) -> int:
    """T1 — racha sin recorte, contando hacia atrás desde el último ejercicio.

    Cota inferior honesta: solo cuenta lo que hay en la serie. Un `None` corta la
    racha (no se puede afirmar que no hubo recorte donde no hay dato).
    """
    values = [point.dps for point in dps_points]
    streak = 0
    for current, previous in zip(reversed(values), reversed(values[:-1]), strict=False):
        if current is None or previous is None or current < previous:
            break
        streak += 1
    return streak


# ── Q4 (anomalía fiscal): flag por serie ──────────────────────────────


def compute_tax_anomaly_flags(series: StatementSeries) -> FlagRuleResult:
    """Q4 — el tipo efectivo del año se aparta a la baja de la mediana de la
    serie (>10 pp), o lleva sostenidamente por debajo del 10%.

    Un crédito fiscal infla el resultado neto sin tocar la caja operativa y no se
    repite: un dividendo que se apoya en él tiene menos colchón del que aparenta.

    Publica también la evaluación de las dos reglas: con menos de dos tipos
    efectivos calculables no hay mediana contra la que comparar, y salir sin
    banderas de ahí no es «no se ha encendido», es que no se ha mirado.
    """
    rates: list[tuple[int, Decimal]] = []
    unevaluable: dict[int, str] = {}
    for statement in series.statements:
        rate = dv.effective_tax_rate(statement)
        if rate.value is None:
            unevaluable[statement.fiscal_year] = (
                rate.reason or "no se pudo calcular el tipo impositivo efectivo"
            )
        else:
            rates.append((statement.fiscal_year, rate.value))
    rate_years = [year for year, _ in rates]

    if len(rates) < 2:
        insufficient = unevaluable_reason(unevaluable, sustained=2, evaluable=rate_years)
        return FlagRuleResult(
            flags=(),
            evaluations=tuple(
                FlagEvaluation(
                    key=key,
                    outcome="not_computable",
                    # La mediana de la serie es la vara de la anomalía: con un
                    # solo tipo efectivo, el año se compararía consigo mismo.
                    reason=(
                        "hacen falta al menos dos ejercicios con tipo impositivo efectivo "
                        f"para tener mediana con la que comparar (hay {len(rates)}): {insufficient}"
                    ),
                    years_evaluated=tuple(rate_years),
                    years_unevaluable=tuple(sorted(unevaluable)),
                )
                for key in ("Q4_tax_anomaly", "Q4_tax_persistently_low")
            ),
        )
    median_etr = median([rate for _, rate in rates])

    flags: list[Flag] = []
    for year, etr in rates:
        if median_etr - etr > ETR_ANOMALY_DROP:
            flags.append(
                Flag(
                    key="Q4_tax_anomaly",
                    severity="amber",
                    message=(
                        f"En {year} el tipo impositivo efectivo ({etr:.1%}) cae más de 10 puntos "
                        f"por debajo de la mediana de la serie ({median_etr:.1%}): parte del "
                        "beneficio se apoya en partidas fiscales que no se repiten."
                    ),
                    evidence={"fiscal_year": year, "etr": str(etr), "median": str(median_etr)},
                )
            )

    low_years = [year for year, etr in rates if etr < ETR_LOW_LEVEL]
    persistently_low = False
    for first, second in itertools.pairwise(low_years):
        if second == first + 1:
            flags.append(
                Flag(
                    key="Q4_tax_persistently_low",
                    severity="amber",
                    message=(
                        f"El tipo impositivo efectivo lleva por debajo del 10% dos años seguidos "
                        f"({first}-{second}): el beneficio se apoya en ventajas fiscales."
                    ),
                    evidence={"years": [first, second]},
                )
            )
            persistently_low = True
            break

    anomaly_fired = any(flag.key == "Q4_tax_anomaly" for flag in flags)
    return FlagRuleResult(
        flags=tuple(flags),
        evaluations=(
            # La anomalía se juzga año a año contra la mediana: con dos tipos
            # efectivos ya hay comparación, aunque no sean consecutivos.
            evaluate_windowed_rule(
                "Q4_tax_anomaly",
                fired=anomaly_fired,
                evaluable=rate_years,
                unevaluable=unevaluable,
                sustained=1,
            ),
            # La persistencia exige DOS ejercicios seguidos: sin racha posible,
            # la regla no puede encenderse y decir «limpia» sería afirmar una
            # comprobación que no cabe hacer.
            evaluate_windowed_rule(
                "Q4_tax_persistently_low",
                fired=persistently_low,
                evaluable=rate_years,
                unevaluable=unevaluable,
                sustained=2,
            ),
        ),
    )


# ── Cruces de balance (B1, B2, B4): flags compuestos ──────────────────

BALANCE_SUPPORT_KEYS: tuple[str, ...] = (
    "B1_debt_competes_with_dividend",
    "B2_interest_priority",
    "B4_dividend_funded_externally",
)
"""Las tres reglas de soporte de balance. Se enumeran para poder publicar su
evaluación también cuando la serie está vacía y ninguna llega a ejecutarse."""


def compute_balance_support_flags(
    series: StatementSeries,
    metrics_by_key: Mapping[str, MetricResult],
    forensic_bands: Mapping[str, Band | None],
) -> FlagRuleResult:
    """B1, B2 y B4 — cruces que combinan la deuda con el dividendo.

    B1/B2 no son ratios nuevos: son la LECTURA CONJUNTA de bandas ya calculadas
    en otras capas (S4/S2 de la Capa 1, D2 de aquí). Se pasan las bandas
    relevantes en vez de recalcular, para que el cruce hable exactamente del
    mismo número que el usuario ve en su métrica.

    Las tres publican su evaluación, y aquí importa especialmente: sus guardas
    son `if` de una sola línea sobre inputs que en una financiera o en una
    empresa sin caja libre son `None`, así que la ausencia de bandera era
    indistinguible de una comprobación limpia. **B4 es la que más pesa**: es una
    de las cuatro condiciones que fuerzan «Evitar» en el perfil de seguridad.
    """
    flags: list[Flag] = []
    latest = series.latest
    if latest is None:
        no_series = "no hay ningún ejercicio en la serie"
        return FlagRuleResult(
            flags=(),
            evaluations=tuple(
                FlagEvaluation(key=key, outcome="not_computable", reason=no_series)
                for key in BALANCE_SUPPORT_KEYS
            ),
        )

    year = latest.fiscal_year
    evaluations: list[FlagEvaluation] = []
    inapplicable = flag_applicability(
        series.security.sector, is_financial=series.security.is_financial
    )
    d2 = metrics_by_key.get("D2")
    s4_band = forensic_bands.get("S4")
    s2_band = forensic_bands.get("S2")

    # B1 — la deuda compite con el dividendo
    b1_fired = s4_band == "stressed" and d2 is not None and d2.band in ("caution", "stressed")
    if b1_fired and d2 is not None:
        flags.append(
            Flag(
                key="B1_debt_competes_with_dividend",
                severity="amber",
                message=(
                    "La deuda neta sobre EBITDA está en zona de alarma y a la vez el dividendo se "
                    "come buena parte de la caja libre: amortizar deuda y sostener el dividendo "
                    "compiten por el mismo dinero."
                ),
                evidence={"s4_band": s4_band, "d2_band": d2.band},
            )
        )
    evaluations.append(
        not_applicable_rule(
            "B1_debt_competes_with_dividend", inapplicable["B1_debt_competes_with_dividend"]
        )
        if "B1_debt_competes_with_dividend" in inapplicable
        else evaluate_single_year_rule(
            "B1_debt_competes_with_dividend",
            fired=b1_fired,
            year=year,
            missing=_missing_cross_input(
                ("la banda de deuda neta / EBITDA (S4)", s4_band is None),
                ("la banda del payout sobre caja libre (D2)", d2 is None or d2.band is None),
                metric=d2,
            ),
        )
    )

    # B2 — los intereses cobran antes que el accionista
    d2_value = d2.value if d2 is not None else None
    b2_fired = s2_band == "stressed" and d2_value is not None and d2_value > Decimal("0.60")
    if b2_fired and d2_value is not None:
        flags.append(
            Flag(
                key="B2_interest_priority",
                severity="red",
                message=(
                    "La cobertura de intereses es débil y el payout supera el 60%: los intereses "
                    "de la deuda se cobran antes que tú, y dejan poco margen si el negocio flojea."
                ),
                evidence={"s2_band": s2_band, "d2": str(d2_value)},
            )
        )
    evaluations.append(
        not_applicable_rule("B2_interest_priority", inapplicable["B2_interest_priority"])
        if "B2_interest_priority" in inapplicable
        else evaluate_single_year_rule(
            "B2_interest_priority",
            fired=b2_fired,
            year=year,
            missing=_missing_cross_input(
                ("la banda de cobertura de intereses (S2)", s2_band is None),
                ("el payout sobre caja libre (D2)", d2_value is None),
                metric=d2,
            ),
        )
    )

    # B4 — el dividendo se financia con deuda o emisión (C7 aplicado al dividendo)
    fcf = dv.fcf_cfo(latest)
    dividends = latest.dividends_paid
    debt_change = latest.debt_change
    share_issuance = latest.share_issuance
    b4_fired = (
        fcf.value is not None
        and dividends is not None
        and dividends > fcf.value
        and (
            (debt_change is not None and debt_change > ZERO)
            or (share_issuance is not None and share_issuance > ZERO)
        )
    )
    evaluations.append(
        evaluate_single_year_rule(
            "B4_dividend_funded_externally",
            fired=b4_fired,
            year=year,
            missing=_b4_missing(
                fcf=fcf,
                dividends=dividends,
                debt_change=debt_change,
                share_issuance=share_issuance,
            ),
        )
    )
    if b4_fired and fcf.value is not None and dividends is not None:
        gap = dividends - fcf.value
        sources = []
        if debt_change is not None and debt_change > ZERO:
            sources.append(f"{debt_change:,.0f} de más deuda")
        if share_issuance is not None and share_issuance > ZERO:
            sources.append(f"{share_issuance:,.0f} de emisión de acciones")
        flags.append(
            Flag(
                key="B4_dividend_funded_externally",
                severity="red",
                message=(
                    f"El dividendo ({dividends:,.0f}) supera a la caja libre ({fcf.value:,.0f}) en "
                    f"{gap:,.0f}, y a la vez entra dinero de {' y '.join(sources)}: el dividendo se "
                    "está pagando con financiación externa, la señal individual más predictiva de "
                    "un recorte futuro."
                ),
                evidence={
                    "dividends_paid": str(dividends),
                    "fcf_cfo": str(fcf.value),
                    "debt_change": str(debt_change) if debt_change is not None else None,
                    "share_issuance": str(share_issuance) if share_issuance is not None else None,
                },
            )
        )
    # RC-2 — en una regulada, un payout alto es su modelo, no un hallazgo. Lo que
    # informa es quién financia el exceso, y eso lo miran C7 y B4. La banda de D2
    # ya está relajada para el sector (0,75/0,95); esto enlaza la lectura para
    # que un ámbar no se quede en «paga mucho» sin la pregunta que sigue.
    if (
        series.security.sector is SectorInternal.UTILITIES
        and d2 is not None
        and d2.band in ("caution", "stressed")
    ):
        flags.append(
            Flag(
                key="RC2_utility_payout_needs_funding_check",
                severity="info",
                message=(
                    "En una regulada, un payout alto sobre la caja libre es su modelo de "
                    "negocio y por eso su banda ya es más ancha. La pregunta que decide no "
                    "es «¿paga mucho?» sino «¿quién paga el exceso?»: mira C7 (retorno al "
                    "accionista financiado con deuda) y B4 (dividendo financiado con deuda "
                    "o emisión), que no se relajan por sector."
                ),
                evidence={"d2_band": d2.band, "d2": str(d2.value) if d2.value else None},
            )
        )

    return FlagRuleResult(flags=tuple(flags), evaluations=tuple(evaluations))


def _missing_cross_input(*inputs: tuple[str, bool], metric: MetricResult | None) -> str | None:
    """El motivo de que un cruce de bandas no se pueda evaluar, o `None`.

    Cuando lo que falta es una métrica de esta capa, se arrastra SU razón: «falta
    el coste de ventas» explica; «falta la banda de D2» sólo traslada la pregunta.
    """
    missing = [label for label, absent in inputs if absent]
    if not missing:
        return None
    detail = f"no se ha podido comprobar: falta {' y falta '.join(missing)}"
    if metric is not None and metric.reason:
        return f"{detail} ({metric.reason})"
    return detail


def _b4_missing(
    *,
    fcf: Amount,
    dividends: Decimal | None,
    debt_change: Decimal | None,
    share_issuance: Decimal | None,
) -> str | None:
    """Por qué B4 no se puede afirmar limpia.

    El orden importa. Si el dividendo NO supera a la caja libre, la regla está
    comprobada y limpia aunque no se sepa nada de la financiación: no hay exceso
    que financiar. Sólo cuando SÍ lo supera hace falta saber de dónde salió el
    dinero — y ahí, una fuente desconocida no se puede leer como «no entró».
    """
    if fcf.value is None:
        return f"no se ha podido comprobar: {fcf.reason or 'falta la caja libre'}"
    if dividends is None:
        return "no se ha podido comprobar: falta el dividendo pagado"
    if dividends <= fcf.value:
        return None
    unknown = [
        label
        for label, value in (
            ("la variación de deuda", debt_change),
            ("la emisión de acciones", share_issuance),
        )
        if value is None
    ]
    if not unknown:
        return None
    return (
        "el dividendo supera a la caja libre y no se sabe de dónde salió el exceso: "
        f"falta {' y falta '.join(unknown)}"
    )


# ── Resultado de la capa ──────────────────────────────────────────────


@dataclass(frozen=True)
class DividendResult:
    metrics: tuple[MetricResult, ...]
    dps_series: tuple[DpsPoint, ...]
    trajectory: DividendTrajectory
    flags: tuple[Flag, ...]
    flag_evaluations: tuple[FlagEvaluation, ...] = ()
    """Qué reglas se pudieron comprobar (las dos de Q4 y las tres de balance).
    Sin esto, la síntesis leía «no hay bandera B4» como «el dividendo no se
    financia con deuda» — y B4 es una de las cuatro condiciones de «Evitar»."""

    def get(self, key: str, fiscal_year: int) -> MetricResult | None:
        for metric in self.metrics:
            if metric.key == key and metric.fiscal_year == fiscal_year:
                return metric
        return None

    def by_key(self, key: str) -> tuple[MetricResult, ...]:
        return tuple(m for m in self.metrics if m.key == key)


# ── Cálculo por ejercicio ─────────────────────────────────────────────


NOT_APPLICABLE_TO_FINANCIALS_CASH = (
    "el modelo de cobertura sobre caja libre no describe a una financiera: "
    "su negocio es mover dinero, así que el cociente sale y no significa nada"
)


def _year_metrics(
    series: StatementSeries,
    statement: CanonicalStatement,
    specs: Mapping[str, ThresholdSpec],
    *,
    is_reit: bool,
    is_financial: bool = False,
) -> list[MetricResult]:
    year = statement.fiscal_year
    dividends = sourced(statement, "dividends_paid")
    revenue = sourced(statement, "revenue")
    cfo = sourced(statement, "cfo")
    ffo = dv.ffo(statement)
    fcf = dv.fcf_cfo(statement)
    ebitda = dv.ebitda(statement)

    profit = profit_base(statement, is_reit=is_reit)
    cash = cash_base(statement, is_reit=is_reit)
    cash_label = "FFO" if is_reit else "caja libre"

    def metric(key: str, amount: Amount) -> MetricResult:
        return to_metric_result(key, year, amount, specs)

    def cash_based(amount: Amount) -> Amount:
        """Las ratios que dividen por caja libre no describen a una financiera.

        En un banco la «caja libre» del esquema CFO − capex no significa lo que
        significa en una empresa industrial: su negocio ES mover dinero, así que
        el cociente sale y no quiere decir nada. Se marca igual que D6 hace con
        las socimis — `not_computable` con motivo, nunca omitido (PHASE-44.19).

        Hasta ahora esto no se veía porque la pestaña entera se ocultaba para
        toda financiera; al dejar de ocultarla, estas cinco habrían salido con
        banda y color, que es peor que no enseñarlas.
        """
        if not is_financial:
            return amount
        return Amount(
            value=None,
            provenance=Provenance.DERIVED,
            status="not_computable",
            reason=NOT_APPLICABLE_TO_FINANCIALS_CASH,
        )

    results = [
        # D1 divide por BENEFICIO, no por caja: es contable y vale igual en un
        # banco que en una fábrica, así que no se exime.
        metric("D1", divide(dividends, profit, denominator_label="beneficio repartible")),
        metric("D2", cash_based(divide(dividends, cash, denominator_label=cash_label))),
        metric("D3", cash_based(divide(cash, dividends, denominator_label="dividendos"))),
        metric(
            "D4",
            cash_based(
                divide(
                    dividends,
                    subtract(fcf, sourced(statement, "sbc_expense")),
                    denominator_label="caja libre menos retribución en acciones",
                )
            ),
        ),
        metric(
            "D5",
            cash_based(
                divide(
                    add(dividends, sourced(statement, "buybacks")),
                    fcf,
                    denominator_label="caja libre",
                )
            ),
        ),
        metric(
            "D6",
            (
                divide(dividends, ffo, denominator_label="FFO")
                if is_reit
                else Amount(
                    value=None,
                    provenance=Provenance.DERIVED,
                    status="not_computable",
                    reason="solo aplica a socimis (is_reit=false)",
                )
            ),
        ),
        # D8 también divide por caja libre (`cash − dividendos`), pese a que su
        # nombre —«margen de seguridad»— no lo sugiere.
        metric(
            "D8",
            cash_based(divide(subtract(cash, dividends), revenue, denominator_label="ventas")),
        ),
        # Calidad de la caja
        metric(
            "Q1",
            divide(cfo, sourced(statement, "net_income"), denominator_label="resultado neto"),
        ),
        metric("Q2", divide(fcf, ebitda, denominator_label="EBITDA")),
        metric("Q3", _fcf_divergence(series, statement)),
        metric("Q5", _extraordinary_weight(statement)),
        # Soporte del balance
        metric(
            "B3",
            divide(
                add(sourced(statement, "cash"), sourced(statement, "current_financial_assets")),
                dividends,
                denominator_label="dividendos",
            ),
        ),
    ]
    return results


def _fcf_divergence(series: StatementSeries, statement: CanonicalStatement) -> Amount:
    """Q3 — |fcf_cfo − fcf_ebitda| / fcf_cfo. Necesita t−1 (para fcf_ebitda)."""
    primary = dv.fcf_cfo(statement)
    contrast = dv.fcf_ebitda(series, statement.fiscal_year)
    if primary.is_missing:
        return primary
    if contrast.is_missing:
        return contrast
    assert primary.value is not None and contrast.value is not None
    if primary.value == ZERO:
        return Amount(
            value=None,
            provenance=Provenance.DERIVED,
            status="not_computable",
            reason="la caja libre es cero: la divergencia relativa no está definida",
        )
    divergence = abs(primary.value - contrast.value) / abs(primary.value)
    return Amount(value=divergence, provenance=Provenance.DERIVED)


def _extraordinary_weight(statement: CanonicalStatement) -> Amount:
    """Q5 — |plusvalías − deterioros| / |EBT|."""
    gains = sourced(statement, "gains_on_sale_of_business")
    impairments = sourced(statement, "impairments")
    ebt = dv.ebt(statement)
    if gains.is_missing or impairments.is_missing:
        return subtract(gains, impairments)
    if ebt.is_missing:
        return ebt
    assert gains.value is not None and impairments.value is not None and ebt.value is not None
    if ebt.value == ZERO:
        return Amount(
            value=None,
            provenance=Provenance.DERIVED,
            status="not_computable",
            reason="el resultado antes de impuestos es cero",
        )
    weight = abs(gains.value - impairments.value) / abs(ebt.value)
    return Amount(value=weight, provenance=Provenance.DERIVED)


# ── Trayectoria bandeable (T2, T3) ────────────────────────────────────


def compute_dividend_cagr(dps_points: tuple[DpsPoint, ...]) -> Amount:
    """T2 — CAGR del dividendo por acción sobre la serie."""
    values = [(p.fiscal_year, p.dps) for p in dps_points if p.dps is not None]
    if len(values) < 2:
        return Amount(
            value=None,
            provenance=Provenance.DERIVED,
            status="not_computable",
            reason="hacen falta al menos dos ejercicios con dividendo por acción",
        )
    growth, reason = cagr(values[0][1], values[-1][1], values[-1][0] - values[0][0])
    if growth is None:
        return Amount(
            value=None, provenance=Provenance.DERIVED, status="not_computable", reason=reason
        )
    return Amount(value=growth, provenance=Provenance.DERIVED)


def compute_payout_stability(payouts: list[Decimal]) -> Amount:
    """T3 — σ del payout sobre FCF (D2) en la serie, en pp."""
    if len(payouts) < MIN_YEARS_FOR_PAYOUT_STABILITY:
        return Amount(
            value=None,
            provenance=Provenance.DERIVED,
            status="not_computable",
            reason=(
                f"hacen falta al menos {MIN_YEARS_FOR_PAYOUT_STABILITY} ejercicios con payout "
                f"calculable para medir su estabilidad (hay {len(payouts)})"
            ),
        )
    return Amount(value=population_stdev(payouts) * PP, provenance=Provenance.DERIVED)


# ── Orquestación ──────────────────────────────────────────────────────


def compute(
    series: StatementSeries,
    thresholds: Mapping[str, ThresholdSpec] | None = None,
    *,
    forensic_bands: Mapping[str, Band | None] | None = None,
) -> DividendResult:
    """Calcula la Capa 3 completa.

    `forensic_bands` son las bandas de S2/S4 (Capa 1) del ÚLTIMO ejercicio, que
    B1/B2 leen para su cruce. Si no se pasan, esos cruces no se evalúan (el
    servicio las inyecta; los tests pueden probar el resto sin ellas).
    """
    specs = DEFAULT_THRESHOLDS if thresholds is None else thresholds
    is_reit = series.security.is_reit

    metrics: list[MetricResult] = []
    payouts_over_fcf: list[Decimal] = []
    for statement in series.statements:
        year_metrics = _year_metrics(
            series,
            statement,
            specs,
            is_reit=is_reit,
            is_financial=series.security.is_financial,
        )
        metrics.extend(year_metrics)
        d2 = next((m for m in year_metrics if m.key == "D2"), None)
        if d2 is not None and d2.value is not None:
            payouts_over_fcf.append(d2.value)

    dps_series = compute_dps_series(series)

    # Trayectoria bandeable, referida al último ejercicio.
    last_year = series.years[-1] if series.years else 0
    metrics.append(to_metric_result("T2", last_year, compute_dividend_cagr(dps_series), specs))
    metrics.append(
        to_metric_result("T3", last_year, compute_payout_stability(payouts_over_fcf), specs)
    )

    trajectory = DividendTrajectory(
        streak_no_cut=compute_streak_no_cut(dps_series),
        momentum_slowdown=_momentum_slowdown(dps_series),
    )

    tax = compute_tax_anomaly_flags(series)
    latest_metrics = {m.key: m for m in metrics if m.fiscal_year == last_year}
    balance = compute_balance_support_flags(series, latest_metrics, forensic_bands or {})

    return DividendResult(
        metrics=tuple(metrics),
        dps_series=dps_series,
        trajectory=trajectory,
        flags=tuple([*tax.flags, *balance.flags]),
        flag_evaluations=tuple([*tax.evaluations, *balance.evaluations]),
    )


def _momentum_slowdown(dps_points: tuple[DpsPoint, ...]) -> bool:
    """T4 — el crecimiento del dividendo del último año es menos de la mitad del
    CAGR de la serie: el dividendo pierde impulso, posible techo."""
    values = [(p.fiscal_year, p.dps) for p in dps_points if p.dps is not None]
    if len(values) < 3:
        return False
    recent_prev, recent_last = values[-2][1], values[-1][1]
    if recent_prev is None or recent_last is None or recent_prev <= ZERO:
        return False
    recent_growth = (recent_last - recent_prev) / recent_prev
    series_cagr, _ = cagr(values[0][1], values[-1][1], values[-1][0] - values[0][0])
    if series_cagr is None or series_cagr <= ZERO:
        return False
    return recent_growth < series_cagr * MOMENTUM_SLOWDOWN
