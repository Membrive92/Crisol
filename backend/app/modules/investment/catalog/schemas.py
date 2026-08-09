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
    """Un resultado del buscador.

    `in_catalog=False` marca una fila que todavía no es un `Security`: viene del
    índice de la SEC y se materializa al adoptarla (`POST /adopt` con
    `listing_key`).
    """

    id: uuid.UUID | None
    ticker: str
    exchange: str
    name: str
    in_catalog: bool = True
    analysis_available: bool = False

    listing_key: str = ""
    """Clave opaca que el cliente devuelve al elegir la fila (PHASE-44.8 E2).

    Existe para que el cliente deje de decidir el mercado: mandaba `'US'` —un
    país— y eso duplicaba filas contra la restricción única `(ticker, exchange)`.
    Con la clave, la plaza la vuelve a resolver el servidor."""

    source: str = "catalog"
    """`catalog` (ya en el catálogo), `sec_index` (índice de la SEC) o
    `eu_directory` (directorio FIRDS UE/UK, PHASE-44.14)."""

    cik: str | None = None
    exchange_label: str = ""
    """Etiqueta de la plaza para pintar (`Nasdaq`, no `NASDAQ`)."""

    isin: str | None = None
    """Identidad registral de las filas del directorio: no llevan ticker (FIRDS
    no lo publica) y el ISIN es lo que las distingue en pantalla."""

    currency: str | None = None
    """Divisa registral (`NtnlCcy`) de las filas del directorio."""

    analysis_reason: str | None = None
    """Por qué NO se puede analizar, para decirlo antes del clic. `None` cuando
    sí se puede."""


class SecurityAdoptRequest(BaseModel):
    """Materializa un resultado del buscador como `Security`.

    Sólo viaja la clave: ni plaza, ni divisa, ni CIK. Lo que el cliente no manda
    no lo puede inventar.

    `ticker` es la ÚNICA excepción, y sólo para claves `ext:`: es el bypass
    manual de la resolución ISIN→símbolo cuando el proveedor no reconoce el ISIN
    (el servidor responde 422 `ticker_required` y el formulario lo pide). Sigue
    sin decidir nada de identidad — la plaza, el nombre y la divisa vienen del
    directorio, y el ticker se valida contra una cotización real antes de
    persistir nada.
    """

    listing_key: str = Field(min_length=3, max_length=128)
    ticker: str | None = Field(default=None, max_length=12)


class SecuritySearchResponse(BaseModel):
    """Resultados del buscador estilo broker."""

    results: list[SecuritySearchHit]
    external_search_available: bool = False
    """`False` mientras no haya proveedor multi-mercado (Entrega 5 de
    PHASE-44.8). Hasta entonces el buscador mira el catálogo y el índice de la
    SEC, ambos locales."""

    index_ready: bool = False
    """Si el índice de la SEC está cargado y con filas.

    Se publica porque cero resultados significan dos cosas distintas —«no hay
    coincidencias» y «el índice no está disponible»— y la segunda no se puede
    presentar como la primera."""

    notice: str | None = None
    """Aviso cuando el vacío mentiría: `NESN` no devuelve nada porque SIX no
    reporta a FIRDS (frontera suiza), no porque Nestlé no exista."""

    directory_seeded_at: datetime | None = None
    """Fecha del último seed del directorio UE/UK, o `None` si está vacío.

    Se publica porque cero resultados europeos con el directorio SIN SEMBRAR
    significa «no se ha mirado», no «no cotiza en Europa» — y la pantalla no
    puede presentar lo primero como lo segundo. Es el «directorio actualizado
    el X» del plan E5 §2.6."""
