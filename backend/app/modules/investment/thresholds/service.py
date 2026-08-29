"""Servicio de umbrales (PHASE-44.7, ARCHITECTURE §4.3).

Tres cosas: cargar el juego de umbrales de un (sector × norma) fusionado sobre
los defaults del engine, hashearlo de forma estable para `AnalysisRun.thresholds_version`,
y sembrar la tabla de forma idempotente.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import SessionLocal
from app.modules.investment.analysis.engine.sector_profiles import resolve_thresholds
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
        not_applicable_reason=row.not_applicable_reason,
    )


async def load_thresholds(
    db: AsyncSession,
    sector: SectorInternal,
    accounting_std: AccountingStd,
    *,
    is_financial: bool = False,
) -> dict[str, ThresholdSpec]:
    """El juego de umbrales para un valor, fusionado SOBRE lo que resuelve el engine.

    La base es `sector_profiles.resolve_thresholds`, no el catálogo genérico
    (PHASE-44.21): así una base sin sembrar se comporta igual que una sembrada, y
    un banco no se juzga con cortes industriales por el camino de que su fila no
    existiera. La tabla se superpone encima, que es para lo que está — poder
    recalibrar de forma auditable sin tocar el motor.

    `is_financial` es del VALOR y no del sector, así que sólo puede aplicarlo el
    engine: la tabla guarda (sector × norma).
    """
    resolved = resolve_thresholds(sector, accounting_std, is_financial=is_financial)
    for row in await repo.list_for(db, sector, accounting_std):
        current = resolved.get(row.metric_key)
        if current is None:
            # Una fila de una métrica que el catálogo ya no tiene. Se ignora en
            # vez de reventar: la tabla sobrevive a las versiones del motor.
            continue
        spec = _spec_from_row(row)
        # Una fila que dice «no aplica» manda; una que dice que sí NO puede
        # reactivar lo que el perfil del VALOR apagó (un banco clasificado fuera
        # del sector financiero, cuya fila de sector no sabe que es un banco).
        if spec.applies and not current.applies:
            continue
        # PHASE-44.24.M — el seed es un ESPEJO de lo que el motor resuelve, así
        # que una fila que coincide no aporta nada y conserva la procedencia del
        # perfil. Una que difiere es una recalibración hecha a mano —para lo que
        # la tabla existe— y hasta ahora era indistinguible del resto.
        #
        # La comparación es NUMÉRICA (`Decimal`), no textual: la columna es
        # `Numeric(12, 6)`, así que la fila trae `Decimal('0.600000')` donde el
        # motor tiene `Decimal('0.6')` — iguales como número y distintas como
        # cadena. Compararlas como texto marcaría TODA fila sembrada como
        # recalibrada.
        spec = replace(spec, origin="table" if _differs(spec, current) else current.origin)
        resolved[row.metric_key] = spec
    return resolved


def _differs(row: ThresholdSpec, resolved: ThresholdSpec) -> bool:
    """Si una fila de la tabla dice algo distinto de lo que el motor resuelve.

    Compara los cuatro cortes como NÚMERO —`Decimal('0.600000') == Decimal('0.6')`
    es cierto, y como cadena no lo sería— más la dirección, la variante y la
    aplicabilidad, que son las otras tres formas de recalibrar sin mover un corte.
    """
    return (
        row.direction != resolved.direction
        or row.low_alarm != resolved.low_alarm
        or row.low_ok != resolved.low_ok
        or row.high_ok != resolved.high_ok
        or row.high_alarm != resolved.high_alarm
        or row.model_variant != resolved.model_variant
        or row.applies != resolved.applies
    )


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


_ROW_FIELDS = (
    "direction",
    "low_alarm",
    "low_ok",
    "high_ok",
    "high_alarm",
    "model_variant",
    "applies",
    "not_applicable_reason",
)


@dataclass(frozen=True)
class SeedOutcome:
    """Qué cambió al sincronizar la tabla con la calibración del engine."""

    inserted: int
    updated: int

    @property
    def changed(self) -> int:
        return self.inserted + self.updated


async def sync_thresholds(db: AsyncSession) -> SeedOutcome:
    """Deja la tabla exactamente igual a lo que resuelve el engine.

    Inserta lo que falta y **reescribe sólo lo que difiere** — si no difiere, no
    escribe: en régimen estacionario esto es una consulta y cero UPDATEs.

    **Por qué ahora sí actualiza** (PHASE-44.21). PHASE-44.18 hizo el arranque
    sólo-inserción para no reescribir filas bajo los pies de un run ya guardado.
    Esa preocupación está resuelta desde PHASE-44.9: cada `AnalysisRun` persiste
    su `thresholds_used`, así que un run viejo se explica con SU vara aunque la
    tabla cambie. Y sin actualizar aparece el defecto simétrico al de 44.18: una
    calibración nueva llegaría a las bases recién creadas y **nunca** a la que
    lleva meses funcionando, que es justo la que se usa.

    Lo que no cambia: la calibración se escribe en el engine, no aquí. Esta
    función no decide nada, sólo hace que la tabla lo refleje.
    """
    existing = {
        (row.sector, row.accounting_std, row.metric_key): row for row in await repo.list_all(db)
    }
    inserted = 0
    updated = 0
    for row in build_threshold_rows():
        current = existing.get((row.sector, row.accounting_std, row.metric_key))
        if current is None:
            db.add(
                ScoringThresholds(
                    sector=row.sector,
                    accounting_std=row.accounting_std,
                    metric_key=row.metric_key,
                    **{field: getattr(row, field) for field in _ROW_FIELDS},
                )
            )
            inserted += 1
            continue
        differences = [
            field for field in _ROW_FIELDS if getattr(current, field) != getattr(row, field)
        ]
        if not differences:
            continue
        for field in differences:
            setattr(current, field, getattr(row, field))
        updated += 1
    await db.flush()
    return SeedOutcome(inserted=inserted, updated=updated)


async def seed_on_startup(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> SeedOutcome:
    """Sincroniza la tabla de umbrales al arrancar.

    Se ejecuta SIEMPRE, no sólo con la tabla vacía: el caso que importa —una
    métrica nueva en el catálogo, o una calibración que cambia— sólo se da cuando
    la tabla YA tiene filas. Ése fue el defecto de `seed_if_empty` (PHASE-44.18),
    que salía por la puerta de atrás en cuanto había una fila y dejó S7 y S8 sin
    sembrar para siempre.
    """
    factory = session_factory or SessionLocal
    async with factory() as db:
        outcome = await sync_thresholds(db)
        if outcome.changed:
            await db.commit()
        return outcome
