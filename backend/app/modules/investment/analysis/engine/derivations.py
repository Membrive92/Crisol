"""Derivaciones canónicas (PHASE-44.2, DESIGN §4.4).

Magnitudes que NO vienen del filing pero se calculan con una regla explícita y
estable. Cada función devuelve un `Amount` con procedencia `derived` y propaga
los huecos: si falta un input, la derivada es `not_computable` con la razón —
nunca un total inventado tratando el hueco como cero [Dec.4].

Cada función cita en su docstring la fila del DESIGN §4.4 que implementa. No
inventar derivadas fuera de esa tabla (ARCHITECTURE §4.2).
"""

from __future__ import annotations

import itertools
from decimal import Decimal

from app.modules.investment.analysis.engine.conventions import (
    ONE,
    ZERO,
    add,
    constant,
    derived,
    divide,
    multiply,
    sourced,
    subtract,
)
from app.modules.investment.analysis.engine.types import Amount, Flag, StatementSeries
from app.modules.investment.fundamentals.canonical import CanonicalStatement, Provenance

EBT_DIVERGENCE_TOLERANCE = Decimal("0.02")
"""[Dec.2] Divergencia relativa a partir de la cual el EBT reconstruido se
considera sospechoso de tener partidas no modeladas."""

FCF_DIVERGENCE_TOLERANCE = Decimal("0.15")
"""Divergencia relativa entre `fcf_cfo` y `fcf_ebitda` que, SOSTENIDA 2 años,
levanta bandera ámbar (ARCHITECTURE §4.2)."""


# ── Deuda y caja ──────────────────────────────────────────────────────


def total_debt(statement: CanonicalStatement) -> Amount:
    """`short_term_debt + ltd_current_portion + long_term_debt`.

    **Sin leases** por defecto: desde IFRS16/ASC842 los arrendamientos van al
    balance, y meterlos aquí rompería la comparación con series anteriores a la
    norma. La variante con leases se expone aparte.
    """
    return add(
        sourced(statement, "short_term_debt"),
        sourced(statement, "ltd_current_portion"),
        sourced(statement, "long_term_debt"),
    )


def total_debt_incl_leases(statement: CanonicalStatement) -> Amount:
    """`total_debt + lease_liabilities_current + lease_liabilities_noncurrent`.

    Variante para comparabilidad IFRS16/ASC842. Ambas se exponen: cuál es la
    "buena" depende de si el arrendamiento es operativo del negocio o
    financiación encubierta, y eso lo juzga el usuario, no el engine.
    """
    return add(
        total_debt(statement),
        sourced(statement, "lease_liabilities_current"),
        sourced(statement, "lease_liabilities_noncurrent"),
    )


def net_debt(statement: CanonicalStatement) -> Amount:
    """`total_debt − cash − current_financial_assets`."""
    return subtract(
        total_debt(statement),
        sourced(statement, "cash"),
        sourced(statement, "current_financial_assets"),
    )


# ── Resultado ─────────────────────────────────────────────────────────


def ebitda(statement: CanonicalStatement) -> Amount:
    """`ebit + depreciation_amortization`."""
    return add(sourced(statement, "ebit"), sourced(statement, "depreciation_amortization"))


def ebit_clean(statement: CanonicalStatement) -> Amount:
    """`ebit + impairments − gains_on_sale_of_business` [Dec.5].

    Base de márgenes y coberturas "limpias". Un deterioro de goodwill o una
    plusvalía por venta de negocio son sucesos de una vez que distorsionan el
    EBIT del año y, en cascada, todo lo que cuelga de él. El EBIT reportado se
    muestra al lado, no se sustituye.
    """
    return subtract(
        add(sourced(statement, "ebit"), sourced(statement, "impairments")),
        sourced(statement, "gains_on_sale_of_business"),
    )


def ebt(statement: CanonicalStatement) -> Amount:
    """Resultado antes de impuestos.

    Prefiere el `pretax_income` REPORTADO (partida 49, PHASE-44.6) y solo si
    falta cae a la reconstrucción `net_income + taxes` [Dec.2]. El orden importa:
    la reconstrucción parte del resultado ATRIBUIBLE A LA MATRIZ, así que se deja
    fuera los minoritarios y las actividades discontinuadas — en Realty Income,
    11,2 M$ de diferencia sobre el pretax publicado.
    """
    reported = sourced(statement, "pretax_income")
    if not reported.is_missing:
        return reported
    return add(sourced(statement, "net_income"), sourced(statement, "taxes"))


def ebt_reconstruction_flag(statement: CanonicalStatement) -> Flag | None:
    """Bandera si el pretax reportado se aparta >2% de `net_income + taxes`.

    Compara dos fuentes INDEPENDIENTES del mismo número, así que solo tiene
    sentido cuando ambas existen. Lo que delata la diferencia es lo que vive
    entre el pretax y el resultado neto: minoritarios y actividades
    discontinuadas. Severidad `info` — habla de la COMPLETITUD DEL MAPEO, no de
    la salud del negocio.
    """
    reported = sourced(statement, "pretax_income")
    rebuilt = add(sourced(statement, "net_income"), sourced(statement, "taxes"))
    if reported.is_missing or rebuilt.is_missing:
        return None
    assert reported.value is not None and rebuilt.value is not None
    if reported.value == ZERO:
        return None
    divergence = abs(reported.value - rebuilt.value) / abs(reported.value)
    if divergence <= EBT_DIVERGENCE_TOLERANCE:
        return None
    return Flag(
        key="ebt_reconstruction_divergence",
        severity="info",
        message=(
            f"El resultado antes de impuestos publicado ({reported.value:,.0f}) se aparta un "
            f"{divergence:.1%} de resultado neto + impuestos ({rebuilt.value:,.0f}) en "
            f"{statement.fiscal_year}: por debajo del pretax hay partidas que el modelo no "
            "recoge (minoritarios o actividades discontinuadas)."
        ),
        evidence={
            "fiscal_year": statement.fiscal_year,
            "pretax_reported": str(reported.value),
            "net_income_plus_taxes": str(rebuilt.value),
            "divergence": str(divergence),
        },
    )


def ebt_divergence_flag(statement: CanonicalStatement) -> Flag | None:
    """Bandera si el EBT diverge >2% de `ebit − interest_expense`.

    Delata partidas no modeladas en el canónico (resultado financiero que no es
    interés, puesta en equivalencia, minoritarios). Severidad `info`: es una
    señal sobre la CALIDAD DE LOS DATOS, no sobre la salud de la empresa — el
    DESIGN §4.4 pide "flag" sin fijar severidad, y mezclarla con las alarmas de
    negocio del informe daría una alarma roja por un mapeo incompleto.

    Guarda de PHASE-44.6: si el `ebit` no es SOURCED, la ingesta lo derivó como
    `ebt + interest_expense` y entonces `ebit − interest_expense ≡ ebt` por
    construcción. Comparar sería tautológico, y una bandera que jamás puede
    dispararse es peor que ninguna: parece una comprobación superada. No se
    evalúa.
    """
    if statement.provenance_of("ebit") is not Provenance.SOURCED:
        return None
    reconstructed = ebt(statement)
    operating = subtract(sourced(statement, "ebit"), sourced(statement, "interest_expense"))
    if reconstructed.is_missing or operating.is_missing:
        return None
    assert reconstructed.value is not None and operating.value is not None
    if reconstructed.value == ZERO:
        return None
    divergence = abs(reconstructed.value - operating.value) / abs(reconstructed.value)
    if divergence <= EBT_DIVERGENCE_TOLERANCE:
        return None
    return Flag(
        key="ebt_divergence",
        severity="info",
        message=(
            f"El resultado antes de impuestos reconstruido ({reconstructed.value:,.0f}) se "
            f"aparta un {divergence:.1%} de EBIT − intereses ({operating.value:,.0f}) en "
            f"{statement.fiscal_year}: hay partidas que el modelo no recoge "
            "(resultado financiero no-interés, asociadas o minoritarios)."
        ),
        evidence={
            "fiscal_year": statement.fiscal_year,
            "ebt_reconstructed": str(reconstructed.value),
            "ebit_minus_interest": str(operating.value),
            "divergence": str(divergence),
        },
    )


def effective_tax_rate(statement: CanonicalStatement) -> Amount:
    """`taxes / ebt`. Guard: `ebt ≤ 0` → `not_computable` (§4.4).

    Con base imponible negativa el "tipo efectivo" no significa nada: un crédito
    fiscal sobre pérdidas daría un porcentaje positivo que parece un impuesto.
    """
    return divide(
        sourced(statement, "taxes"),
        ebt(statement),
        denominator_label="resultado antes de impuestos",
        require_positive_denominator=True,
    )


def nopat(statement: CanonicalStatement) -> Amount:
    """`ebit_clean × (1 − effective_tax_rate)` — resultado operativo después de
    impuestos, sin efecto del apalancamiento."""
    return multiply(
        ebit_clean(statement),
        subtract(constant(ONE), effective_tax_rate(statement)),
    )


def invested_capital(statement: CanonicalStatement) -> Amount:
    """`equity + total_debt − cash` — el capital que el negocio realmente
    emplea."""
    return subtract(
        add(sourced(statement, "equity"), total_debt(statement)),
        sourced(statement, "cash"),
    )


# ── Circulante [Dec.1] ────────────────────────────────────────────────


def wc_total(statement: CanonicalStatement) -> Amount:
    """`current_assets − current_liabilities` — fondo de maniobra TOTAL.

    Es el que pide Altman (X1). Para eficiencia operativa NO sirve: mete deuda
    financiera a corto, que no es circulante del negocio.
    """
    return subtract(
        sourced(statement, "current_assets"),
        sourced(statement, "current_liabilities"),
    )


def wc_operating(statement: CanonicalStatement) -> Amount:
    """`(receivables + inventory) − accounts_payable` — circulante OPERATIVO.

    El que refleja el ciclo del negocio, limpio de financiación [Dec.1].
    """
    return subtract(
        add(sourced(statement, "receivables"), sourced(statement, "inventory")),
        sourced(statement, "accounts_payable"),
    )


# ── Caja libre ────────────────────────────────────────────────────────


def fcf_cfo(statement: CanonicalStatement) -> Amount:
    """`cfo − capex` — caja libre. **Primaria** (D2, Q*, stress)."""
    return subtract(sourced(statement, "cfo"), sourced(statement, "capex"))


def fcf_ebitda(series: StatementSeries, fiscal_year: int) -> Amount:
    """`ebitda − capex − Δwc_operating − taxes_paid` — caja libre reconstruida
    desde el devengo, como **contraste** de `fcf_cfo`.

    Necesita t−1 para el Δ del circulante: sin ejercicio anterior no hay
    variación que calcular, y suponerla cero inventaría caja.
    """
    statement = series.by_year(fiscal_year)
    if statement is None:
        return Amount.absent("statement", reason=f"no hay ejercicio {fiscal_year} en la serie")
    previous = series.prior(fiscal_year)
    if previous is None:
        return Amount(
            value=None,
            provenance=Provenance.DERIVED,
            status="not_computable",
            reason=(
                f"sin ejercicio {fiscal_year - 1} no hay variación del circulante "
                "operativo que descontar"
            ),
        )
    delta_wc = subtract(wc_operating(statement), wc_operating(previous))
    return subtract(
        ebitda(statement),
        sourced(statement, "capex"),
        delta_wc,
        sourced(statement, "taxes_paid"),
    )


def fcf_divergence_flags(series: StatementSeries) -> tuple[Flag, ...]:
    """Bandera ámbar si `fcf_cfo` y `fcf_ebitda` divergen >15% **sostenido 2
    años** (ARCHITECTURE §4.2).

    Dos formas de medir la misma caja que no cuadran de forma persistente es
    señal de accruals agresivos o de partidas del flujo de explotación que el
    canónico no recoge. Se exige que sean dos años CONSECUTIVOS: un año suelto
    lo explica cualquier estacionalidad del circulante.
    """
    divergent_years: list[int] = []
    for statement in series.statements:
        year = statement.fiscal_year
        primary = fcf_cfo(statement)
        contrast = fcf_ebitda(series, year)
        if primary.is_missing or contrast.is_missing:
            continue
        assert primary.value is not None and contrast.value is not None
        if primary.value == ZERO:
            continue
        divergence = abs(primary.value - contrast.value) / abs(primary.value)
        if divergence > FCF_DIVERGENCE_TOLERANCE:
            divergent_years.append(year)

    flags: list[Flag] = []
    for first, second in itertools.pairwise(divergent_years):
        if second == first + 1:
            flags.append(
                Flag(
                    key="fcf_divergence",
                    severity="amber",
                    message=(
                        f"La caja libre medida desde el flujo de explotación y la reconstruida "
                        f"desde el devengo se separan más de un 15% dos años seguidos "
                        f"({first} y {second}): revisa la calidad del devengo o partidas del "
                        "flujo de explotación no recogidas."
                    ),
                    evidence={"years": [first, second]},
                )
            )
    return tuple(flags)


def maintenance_capex(statement: CanonicalStatement) -> Amount:
    """`min(capex, depreciation_amortization)` [Dec.4].

    SIEMPRE `estimated`: es un proxy: la parte del capex que solo mantiene la
    capacidad instalada no se publica. Al declararse como estimación, jamás
    cuenta como hueco de datos ni penaliza la completitud del informe.
    """
    capex = sourced(statement, "capex")
    dna = sourced(statement, "depreciation_amortization")
    if capex.is_missing or dna.is_missing:
        result = derived(None, capex, dna)
    else:
        assert capex.value is not None and dna.value is not None
        result = derived(min(capex.value, dna.value), capex, dna)
    return Amount(
        value=result.value,
        provenance=Provenance.ESTIMATED,
        status=result.status,
        missing=result.missing,
        reason=result.reason,
    )


def ffo(statement: CanonicalStatement) -> Amount:
    """`net_income + depreciation_amortization + impairments −
    gains_on_sale_of_business` — Funds From Operations.

    Solo aplica a REITs (D6): en un REIT la amortización del inmueble es un
    apunte contable que no refleja deterioro económico, así que el resultado
    neto infravalora sistemáticamente la caja. Sustituye al FCF en la capa 3.
    AFFO queda fuera de alcance.
    """
    return subtract(
        add(
            sourced(statement, "net_income"),
            sourced(statement, "depreciation_amortization"),
            sourced(statement, "impairments"),
        ),
        sourced(statement, "gains_on_sale_of_business"),
    )


def dividend_per_share(statement: CanonicalStatement) -> Amount:
    """`dividends_paid / shares_basic`."""
    return divide(
        sourced(statement, "dividends_paid"),
        sourced(statement, "shares_basic"),
        denominator_label="acciones básicas",
    )
