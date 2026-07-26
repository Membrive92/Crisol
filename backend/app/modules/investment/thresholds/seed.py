"""Constructor de filas de `scoring_thresholds` (PHASE-44.7, ARCHITECTURE §8, Dec.8).

PURO: no toca BD. Genera una fila por (sector × norma × métrica banded) a partir
de `ALL_DEFAULT_THRESHOLDS` —la fuente ÚNICA del engine—, de modo que las
`metric_key` sembradas no pueden divergir de las que el engine calcula.

Dos únicas diferenciaciones sobre la banda genérica US-GAAP (el DESIGN §5 no da
cortes por sector):
- **Financieras**: las 8 métricas forenses (Beneish, Altman, Piotroski…) salen
  `applies=False` — no se calibraron sobre bancos. La lista de forenses se toma
  de `forensic.METRIC_CATALOG`, no de una lista escrita a mano.
- **IFRS / PGC**: `model_variant='uncalibrated'` — los cortes son US-GAAP; se
  muestran con badge de "sin calibrar", nunca ocultos ni como números propios.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.modules.investment.analysis.engine import forensic
from app.modules.investment.analysis.engine.catalog import ALL_DEFAULT_THRESHOLDS
from app.modules.investment.enums import (
    AccountingStd,
    SectorInternal,
    ThresholdDirection,
)

FORENSIC_KEYS: frozenset[str] = frozenset(d.key for d in forensic.METRIC_CATALOG)
"""Las métricas forenses (Beneish/Altman/Piotroski…), tomadas del catálogo del
engine para no divergir. En financieras salen `applies=False`."""

UNCALIBRATED = "uncalibrated"
"""`model_variant` para IFRS/PGC: los cortes son US-GAAP, sin recalibrar."""


@dataclass(frozen=True)
class ThresholdRow:
    """Una fila de `scoring_thresholds` antes de persistirse."""

    sector: SectorInternal
    accounting_std: AccountingStd
    metric_key: str
    direction: ThresholdDirection
    low_alarm: Decimal | None
    low_ok: Decimal | None
    high_ok: Decimal | None
    high_alarm: Decimal | None
    model_variant: str | None
    applies: bool


def build_threshold_rows() -> list[ThresholdRow]:
    """Todas las filas del seed: sector × norma × métrica banded."""
    rows: list[ThresholdRow] = []
    for sector in SectorInternal:
        for std in AccountingStd:
            for metric_key, spec in ALL_DEFAULT_THRESHOLDS.items():
                is_forensic = metric_key in FORENSIC_KEYS
                applies = not (sector is SectorInternal.FINANCIALS and is_forensic)
                model_variant = spec.model_variant if std is AccountingStd.GAAP else UNCALIBRATED
                rows.append(
                    ThresholdRow(
                        sector=sector,
                        accounting_std=std,
                        metric_key=metric_key,
                        direction=spec.direction,
                        low_alarm=spec.low_alarm,
                        low_ok=spec.low_ok,
                        high_ok=spec.high_ok,
                        high_alarm=spec.high_alarm,
                        model_variant=model_variant,
                        applies=applies,
                    )
                )
    return rows
