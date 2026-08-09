"""Servicio de umbrales (PHASE-44.7, ARCHITECTURE §4.3).

Tres cosas: cargar el juego de umbrales de un (sector × norma) fusionado sobre
los defaults del engine, hashearlo de forma estable para `AnalysisRun.thresholds_version`,
y sembrar la tabla de forma idempotente.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import SessionLocal
from app.modules.investment.analysis.engine.catalog import ALL_DEFAULT_THRESHOLDS
from app.modules.investment.analysis.engine.types import ThresholdSpec
from app.modules.investment.enums import AccountingStd, SectorInternal
from app.modules.investment.thresholds import repository as repo
from app.modules.investment.thresholds.models import ScoringThresholds
from app.modules.investment.thresholds.seed import build_threshold_rows


def _spec_from_row(row: ScoringThresholds) -> ThresholdSpec:
    return ThresholdSpec(
        metric_key=row.metric_key,
        direction=row.direction,
        low_alarm=row.low_alarm,
        low_ok=row.low_ok,
        high_ok=row.high_ok,
        high_alarm=row.high_alarm,
        model_variant=row.model_variant,
        applies=row.applies,
    )


async def load_thresholds(
    db: AsyncSession, sector: SectorInternal, accounting_std: AccountingStd
) -> dict[str, ThresholdSpec]:
    """El juego de umbrales para (sector × norma), fusionado SOBRE los defaults
    del engine.

    Si la tabla no está sembrada, se usan íntegramente los defaults del engine —
    el análisis sigue funcionando (y en financieras el engine ya apaga los
    forenses por `is_financial`, con independencia de `applies`)."""
    resolved: dict[str, ThresholdSpec] = dict(ALL_DEFAULT_THRESHOLDS)
    for row in await repo.list_for(db, sector, accounting_std):
        resolved[row.metric_key] = _spec_from_row(row)
    return resolved


def _fmt(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def thresholds_hash(specs: Mapping[str, ThresholdSpec]) -> str:
    """SHA-256 (hex, 64 chars) del juego de umbrales en orden canónico.

    Va a `AnalysisRun.thresholds_version`: dos runs con el mismo hash usaron
    exactamente los mismos cortes, así que un cambio de calibración es visible en
    la reproducibilidad del run [Dec.7]."""
    payload = [
        [
            key,
            str(spec.direction),
            _fmt(spec.low_alarm),
            _fmt(spec.low_ok),
            _fmt(spec.high_ok),
            _fmt(spec.high_alarm),
            spec.model_variant or "",
            spec.applies,
        ]
        for key, spec in sorted(specs.items())
    ]
    blob = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


async def seed_scoring_thresholds(db: AsyncSession) -> int:
    """Siembra/actualiza toda la tabla. Idempotente: devuelve cuántas filas
    NUEVAS insertó (0 en re-ejecuciones sobre una tabla ya sembrada)."""
    inserted = 0
    for row in build_threshold_rows():
        existing = await repo.get_one(db, row.sector, row.accounting_std, row.metric_key)
        if existing is None:
            db.add(
                ScoringThresholds(
                    sector=row.sector,
                    accounting_std=row.accounting_std,
                    metric_key=row.metric_key,
                    direction=row.direction,
                    low_alarm=row.low_alarm,
                    low_ok=row.low_ok,
                    high_ok=row.high_ok,
                    high_alarm=row.high_alarm,
                    model_variant=row.model_variant,
                    applies=row.applies,
                )
            )
            inserted += 1
        else:
            existing.direction = row.direction
            existing.low_alarm = row.low_alarm
            existing.low_ok = row.low_ok
            existing.high_ok = row.high_ok
            existing.high_alarm = row.high_alarm
            existing.model_variant = row.model_variant
            existing.applies = row.applies
    await db.flush()
    return inserted


async def seed_missing_thresholds(db: AsyncSession) -> int:
    """Inserta las filas que faltan y **no toca ni una de las existentes**.

    Es la hermana conservadora de `seed_scoring_thresholds`, que además actualiza
    lo que ya está. Esa mutación in situ es correcta para resembrar a propósito,
    pero inaceptable como paso de arranque: `AnalysisRun.thresholds_version` es un
    hash irreversible de los cortes efectivos, y por eso PHASE-44.9 tuvo que
    persistir `thresholds_used` en cada run. Si el arranque reescribiera filas,
    los runs viejos dejarían de poder explicarse.

    **Por qué existe** (PHASE-44.18): el arranque llamaba a `seed_if_empty`, que
    salía por la puerta de atrás en cuanto la tabla tenía UNA fila. Efecto: toda
    métrica añadida al catálogo después del primer seed quedaba fuera para
    siempre. Medido en la BD real: 1440 filas, **40 métricas sembradas frente a
    42 con banda** — S7 y S8, que llegaron en PHASE-44.10, nunca entraron.

    Una sola consulta para saber qué hay; el resto es diferencia en memoria.
    """
    existing = await repo.existing_keys(db)
    inserted = 0
    for row in build_threshold_rows():
        if (row.sector, row.accounting_std, row.metric_key) in existing:
            continue
        db.add(
            ScoringThresholds(
                sector=row.sector,
                accounting_std=row.accounting_std,
                metric_key=row.metric_key,
                direction=row.direction,
                low_alarm=row.low_alarm,
                low_ok=row.low_ok,
                high_ok=row.high_ok,
                high_alarm=row.high_alarm,
                model_variant=row.model_variant,
                applies=row.applies,
            )
        )
        inserted += 1
    await db.flush()
    return inserted


async def seed_on_startup(session_factory: async_sessionmaker[AsyncSession] | None = None) -> int:
    """Completa la tabla de umbrales al arrancar. Devuelve cuántas filas insertó.

    Sustituye a `seed_if_empty`: se ejecuta SIEMPRE, no sólo con la tabla vacía,
    porque el caso que importa —una métrica nueva en el catálogo— sólo se da
    cuando la tabla YA tiene filas.
    """
    factory = session_factory or SessionLocal
    async with factory() as db:
        inserted = await seed_missing_thresholds(db)
        if inserted:
            await db.commit()
        return inserted
