"""Tests del seed y la carga de umbrales (PHASE-44.7)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import replace
from decimal import Decimal

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.investment.analysis.engine.catalog import ALL_DEFAULT_THRESHOLDS
from app.modules.investment.enums import AccountingStd, SectorInternal
from app.modules.investment.thresholds import repository as repo
from app.modules.investment.thresholds.models import ScoringThresholds
from app.modules.investment.thresholds.seed import (
    FORENSIC_KEYS,
    NOT_FOR_FINANCIALS,
    build_threshold_rows,
)
from app.modules.investment.thresholds.service import (
    load_thresholds,
    seed_missing_thresholds,
    seed_on_startup,
    seed_scoring_thresholds,
    thresholds_hash,
)

_EXPECTED = len(SectorInternal) * len(AccountingStd) * len(ALL_DEFAULT_THRESHOLDS)


@pytest_asyncio.fixture
async def db(test_engine) -> AsyncIterator[AsyncSession]:  # type: ignore[no-untyped-def]
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        yield session


# ── Constructor puro ──────────────────────────────────────────────────


def test_cardinalidad() -> None:
    assert len(build_threshold_rows()) == _EXPECTED


def test_forenses_no_aplican_en_financieras() -> None:
    rows = build_threshold_rows()
    key = next(iter(FORENSIC_KEYS))
    financials = [r for r in rows if r.sector is SectorInternal.FINANCIALS and r.metric_key == key]
    technology = [r for r in rows if r.sector is SectorInternal.TECHNOLOGY and r.metric_key == key]
    assert financials and all(not r.applies for r in financials)
    assert technology and all(r.applies for r in technology)


def test_no_forenses_si_aplican_en_financieras() -> None:
    rows = build_threshold_rows()
    non_forensic = next(
        k for k in ALL_DEFAULT_THRESHOLDS if k not in FORENSIC_KEYS and k not in NOT_FOR_FINANCIALS
    )
    financials = [
        r for r in rows if r.sector is SectorInternal.FINANCIALS and r.metric_key == non_forensic
    ]
    assert financials and all(r.applies for r in financials)


def test_el_endeudamiento_no_se_aplica_en_financieras() -> None:
    """S7 (pasivo/patrimonio) está calibrada para negocios con activo tangible.

    En un banco el apalancamiento ES el negocio: un 10× es normal y el corte de
    3 pintaría un rojo permanente que no informa de nada. Se siembra sin aplicar
    —el número se ve, sin semáforo— en vez de esperar a la recalibración por
    sector (PHASE-44.10). Es el mismo mecanismo que ya usaban los forenses.
    """
    rows = build_threshold_rows()
    financieras = [
        r for r in rows if r.sector is SectorInternal.FINANCIALS and r.metric_key == "S7"
    ]
    industriales = [
        r for r in rows if r.sector is SectorInternal.INDUSTRIALS and r.metric_key == "S7"
    ]
    assert financieras and all(not r.applies for r in financieras)
    assert industriales and all(r.applies for r in industriales)


def test_la_calidad_de_la_deuda_si_aplica_en_financieras() -> None:
    """S8 mide qué parte de la deuda vence a menos de un año. Eso significa lo
    mismo en un banco que en una fábrica, así que no se exime."""
    rows = build_threshold_rows()
    financieras = [
        r for r in rows if r.sector is SectorInternal.FINANCIALS and r.metric_key == "S8"
    ]
    assert financieras and all(r.applies for r in financieras)


def test_ifrs_pgc_uncalibrated() -> None:
    rows = build_threshold_rows()
    key = next(iter(ALL_DEFAULT_THRESHOLDS))
    for r in rows:
        if r.metric_key != key or r.sector is not SectorInternal.TECHNOLOGY:
            continue
        if r.accounting_std is AccountingStd.GAAP:
            assert r.model_variant == ALL_DEFAULT_THRESHOLDS[key].model_variant
        else:
            assert r.model_variant == "uncalibrated"


# ── Hash ──────────────────────────────────────────────────────────────


def test_hash_estable_y_sensible() -> None:
    specs = dict(ALL_DEFAULT_THRESHOLDS)
    h1 = thresholds_hash(specs)
    assert len(h1) == 64
    assert thresholds_hash(dict(ALL_DEFAULT_THRESHOLDS)) == h1

    key = next(iter(specs))
    mutated = dict(specs)
    mutated[key] = replace(specs[key], applies=not specs[key].applies)
    assert thresholds_hash(mutated) != h1


# ── Seed + carga (BD) ─────────────────────────────────────────────────


async def test_seed_es_idempotente(db: AsyncSession) -> None:
    first = await seed_scoring_thresholds(db)
    await db.commit()
    assert first == _EXPECTED
    second = await seed_scoring_thresholds(db)
    await db.commit()
    assert second == 0
    assert await repo.count(db) == _EXPECTED


async def test_load_thresholds_tras_seed(db: AsyncSession) -> None:
    await seed_scoring_thresholds(db)
    await db.commit()
    key = next(iter(FORENSIC_KEYS))

    financials = await load_thresholds(db, SectorInternal.FINANCIALS, AccountingStd.GAAP)
    technology = await load_thresholds(db, SectorInternal.TECHNOLOGY, AccountingStd.GAAP)

    assert financials[key].applies is False
    assert technology[key].applies is True


async def test_load_thresholds_sin_seed_cae_a_defaults(db: AsyncSession) -> None:
    resolved = await load_thresholds(db, SectorInternal.TECHNOLOGY, AccountingStd.GAAP)
    assert set(resolved) == set(ALL_DEFAULT_THRESHOLDS)


async def test_seed_on_startup_siembra_y_luego_no_duplica(test_engine) -> None:  # type: ignore[no-untyped-def]
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    first = await seed_on_startup(factory)
    second = await seed_on_startup(factory)
    assert first == _EXPECTED
    assert second == 0


async def test_una_metrica_anadida_despues_del_primer_seed_si_entra(db: AsyncSession) -> None:
    """El defecto de PHASE-44.18, reproducido: una tabla CON historia.

    `seed_if_empty` se rendía en cuanto la tabla tenía una fila, así que toda
    métrica añadida al catálogo después del primer seed quedaba fuera para
    siempre. Medido en la BD real del usuario: 1440 filas, **40 métricas
    sembradas frente a 42 con banda** — S7 y S8, de PHASE-44.10, nunca entraron.

    Este test es el detector, y su forma importa: la suite anterior nunca pudo
    cazarlo porque **siembra siempre una base limpia**, donde el catálogo entero
    entra de una vez. El bug sólo existe cuando la tabla ya tiene filas de un
    catálogo ANTERIOR, así que hay que fabricar esa situación a mano.
    """
    llegan_despues = {"S7", "S8"}
    catalogo_viejo = [r for r in build_threshold_rows() if r.metric_key not in llegan_despues]
    for row in catalogo_viejo:
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
    await db.flush()
    antes = await repo.existing_keys(db)
    assert not any(key in llegan_despues for _, _, key in antes)

    inserted = await seed_missing_thresholds(db)

    despues = await repo.existing_keys(db)
    sembradas_ahora = {key for _, _, key in despues}
    assert llegan_despues <= sembradas_ahora, "las métricas nuevas siguen sin sembrarse"
    assert inserted == len(llegan_despues) * len(SectorInternal) * len(AccountingStd)
    # Y no ha tocado nada de lo que ya estaba.
    assert antes <= despues


async def test_el_sembrado_incremental_no_reescribe_las_filas_existentes(
    db: AsyncSession,
) -> None:
    """`thresholds_version` es un hash irreversible de los cortes efectivos.

    Por eso PHASE-44.9 tuvo que persistir `thresholds_used` en cada run: si el
    arranque reescribiera filas, los runs viejos dejarían de poder explicarse.
    `seed_scoring_thresholds` SÍ actualiza (correcto al resembrar a propósito);
    el paso de arranque no puede.
    """
    await seed_scoring_thresholds(db)
    key = next(iter(ALL_DEFAULT_THRESHOLDS))
    row = await repo.get_one(db, SectorInternal.TECHNOLOGY, AccountingStd.GAAP, key)
    assert row is not None
    row.high_ok = Decimal("999")
    await db.flush()

    assert await seed_missing_thresholds(db) == 0

    intacta = await repo.get_one(db, SectorInternal.TECHNOLOGY, AccountingStd.GAAP, key)
    assert intacta is not None
    assert intacta.high_ok == Decimal("999"), "el sembrado de arranque ha pisado una fila existente"


async def test_toda_metrica_con_banda_del_catalogo_se_siembra() -> None:
    """Gate de cobertura, SIN BD: lo que el motor puede colorear, se siembra.

    Es el invariante que se rompió en silencio. Sin él, añadir una métrica con
    banda al catálogo y olvidar el resto no falla en ninguna parte — la métrica
    simplemente pierde su diferenciación por (sector × norma) y nadie se entera.
    """
    sembradas = {row.metric_key for row in build_threshold_rows()}
    assert sembradas == set(ALL_DEFAULT_THRESHOLDS)
