"""Múltiplos de valoración (PHASE-44.12) — capa PURA.

Es la única capa del engine que necesita un dato que no está en los estados
financieros: **el precio**. Por eso vive aparte y no entra en el `AnalysisRun`.

## Por qué fuera del run

El motor forense es *book-based* a propósito: un `AnalysisRun` guardado se puede
reejecutar dentro de un año y da lo mismo, porque sus entradas son cuentas
cerradas. Un múltiplo se mueve con la cotización, así que persistirlo dentro
rompería esa reproducibilidad — el mismo run daría dos veredictos distintos
según el día. La valoración se calcula al vuelo cruzando el run vigente con la
quote del momento, y la UI la presenta separada del veredicto: «¿es seguro?» y
«¿está cara?» son preguntas distintas y mezclarlas contamina la primera.

## Cómo recibe el precio

`compute_valuation` toma `price` ya **en la divisa de los estados financieros**.
La conversión, la lectura de la quote y el tipo de cambio son IO y viven en
`analysis/service.py`; aquí no se importa `pricing` ni `currency` (lo vigila
`test_el_engine_no_importa_io`). Esa frontera es la que permite probar los cinco
múltiplos con estados sintéticos y un `Decimal`.

## Política de casos límite (una sola regla por caso, para los cinco)

- **Denominador ≤ 0** → `require_positive_denominator`. Un PER con beneficio
  negativo sale "positivo" y se lee como barato; un P/VC con patrimonio negativo
  igual. No se muestra: se dice por qué no existe.
- **Numerador ≤ 0** sólo puede pasar en el valor de empresa (caja neta mayor que
  la capitalización) y se intercepta ANTES de dividir, porque `divide` no mira
  el numerador.
- **Escala de acciones**: NO se re-deriva aquí. La ingesta ya la normaliza y
  emite sus banderas; repetir el predicado sería una segunda definición que
  acabaría divergiendo.
- **Sin ejercicios** → no computable, nunca `AttributeError`.

Los acompañantes (`book_value_per_share`, `fcf_yield`) se emiten **sin** el
guard de positividad: ahí el negativo informa en vez de engañar. Un valor
contable por acción de −2,52 $ dice algo verdadero; un P/VC de −118× no.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.modules.investment.analysis.engine import derivations as dv
from app.modules.investment.analysis.engine.conventions import (
    STALENESS_FRESH_DAYS,
    STALENESS_STALE_DAYS,
    ZERO,
    add,
    constant,
    divide,
    multiply,
    sourced,
)
from app.modules.investment.analysis.engine.metrics import MetricDefinition, MetricUnit
from app.modules.investment.analysis.engine.types import (
    Amount,
    MetricResult,
    StatementSeries,
)
from app.modules.investment.fundamentals.canonical import CanonicalStatement, Provenance

#: Recuento de acciones para la capitalización.
#:
#: `shares_outstanding_eop` y no `shares_diluted`: la capitalización es un stock
#: a una fecha (precio de hoy × acciones que existen hoy), no una media del
#: ejercicio. Usar la media daría un PER un 0,85 % distinto en MCD y, peor,
#: haría que «capitalización» significara dos cosas según el múltiplo que se
#: mirara. Decisión del usuario (2026-08-06): un solo denominador para los cinco.
SHARES_ITEM = "shares_outstanding_eop"

METRIC_CATALOG: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        key="V1",
        label="PER (precio / beneficio)",
        family="valuation",
        unit=MetricUnit.TIMES,
        note="Capitalización sobre resultado neto del último ejercicio cerrado.",
    ),
    MetricDefinition(
        key="V2",
        label="Precio / ventas",
        family="valuation",
        unit=MetricUnit.TIMES,
    ),
    MetricDefinition(
        key="V3",
        label="Precio / valor contable",
        family="valuation",
        unit=MetricUnit.TIMES,
    ),
    MetricDefinition(
        key="V4",
        label="Precio / caja libre",
        family="valuation",
        unit=MetricUnit.TIMES,
    ),
    MetricDefinition(
        key="V5",
        label="Valor de empresa / EBITDA",
        family="valuation",
        unit=MetricUnit.TIMES,
        note=(
            "El valor de empresa no incluye intereses minoritarios ni acciones "
            "preferentes (no están entre las 49 partidas) mientras el EBITDA "
            "consolida el 100 %."
        ),
    ),
    MetricDefinition(
        key="V6",
        label="Valor contable por acción",
        family="valuation",
        unit=MetricUnit.CURRENCY_PER_SHARE,
        note="Se emite aunque sea negativo: ahí el signo informa.",
    ),
    MetricDefinition(
        key="V7",
        label="Rentabilidad de la caja libre",
        family="valuation",
        unit=MetricUnit.PERCENT,
        note="No es el recíproco de V4: con caja libre negativa sigue teniendo sentido.",
    ),
)
"""Ninguna lleva banda ni `direction`.

No es un olvido: sin comparables de sector, una banda sería una opinión
disfrazada de dato. Un PER de 25× es caro en una eléctrica y barato en software,
y el módulo no tiene fuente de múltiplos de comparables — se dice en el
«Alcance» del informe. Se muestra el número y su serie; el juicio lo pone quien
mira. Corolario: no se siembran en `scoring_thresholds`.
"""


@dataclass(frozen=True)
class ValuationInputs:
    """Lo que la capa impura tiene que resolver antes de llamar aquí."""

    price: Decimal
    """Cotización YA convertida a la divisa de los estados financieros."""
    quote_as_of: date
    quote_currency: str
    quote_stale: bool = False
    provider_status: str = "live"
    """`live` | `cached` | `unreachable`. Ver `pricing.service.QuoteOutcome`."""
    fx_rate: Decimal | None = None
    """Tipo aplicado si hubo conversión. `None` = no hizo falta."""
    fx_as_of: date | None = None


@dataclass(frozen=True)
class ValuationResult:
    """Los múltiplos y todo lo que hace falta para leerlos con honestidad."""

    metrics: tuple[MetricResult, ...]
    fiscal_year: int | None
    fiscal_year_end: date | None
    statement_currency: str | None
    market_cap: Decimal | None
    enterprise_value: Decimal | None
    quote_as_of: date | None
    quote_stale: bool
    provider_status: str
    fx_rate: Decimal | None
    fx_as_of: date | None
    days_since_fiscal_year_end: int | None
    """Distancia entre el precio y las cuentas con que se compara.

    Es la mitad del «doble staleness»: un PER con precio de hoy sobre un
    beneficio de hace catorce meses no es falso, pero tiene que decirlo."""
    staleness: str | None
    """`None` | `'aging'` (≥9 meses) | `'stale'` (≥18 meses)."""
    notes: tuple[str, ...]


def _not_computable(key: str, fiscal_year: int, reason: str) -> MetricResult:
    return MetricResult(
        key=key,
        fiscal_year=fiscal_year,
        value=None,
        status="not_computable",
        provenance=Provenance.DERIVED,
        reason=reason,
    )


def _as_metric(key: str, fiscal_year: int, amount: Amount) -> MetricResult:
    if amount.value is None or amount.status == "not_computable":
        return MetricResult(
            key=key,
            fiscal_year=fiscal_year,
            value=None,
            status="not_computable",
            provenance=amount.provenance,
            reason=amount.reason,
        )
    return MetricResult(
        key=key,
        fiscal_year=fiscal_year,
        value=amount.value,
        status=amount.status,
        provenance=amount.provenance,
        reason=amount.reason,
    )


def market_cap_amount(statement: CanonicalStatement, price: Decimal) -> Amount:
    """`precio × acciones en circulación al cierre`.

    Definición ÚNICA para los cinco múltiplos: si cada uno usara su propio
    recuento, la misma palabra significaría números distintos en la misma
    pantalla.
    """
    return multiply(constant(price), sourced(statement, SHARES_ITEM))


def _staleness(days: int | None) -> str | None:
    """Etiqueta de antigüedad del estado frente al precio.

    Los cortes se **importan** de `synthesis` en vez de copiarse: son la misma
    idea («cuánto puede envejecer un ejercicio antes de que comparar con él
    empiece a engañar») y dos copias divergirían a la primera revisión.
    """
    if days is None:
        return None
    if days >= STALENESS_STALE_DAYS:
        return "stale"
    if days >= STALENESS_FRESH_DAYS:
        return "aging"
    return None


def compute_valuation(series: StatementSeries, inputs: ValuationInputs) -> ValuationResult:
    """Los múltiplos del último ejercicio cerrado contra el precio dado.

    PURA: sin BD, sin red y sin reloj. La fecha de referencia entra por
    `inputs.quote_as_of`, no se lee del sistema — así el resultado es
    reproducible en un test.
    """
    statement = series.latest
    if statement is None:
        return ValuationResult(
            metrics=(),
            fiscal_year=None,
            fiscal_year_end=None,
            statement_currency=None,
            market_cap=None,
            enterprise_value=None,
            quote_as_of=inputs.quote_as_of,
            quote_stale=inputs.quote_stale,
            provider_status=inputs.provider_status,
            fx_rate=inputs.fx_rate,
            fx_as_of=inputs.fx_as_of,
            days_since_fiscal_year_end=None,
            staleness=None,
            notes=("No hay ningún ejercicio ingerido para este valor.",),
        )

    year = statement.fiscal_year
    notes: list[str] = []
    market_cap = market_cap_amount(statement, inputs.price)

    metrics: list[MetricResult] = []

    # ── V1-V4: capitalización sobre una magnitud del ejercicio ──────────
    for key, item_amount, label in (
        ("V1", sourced(statement, "net_income"), "resultado neto"),
        ("V2", sourced(statement, "revenue"), "ventas"),
        ("V3", sourced(statement, "equity"), "patrimonio neto"),
        ("V4", dv.fcf_cfo(statement), "caja libre"),
    ):
        metrics.append(
            _as_metric(
                key,
                year,
                divide(
                    market_cap,
                    item_amount,
                    denominator_label=label,
                    require_positive_denominator=True,
                ),
            )
        )

    # ── V5: valor de empresa sobre EBITDA ───────────────────────────────
    net_debt = dv.net_debt(statement)
    enterprise_value = add(market_cap, net_debt)
    if enterprise_value.value is not None and enterprise_value.value <= ZERO:
        # `divide` no mira el numerador, así que este caso hay que
        # interceptarlo antes: con caja neta mayor que la capitalización el
        # cociente sale negativo y se leería como "regalado".
        metrics.append(
            _not_computable(
                "V5",
                year,
                "el valor de empresa no es positivo: la caja neta supera a la "
                "capitalización, así que el múltiplo no tiene lectura",
            )
        )
    else:
        metrics.append(
            _as_metric(
                "V5",
                year,
                divide(
                    enterprise_value,
                    dv.ebitda(statement),
                    denominator_label="EBITDA",
                    require_positive_denominator=True,
                ),
            )
        )

    # ── V6-V7: acompañantes, SIN guard de positividad ───────────────────
    metrics.append(
        _as_metric(
            "V6",
            year,
            divide(
                sourced(statement, "equity"),
                sourced(statement, SHARES_ITEM),
                denominator_label="acciones al cierre",
            ),
        )
    )
    metrics.append(
        _as_metric(
            "V7",
            year,
            divide(
                dv.fcf_cfo(statement),
                market_cap,
                denominator_label="capitalización",
            ),
        )
    )

    days = (inputs.quote_as_of - statement.fiscal_year_end).days
    staleness = _staleness(days)
    if staleness == "stale":
        notes.append(
            f"Las cuentas cierran el {statement.fiscal_year_end:%d/%m/%Y} y el precio es del "
            f"{inputs.quote_as_of:%d/%m/%Y}: {days} días de diferencia. Los múltiplos comparan "
            "un precio de hoy con un negocio de hace más de año y medio."
        )
    elif staleness == "aging":
        notes.append(
            f"El último ejercicio cerró hace {days} días; el siguiente 10-K puede mover "
            "estos múltiplos de forma apreciable."
        )
    if inputs.provider_status == "unreachable":
        notes.append(
            "El proveedor de cotizaciones no ha respondido. Se está usando el último "
            f"precio registrado, del {inputs.quote_as_of:%d/%m/%Y}."
        )
    elif inputs.quote_stale:
        notes.append(
            "La cotización no se ha podido refrescar: es la última guardada, "
            f"del {inputs.quote_as_of:%d/%m/%Y}."
        )
    if series.security.is_financial:
        notes.append(
            "En una financiera «ventas» es margen bruto por intereses y comisiones, "
            "así que el precio/ventas no es comparable con el de una empresa industrial."
        )

    return ValuationResult(
        metrics=tuple(metrics),
        fiscal_year=year,
        fiscal_year_end=statement.fiscal_year_end,
        statement_currency=statement.currency,
        market_cap=market_cap.value,
        enterprise_value=enterprise_value.value,
        quote_as_of=inputs.quote_as_of,
        quote_stale=inputs.quote_stale,
        provider_status=inputs.provider_status,
        fx_rate=inputs.fx_rate,
        fx_as_of=inputs.fx_as_of,
        days_since_fiscal_year_end=days,
        staleness=staleness,
        notes=tuple(notes),
    )
