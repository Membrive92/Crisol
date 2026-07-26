"""Schemas Pydantic de fundamentales (PHASE-44.7).

Los importes son `Decimal | None`; Pydantic v2 los serializa a string en JSON
(mismo criterio Decimal-no-float que el resto de la API), y `None` marca el hueco.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.modules.investment.enums import (
    AccountingStd,
    JobStatus,
    PeriodType,
    StatementSource,
)


class IngestRequest(BaseModel):
    filings_back: int = Field(default=5, ge=1, le=10)


class IngestionJobResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    security_id: uuid.UUID
    status: JobStatus
    params: dict[str, Any]
    progress: dict[str, Any]
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class StatementResponse(BaseModel):
    """Un ejercicio persistido: metadatos + las 49 partidas canónicas."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    security_id: uuid.UUID
    fiscal_year: int
    fiscal_year_end: date
    period_type: PeriodType
    filing_accession: str
    filing_date: date
    is_latest_view: bool
    source: StatementSource
    accounting_std: AccountingStd
    currency: str

    # ── Balance (23) ──────────────────────────────────────────────
    cash: Decimal | None
    current_financial_assets: Decimal | None
    receivables: Decimal | None
    inventory: Decimal | None
    current_assets: Decimal | None
    ppe_net: Decimal | None
    goodwill: Decimal | None
    intangibles: Decimal | None
    deferred_tax_assets: Decimal | None
    total_assets: Decimal | None
    short_term_debt: Decimal | None
    ltd_current_portion: Decimal | None
    accounts_payable: Decimal | None
    lease_liabilities_current: Decimal | None
    current_liabilities: Decimal | None
    long_term_debt: Decimal | None
    lease_liabilities_noncurrent: Decimal | None
    deferred_tax_liabilities: Decimal | None
    total_liabilities: Decimal | None
    share_premium: Decimal | None
    retained_earnings: Decimal | None
    treasury_stock: Decimal | None
    equity: Decimal | None

    # ── Cuenta de resultados (16) ─────────────────────────────────
    revenue: Decimal | None
    cogs: Decimal | None
    sga_expense: Decimal | None
    rd_expense: Decimal | None
    depreciation_amortization: Decimal | None
    impairments: Decimal | None
    gains_on_sale_of_business: Decimal | None
    ebit: Decimal | None
    interest_expense: Decimal | None
    pretax_income: Decimal | None
    taxes: Decimal | None
    net_income: Decimal | None
    shares_basic: Decimal | None
    shares_diluted: Decimal | None
    shares_outstanding_eop: Decimal | None
    sbc_expense: Decimal | None

    # ── Flujo de caja (10) ────────────────────────────────────────
    cfo: Decimal | None
    wc_change_inventory: Decimal | None
    capex: Decimal | None
    acquisitions: Decimal | None
    divestitures: Decimal | None
    dividends_paid: Decimal | None
    buybacks: Decimal | None
    share_issuance: Decimal | None
    debt_change: Decimal | None
    taxes_paid: Decimal | None

    raw_source_ref: dict[str, Any]
    created_at: datetime


class StatementListResponse(BaseModel):
    items: list[StatementResponse]


class RestatementResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    security_id: uuid.UUID
    fiscal_year: int
    filing_a: str
    filing_b: str
    divergences: list[dict[str, Any]]
    detected_at: datetime


class RestatementListResponse(BaseModel):
    items: list[RestatementResponse]
