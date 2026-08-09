"""Capa 2 — forense (PHASE-44.3, DESIGN §5).

Modelos académicos de manipulación contable y de quiebra. Todos **book-based**
y deterministas: ninguno depende del precio de mercado, porque un score que se
mueve con la cotización no sería reproducible al reejecutar un run antiguo
(ARCHITECTURE §4.3).

Regla dura del §5 y de ARCHITECTURE §4.2: **si `is_financial` no se calculan**.
Los coeficientes de Beneish y Altman se estimaron sobre empresas industriales;
en un banco, "deuda sobre activo" o "rotación de activos" significan algo
distinto y el score saldría catastrófico por construcción. Pero la clave NUNCA
se omite: sale `not_computable` con la razón, para que el informe explique por
qué falta en vez de dejar un hueco mudo.

Modelos implementados: M-Score (Beneish), Z''-Score (Altman 1995 book-based),
F-Score (Piotroski), accruals de Sloan, F5 (riesgo de fondo de comercio),
F6 (anomalía del circulante), FZ (X-Score de Zmijewski) y F7 (C-Score de
Montier).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from app.modules.investment.analysis.engine import derivations as dv
from app.modules.investment.analysis.engine.conventions import (
    ZERO,
    avg_balance,
    divide,
    sourced,
    subtract,
)
from app.modules.investment.analysis.engine.flag_rules import NO_MATERIAL_INVENTORY
from app.modules.investment.analysis.engine.metrics import (
    MetricDefinition,
    MetricUnit,
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

NOT_APPLICABLE_TO_FINANCIALS = "modelo no aplicable a financieras"
"""Razón EXACTA que exige ARCHITECTURE §4.2. Constante para que los ocho scores
digan lo mismo y la UI pueda reconocerla."""

_LOWER = ThresholdDirection.LOWER_BETTER
_HIGHER = ThresholdDirection.HIGHER_BETTER


# ── Catálogo ──────────────────────────────────────────────────────────

METRIC_CATALOG: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        "m_score",
        "M-Score de Beneish",
        "forense",
        MetricUnit.SCORE,
        _LOWER,
        high_ok=Decimal("-2.22"),
        high_alarm=Decimal("-1.78"),
        note=(
            "Probabilidad de manipulación contable a partir de 8 ratios t/t−1. "
            "La variable que dispara importa más que el agregado, por eso se "
            "reportan las 8 junto al score."
        ),
    ),
    MetricDefinition(
        "z_score",
        "Z''-Score de Altman",
        "forense",
        MetricUnit.SCORE,
        _HIGHER,
        low_alarm=Decimal("1.10"),
        low_ok=Decimal("2.60"),
        model_variant="Z''(1995)",
        note=(
            "Riesgo de insolvencia, variante book-based de 1995: no depende de "
            "capitalización, así que el run es reproducible. La Z clásica queda "
            "como model_variant futura."
        ),
    ),
    MetricDefinition(
        "f_score",
        "F-Score de Piotroski",
        "forense",
        MetricUnit.COUNT,
        _HIGHER,
        low_alarm=Decimal(4),
        low_ok=Decimal(7),
        note="9 tests binarios de calidad y fortaleza financiera.",
    ),
    MetricDefinition(
        "accruals",
        "Accruals de Sloan",
        "forense",
        MetricUnit.PERCENT,
        _LOWER,
        high_ok=Decimal("0.05"),
        high_alarm=Decimal("0.10"),
        note=(
            "(Resultado neto − flujo de explotación) / activo medio. Positivo alto "
            "= el beneficio va por delante de la caja. La banda es sobre el VALOR "
            "ABSOLUTO: un accrual muy negativo también es una anomalía."
        ),
    ),
    MetricDefinition(
        "F5",
        "Riesgo de fondo de comercio",
        "forense",
        MetricUnit.PERCENT,
        _LOWER,
        high_ok=Decimal("0.30"),
        high_alarm=Decimal("0.50"),
        note=(
            "Fondo de comercio sobre activo total. Calibrable por sector: un "
            "comprador serial sano puede vivir en ámbar."
        ),
    ),
    MetricDefinition(
        "F6",
        "Anomalía del circulante",
        "forense",
        MetricUnit.PERCENT,
        _LOWER,
        high_ok=Decimal("0.15"),
        high_alarm=Decimal("0.30"),
        note=(
            "|Δcirculante operativo| − Δventas, en tanto por uno. Es la "
            "descomposición visible de TATA: DÓNDE se acumula el devengo."
        ),
    ),
    MetricDefinition(
        "FZ",
        "X-Score de Zmijewski",
        "forense",
        MetricUnit.SCORE,
        _LOWER,
        high_ok=Decimal("-1.036433"),
        high_alarm=Decimal("-0.253347"),
        note=(
            "Probit de quiebra book-based. Los cortes son los cuantiles normales "
            "de P(distress)=15% y 40%: como Φ es monótona, bandear X equivale a "
            "bandear P, y así el engine se queda en Decimal exacto (la conversión "
            "a probabilidad es de presentación)."
        ),
    ),
    MetricDefinition(
        "F7",
        "C-Score de Montier",
        "forense",
        MetricUnit.COUNT,
        _LOWER,
        high_ok=Decimal(1),
        high_alarm=Decimal(3),
        note=(
            "6 checks binarios de 'cocina' contable. Complementa a Beneish: "
            "conteo robusto frente a regresión. Cuando ambos disparan, la "
            "evidencia es fuerte; cuando divergen, el desglose dice por qué."
        ),
    ),
)

METRIC_KEYS: tuple[str, ...] = tuple(definition.key for definition in METRIC_CATALOG)
DEFAULT_THRESHOLDS: Mapping[str, ThresholdSpec] = thresholds_from(METRIC_CATALOG)

ZMIJEWSKI_P_CUTOFFS: tuple[tuple[Decimal, Decimal], ...] = (
    (Decimal("0.15"), Decimal("-1.036433")),
    (Decimal("0.40"), Decimal("-0.253347")),
)
"""(P, Φ⁻¹(P)) — la correspondencia que justifica los cortes de `FZ`. Se usa en
los tests para comprobar que bandear X y bandear P dan lo mismo."""


# ── Resultado ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ScoreBreakdown:
    """Desglose de un score compuesto.

    Existe porque el agregado es la parte MENOS informativa: un M-Score de −1,5
    no dice nada; que lo dispare DSRI (cobros) o TATA (devengo) apunta a
    problemas distintos. La UI enseña el desglose, no solo el número.
    """

    key: str
    fiscal_year: int
    components: dict[str, Decimal]
    checks: dict[str, bool]


@dataclass(frozen=True)
class ForensicResult:
    metrics: tuple[MetricResult, ...]
    breakdowns: tuple[ScoreBreakdown, ...] = ()
    flags: tuple[Flag, ...] = ()

    def get(self, key: str, fiscal_year: int) -> MetricResult | None:
        for metric in self.metrics:
            if metric.key == key and metric.fiscal_year == fiscal_year:
                return metric
        return None

    def breakdown_for(self, key: str, fiscal_year: int) -> ScoreBreakdown | None:
        for breakdown in self.breakdowns:
            if breakdown.key == key and breakdown.fiscal_year == fiscal_year:
                return breakdown
        return None


# ── Utilidades ────────────────────────────────────────────────────────


def _not_computable(reason: str) -> Amount:
    return Amount(value=None, provenance=Provenance.DERIVED, status="not_computable", reason=reason)


def _ratio(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator == ZERO:
        return None
    return numerator / denominator


def _quotient(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    """Cociente t/t−1 de un ratio ya calculado (la forma de todas las variables
    de Beneish)."""
    if current is None or previous is None or previous == ZERO:
        return None
    return current / previous


# ── M-Score de Beneish ────────────────────────────────────────────────


def _depreciation_rate(statement: CanonicalStatement) -> Decimal | None:
    """D&A / (D&A + inmovilizado neto) — la tasa a la que amortiza."""
    dna = statement.depreciation_amortization
    ppe = statement.ppe_net
    if dna is None or ppe is None:
        return None
    denominator = dna + ppe
    return dna / denominator if denominator != ZERO else None


def _asset_quality(statement: CanonicalStatement) -> Decimal | None:
    """1 − (activo corriente + inmovilizado) / activo total: la porción del
    activo que NO es ni circulante ni ladrillo — donde se esconde lo capitalizado
    de más."""
    current_assets = statement.current_assets
    ppe = statement.ppe_net
    total = statement.total_assets
    if current_assets is None or ppe is None or total is None or total == ZERO:
        return None
    return Decimal(1) - (current_assets + ppe) / total


def compute_m_score(
    current: CanonicalStatement, previous: CanonicalStatement
) -> tuple[Amount, dict[str, Decimal]]:
    """M-Score de Beneish (8 variables), DESIGN §5 Capa 2."""
    dsri = _quotient(
        _ratio(current.receivables, current.revenue),
        _ratio(previous.receivables, previous.revenue),
    )
    gross_margin_now = _ratio(
        (
            (current.revenue - current.cogs)
            if current.revenue is not None and current.cogs is not None
            else None
        ),
        current.revenue,
    )
    gross_margin_before = _ratio(
        (
            (previous.revenue - previous.cogs)
            if previous.revenue is not None and previous.cogs is not None
            else None
        ),
        previous.revenue,
    )
    gmi = _quotient(gross_margin_before, gross_margin_now)
    aqi = _quotient(_asset_quality(current), _asset_quality(previous))
    sgi = _quotient(current.revenue, previous.revenue)
    depi = _quotient(_depreciation_rate(previous), _depreciation_rate(current))
    sgai = _quotient(
        _ratio(current.sga_expense, current.revenue),
        _ratio(previous.sga_expense, previous.revenue),
    )
    lvgi = _quotient(
        _ratio(
            (
                (current.current_liabilities + current.long_term_debt)
                if current.current_liabilities is not None and current.long_term_debt is not None
                else None
            ),
            current.total_assets,
        ),
        _ratio(
            (
                (previous.current_liabilities + previous.long_term_debt)
                if previous.current_liabilities is not None and previous.long_term_debt is not None
                else None
            ),
            previous.total_assets,
        ),
    )
    tata = _ratio(
        (
            (current.net_income - current.cfo)
            if current.net_income is not None and current.cfo is not None
            else None
        ),
        current.total_assets,
    )

    variables = {
        "DSRI": dsri,
        "GMI": gmi,
        "AQI": aqi,
        "SGI": sgi,
        "DEPI": depi,
        "SGAI": sgai,
        "LVGI": lvgi,
        "TATA": tata,
    }
    missing = [name for name, value in variables.items() if value is None]
    if missing:
        return (
            _not_computable(
                f"no se pueden calcular las variables {', '.join(missing)} del M-Score"
            ),
            {},
        )
    resolved = {name: value for name, value in variables.items() if value is not None}
    score = (
        Decimal("-4.84")
        + Decimal("0.920") * resolved["DSRI"]
        + Decimal("0.528") * resolved["GMI"]
        + Decimal("0.404") * resolved["AQI"]
        + Decimal("0.892") * resolved["SGI"]
        + Decimal("0.115") * resolved["DEPI"]
        - Decimal("0.172") * resolved["SGAI"]
        + Decimal("4.679") * resolved["TATA"]
        - Decimal("0.327") * resolved["LVGI"]
    )
    return Amount(value=score, provenance=Provenance.DERIVED), resolved


# ── Z''-Score de Altman ───────────────────────────────────────────────


def compute_z_score(statement: CanonicalStatement) -> tuple[Amount, dict[str, Decimal]]:
    """Z'' = 6,56·X1 + 3,26·X2 + 6,72·X3 + 1,05·X4 (Altman 1995, book-based).

    X3 usa el EBIT **reportado**, no `ebit_clean`: el modelo se calibró sobre
    EBIT contable, y sustituirlo por una versión limpia cambiaría la escala de
    los cortes originales.
    """
    total_assets = statement.total_assets
    x1 = _ratio(dv.wc_total(statement).value, total_assets)
    x2 = _ratio(statement.retained_earnings, total_assets)
    x3 = _ratio(statement.ebit, total_assets)
    x4 = _ratio(statement.equity, statement.total_liabilities)

    variables = {"X1": x1, "X2": x2, "X3": x3, "X4": x4}
    missing = [name for name, value in variables.items() if value is None]
    if missing:
        return (
            _not_computable(f"no se pueden calcular las variables {', '.join(missing)} de Z''"),
            {},
        )
    resolved = {name: value for name, value in variables.items() if value is not None}
    score = (
        Decimal("6.56") * resolved["X1"]
        + Decimal("3.26") * resolved["X2"]
        + Decimal("6.72") * resolved["X3"]
        + Decimal("1.05") * resolved["X4"]
    )
    return Amount(value=score, provenance=Provenance.DERIVED), resolved


# ── F-Score de Piotroski ──────────────────────────────────────────────


def compute_f_score(
    current: CanonicalStatement, previous: CanonicalStatement
) -> tuple[Amount, dict[str, bool]]:
    """9 tests binarios. Un test que no se puede evaluar hace el score
    `not_computable`: un F-Score sobre 7 tests no es comparable con la banda
    0-9, y presentarlo como si lo fuera sería peor que no darlo."""
    roa_now = _ratio(current.net_income, current.total_assets)
    roa_before = _ratio(previous.net_income, previous.total_assets)
    current_ratio_now = _ratio(current.current_assets, current.current_liabilities)
    current_ratio_before = _ratio(previous.current_assets, previous.current_liabilities)
    gross_margin_now = _ratio(
        (
            (current.revenue - current.cogs)
            if current.revenue is not None and current.cogs is not None
            else None
        ),
        current.revenue,
    )
    gross_margin_before = _ratio(
        (
            (previous.revenue - previous.cogs)
            if previous.revenue is not None and previous.cogs is not None
            else None
        ),
        previous.revenue,
    )
    turnover_now = _ratio(current.revenue, current.total_assets)
    turnover_before = _ratio(previous.revenue, previous.total_assets)
    leverage_now = _ratio(current.long_term_debt, current.total_assets)
    leverage_before = _ratio(previous.long_term_debt, previous.total_assets)

    tests: dict[str, bool | None] = {
        "P1_roa_positivo": roa_now > ZERO if roa_now is not None else None,
        "P2_cfo_positivo": current.cfo > ZERO if current.cfo is not None else None,
        "P3_roa_mejora": (
            roa_now > roa_before if roa_now is not None and roa_before is not None else None
        ),
        "P4_cfo_supera_beneficio": (
            current.cfo > current.net_income
            if current.cfo is not None and current.net_income is not None
            else None
        ),
        "P5_menos_apalancamiento": (
            leverage_now < leverage_before
            if leverage_now is not None and leverage_before is not None
            else None
        ),
        "P6_mejor_liquidez": (
            current_ratio_now > current_ratio_before
            if current_ratio_now is not None and current_ratio_before is not None
            else None
        ),
        "P7_sin_emision": (
            current.share_issuance == ZERO if current.share_issuance is not None else None
        ),
        "P8_mejor_margen_bruto": (
            gross_margin_now > gross_margin_before
            if gross_margin_now is not None and gross_margin_before is not None
            else None
        ),
        "P9_mejor_rotacion": (
            turnover_now > turnover_before
            if turnover_now is not None and turnover_before is not None
            else None
        ),
    }
    missing = [name for name, value in tests.items() if value is None]
    if missing:
        return (
            _not_computable(f"no se pueden evaluar los tests {', '.join(missing)} del F-Score"),
            {},
        )
    resolved = {name: value for name, value in tests.items() if value is not None}
    return (
        Amount(
            value=Decimal(sum(1 for passed in resolved.values() if passed)),
            provenance=Provenance.DERIVED,
        ),
        resolved,
    )


# ── C-Score de Montier ────────────────────────────────────────────────


def _other_current_assets_over_revenue(statement: CanonicalStatement) -> Decimal | None:
    """ "Otros activos corrientes" sobre ventas: el cajón donde acaba lo que no
    es caja, cobros ni inventario."""
    parts = (
        statement.current_assets,
        statement.cash,
        statement.current_financial_assets,
        statement.receivables,
        statement.inventory,
    )
    if any(part is None for part in parts) or statement.revenue in (None, ZERO):
        return None
    current_assets, cash, financial, receivables, inventory = parts
    assert current_assets is not None and cash is not None and financial is not None
    assert receivables is not None and inventory is not None and statement.revenue is not None
    other = current_assets - cash - financial - receivables - inventory
    return other / statement.revenue


C_SCORE_INVENTORY_CHECK = "C3_dias_de_inventario_suben"

MIN_C_SCORE_CHECKS = 4
"""Checks aplicables por debajo de los cuales F7 no se computa.

Con tres de seis, el score deja de significar lo que su banda dice: un 2 sobre 3
y un 2 sobre 6 son cosas muy distintas, y la banda está escrita para el segundo.
Antes que un número descontextualizado, `not_computable` con su motivo."""


def compute_c_score(
    current: CanonicalStatement,
    previous: CanonicalStatement,
    *,
    inapplicable_checks: frozenset[str] = frozenset(),
) -> tuple[Amount, dict[str, bool]]:
    """6 checks binarios de "cocina" contable (F7), con denominador variable.

    Los checks que no se plantean en el sector salen del cómputo en vez de
    bloquearlo (PHASE-44.21): a una eléctrica no le suben los días de inventario
    porque no tiene inventario, y hasta ahora ese `None` hacía que TODO el
    C-Score saliera no computable. La empresa perdía cinco comprobaciones buenas
    por una que no le corresponde.

    El valor sigue siendo el RECUENTO de checks encendidos, no un porcentaje
    reescalado: escalar 2/5 a 2,4/6 inventaría precisión que no hay. Lo que se
    publica junto al número es cuántos se pudieron mirar, y por eso el mínimo de
    `MIN_C_SCORE_CHECKS` es una guarda y no un detalle.
    """
    dso_now = _ratio(current.receivables, current.revenue)
    dso_before = _ratio(previous.receivables, previous.revenue)
    dio_now = _ratio(current.inventory, current.cogs)
    dio_before = _ratio(previous.inventory, previous.cogs)
    other_now = _other_current_assets_over_revenue(current)
    other_before = _other_current_assets_over_revenue(previous)
    depi = _quotient(_depreciation_rate(previous), _depreciation_rate(current))
    assets_growth = (
        (current.total_assets - previous.total_assets) / previous.total_assets
        if current.total_assets is not None
        and previous.total_assets is not None
        and previous.total_assets != ZERO
        else None
    )

    checks: dict[str, bool | None] = {
        "C1_beneficio_por_delante_de_caja": (
            current.net_income > current.cfo
            if current.net_income is not None and current.cfo is not None
            else None
        ),
        "C2_dias_de_cobro_suben": (
            dso_now > dso_before if dso_now is not None and dso_before is not None else None
        ),
        "C3_dias_de_inventario_suben": (
            dio_now > dio_before if dio_now is not None and dio_before is not None else None
        ),
        "C4_otros_activos_corrientes_suben": (
            other_now > other_before if other_now is not None and other_before is not None else None
        ),
        "C5_amortiza_mas_despacio": depi < Decimal(1) if depi is not None else None,
        "C6_activo_crece_mas_del_10": (
            assets_growth > Decimal("0.10") if assets_growth is not None else None
        ),
    }
    applicable = {name: value for name, value in checks.items() if name not in inapplicable_checks}
    missing = [name for name, value in applicable.items() if value is None]
    if missing:
        return (
            _not_computable(f"no se pueden evaluar los checks {', '.join(missing)} del C-Score"),
            {},
        )
    if len(applicable) < MIN_C_SCORE_CHECKS:
        return (
            _not_computable(
                f"sólo {len(applicable)} de los 6 checks del C-Score aplican a este sector: "
                f"por debajo de {MIN_C_SCORE_CHECKS} el recuento no significa lo que dice su banda"
            ),
            {},
        )
    resolved = {name: value for name, value in applicable.items() if value is not None}
    return (
        Amount(
            value=Decimal(sum(1 for hit in resolved.values() if hit)), provenance=Provenance.DERIVED
        ),
        resolved,
    )


# ── Scores de un solo ratio ───────────────────────────────────────────


def compute_accruals(series: StatementSeries, statement: CanonicalStatement) -> Amount:
    """Sloan: `(net_income − cfo) / total_assets_avg`, en valor absoluto.

    El signo se pierde a propósito para bandear: un accrual muy NEGATIVO (caja
    muy por delante del beneficio) también es una anomalía que merece mirarse.
    El signo original queda en el desglose.
    """
    gap = subtract(sourced(statement, "net_income"), sourced(statement, "cfo"))
    ratio = divide(
        gap,
        avg_balance(series, "total_assets", statement.fiscal_year),
        denominator_label="activo total medio",
    )
    if ratio.value is None:
        return ratio
    return Amount(
        value=abs(ratio.value),
        provenance=ratio.provenance,
        status=ratio.status,
        reason=ratio.reason,
    )


def compute_goodwill_risk(statement: CanonicalStatement) -> Amount:
    """F5: fondo de comercio / activo total."""
    return divide(
        sourced(statement, "goodwill"),
        sourced(statement, "total_assets"),
        denominator_label="activo total",
        require_positive_denominator=True,
    )


def compute_working_capital_anomaly(
    current: CanonicalStatement, previous: CanonicalStatement
) -> Amount:
    """F6: |Δcirculante operativo| − Δventas, en tanto por uno.

    Si el circulante operativo se mueve mucho más que las ventas, el devengo se
    está acumulando en algún sitio — y F6 dice en qué año mirar.
    """
    wc_now = dv.wc_operating(current).value
    wc_before = dv.wc_operating(previous).value
    revenue_now = current.revenue
    revenue_before = previous.revenue
    if wc_now is None or wc_before is None:
        return _not_computable("no se puede calcular el circulante operativo de ambos años")
    if revenue_now is None or revenue_before is None or revenue_before == ZERO:
        return _not_computable("no hay ventas comparables entre los dos ejercicios")
    if wc_before == ZERO:
        return _not_computable("el circulante operativo del ejercicio anterior es cero")
    wc_growth = abs((wc_now - wc_before) / abs(wc_before))
    revenue_growth = (revenue_now - revenue_before) / abs(revenue_before)
    return Amount(value=wc_growth - revenue_growth, provenance=Provenance.DERIVED)


def compute_zmijewski(series: StatementSeries, statement: CanonicalStatement) -> Amount:
    """FZ: `X = −4,336 − 4,513·ROA + 5,679·apalancamiento + 0,004·liquidez`.

    Se devuelve X (Decimal exacto). La probabilidad `P = Φ(X)` es de
    presentación; los cortes de la banda son los cuantiles normales de P=15% y
    P=40%, así que bandear X equivale exactamente a bandear P sin salir de
    Decimal (ver `ZMIJEWSKI_P_CUTOFFS`).
    """
    roa = _ratio(statement.net_income, statement.total_assets)
    leverage = _ratio(statement.total_liabilities, statement.total_assets)
    liquidity = _ratio(statement.current_assets, statement.current_liabilities)
    missing = [
        name
        for name, value in (("ROA", roa), ("apalancamiento", leverage), ("liquidez", liquidity))
        if value is None
    ]
    if missing:
        return _not_computable(
            f"no se pueden calcular las variables {', '.join(missing)} del X-Score"
        )
    assert roa is not None and leverage is not None and liquidity is not None
    score = (
        Decimal("-4.336")
        - Decimal("4.513") * roa
        + Decimal("5.679") * leverage
        + Decimal("0.004") * liquidity
    )
    return Amount(value=score, provenance=Provenance.DERIVED)


# ── Orquestación de la capa ───────────────────────────────────────────


def compute(
    series: StatementSeries,
    thresholds: Mapping[str, ThresholdSpec] | None = None,
) -> ForensicResult:
    """Calcula la capa 2 para todos los ejercicios con t−1 disponible.

    En financieras devuelve las 8 claves como `not_computable` con la razón
    reglamentaria — nunca las omite (ARCHITECTURE §4.2).
    """
    specs = DEFAULT_THRESHOLDS if thresholds is None else thresholds
    # El check de inventario del C-Score no se plantea en un sector que no tiene
    # inventario. Sin esto, su `None` tumbaba el score entero y la empresa perdía
    # cinco comprobaciones buenas por una que no le corresponde (PHASE-44.21).
    inapplicable_c_checks = (
        frozenset({C_SCORE_INVENTORY_CHECK})
        if series.security.sector in NO_MATERIAL_INVENTORY
        else frozenset()
    )
    metrics: list[MetricResult] = []
    breakdowns: list[ScoreBreakdown] = []
    flags: list[Flag] = []

    if series.security.is_financial:
        excluded = _not_computable(NOT_APPLICABLE_TO_FINANCIALS)
        for statement in series.statements:
            metrics.extend(
                to_metric_result(key, statement.fiscal_year, excluded, specs) for key in METRIC_KEYS
            )
        return ForensicResult(metrics=tuple(metrics))

    if series.security.is_reit:
        flags.append(
            Flag(
                key="z_score_uncalibrated_for_reit",
                severity="amber",
                message=(
                    "El modelo de insolvencia (Z'') no está calibrado para socimis: "
                    "su balance es intensivo en inmuebles y el score sale sesgado. "
                    "Léelo como orientación, no como veredicto."
                ),
                evidence={"model_variant": "uncalibrated"},
            )
        )

    for statement in series.statements:
        year = statement.fiscal_year
        previous = series.prior(year)

        # ── Scores que solo necesitan el ejercicio corriente ──
        z_amount, z_variables = compute_z_score(statement)
        metrics.append(to_metric_result("z_score", year, z_amount, specs))
        if z_variables:
            breakdowns.append(
                ScoreBreakdown(key="z_score", fiscal_year=year, components=z_variables, checks={})
            )
        metrics.append(to_metric_result("F5", year, compute_goodwill_risk(statement), specs))
        metrics.append(
            to_metric_result("accruals", year, compute_accruals(series, statement), specs)
        )
        metrics.append(to_metric_result("FZ", year, compute_zmijewski(series, statement), specs))

        # ── Scores que exigen t−1 ──
        if previous is None:
            reason = f"sin ejercicio {year - 1} no hay variación interanual que comparar"
            metrics.extend(
                to_metric_result(key, year, _not_computable(reason), specs)
                for key in ("m_score", "f_score", "F6", "F7")
            )
            continue

        m_amount, m_variables = compute_m_score(statement, previous)
        metrics.append(to_metric_result("m_score", year, m_amount, specs))
        if m_variables:
            breakdowns.append(
                ScoreBreakdown(key="m_score", fiscal_year=year, components=m_variables, checks={})
            )

        f_amount, f_tests = compute_f_score(statement, previous)
        metrics.append(to_metric_result("f_score", year, f_amount, specs))
        if f_tests:
            breakdowns.append(
                ScoreBreakdown(key="f_score", fiscal_year=year, components={}, checks=f_tests)
            )

        metrics.append(
            to_metric_result(
                "F6", year, compute_working_capital_anomaly(statement, previous), specs
            )
        )

        c_amount, c_checks = compute_c_score(
            statement, previous, inapplicable_checks=inapplicable_c_checks
        )
        metrics.append(to_metric_result("F7", year, c_amount, specs))
        if c_checks:
            breakdowns.append(
                ScoreBreakdown(key="F7", fiscal_year=year, components={}, checks=c_checks)
            )

    return ForensicResult(metrics=tuple(metrics), breakdowns=tuple(breakdowns), flags=tuple(flags))
