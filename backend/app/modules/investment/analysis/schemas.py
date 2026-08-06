"""Schemas Pydantic de análisis (PHASE-44.7)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.modules.investment.analysis.engine.metrics import MetricUnit
from app.modules.investment.enums import ThresholdDirection


class MetricDefinitionResponse(BaseModel):
    """Una entrada del catálogo de métricas del engine (PHASE-44.9).

    Existe porque hasta ahora el catálogo NO viajaba: el cliente tenía que
    escribir a mano la etiqueta de cada métrica, y tres de ellas acabaron
    mintiendo sobre el número que enseñaban (F5 se pintaba como «deuda
    emergente» siendo riesgo de fondo de comercio; D8 como «rentabilidad por
    dividendo» siendo margen de seguridad). Con el catálogo servido, la etiqueta
    tiene UNA sola fuente y no puede divergir.
    """

    model_config = {"from_attributes": True}

    key: str
    label: str
    family: str
    unit: MetricUnit
    """Escala de lectura: sin ella un `0,42` es indistinguible entre 42 %,
    0,42 veces y 42 días."""
    direction: ThresholdDirection | None
    """`None` = **sin banda absoluta**. NO significa «sana»: significa que no hay
    corte global que aplicar (un DSO de 45 días es excelente en retail y pésimo
    en software)."""
    low_alarm: Decimal | None
    low_ok: Decimal | None
    high_ok: Decimal | None
    high_alarm: Decimal | None
    model_variant: str | None
    note: str


class MetricCatalogResponse(BaseModel):
    items: list[MetricDefinitionResponse]
    engine_version: str
    """La versión que produjo ESTE catálogo. Si no coincide con la del run que
    se está pintando, las etiquetas pueden no corresponder."""


class StressParamsRequest(BaseModel):
    """Overrides de los escenarios de stress. Cualquiera omitido usa el default
    del DESIGN §5."""

    revenue_drops: list[Decimal] | None = Field(default=None, max_length=6)
    rate_shocks_bps: list[int] | None = Field(default=None, max_length=6)
    pct_variable_debt: Decimal | None = None


class RunRequest(BaseModel):
    stress_params: StressParamsRequest | None = None


class AnalysisRunResponse(BaseModel):
    """El run completo, con scores en columnas y el desglose en JSONB."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    security_id: uuid.UUID
    run_date: datetime
    engine_version: str
    thresholds_version: str
    thresholds_used: dict[str, Any]
    """`metric_key → spec` con los cortes que se aplicaron en ESTE run. Vacío en
    los runs anteriores a PHASE-44.9: su calibración no es recuperable."""
    years_covered: list[int]

    m_score: Decimal | None
    z_score: Decimal | None
    z_variant: str | None
    f_score: int | None
    accruals_ratio: Decimal | None
    fcf_payout: Decimal | None
    fcf_coverage: Decimal | None
    dividend_verdict: str | None
    confidence: Decimal

    scores_detail: dict[str, Any]
    dividend_analysis: dict[str, Any]
    evolution: dict[str, Any]
    flags: list[dict[str, Any]]
    verdict: dict[str, Any]
    data_completeness: dict[str, Any]


class AnalysisRunSummary(BaseModel):
    """Fila ligera para el histórico (sin el JSONB pesado)."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    run_date: datetime
    engine_version: str
    years_covered: list[int]
    m_score: Decimal | None
    z_score: Decimal | None
    f_score: int | None
    dividend_verdict: str | None
    confidence: Decimal


class AnalysisRunListResponse(BaseModel):
    items: list[AnalysisRunSummary]


# ── Valoración por múltiplos (PHASE-44.12) ────────────────────────────


class ValuationMetricResponse(BaseModel):
    """Un múltiplo. `value` es `None` si y sólo si no se puede calcular, y
    entonces `reason` lo explica en español para el usuario."""

    model_config = {"from_attributes": True}

    key: str
    value: Decimal | None
    status: str
    reason: str | None


class ValuationResponse(BaseModel):
    """Los múltiplos de un valor contra su cotización.

    NO sale del `AnalysisRun` y no se persiste: se calcula al vuelo cruzando el
    último ejercicio con el precio del momento. Por eso lleva las dos fechas
    —`quote_as_of` y `fiscal_year_end`— bien visibles: un PER con precio de hoy
    sobre un beneficio de hace catorce meses no es falso, pero tiene que decirlo.
    """

    available: bool
    reason: str | None
    """Por qué no hay múltiplos. `None` cuando sí los hay."""
    price_is_override: bool
    """El precio lo puso el usuario, no el proveedor. Se declara para que un
    precio simulado no se confunda con uno de mercado."""

    metrics: list[ValuationMetricResponse] = Field(default_factory=list)
    fiscal_year: int | None = None
    fiscal_year_end: date | None = None
    statement_currency: str | None = None
    market_cap: Decimal | None = None
    enterprise_value: Decimal | None = None
    quote_as_of: date | None = None
    quote_stale: bool = False
    provider_status: str = "cached"
    """Estado del proveedor de cotizaciones en ESTA consulta:

    - `live` — se le ha pedido y ha respondido.
    - `cached` — no se le ha pedido (la cotización guardada seguía fresca), así
      que de su estado no se sabe nada.
    - `unreachable` — se le ha pedido y ha fallado; se sirve el último precio
      registrado.
    """
    fx_rate: Decimal | None = None
    fx_as_of: date | None = None
    days_since_fiscal_year_end: int | None = None
    staleness: str | None = None
    """`null` | `aging` (≥9 meses) | `stale` (≥18 meses)."""
    notes: list[str] = Field(default_factory=list)
