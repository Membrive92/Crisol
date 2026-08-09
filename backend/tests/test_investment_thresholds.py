"""Tests del seed y la carga de umbrales (PHASE-44.7, recalibrados en 44.21)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import replace
from decimal import Decimal

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.investment.analysis.engine.catalog import ALL_DEFAULT_THRESHOLDS
from app.modules.investment.analysis.engine.sector_profiles import (
    FINANCIALS_NOT_APPLICABLE,
    resolve_thresholds,
)
from app.modules.investment.enums import AccountingStd, SectorInternal
from app.modules.investment.thresholds import repository as repo
from app.modules.investment.thresholds.models import ScoringThresholds
from app.modules.investment.thresholds.seed import build_threshold_rows
from app.modules.investment.thresholds.service import (
    load_thresholds,
    seed_on_startup,
    sync_thresholds,
    thresholds_hash,
)

_EXPECTED = len(build_threshold_rows())

_FORENSIC_KEY = "m_score"
"""Un forense cualquiera: en financieras los ocho salen sin aplicar."""


@pytest_asyncio.fixture
async def db(test_engine) -> AsyncIterator[AsyncSession]:  # type: ignore[no-untyped-def]
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        yield session


def _rows_for(metric_key: str, sector: SectorInternal) -> list[object]:
    return [r for r in build_threshold_rows() if r.sector is sector and r.metric_key == metric_key]


# ── Constructor puro ──────────────────────────────────────────────────


def test_cardinalidad() -> None:
    """Al menos una fila por (sector × norma × métrica con banda).

    Puede haber MÁS: un perfil que apaga una métrica sin banda absoluta —A2 en
    una eléctrica— le fabrica su fila para que la exención tenga dónde viajar.
    """
    rows = build_threshold_rows()
    minimo = len(SectorInternal) * len(AccountingStd) * len(ALL_DEFAULT_THRESHOLDS)
    assert len(rows) >= minimo
    assert len({(r.sector, r.accounting_std, r.metric_key) for r in rows}) == len(rows)


def test_forenses_no_aplican_en_financieras() -> None:
    financials = _rows_for(_FORENSIC_KEY, SectorInternal.FINANCIALS)
    technology = _rows_for(_FORENSIC_KEY, SectorInternal.TECHNOLOGY)
    assert financials and all(not r.applies for r in financials)  # type: ignore[attr-defined]
    assert technology and all(r.applies for r in technology)  # type: ignore[attr-defined]


def test_todo_lo_apagado_dice_por_que() -> None:
    """La razón es lo que separa un «no aplica» de un fallo de cálculo.

    Sin ella la pantalla enseña un número gris, el usuario lee «no se ha podido
    calcular» y el diagnóstico se va a las cuentas de la empresa cuando el
    problema es que la vara no sirve para ese sector.
    """
    for row in build_threshold_rows():
        if not row.applies:
            assert row.not_applicable_reason, f"{row.sector}/{row.metric_key} apagada sin motivo"


def test_el_nucleo_del_juicio_bancario_sobrevive() -> None:
    """Lo que se conserva en una financiera es deliberado, no un olvido.

    Si esta lista se vacía, el informe de un banco deja de tener veredicto y
    nadie se entera: todas sus métricas saldrían grises con una explicación
    razonable.
    """
    sobreviven = {"R5", "R6", "S3", "D1", "T2", "T3", "Q1", "Q5", "S8"}
    for key in sobreviven:
        rows = _rows_for(key, SectorInternal.FINANCIALS)
        assert rows and all(r.applies for r in rows), f"{key} debería seguir aplicando en un banco"  # type: ignore[attr-defined]


def test_la_banda_bancaria_de_roa_no_es_la_industrial() -> None:
    """Un banco con ROA del 1% es un buen banco; con la vara industrial (2%
    ámbar, 5% verde) saldría en rojo permanente."""
    bank = resolve_thresholds(SectorInternal.FINANCIALS, AccountingStd.GAAP, is_financial=True)
    generic = ALL_DEFAULT_THRESHOLDS["R6"]
    assert bank["R6"].low_alarm == Decimal("0.007")
    assert bank["R6"].low_ok == Decimal("0.012")
    assert generic.low_alarm == Decimal("0.02")
    assert bank["R6"].band_for(Decimal("0.010")) == "caution"
    assert generic.band_for(Decimal("0.010")) == "stressed"


def test_la_hermana_derivada_se_mueve_con_la_que_se_escribe() -> None:
    """S6 es S2 medida con caja, y L2 es L1 sin inventario: si un sector mueve
    una y la otra se queda en el corte genérico, las dos dejan de contar la misma
    historia sobre la misma empresa."""
    utility = resolve_thresholds(SectorInternal.UTILITIES, AccountingStd.GAAP)
    assert utility["S6"].low_alarm != ALL_DEFAULT_THRESHOLDS["S6"].low_alarm
    assert utility["L2"].low_alarm != ALL_DEFAULT_THRESHOLDS["L2"].low_alarm
    # Y el factor es el mismo que el de su fuente (2/3 sobre el corte de alarma).
    factor = utility["S2"].low_alarm / ALL_DEFAULT_THRESHOLDS["S2"].low_alarm  # type: ignore[operator]
    esperado = (ALL_DEFAULT_THRESHOLDS["S6"].low_alarm * factor).quantize(Decimal("0.01"))  # type: ignore[operator]
    assert utility["S6"].low_alarm == esperado


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


def test_los_perfiles_solo_nombran_metricas_del_catalogo() -> None:
    """Una clave con typo apagaría una métrica que no existe y dejaría encendida
    la que se quería apagar, sin que nada avise."""
    for key in FINANCIALS_NOT_APPLICABLE:
        assert key in {d for d in _catalog_keys()}, f"'{key}' no está en el catálogo del engine"


def _catalog_keys() -> set[str]:
    from app.modules.investment.analysis.engine.catalog import ALL_METRIC_KEYS

    return set(ALL_METRIC_KEYS)


# ── Hash ──────────────────────────────────────────────────────────────


def test_hash_estable_y_sensible() -> None:
    specs = dict(ALL_DEFAULT_THRESHOLDS)
    h1 = thresholds_hash(specs)
    assert len(h1) == 64
    assert thresholds_hash(dict(ALL_DEFAULT_THRESHOLDS)) == h1

    key = next(iter(specs))
    mutated = dict(specs)
    mutated[key] = replace(
        specs[key], applies=not specs[key].applies, not_applicable_reason="prueba"
    )
    assert thresholds_hash(mutated) != h1


def test_dos_sectores_no_comparten_hash() -> None:
    """La calibración sectorial tiene que ser visible en la reproducibilidad del
    run: si el hash no se mueve, dos análisis con varas distintas dirían haber
    usado la misma."""
    utility = thresholds_hash(resolve_thresholds(SectorInternal.UTILITIES, AccountingStd.GAAP))
    tech = thresholds_hash(resolve_thresholds(SectorInternal.TECHNOLOGY, AccountingStd.GAAP))
    assert utility != tech


# ── Seed + carga (BD) ─────────────────────────────────────────────────


async def test_seed_es_idempotente(db: AsyncSession) -> None:
    first = await sync_thresholds(db)
    await db.commit()
    assert first.inserted == _EXPECTED and first.updated == 0
    second = await sync_thresholds(db)
    await db.commit()
    assert second.changed == 0
    assert await repo.count(db) == _EXPECTED


async def test_load_thresholds_tras_seed(db: AsyncSession) -> None:
    await sync_thresholds(db)
    await db.commit()

    financials = await load_thresholds(
        db, SectorInternal.FINANCIALS, AccountingStd.GAAP, is_financial=True
    )
    technology = await load_thresholds(db, SectorInternal.TECHNOLOGY, AccountingStd.GAAP)

    assert financials[_FORENSIC_KEY].applies is False
    assert financials[_FORENSIC_KEY].not_applicable_reason
    assert technology[_FORENSIC_KEY].applies is True


async def test_load_thresholds_sin_seed_ya_trae_la_calibracion(db: AsyncSession) -> None:
    """Una base sin sembrar tiene que comportarse igual que una sembrada.

    Antes caía al catálogo genérico, así que un banco se juzgaba con cortes
    industriales por el camino de que su fila no existiera — la variante exacta
    del defecto de PHASE-44.18, donde una exención razonada era inerte porque
    dependía de una fila.
    """
    resolved = await load_thresholds(
        db, SectorInternal.FINANCIALS, AccountingStd.GAAP, is_financial=True
    )
    assert resolved[_FORENSIC_KEY].applies is False
    assert resolved["R6"].low_alarm == Decimal("0.007")


async def test_seed_on_startup_siembra_y_luego_no_duplica(test_engine) -> None:  # type: ignore[no-untyped-def]
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    first = await seed_on_startup(factory)
    second = await seed_on_startup(factory)
    assert first.inserted == _EXPECTED
    assert second.changed == 0


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
                not_applicable_reason=row.not_applicable_reason,
            )
        )
    await db.flush()
    antes = await repo.existing_keys(db)
    assert not any(key in llegan_despues for _, _, key in antes)

    outcome = await sync_thresholds(db)

    despues = await repo.existing_keys(db)
    assert llegan_despues <= {key for _, _, key in despues}
    assert outcome.inserted == len(
        [r for r in build_threshold_rows() if r.metric_key in llegan_despues]
    )
    assert outcome.updated == 0, "sembrar lo que falta no debe tocar lo demás"


async def test_una_recalibracion_llega_a_una_base_que_ya_existia(db: AsyncSession) -> None:
    """El defecto SIMÉTRICO al de PHASE-44.18, y por el que el arranque volvió a
    actualizar (PHASE-44.21).

    Con sembrado sólo-inserción, una calibración nueva llega a las bases recién
    creadas y **nunca** a la que lleva meses funcionando — que es justo la que se
    usa. Es seguro porque cada run persiste su `thresholds_used` desde
    PHASE-44.9: un análisis viejo se sigue explicando con SU vara.
    """
    await sync_thresholds(db)
    await db.commit()
    key = "S4"
    row = await repo.get_one(db, SectorInternal.UTILITIES, AccountingStd.GAAP, key)
    assert row is not None
    row.high_ok = Decimal("999")
    await db.flush()

    outcome = await sync_thresholds(db)

    assert outcome.updated == 1 and outcome.inserted == 0
    corregida = await repo.get_one(db, SectorInternal.UTILITIES, AccountingStd.GAAP, key)
    assert corregida is not None
    assert corregida.high_ok == Decimal("4")
