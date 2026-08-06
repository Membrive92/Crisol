"""Modelo de análisis — `AnalysisRun` (PHASE-44.1, ARCHITECTURE §2.2, [Dec.7]).

Resultado **INMUTABLE** de una ejecución del engine forense sobre una serie de
`FinancialStatement`. Scoped por usuario. Los scores de primer nivel viven en
columnas (consultables en serie, para comparar runs en el tiempo); el desglose
va en JSONB. `engine_version` + `thresholds_version` hacen el run reproducible:
mismos statements + mismos umbrales + misma versión de engine ⇒ mismo run.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    security_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("securities.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    run_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(16), nullable=False)
    thresholds_version: Mapped[str] = mapped_column(String(64), nullable=False)
    """Hash del set de umbrales usado — parte de la clave de reproducibilidad."""
    years_covered: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), nullable=False)

    thresholds_used: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    """El juego de cortes EFECTIVO de este run, `metric_key → spec` (PHASE-44.9).

    `thresholds_version` detecta que dos runs se midieron distinto; esto permite
    decir CUÁNTO. Es imprescindible para explicar el veredicto: sin los cortes no
    se puede pintar «6,8× frente a un mínimo de 6». Los runs anteriores a la
    columna quedan en `{}` y no se pueden explicar retroactivamente."""

    # ── Scores de primer nivel (en columnas → consultables en serie) ──
    m_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    z_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    z_variant: Mapped[str | None] = mapped_column(String(16), nullable=True)
    f_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    accruals_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    fcf_payout: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    fcf_coverage: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    dividend_verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)
    """healthy | caution | stressed | not_applicable."""
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)

    # ── Desglose (JSONB; nada se agrega sin poder abrirse) ──
    scores_detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    dividend_analysis: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evolution: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    flags: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    verdict: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    data_completeness: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # btree plano (security_id, user_id, run_date): sirve "últimos runs de un
    # valor" con ORDER BY run_date DESC vía scan hacia atrás, sin el índice de
    # expresión que `alembic check` compara mal.
    __table_args__ = (Index("ix_runs_sec_user", "security_id", "user_id", "run_date"),)
