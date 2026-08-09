"""Constructor de filas de `scoring_thresholds` (PHASE-44.7, ARCHITECTURE §8, Dec.8).

PURO: no toca BD. Genera una fila por (sector × norma × métrica banded)
**preguntándole al engine** cuál es el umbral efectivo de esa combinación
(`sector_profiles.resolve_thresholds`), de modo que la tabla no pueda decir una
cosa y el motor otra.

Ese reparto es deliberado (PHASE-44.21). La calibración VIVE en el engine, que la
aplica aunque la tabla esté vacía; la tabla existe para que un `AnalysisRun`
pueda guardar la vara con la que se midió (`thresholds_used`, PHASE-44.9) y para
que una recalibración futura sea auditable. Al revés —la calibración sólo en la
tabla— es lo que dejó la exención de S7 inerte durante ocho fases: dependía de
una fila que nadie había sembrado.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.modules.investment.analysis.engine.sector_profiles import (
    UNCALIBRATED,
    resolve_thresholds,
)
from app.modules.investment.enums import (
    AccountingStd,
    SectorInternal,
    ThresholdDirection,
)

__all__ = ["UNCALIBRATED", "ThresholdRow", "build_threshold_rows"]


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
    not_applicable_reason: str | None = None


def build_threshold_rows() -> list[ThresholdRow]:
    """Todas las filas del seed: sector × norma × métrica banded.

    `is_financial` se deriva del sector porque una fila de la tabla describe un
    (sector × norma), no un valor concreto. Un valor marcado como financiero
    fuera del sector financiero recibe su perfil en el engine, que sí conoce el
    flag — y por eso la aplicabilidad no puede vivir sólo aquí.
    """
    rows: list[ThresholdRow] = []
    for sector in SectorInternal:
        for std in AccountingStd:
            resolved = resolve_thresholds(
                sector, std, is_financial=sector is SectorInternal.FINANCIALS
            )
            for metric_key, spec in resolved.items():
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
                        model_variant=spec.model_variant,
                        applies=spec.applies,
                        not_applicable_reason=spec.not_applicable_reason,
                    )
                )
    return rows
