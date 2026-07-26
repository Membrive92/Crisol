"""Schemas Pydantic de análisis (PHASE-44.7)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


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
