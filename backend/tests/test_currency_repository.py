"""Tests del repository de currency: lookup exacto + fallback hacia atrás."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.currency import repository


async def _session(test_engine):  # type: ignore[no-untyped-def]
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    return factory()


async def test_get_rate_exact(test_engine) -> None:  # type: ignore[no-untyped-def]
    async with await _session(test_engine) as db:
        await repository.upsert_rates(
            db,
            [(date(2026, 4, 1), "EUR", "USD", Decimal("1.10"), "test")],
        )
        await db.commit()

        rate = await repository.get_rate(
            db, rate_date=date(2026, 4, 1), base="EUR", quote="USD"
        )
        assert rate is not None
        assert rate.rate == Decimal("1.10")


async def test_get_rate_returns_none_for_missing(test_engine) -> None:  # type: ignore[no-untyped-def]
    async with await _session(test_engine) as db:
        rate = await repository.get_rate(
            db, rate_date=date(2026, 4, 1), base="EUR", quote="USD"
        )
        assert rate is None


async def test_fallback_returns_previous_within_window(test_engine) -> None:  # type: ignore[no-untyped-def]
    async with await _session(test_engine) as db:
        # La tasa real está 3 días antes de la pedida.
        await repository.upsert_rates(
            db,
            [(date(2026, 4, 10), "EUR", "USD", Decimal("1.12"), "test")],
        )
        await db.commit()

        rate = await repository.get_rate_with_fallback(
            db, rate_date=date(2026, 4, 13), base="EUR", quote="USD"
        )
        assert rate is not None
        assert rate.rate_date == date(2026, 4, 10)
        assert rate.rate == Decimal("1.12")


async def test_fallback_returns_none_outside_window(test_engine) -> None:  # type: ignore[no-untyped-def]
    async with await _session(test_engine) as db:
        # 30 días antes — fuera de la ventana de 14.
        await repository.upsert_rates(
            db,
            [(date(2026, 3, 1), "EUR", "USD", Decimal("1.08"), "test")],
        )
        await db.commit()

        rate = await repository.get_rate_with_fallback(
            db, rate_date=date(2026, 4, 1), base="EUR", quote="USD"
        )
        assert rate is None


async def test_upsert_replaces_existing_rate(test_engine) -> None:  # type: ignore[no-untyped-def]
    """`upsert_rates` debe reescribir la tasa cuando la PK ya existe."""
    async with await _session(test_engine) as db:
        await repository.upsert_rates(
            db,
            [(date(2026, 4, 1), "EUR", "USD", Decimal("1.10"), "snapshot")],
        )
        await repository.upsert_rates(
            db,
            [(date(2026, 4, 1), "EUR", "USD", Decimal("1.15"), "frankfurter")],
        )
        await db.commit()

        rate = await repository.get_rate(
            db, rate_date=date(2026, 4, 1), base="EUR", quote="USD"
        )
        assert rate is not None
        assert rate.rate == Decimal("1.15")
        assert rate.source == "frankfurter"


async def test_list_rates_for_date(test_engine) -> None:  # type: ignore[no-untyped-def]
    async with await _session(test_engine) as db:
        await repository.upsert_rates(
            db,
            [
                (date(2026, 4, 1), "EUR", "USD", Decimal("1.10"), "test"),
                (date(2026, 4, 1), "EUR", "GBP", Decimal("0.85"), "test"),
                (date(2026, 4, 1), "EUR", "JPY", Decimal("172.5"), "test"),
                # Otra fecha para confirmar que el filtro funciona.
                (date(2026, 4, 2), "EUR", "USD", Decimal("1.11"), "test"),
            ],
        )
        await db.commit()

        rows = await repository.list_rates_for_date(
            db, rate_date=date(2026, 4, 1), base="EUR"
        )
        quotes = {r.quote for r in rows}
        assert quotes == {"USD", "GBP", "JPY"}


