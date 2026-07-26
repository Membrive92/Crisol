"""Schemas Pydantic del catálogo de valores (PHASE-44.7)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, computed_field, field_validator

from app.modules.investment.catalog.capabilities import capabilities_for
from app.modules.investment.enums import AccountingStd, SectorInternal, SecurityType


class SecurityResponse(BaseModel):
    """Identidad completa de un valor del catálogo."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    ticker: str
    exchange: str
    name: str
    cik: str | None
    isin: str | None
    sector: SectorInternal
    accounting_std: AccountingStd
    currency: str
    security_type: SecurityType
    is_financial: bool
    is_reit: bool
    analysis_status: str | None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def analysis_available(self) -> bool:
        """Delegado en `capabilities.capabilities_for` — fuente ÚNICA de la regla
        (PHASE-44.8 E1). Antes esto era `cik is not None` aquí, otra vez en el
        router y otra vez en la guarda de ingesta; y era falso, porque SPY y QQQ
        tienen CIK y no presentan 10-K."""
        return capabilities_for(
            cik=self.cik, analysis_status=self.analysis_status
        ).analysis_available

    @computed_field  # type: ignore[prop-decorator]
    @property
    def analysis_reason(self) -> str | None:
        """Por qué no se puede analizar, para pintarlo ANTES del clic en vez de
        fallar después."""
        return capabilities_for(cik=self.cik, analysis_status=self.analysis_status).reason


class SecurityResolveRequest(BaseModel):
    """Alta/resolución de un valor a partir de su ticker.

    `exchange` es **opcional y no vinculante** desde PHASE-44.8 E1: el servidor
    lo normaliza contra el vocabulario de plazas y lo usa sólo como etiqueta. El
    cliente ya no decide el mercado — mandaba `'US'`, que es un país, y eso
    duplicaba filas contra la restricción única `(ticker, exchange)`.
    """

    ticker: str = Field(min_length=1, max_length=12)
    exchange: str | None = Field(default=None, max_length=16)

    @field_validator("ticker")
    @classmethod
    def _normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("exchange")
    @classmethod
    def _normalize_exchange(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper() or None


class SecuritySearchHit(BaseModel):
    """Un resultado del buscador. `in_catalog=False` marca un hit externo aún
    no resuelto (requiere un `POST /resolve` para crear el `Security`)."""

    id: uuid.UUID | None
    ticker: str
    exchange: str
    name: str
    in_catalog: bool = True
    analysis_available: bool = False


class SecuritySearchResponse(BaseModel):
    """Resultados del buscador estilo broker."""

    results: list[SecuritySearchHit]
    external_search_available: bool = False
    """`False` hasta que exista un `PriceAdapter` con symbol-search (Finnhub).
    Hasta entonces el buscador sólo mira el catálogo local."""
