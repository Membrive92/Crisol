"""Infraestructura de catálogo de métricas (PHASE-44.3).

Extraído de `base_ratios` cuando entraron las capas 1.5 y 2: las tres declaran
sus métricas igual, y el seed de `scoring_thresholds` necesita UNA lista con
todas. Aquí viven la definición estática (`MetricDefinition`) y el ensamblado
`Amount → MetricResult`; cada capa aporta su propio catálogo y `catalog.py` los
agrega.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.modules.investment.analysis.engine.types import (
    Amount,
    MetricResult,
    ThresholdSpec,
)
from app.modules.investment.enums import ThresholdDirection


class MetricUnit(enum.StrEnum):
    """Escala en la que se lee el valor de una métrica (PHASE-44.9).

    Vive en el engine y NO se persiste: es la unidad de la fórmula, no un dato
    del usuario. Existe porque 51 métricas heterogéneas viajaban como números
    desnudos y el cliente no podía saber si un `0,42` era 42 %, 0,42 veces o 42
    días — así que la web imprimía márgenes como `0,42`.

    Es campo OBLIGATORIO de `MetricDefinition` a propósito: con default, añadir
    una métrica sin pensar la unidad la etiquetaría mal en silencio.
    """

    PERCENT = "percent"
    """Tanto por uno que se presenta como porcentaje (márgenes, payouts, ROE)."""
    TIMES = "times"
    """Veces (×): coberturas, múltiplos de deuda, rotaciones."""
    DAYS = "days"
    """Días (los ×365 de la capa de actividad)."""
    YEARS = "years"
    """Años (repago de deuda, años de dividendo en caja)."""
    PP = "pp"
    """Puntos porcentuales — σ de un margen o de un payout. NO es un %: un
    "2 pp" es dispersión, no proporción."""
    SCORE = "score"
    """Puntuación de un modelo publicado (Beneish, Altman, Zmijewski): número
    adimensional que sólo significa algo contra sus propios cortes."""
    COUNT = "count"
    """Conteo de tests superados (F-Score 0-9, C-Score 0-6)."""
    CURRENCY_PER_SHARE = "currency_per_share"
    """Importe por acción, en la divisa del estado financiero."""


@dataclass(frozen=True)
class MetricDefinition:
    """Definición estática de una métrica: identidad + unidad + banda por defecto.

    `direction=None` significa **sin banda absoluta**: la métrica solo se juzga
    por su deriva o se muestra como serie (un DSO de 45 días es excelente en
    retail y pésimo en software; lo que informa es que suba 20 días en dos años).
    """

    key: str
    label: str
    family: str
    unit: MetricUnit
    direction: ThresholdDirection | None = None
    low_alarm: Decimal | None = None
    low_ok: Decimal | None = None
    high_ok: Decimal | None = None
    high_alarm: Decimal | None = None
    model_variant: str | None = None
    note: str = ""

    def to_threshold(self) -> ThresholdSpec | None:
        if self.direction is None:
            return None
        return ThresholdSpec(
            metric_key=self.key,
            direction=self.direction,
            low_alarm=self.low_alarm,
            low_ok=self.low_ok,
            high_ok=self.high_ok,
            high_alarm=self.high_alarm,
            model_variant=self.model_variant,
        )


def thresholds_from(catalog: Sequence[MetricDefinition]) -> dict[str, ThresholdSpec]:
    """Bandas por defecto de un catálogo (US-GAAP genérico, DESIGN §5)."""
    return {
        definition.key: spec
        for definition in catalog
        if (spec := definition.to_threshold()) is not None
    }


def to_metric_result(
    key: str,
    fiscal_year: int,
    amount: Amount,
    thresholds: Mapping[str, ThresholdSpec],
) -> MetricResult:
    """`Amount` → `MetricResult`, aplicando la banda si la métrica tiene una.

    Un `Amount` sin valor SIEMPRE produce `not_computable` con su razón: es el
    único camino por el que una métrica puede quedarse sin número, y nunca
    desaparece del informe (§4.5).
    """
    if amount.is_missing:
        return MetricResult(
            key=key,
            fiscal_year=fiscal_year,
            value=None,
            status="not_computable",
            provenance=amount.provenance,
            reason=amount.reason or "input ausente",
        )
    spec = thresholds.get(key)
    return MetricResult(
        key=key,
        fiscal_year=fiscal_year,
        value=amount.value,
        status=amount.status,
        provenance=amount.provenance,
        reason=amount.reason,
        band=spec.band_for(amount.value) if spec is not None else None,
    )
