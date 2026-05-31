"""Tests del service de currency: convert (exact, previous, missing,
same), composición no-EUR via EUR, redondeo banker's."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.currency import repository, service
from app.modules.currency.exceptions import FrankfurterUnavailableError


async def _session(test_engine):  # type: ignore[no-untyped-def]
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    return factory()


async def _seed_eur_to_usd(db, rate_date: date, rate: str) -> None:  # type: ignore[no-untyped-def]
    await repository.upsert_rates(db, [(rate_date, "EUR", "USD", Decimal(rate), "test")])


async def _seed_rate(db, rate_date: date, quote: str, rate: str) -> None:  # type: ignore[no-untyped-def]
    await repository.upsert_rates(db, [(rate_date, "EUR", quote, Decimal(rate), "test")])


async def test_cross_rate_reanchors_both_legs_to_common_older_date(test_engine) -> None:  # type: ignore[no-untyped-def]
    """AUDIT-2026-05 — una cross-rate real (USD→GBP) no debe componer la
    tasa USD fresca de un día con la GBP rancia de otro. Cuando las dos
    piernas resuelven a fechas distintas, ambas se re-anclan a la fecha
    común más antigua.

    Sembrado: EUR→USD en 04-01/03/05; EUR→GBP sólo en 04-01/03.
    convert(USD→GBP, at=04-05): USD encaja exacto el 04-05 (1.20), GBP
    cae al 04-03 (0.85). Sin el fix compondría 0.85/1.20 con la USD del
    04-05; con el fix re-ancla USD al 04-03 (1.15) → 0.85/1.15 ≈ 0.7391,
    rate_date=04-03 y fallback='previous'.
    """
    async with await _session(test_engine) as db:
        await _seed_rate(db, date(2026, 4, 1), "USD", "1.10")
        await _seed_rate(db, date(2026, 4, 3), "USD", "1.15")
        await _seed_rate(db, date(2026, 4, 5), "USD", "1.20")
        await _seed_rate(db, date(2026, 4, 1), "GBP", "0.80")
        await _seed_rate(db, date(2026, 4, 3), "GBP", "0.85")
        await db.commit()

        result = await service.convert(
            db,
            amount=Decimal("100"),
            from_currency="USD",
            to_currency="GBP",
            at_date=date(2026, 4, 5),
        )
        # Re-anclado al 04-03: USD=1.15, GBP=0.85 → 0.85/1.15 ≈ 0.73913
        assert result.rate_date == date(2026, 4, 3)
        assert result.fallback == "previous"
        assert Decimal("0.738") <= result.rate <= Decimal("0.740"), result.rate


async def test_convert_same_currency_returns_amount_unchanged(test_engine) -> None:  # type: ignore[no-untyped-def]
    async with await _session(test_engine) as db:
        result = await service.convert(
            db,
            amount=Decimal("12.34"),
            from_currency="EUR",
            to_currency="EUR",
            at_date=date(2026, 4, 1),
        )
        assert result.amount == Decimal("12.34")
        assert result.rate == Decimal("1")
        assert result.fallback == "same"


async def test_convert_eur_to_usd_exact(test_engine) -> None:  # type: ignore[no-untyped-def]
    async with await _session(test_engine) as db:
        await _seed_eur_to_usd(db, date(2026, 4, 1), "1.10")
        await db.commit()

        result = await service.convert(
            db,
            amount=Decimal("100"),
            from_currency="EUR",
            to_currency="USD",
            at_date=date(2026, 4, 1),
        )
        assert result.amount == Decimal("110.00")
        assert result.fallback == "exact"
        assert result.rate_date == date(2026, 4, 1)


async def test_convert_usd_to_eur_inverts_rate(test_engine) -> None:  # type: ignore[no-untyped-def]
    """USD→EUR es 1/rate(EUR→USD)."""
    async with await _session(test_engine) as db:
        await _seed_eur_to_usd(db, date(2026, 4, 1), "1.25")
        await db.commit()

        result = await service.convert(
            db,
            amount=Decimal("100"),
            from_currency="USD",
            to_currency="EUR",
            at_date=date(2026, 4, 1),
        )
        # 100 USD * (1 / 1.25) = 80 EUR
        assert result.amount == Decimal("80.00")
        assert result.fallback == "exact"


async def test_convert_usd_to_gbp_via_eur(test_engine) -> None:  # type: ignore[no-untyped-def]
    """Composición no-EUR vía EUR: USD→EUR→GBP."""
    async with await _session(test_engine) as db:
        await repository.upsert_rates(
            db,
            [
                (date(2026, 4, 1), "EUR", "USD", Decimal("1.10"), "test"),
                (date(2026, 4, 1), "EUR", "GBP", Decimal("0.85"), "test"),
            ],
        )
        await db.commit()

        result = await service.convert(
            db,
            amount=Decimal("110"),
            from_currency="USD",
            to_currency="GBP",
            at_date=date(2026, 4, 1),
        )
        # 110 USD = 100 EUR (110 / 1.10) = 85 GBP (100 * 0.85)
        assert result.amount == Decimal("85.00")
        assert result.fallback == "exact"


async def test_convert_uses_previous_when_exact_missing(test_engine) -> None:  # type: ignore[no-untyped-def]
    async with await _session(test_engine) as db:
        await _seed_eur_to_usd(db, date(2026, 4, 1), "1.10")
        await db.commit()

        result = await service.convert(
            db,
            amount=Decimal("100"),
            from_currency="EUR",
            to_currency="USD",
            at_date=date(2026, 4, 5),
        )
        assert result.amount == Decimal("110.00")
        assert result.fallback == "previous"
        assert result.rate_date == date(2026, 4, 1)


async def test_convert_missing_returns_unchanged_amount(test_engine) -> None:  # type: ignore[no-untyped-def]
    async with await _session(test_engine) as db:
        result = await service.convert(
            db,
            amount=Decimal("100"),
            from_currency="USD",
            to_currency="EUR",
            at_date=date(2026, 4, 1),
        )
        assert result.amount == Decimal("100.00")
        assert result.fallback == "missing"
        assert result.rate == Decimal("1")


async def test_convert_rounds_with_banker_s_rounding(test_engine) -> None:  # type: ignore[no-untyped-def]
    """Half-to-even: 1.005 → 1.00 (no 1.01) y 1.015 → 1.02."""
    async with await _session(test_engine) as db:
        await _seed_eur_to_usd(db, date(2026, 4, 1), "1.0050")
        await db.commit()
        # 1 EUR * 1.0050 = 1.0050 → 1.00 (half-to-even)
        result = await service.convert(
            db,
            amount=Decimal("1"),
            from_currency="EUR",
            to_currency="USD",
            at_date=date(2026, 4, 1),
        )
        assert result.amount == Decimal("1.00")

    async with await _session(test_engine) as db:
        await _seed_eur_to_usd(db, date(2026, 4, 1), "1.0150")
        await db.commit()
        result = await service.convert(
            db,
            amount=Decimal("1"),
            from_currency="EUR",
            to_currency="USD",
            at_date=date(2026, 4, 1),
        )
        assert result.amount == Decimal("1.02")


async def test_refresh_rates_persists_fetched(test_engine) -> None:  # type: ignore[no-untyped-def]
    async with await _session(test_engine) as db:
        with patch(
            "app.modules.currency.client.fetch_rates",
            new_callable=AsyncMock,
            return_value={"USD": Decimal("1.10"), "GBP": Decimal("0.85")},
        ):
            inserted = await service.refresh_rates(
                db, target_date=date(2026, 4, 1), quotes=["USD", "GBP"]
            )
        await db.commit()

        assert inserted == 2
        rate = await repository.get_rate(db, rate_date=date(2026, 4, 1), base="EUR", quote="USD")
        assert rate is not None
        assert rate.rate == Decimal("1.10")
        assert rate.source == "frankfurter"


async def test_refresh_rates_propagates_unavailable(test_engine) -> None:  # type: ignore[no-untyped-def]
    """Si frankfurter falla, refresh_rates propaga la excepción."""
    async with await _session(test_engine) as db:
        with (
            patch(
                "app.modules.currency.client.fetch_rates",
                new_callable=AsyncMock,
                side_effect=FrankfurterUnavailableError("offline"),
            ),
            pytest.raises(FrankfurterUnavailableError),
        ):
            await service.refresh_rates(db, target_date=date(2026, 4, 1), quotes=["USD"])


async def test_ensure_rate_short_circuits_when_existing(test_engine) -> None:  # type: ignore[no-untyped-def]
    """Si ya hay tasa, ensure_rate no llama al cliente."""
    async with await _session(test_engine) as db:
        await _seed_eur_to_usd(db, date(2026, 4, 1), "1.10")
        await db.commit()

        with patch(
            "app.modules.currency.client.fetch_rates",
            new_callable=AsyncMock,
        ) as mock:
            ok = await service.ensure_rate(db, quote="USD", at_date=date(2026, 4, 1))
        assert ok is True
        mock.assert_not_called()


async def test_ensure_rate_returns_false_on_network_error(test_engine) -> None:  # type: ignore[no-untyped-def]
    async with await _session(test_engine) as db:
        with patch(
            "app.modules.currency.client.fetch_rates",
            new_callable=AsyncMock,
            side_effect=FrankfurterUnavailableError("offline"),
        ):
            ok = await service.ensure_rate(db, quote="USD", at_date=date(2026, 4, 1))
        assert ok is False
