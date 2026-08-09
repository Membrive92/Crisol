"""Modelo de umbrales de scoring — `ScoringThresholds` (PHASE-44.1,
ARCHITECTURE §2.2, [Dec.8]).

Tabla **GLOBAL**. Un umbral por (sector × norma × `metric_key`): `direction`
dice el sentido de la banda (menos-mejor / más-mejor / banda central) y los 4
cortes definen verde|ámbar|rojo. `model_variant` permite variantes de un mismo
score (p. ej. Z'' vs Z clásica). Los seeds nacen calibrados para US-GAAP
genérico; IFRS/PGC nacen `model_variant='uncalibrated'` [D4].

NOTA de scope (PHASE-44.1): esta fase entrega la TABLA. El SEED de filas se
difiere a la fase del engine (40.2/40.3), donde las `metric_key` quedan fijadas
por el catálogo §5; sembrar antes arriesga drift silencioso entre las claves
sembradas y las que el engine consuma.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.investment.enums import (
    AccountingStd,
    SectorInternal,
    ThresholdDirection,
    pg_enum,
)


class ScoringThresholds(Base):
    __tablename__ = "scoring_thresholds"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sector: Mapped[SectorInternal] = mapped_column(
        pg_enum(SectorInternal, "sector_internal"), nullable=False
    )
    accounting_std: Mapped[AccountingStd] = mapped_column(
        pg_enum(AccountingStd, "accounting_std"), nullable=False
    )
    metric_key: Mapped[str] = mapped_column(String(64), nullable=False)
    """Clave estable de la métrica (§5 del DESIGN): 'L1', 'S4', 'm_score'…"""
    direction: Mapped[ThresholdDirection] = mapped_column(
        pg_enum(ThresholdDirection, "threshold_direction"), nullable=False
    )
    low_alarm: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    low_ok: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    high_ok: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    high_alarm: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    model_variant: Mapped[str | None] = mapped_column(String(32), nullable=True)
    applies: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    """FALSE = el modelo no aplica a este (sector × norma): p. ej. Beneish en
    financieras. El engine reporta `not_computable` con razón, no basura."""
    not_applicable_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Por qué no aplica, en español (PHASE-44.21). Viaja en `thresholds_used` y
    de ahí a la pantalla: un número gris sin explicación se lee como «no se ha
    podido calcular», que es otra cosa — y el usuario acaba culpando a las
    cuentas de la empresa de una decisión del motor."""

    __table_args__ = (
        UniqueConstraint(
            "sector", "accounting_std", "metric_key", name="uq_thresholds_sector_std_metric"
        ),
    )
