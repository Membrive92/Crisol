"""Enums nativos Postgres del módulo Inversión (PHASE-44.1).

Convención: `StrEnum` con nombre de miembro en `UPPER_SNAKE` (estilo Python) y
`.value` = el string EXACTO del DDL (ARCHITECTURE §2.2). Se persiste el `.value`
vía `values_callable` (no el nombre del miembro, que es el default de
SQLAlchemy), para que la columna Postgres tenga los valores del spec
(`'unknown'`, `'pending'`, `'STOCK'`, `'GAAP'`…) y la serialización Pydantic
(por `.value`) coincida con la BD.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Enum as SAEnum


def pg_enum(py_enum: type[enum.Enum], name: str) -> SAEnum:
    """Tipo `Enum` nativo Postgres que guarda el `.value` del miembro."""

    def _values(enum_cls: type[enum.Enum]) -> Sequence[str]:
        return [str(member.value) for member in enum_cls]

    # `values_callable` recibe la clase enum y devuelve la lista de labels.
    return SAEnum(py_enum, name=name, native_enum=True, values_callable=_values)  # type: ignore[arg-type]


class SectorInternal(enum.StrEnum):
    """Taxonomía sectorial PROPIA derivada de SIC [Dec.15] — el sector sólo
    gobierna umbrales (`scoring_thresholds`) y aplicabilidad de modelos, no
    contabilidad. NO es GICS (licenciado). Conjunto provisional y ampliable
    (Postgres admite `ALTER TYPE ... ADD VALUE`); se calibrará antes del seed
    de umbrales (fase posterior)."""

    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    FINANCIALS = "financials"  # is_financial=True → excluido del forense
    CONSUMER_STAPLES = "consumer_staples"
    CONSUMER_DISCRETIONARY = "consumer_discretionary"
    INDUSTRIALS = "industrials"
    ENERGY = "energy"
    MATERIALS = "materials"
    UTILITIES = "utilities"
    REAL_ESTATE = "real_estate"
    COMMUNICATION = "communication"
    UNKNOWN = "unknown"


class AccountingStd(enum.StrEnum):
    """Norma contable [D2]. GAAP calibrado en MVP; IFRS/PGC nacen
    `uncalibrated` (los cutoffs de Beneish/Altman son US-GAAP)."""

    GAAP = "GAAP"
    IFRS = "IFRS"
    PGC = "PGC"


class SecurityType(enum.StrEnum):
    """Tipo de valor. `is_reit` es un flag aparte (activa la variante FFO), no
    un `security_type`. Conjunto ampliable."""

    STOCK = "STOCK"
    ADR = "ADR"
    ETF = "ETF"


class PeriodType(enum.StrEnum):
    """Periodicidad del estado financiero. 10-Q (`QUARTERLY`) se reserva pero
    NO se ingiere en MVP (anti-objetivo del ARCHITECTURE §10)."""

    ANNUAL = "ANNUAL"
    QUARTERLY = "QUARTERLY"


class StatementSource(enum.StrEnum):
    """Procedencia del estado financiero [D3]."""

    EDGAR_XBRL = "EDGAR_XBRL"
    MANUAL = "MANUAL"


class JobStatus(enum.StrEnum):
    """Estado de un job de ingesta (BackgroundTask, single-user local)."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class ThresholdDirection(enum.StrEnum):
    """Sentido de la banda de un umbral [Dec.8]: si menos es mejor
    (apalancamiento), más es mejor (cobertura) o es una banda central."""

    LOWER_BETTER = "lower_better"
    HIGHER_BETTER = "higher_better"
    BAND = "band"


class CorpActionType(enum.StrEnum):
    """Acción corporativa que ajusta lotes de forma auditada y reversible
    [Dec.9]."""

    SPLIT = "split"
    SPINOFF = "spinoff"
    STOCK_DIVIDEND = "stock_dividend"
    RETURN_OF_CAPITAL = "return_of_capital"


# Sectores que se excluyen del scoring forense (Beneish/Altman no aplican).
# `securities.is_financial` es la fuente de verdad por-valor; esto es el mapa
# por defecto que el seeding de securities puede usar.
FINANCIAL_SECTORS: frozenset[SectorInternal] = frozenset({SectorInternal.FINANCIALS})


def _all_labels(py_enum: type[enum.Enum]) -> list[Any]:
    """Helper de tests/seed: labels persistidos de un enum."""
    return [member.value for member in py_enum]
