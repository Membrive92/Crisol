"""Tests del seed y la carga de umbrales (PHASE-44.7)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import replace

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.investment.analysis.engine.catalog import ALL_DEFAULT_THRESHOLDS
from app.modules.investment.enums import AccountingStd, SectorInternal
from app.modules.investment.thresholds import repository as repo
from app.modules.investment.thresholds.seed import FORENSIC_KEYS, build_threshold_rows
from app.modules.investment.thresholds.service import (
    load_thresholds,
    seed_if_empty,
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
    non_forensic = next(k for k in ALL_DEFAULT_THRESHOLDS if k not in FORENSIC_KEYS)
    financials = [
        r for r in rows if r.sector is SectorInternal.FINANCIALS and r.metric_key == non_forensic
    ]
    assert financials and all(r.applies for r in financials)


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


async def test_seed_if_empty_siembra_una_sola_vez(test_engine) -> None:  # type: ignore[no-untyped-def]
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    first = await seed_if_empty(factory)
    second = await seed_if_empty(factory)
    assert first == _EXPECTED
    assert second == 0
