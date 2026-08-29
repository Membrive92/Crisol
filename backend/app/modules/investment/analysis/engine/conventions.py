"""Convenciones de cálculo del engine (PHASE-44.2, DESIGN §4.5).

Reglas, todas no negociables:

- `DAY_COUNT = 365`.
- **Denominadores de balance en medias**: `avg(t, t−1)`. El primer año de la
  serie no tiene t−1 → se usa el saldo final y la métrica sale con
  `status="approximation"` [Dec.3]. **Nunca se omite en silencio**: un DSO
  calculado sobre saldo final no es comparable con uno sobre media, y callarlo
  convertiría una serie en una comparación falsa.
- `Decimal` en todo. El redondeo es cosa de la presentación, no del cálculo.
- Hueco (`None`) en cualquier input → `not_computable` con razón. Jamás 0
  implícito, jamás excepción.
- Guards explícitos de denominador: cero siempre; y no-positivo donde el ratio
  pierde sentido (equity ≤ 0, revenue ≤ 0, ebt ≤ 0).
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from app.modules.investment.analysis.engine.types import (
    Amount,
    StatementSeries,
    combine_amounts,
    item_label,
)
from app.modules.investment.fundamentals.canonical import (
    CANONICAL_BALANCE_ITEM_SET,
    CanonicalStatement,
    Provenance,
)

DAY_COUNT = Decimal(365)

STALENESS_FRESH_DAYS = 274  # ~9 meses
STALENESS_STALE_DAYS = 548  # ~18 meses
"""Cuánto puede envejecer un ejercicio antes de que compararse con él engañe.

Viven aquí y no en `synthesis` desde PHASE-44.12: los usan la síntesis (para
degradar la confianza del veredicto) y la valoración (para avisar de que un
múltiplo cruza un precio de hoy con cuentas viejas). Es la MISMA idea, así que
tiene una sola definición — y `conventions` es hoja del grafo de imports, con lo
que ambas pueden leerla sin ciclo."""

ZERO = Decimal(0)
ONE = Decimal(1)


# ── Construcción de importes ──────────────────────────────────────────


def sourced(statement: CanonicalStatement, item: str) -> Amount:
    """Una partida canónica del filing como `Amount`, con su procedencia."""
    value = statement.get(item)
    if value is None:
        return Amount.absent(item)
    return Amount(value=value, provenance=statement.provenance_of(item))


def constant(value: Decimal) -> Amount:
    """Una constante del modelo (no procede de datos: no degrada procedencia)."""
    return Amount(value=value, provenance=Provenance.SOURCED)


def derived(value: Decimal | None, *inputs: Amount, missing: str | None = None) -> Amount:
    """Un importe calculado a partir de otros. Hereda el estado combinado de sus
    inputs y marca procedencia DERIVED (o peor, si algún input es `estimated`)."""
    provenance, status, reason = combine_amounts(*inputs)
    provenance = Provenance.DERIVED if provenance is Provenance.SOURCED else provenance
    if status == "not_computable" or value is None:
        return Amount(
            value=None,
            provenance=provenance,
            status="not_computable",
            missing=missing,
            reason=reason
            or (
                f"el filing no publica {item_label(missing)}"
                if missing
                else "falta un dato de entrada"
            ),
        )
    return Amount(value=value, provenance=provenance, status=status, reason=reason)


# ── Aritmética que propaga huecos ─────────────────────────────────────


def add(*amounts: Amount) -> Amount:
    """Suma. Cualquier hueco entre los sumandos hace la suma no computable: un
    hueco NO es cero [Dec.4] y tratarlo como tal inventaría un total."""
    if not amounts:
        return constant(ZERO)
    total = ZERO
    for amount in amounts:
        if amount.value is not None:
            total += amount.value
    computed = None if any(a.is_missing for a in amounts) else total
    return derived(computed, *amounts)


def subtract(minuend: Amount, *subtrahends: Amount) -> Amount:
    """Resta encadenada: `minuend − s1 − s2 …`."""
    inputs = (minuend, *subtrahends)
    if any(a.is_missing for a in inputs):
        return derived(None, *inputs)
    assert minuend.value is not None  # garantizado por el check de arriba
    result = minuend.value
    for subtrahend in subtrahends:
        assert subtrahend.value is not None
        result -= subtrahend.value
    return derived(result, *inputs)


def multiply(*amounts: Amount) -> Amount:
    if any(a.is_missing for a in amounts):
        return derived(None, *amounts)
    product = ONE
    for amount in amounts:
        assert amount.value is not None
        product *= amount.value
    return derived(product, *amounts)


def divide(
    numerator: Amount,
    denominator: Amount,
    *,
    denominator_label: str,
    require_positive_denominator: bool = False,
) -> Amount:
    """División con las guardas del §4.5.

    `require_positive_denominator` es el guard de los ratios cuyo denominador
    pierde sentido en negativo: un ROE con patrimonio negativo sale "positivo"
    cuando la empresa pierde dinero — un número peligrosamente engañoso, así que
    se reporta como no computable con la razón, no se muestra.
    """
    inputs = (numerator, denominator)
    if any(a.is_missing for a in inputs):
        return derived(None, *inputs)
    assert numerator.value is not None and denominator.value is not None
    if denominator.value == ZERO:
        provenance, _, _ = combine_amounts(*inputs)
        return Amount(
            value=None,
            provenance=provenance,
            status="not_computable",
            reason=f"denominador cero ({denominator_label})",
        )
    if require_positive_denominator and denominator.value < ZERO:
        provenance, _, _ = combine_amounts(*inputs)
        return Amount(
            value=None,
            provenance=provenance,
            status="not_computable",
            reason=f"denominador no positivo ({denominator_label} < 0)",
        )
    return derived(numerator.value / denominator.value, *inputs)


# ── Medias de balance [Dec.3] ─────────────────────────────────────────


def avg_balance(series: StatementSeries, item: str, fiscal_year: int) -> Amount:
    """Media `(t, t−1)` de una partida de BALANCE, para usarla de denominador
    frente a una magnitud de flujo (ventas, resultado).

    Por qué: mezclar un flujo del año con un saldo puntual de fin de año sesga
    el ratio cuando el balance se mueve (una ampliación de capital en diciembre
    hunde el ROE del año sin que el negocio haya cambiado).

    Sin t−1 en la serie → saldo final + `status="approximation"` [Dec.3].
    """
    if item not in CANONICAL_BALANCE_ITEM_SET:
        raise KeyError(f"'{item}' no es una partida de balance: la media (t, t−1) no aplica")
    current = series.by_year(fiscal_year)
    if current is None:
        return Amount.absent(item, reason=f"no hay ejercicio {fiscal_year} en la serie")
    current_amount = sourced(current, item)
    if current_amount.is_missing:
        return current_amount

    previous = series.prior(fiscal_year)
    if previous is None:
        assert current_amount.value is not None
        return Amount(
            value=current_amount.value,
            provenance=current_amount.provenance,
            status="approximation",
            reason=(
                f"sin ejercicio {fiscal_year - 1} en la serie: se usa el saldo "
                f"final de {item_label(item)} en vez de la media entre los dos "
                "ejercicios"
            ),
        )
    previous_amount = sourced(previous, item)
    if previous_amount.is_missing:
        assert current_amount.value is not None
        return Amount(
            value=current_amount.value,
            provenance=current_amount.provenance,
            status="approximation",
            reason=(
                f"el filing de {fiscal_year - 1} no publica {item_label(item)}: "
                "se usa el saldo final en vez de la media entre los dos "
                "ejercicios"
            ),
        )
    assert current_amount.value is not None and previous_amount.value is not None
    mean = (current_amount.value + previous_amount.value) / Decimal(2)
    return derived(mean, current_amount, previous_amount)


def avg_derived(
    series: StatementSeries,
    fiscal_year: int,
    compute: Callable[[CanonicalStatement], Amount],
    *,
    label: str,
) -> Amount:
    """Media `(t, t−1)` de una magnitud de balance DERIVADA (capital invertido…).

    Misma convención que `avg_balance` [Dec.3], pero sobre algo que no es una
    partida canónica y por tanto hay que recalcular en cada ejercicio.
    """
    current = series.by_year(fiscal_year)
    if current is None:
        return Amount.absent(label, reason=f"no hay ejercicio {fiscal_year} en la serie")
    current_amount = compute(current)
    if current_amount.is_missing:
        return current_amount

    previous = series.prior(fiscal_year)
    previous_amount = compute(previous) if previous is not None else None
    if previous_amount is None or previous_amount.is_missing:
        assert current_amount.value is not None
        missing_reason = (
            f"sin ejercicio {fiscal_year - 1} en la serie"
            if previous is None
            else f"no se puede calcular {label} en {fiscal_year - 1}"
        )
        return Amount(
            value=current_amount.value,
            provenance=current_amount.provenance,
            status="approximation",
            reason=(f"{missing_reason}: se usa {label} a cierre en vez de la media (t, t−1)"),
        )
    assert current_amount.value is not None and previous_amount.value is not None
    mean = (current_amount.value + previous_amount.value) / Decimal(2)
    return derived(mean, current_amount, previous_amount)


# ── Estadística de serie (compartida entre capas) ─────────────────────


def median(values: list[Decimal]) -> Decimal:
    """Mediana de una serie. Asume ≥1 valor (el llamador decide el mínimo)."""
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal(2)


def population_stdev(values: list[Decimal]) -> Decimal:
    """Desviación típica POBLACIONAL (÷N) de una serie de valores.

    Poblacional y no muestral (÷N−1): la serie NO es una muestra de una
    población mayor, son TODOS los ejercicios de los que hay datos. Con 3-5
    puntos la diferencia es visible, así que la elección importa.

    Asume ≥1 valor; el mínimo de puntos "con sentido" (p. ej. E3 exige 3) lo
    decide cada llamador, no esta primitiva.
    """
    count = Decimal(len(values))
    mean = sum(values, ZERO) / count
    variance = sum(((v - mean) ** 2 for v in values), ZERO) / count
    return variance.sqrt()


def cagr(
    first: Decimal | None, last: Decimal | None, periods: int
) -> tuple[Decimal | None, str | None]:
    """Tasa compuesta anual entre el primer y el último valor de una serie.

    Solo existe con extremos positivos: con un extremo ≤ 0 la raíz n-ésima del
    cociente no está definida en reales (o cambia de sentido). Devuelve
    `(None, razón)` en ese caso — nunca un número inventado.
    """
    if first is None or last is None:
        return None, "faltan los extremos de la serie"
    if periods < 1:
        return None, "hacen falta al menos dos ejercicios"
    if first <= ZERO or last <= ZERO:
        return None, (
            "la tasa compuesta no está definida con un extremo negativo o cero "
            "(cambio de signo en la serie)"
        )
    growth = ((last / first).ln() / Decimal(periods)).exp() - ONE
    return growth, None
