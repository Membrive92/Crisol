"""Capa 1 — métricas base (PHASE-44.2, DESIGN §5).

33 métricas en cuatro familias: liquidez (L), actividad (A), solvencia (S) y
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
from dataclasses import dataclass, replace
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
    MetricUnit,
    thresholds_from,
    to_metric_result,
)
from app.modules.investment.analysis.engine.types import (
    Amount,
    Band,
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
    MetricDefinition(
        "L1", "Ratio corriente", "liquidez", MetricUnit.TIMES, _HIGHER, _d("1.0"), _d("1.5")
    ),
    MetricDefinition(
        "L2", "Prueba ácida", "liquidez", MetricUnit.TIMES, _HIGHER, _d("0.7"), _d("1.0")
    ),
    MetricDefinition(
        "L3", "Ratio de caja", "liquidez", MetricUnit.TIMES, _HIGHER, _d("0.15"), _d("0.3")
    ),
    MetricDefinition(
        "L4",
        "Muro de vencimientos",
        "liquidez",
        MetricUnit.TIMES,
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
    MetricDefinition("A1", "Días de cobro (DSO)", "actividad", MetricUnit.DAYS),
    MetricDefinition("A2", "Días de inventario (DIO)", "actividad", MetricUnit.DAYS),
    MetricDefinition("A3", "Días de pago (DPO)", "actividad", MetricUnit.DAYS),
    MetricDefinition("A4", "Rotación de activos", "actividad", MetricUnit.TIMES),
    MetricDefinition(
        "A5",
        "Ciclo de conversión de caja",
        "actividad",
        MetricUnit.DAYS,
        note="Su deriva (>15 días vs mediana de 3 años) se evalúa en la capa 1.5.",
    ),
    # ── Solvencia ─────────────────────────────────────────────────
    MetricDefinition(
        "S1",
        "Apalancamiento",
        "solvencia",
        MetricUnit.PERCENT,
        _LOWER,
        high_ok=_d("0.6"),
        high_alarm=_d("0.75"),
        note=(
            "Pasivo total sobre activo total. NO confundir con el 'apalancamiento "
            "financiero' del análisis DuPont (activo / patrimonio), que es DUPONT_EM."
        ),
    ),
    MetricDefinition(
        "S2", "Cobertura de intereses", "solvencia", MetricUnit.TIMES, _HIGHER, _d("3"), _d("6")
    ),
    MetricDefinition(
        "S3",
        "Autonomía financiera",
        "solvencia",
        MetricUnit.PERCENT,
        _HIGHER,
        _d("0.2"),
        _d("0.35"),
    ),
    MetricDefinition(
        "S4",
        "Deuda neta / EBITDA",
        "solvencia",
        MetricUnit.TIMES,
        _LOWER,
        high_ok=_d("2"),
        high_alarm=_d("3.5"),
    ),
    MetricDefinition(
        "S4b",
        "Deuda neta / EBIT",
        "solvencia",
        MetricUnit.TIMES,
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
        MetricUnit.YEARS,
        _LOWER,
        high_ok=_d("4"),
        high_alarm=_d("8"),
        note="Años de caja libre real que costaría devolver la deuda neta.",
    ),
    MetricDefinition(
        "S6",
        "Cobertura de intereses por caja",
        "solvencia",
        MetricUnit.TIMES,
        _HIGHER,
        _d("4"),
        _d("8"),
        note=(
            "S2 usa EBIT (devengo, maquillable); esta usa caja generada. "
            "Si S2 sale verde y S6 rojo, el devengo está mintiendo."
        ),
    ),
    MetricDefinition(
        "S7",
        "Ratio de endeudamiento",
        "solvencia",
        MetricUnit.TIMES,
        ThresholdDirection.BAND,
        low_ok=_d("1"),
        high_ok=_d("2"),
        high_alarm=_d("3"),
        note=(
            "Pasivo total sobre patrimonio neto. Banda central 1-2: por debajo de 1 "
            "sale ÁMBAR, no rojo — poca deuda no es un riesgo, sólo puede ser "
            "capital ocioso. El corte rojo (3) es la traducción exacta del de S1 "
            "(pasivo/activo 0,75), para que las dos métricas no se contradigan. "
            "Calibrado para negocios con activo tangible: en bancos, aseguradoras "
            "e intensivas en intangibles este rango se queda corto, y por eso en "
            "financieras se siembra sin aplicar."
        ),
    ),
    MetricDefinition(
        "S8",
        "Calidad de la deuda",
        "solvencia",
        MetricUnit.PERCENT,
        _LOWER,
        high_ok=_d("0.40"),
        high_alarm=_d("0.80"),
        note=(
            "Qué parte de la deuda vence en menos de doce meses. Cuanto más alta, "
            "más depende la empresa de poder refinanciar; complementa a L4, que "
            "mira si tiene con qué pagarla."
        ),
    ),
    # ── Rentabilidad ──────────────────────────────────────────────
    MetricDefinition("R1", "Margen bruto", "rentabilidad", MetricUnit.PERCENT),
    MetricDefinition("R2", "Margen EBITDA", "rentabilidad", MetricUnit.PERCENT),
    MetricDefinition("R3", "Margen EBIT", "rentabilidad", MetricUnit.PERCENT),
    MetricDefinition("R4", "Margen neto", "rentabilidad", MetricUnit.PERCENT),
    MetricDefinition(
        "R5", "ROE", "rentabilidad", MetricUnit.PERCENT, _HIGHER, _d("0.08"), _d("0.12")
    ),
    MetricDefinition(
        "R6", "ROA", "rentabilidad", MetricUnit.PERCENT, _HIGHER, _d("0.02"), _d("0.05")
    ),
    MetricDefinition(
        "R7",
        "Margen FCF",
        "rentabilidad",
        MetricUnit.PERCENT,
        _HIGHER,
        _d("0.03"),
        _d("0.08"),
        note="Cuánta venta acaba siendo caja libre; su estabilidad es proxy de foso.",
    ),
    MetricDefinition(
        "R8",
        "FCF por acción",
        "rentabilidad",
        MetricUnit.CURRENCY_PER_SHARE,
        note=(
            "Sin banda: es serie. Contrapartida por acción de la dilución — el FCF total "
            "puede crecer mientras el FCF por acción cae."
        ),
    ),
    MetricDefinition(
        "R9",
        "ROIC",
        "rentabilidad",
        MetricUnit.PERCENT,
        _HIGHER,
        _d("0.06"),
        _d("0.10"),
        note="La métrica de creación de valor: separa negocio de apalancamiento (vs ROE).",
    ),
    MetricDefinition(
        "R9b",
        "CROIC",
        "rentabilidad",
        MetricUnit.PERCENT,
        _HIGHER,
        _d("0.04"),
        _d("0.08"),
        note="El ROIC medido en caja: si R9 sale verde y R9b rojo, el retorno es contable.",
    ),
    MetricDefinition(
        "R10",
        "Rentabilidad bruta sobre activos",
        "rentabilidad",
        MetricUnit.PERCENT,
        _HIGHER,
        _d("0.18"),
        _d("0.33"),
        note=(
            "Novy-Marx: el factor de calidad con mejor respaldo empírico. Margen bruto por "
            "unidad de activo, difícil de manipular por estar arriba de la cascada contable."
        ),
    ),
    MetricDefinition(
        "DUPONT_EM",
        "Apalancamiento financiero",
        "rentabilidad",
        MetricUnit.TIMES,
        note=(
            "Activo total medio / patrimonio medio: el tercer factor de DuPont. Se calculaba "
            "desde PHASE-44.2 pero vivía FUERA del catálogo, así que viajaba sin etiqueta ni "
            "unidad y el cliente tenía que inventárselas (PHASE-44.9). Sin banda: el nivel "
            "sano depende del sector — un banco vive en 10× sin patología."
        ),
    ),
    # ── Factores del DuPont extendido (PHASE-44.10) ───────────────
    # Los tres van SIN banda a propósito: son piezas de una identidad
    # aritmética, no ratios de salud. Un efecto fiscal de 0,75 no es bueno ni
    # malo. Como efecto secundario deseable, al no llevar banda no siembran
    # ninguna fila en `scoring_thresholds` y el `thresholds_version` de los runs
    # no se mueve por su culpa.
    MetricDefinition(
        "DUPONT_OM",
        "Margen operativo (DuPont)",
        "rentabilidad",
        MetricUnit.PERCENT,
        note=(
            "EBIT REPORTADO sobre ventas. No confundir con R3, que usa el EBIT limpio de "
            "deterioros y plusvalías: aquí hace falta el reportado para que la identidad de "
            "cinco factores CIERRE. Con el limpio en este factor y el reportado en el coste "
            "financiero, el EBIT no se cancela y la comprobación saldría distinta de cero "
            "justo en los años con deterioros — inflando el ROE reconstruido."
        ),
    ),
    MetricDefinition(
        "DUPONT_TAX",
        "Efecto fiscal",
        "rentabilidad",
        MetricUnit.PERCENT,
        note=(
            "Resultado neto sobre resultado antes de impuestos: qué fracción del beneficio "
            "sobrevive a Hacienda. Un valor que sube de forma sostenida puede ser eficiencia "
            "fiscal real o el aviso que da el cuaderno — mejorar el beneficio por acción "
            "pagando menos impuestos no es mejorar el negocio."
        ),
    ),
    MetricDefinition(
        "DUPONT_FIN",
        "Coste financiero",
        "rentabilidad",
        MetricUnit.PERCENT,
        note=(
            "Resultado antes de impuestos sobre EBIT reportado: qué fracción del resultado "
            "operativo sobrevive a los gastos financieros. Es el complementario del límite "
            "que pide el cuaderno (que los intereses no se coman más del 20% del EBIT, o "
            "sea que este factor no baje de 0,80)."
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
    """Las dos descomposiciones del ROE, de 3 y de 5 factores.

    Explicativa, sin banda propia: dice QUÉ movió el ROE. Un ROE que sube solo
    por el multiplicador no es mejora del negocio, es deuda.

    - **3 factores**: `margen neto × rotación × apalancamiento`.
    - **5 factores** (PHASE-44.10): `margen operativo × efecto fiscal × coste
      financiero × rotación × apalancamiento`. Desdobla el margen neto en de
      dónde sale: cuánto gana el negocio, cuánto se lleva la financiación y
      cuánto Hacienda.

    Las dos comparten rotación y apalancamiento, así que se emiten juntas.
    """

    fiscal_year: int
    net_margin: MetricResult
    asset_turnover: MetricResult
    equity_multiplier: MetricResult
    operating_margin: MetricResult
    tax_effect: MetricResult
    financial_cost: MetricResult
    check_three: Decimal | None = None
    """`(margen × rotación × apalancamiento) − ROE`. Debe ser 0.

    `None` significa **no verificable** —falta algún factor o el propio ROE—, que
    NO es lo mismo que verificado: un cuadre que no se ha podido comprobar jamás
    se presenta como superado (misma regla que el cuadre de balance en la
    ingesta, PHASE-44.6)."""
    check_five: Decimal | None = None
    """`(margen op. × efecto fiscal × coste financiero × rotación ×
    apalancamiento) − ROE`. Debe ser 0."""


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


#: Métricas de esta capa cuyos CORTES no están calibrados para una financiera
#: (PHASE-44.18). No es lo mismo que «no se puede calcular»: el número sale
#: igual, pero sin semáforo, porque la vara no sirve.
#:
#: `S7` (pasivo / patrimonio) está calibrada para negocios con activo tangible:
#: la banda 1-2 sale de que el pasivo financie entre la mitad y dos tercios del
#: activo. En un banco el apalancamiento ES el negocio y un 10× es normal, así
#: que aplicarle ese corte pintaría un rojo permanente que no informa de nada.
#:
#: **Vive en el engine y no en el seed a propósito.** La misma exención estaba
#: declarada en `thresholds/seed.py` desde PHASE-44.10 y era INERTE: dependía de
#: que existiera una fila en `scoring_thresholds`, S7 nunca se sembró (el seed
#: se cierra en cuanto la tabla tiene una fila), y `ThresholdSpec.applies` vale
#: `True` por defecto. Una exención razonada, documentada y que nunca llegó a
#: ejecutarse. Aquí no puede perderse: no depende de la BD, así que una base
#: recién creada se comporta igual que una sembrada.
FINANCIAL_LEVERAGE_REASON = (
    "un pasivo del 90% del activo ES el negocio bancario, no un riesgo: la vara "
    "industrial pintaría un rojo permanente que no informa de nada"
)

NOT_CALIBRATED_FOR_FINANCIALS: Mapping[str, str] = {"S7": FINANCIAL_LEVERAGE_REASON}
"""Métricas de ESTA capa cuyos cortes no valen para una financiera, con su
motivo. El perfil sectorial completo (PHASE-44.21) vive en `sector_profiles` y
apaga muchas más; esto es el suelo que se aplica aunque nadie haya resuelto un
perfil —el camino de `thresholds=None`—, para que la exención no dependa nunca de
una fila de base de datos ni de quién llame al motor."""


def _drop_bands_for_financials(
    specs: Mapping[str, ThresholdSpec],
) -> Mapping[str, ThresholdSpec]:
    """Apaga el semáforo (no el cálculo) de las métricas sin calibrar para bancos."""
    adjusted = dict(specs)
    for key, reason in NOT_CALIBRATED_FOR_FINANCIALS.items():
        spec = adjusted.get(key)
        if spec is not None and spec.applies:
            adjusted[key] = replace(spec, applies=False, not_applicable_reason=reason)
    return adjusted


# ── Cálculo ───────────────────────────────────────────────────────────


def compute(
    series: StatementSeries,
    thresholds: Mapping[str, ThresholdSpec] | None = None,
) -> BaseRatiosResult:
    """Calcula las 33 métricas de la Capa 1 para todos los ejercicios.

    `thresholds=None` usa las bandas por defecto del catálogo (US-GAAP
    genérico). Una métrica sin umbral sale con `band=None` — que NO significa
    "sana", sino "no hay banda que aplicar".
    """
    specs = DEFAULT_THRESHOLDS if thresholds is None else thresholds
    if series.security.is_financial:
        specs = _drop_bands_for_financials(specs)
    metrics: list[MetricResult] = []
    dupont: list[DuPontDecomposition] = []
    flags: list[Flag] = []

    for statement in series.statements:
        year = statement.fiscal_year
        year_metrics = {metric.key: metric for metric in _compute_year(series, statement, specs)}
        rc1 = _negative_working_capital_rule(year_metrics)
        if rc1 is not None:
            flags.append(rc1)
        metrics.extend(year_metrics.values())

        roe = year_metrics["R5"]
        dupont.append(
            DuPontDecomposition(
                fiscal_year=year,
                net_margin=year_metrics["R4"],
                asset_turnover=year_metrics["A4"],
                equity_multiplier=year_metrics["DUPONT_EM"],
                operating_margin=year_metrics["DUPONT_OM"],
                tax_effect=year_metrics["DUPONT_TAX"],
                financial_cost=year_metrics["DUPONT_FIN"],
                check_three=_identity_check(
                    roe, year_metrics["R4"], year_metrics["A4"], year_metrics["DUPONT_EM"]
                ),
                check_five=_identity_check(
                    roe,
                    year_metrics["DUPONT_OM"],
                    year_metrics["DUPONT_TAX"],
                    year_metrics["DUPONT_FIN"],
                    year_metrics["A4"],
                    year_metrics["DUPONT_EM"],
                ),
            )
        )

        for flag in (dv.ebt_divergence_flag(statement), dv.ebt_reconstruction_flag(statement)):
            if flag is not None:
                flags.append(flag)

    flags.extend(dv.fcf_divergence_flags(series))
    return BaseRatiosResult(metrics=tuple(metrics), flags=tuple(flags), dupont=tuple(dupont))


RC1_LIQUIDITY_KEYS = ("L1", "L2")

RC1_MESSAGE = (
    "El ciclo de conversión de caja es NEGATIVO: la empresa cobra a sus clientes "
    "antes de pagar a sus proveedores, así que financia su operación con el "
    "circulante en vez de con caja parada. Es el modelo de la distribución y del "
    "gran retail — una fortaleza estructural, no un riesgo de liquidez—, y por eso "
    "un ratio corriente por debajo de 1 aquí no se pinta en rojo."
)


def _negative_working_capital_rule(year_metrics: dict[str, MetricResult]) -> Flag | None:
    """RC-1 — con circulante negativo, un rojo de liquidez corriente NO informa.

    Muta las métricas del año EN EL SITIO (el diccionario que se acaba de
    construir, antes de publicarse) para quitarles la banda roja y dejar el
    motivo en su lugar: el número sigue ahí, deja de estar en rojo, y dice por
    qué. Devuelve la bandera informativa que lo explica en el informe, o `None`
    si la regla no aplica.

    El caso: Inditex, Mercadona, cualquier supermercado. Su ratio corriente
    ronda 0,8 porque cobran al contado y pagan a 60 días — el rojo permanente
    que salía ahí es el ejemplo de manual de una alarma que se aprende a
    ignorar. Sólo degrada el ROJO: un ámbar sigue informando de la tendencia.
    """
    ccc = year_metrics.get("A5")
    if ccc is None or ccc.value is None or ccc.value >= ZERO:
        return None
    degraded = [
        key
        for key in RC1_LIQUIDITY_KEYS
        if (metric := year_metrics.get(key)) is not None and metric.band == "stressed"
    ]
    if not degraded:
        return None
    for key in degraded:
        year_metrics[key] = replace(year_metrics[key], band=None, reason=RC1_MESSAGE)
    return Flag(
        key="RC1_negative_working_capital",
        severity="info",
        message=RC1_MESSAGE,
        evidence={
            "fiscal_year": ccc.fiscal_year,
            "cash_conversion_cycle_days": str(ccc.value),
            "degraded": degraded,
        },
    )


def _identity_check(roe: MetricResult, *factors: MetricResult) -> Decimal | None:
    """`(producto de los factores) − ROE`. Cero si la identidad cierra.

    Devuelve `None` —**no verificable**— en cuanto falte un solo factor o el
    propio ROE. Un cuadre que no se ha podido comprobar nunca se reporta como
    superado: es la misma regla que aplica la ingesta al cuadre del balance
    cuando el pasivo total viene derivado (PHASE-44.6).
    """
    if roe.value is None:
        return None
    product = Decimal(1)
    for factor in factors:
        if factor.value is None:
            return None
        product *= factor.value
    return product - roe.value


def _maturity_wall(
    statement: CanonicalStatement,
    year: int,
    liquidity: Amount,
    specs: Mapping[str, ThresholdSpec],
) -> MetricResult:
    """L4 — el muro de vencimientos, con el caso «no hay muro» dicho como tal.

    Sin deuda venciendo en doce meses no hay nada que refinanciar: es el MEJOR
    resultado posible de esta métrica, no un hueco. Se publicaba como
    «denominador cero (deuda que vence en 12 meses)», que la pantalla presenta
    igual que un dato que falta — así que una empresa que lo tiene todo pagado
    perdía una señal de resiliencia por tenerlo pagado.

    Hay DOS ceros distintos, y de cuál sea depende que se pueda dar el verde:

    - **Publicado** (`sourced`): la empresa declara que no debe nada a corto.
      Comprobado → banda verde.
    - **Imputado** (`imputed_zero`): el filing no publica el concepto y la
      ingesta lo lee como cero (§4.5). Eso es una lectura del silencio, no una
      comprobación, así que sale SIN banda diciendo exactamente eso. El verde se
      gana; no se hereda de que el emisor no etiquete un concepto.

    Si la vara no aplica a este (sector × norma), tampoco se pinta verde: el
    `applies=False` manda por encima de todo lo demás.
    """
    maturities = add(
        sourced(statement, "short_term_debt"),
        sourced(statement, "ltd_current_portion"),
    )
    label = "deuda que vence en 12 meses"
    if maturities.is_missing or maturities.value != ZERO:
        return _result("L4", year, divide(liquidity, maturities, denominator_label=label), specs)

    spec = specs.get("L4")
    imputed = maturities.provenance is Provenance.IMPUTED_ZERO
    band: Band | None = None if imputed or spec is None or not spec.applies else "healthy"
    reason = (
        "el filing no publica deuda a corto plazo y la ingesta la supone cero: "
        "probablemente no haya muro que refinanciar, pero eso no se ha comprobado"
        if imputed
        else "no hay deuda venciendo en los próximos doce meses: no hay muro que refinanciar"
    )
    return MetricResult(
        key="L4",
        fiscal_year=year,
        value=None,
        status="not_applicable",
        provenance=maturities.provenance,
        reason=reason,
        band=band,
    )


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
        _maturity_wall(statement, year, add(liquid_assets, fcf), specs),
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
        metric(
            "S7",
            divide(
                sourced(statement, "total_liabilities"),
                sourced(statement, "equity"),
                denominator_label="patrimonio neto",
                # Con patrimonio negativo el cociente sale POSITIVO y parece
                # sano justo en la empresa más frágil. Misma guarda que R5.
                require_positive_denominator=True,
            ),
        ),
        metric(
            "S8",
            divide(
                add(
                    sourced(statement, "short_term_debt"),
                    sourced(statement, "ltd_current_portion"),
                ),
                dv.total_debt(statement),
                # Sin deuda no hay calidad de la deuda que medir: sale
                # `not_computable` con «denominador cero», que es la verdad.
                denominator_label="deuda total",
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
        # Tercer factor de DuPont. Se emite aquí (y no aparte, como hasta
        # PHASE-44.9) para que exista UNA sola instancia: la fila de la matriz y
        # la de la descomposición son el mismo `MetricResult`, así que no pueden
        # divergir.
        metric(
            "DUPONT_EM",
            divide(
                total_assets_avg,
                equity_avg,
                denominator_label="patrimonio medio",
                require_positive_denominator=True,
            ),
        ),
        # ── Factores 1, 2 y 3 del DuPont extendido ────────────────
        # El EBIT de DUPONT_OM y el de DUPONT_FIN tienen que ser EL MISMO para
        # que se cancelen en el producto. Se usa el REPORTADO en ambos, no
        # `ebit_clean`: con el limpio arriba y el reportado abajo la identidad
        # se infla por el factor (limpio/reportado) —exactamente el peso de los
        # deterioros— y la comprobación saldría ≠ 0 por construcción.
        metric(
            "DUPONT_OM",
            divide(
                sourced(statement, "ebit"),
                revenue,
                denominator_label="ventas",
                require_positive_denominator=True,
            ),
        ),
        metric(
            "DUPONT_TAX",
            # Sin `require_positive_denominator`: con resultado antes de
            # impuestos NEGATIVO la identidad sigue cerrando (el signo se
            # cancela contra DUPONT_FIN). El factor se vuelve difícil de leer,
            # pero bloquearlo rompería la descomposición de un año en pérdidas,
            # que es justo cuando interesa mirarla.
            divide(
                net_income,
                dv.ebt(statement),
                denominator_label="resultado antes de impuestos",
            ),
        ),
        metric(
            "DUPONT_FIN",
            divide(
                dv.ebt(statement),
                sourced(statement, "ebit"),
                denominator_label="EBIT reportado",
            ),
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
