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


# --- Las dos políticas de frescura -------------------------------------------
#
# `ensure_rates_for_dates` (laxa) y `ensure_exact_rates_for_dates` (estricta)
# difieren SÓLO en el canario, y esa diferencia es la que decide si se pide algo.
# Los dos tests siguientes son hermanos a propósito: sembrado idéntico, veredicto
# opuesto. Si alguien "unifica" las dos funciones, uno de los dos cae.

_SEED_DAY = date(2026, 4, 1)
_SIX_DAYS_LATER = date(2026, 4, 7)


async def test_ensure_exact_pide_aunque_haya_una_tasa_dentro_de_la_ventana(  # type: ignore[no-untyped-def]
    test_engine,
) -> None:
    """Regresión del cron muerto (2026-08-07).

    Con una tasa de hace 6 días —dentro de la ventana de fallback de 14— la
    política laxa se da por satisfecha y no pide nada. Ése era el defecto: el
    cron nocturno llevaba desde PHASE-11.1 callado hasta que la última tasa
    cumplía dos semanas, y por eso una compra del 24 de julio se valoró con el
    tipo del 18.
    """
    async with await _session(test_engine) as db:
        await _seed_rate(db, _SEED_DAY, "USD", "1.10")
        await db.commit()

        asked: list[date] = []

        async def _fake_fetch(*, target_date, base, quotes, timeout=None):  # type: ignore[no-untyped-def]
            asked.append(target_date)
            return {q: Decimal("1.20") for q in quotes}

        with patch("app.modules.currency.client.fetch_rates", side_effect=_fake_fetch):
            fetched = await service.ensure_exact_rates_for_dates(
                db, [_SIX_DAYS_LATER], quotes=["USD"]
            )

        assert fetched == 1
        assert asked == [_SIX_DAYS_LATER]
        stored = await repository.get_rate(db, rate_date=_SIX_DAYS_LATER, base="EUR", quote="USD")
        assert stored is not None, "la tasa del día no se persistió"
        assert stored.rate == Decimal("1.20")


async def test_ensure_laxa_sigue_conformandose_con_la_ventana(test_engine) -> None:  # type: ignore[no-untyped-def]
    """La política laxa NO cambia: es la correcta para rellenar fechas pasadas.

    Mismo sembrado que el test anterior y veredicto opuesto. Está escrito para
    que quede constancia de que la diferencia es deliberada: si esta función
    empezara a pedir, rellenar 50 fechas históricas serían 50 round-trips.
    """
    async with await _session(test_engine) as db:
        await _seed_rate(db, _SEED_DAY, "USD", "1.10")
        await db.commit()

        asked: list[date] = []

        async def _fake_fetch(*, target_date, base, quotes, timeout=None):  # type: ignore[no-untyped-def]
            asked.append(target_date)
            return {q: Decimal("1.20") for q in quotes}

        with patch("app.modules.currency.client.fetch_rates", side_effect=_fake_fetch):
            fetched = await service.ensure_rates_for_dates(db, [_SIX_DAYS_LATER], quotes=["USD"])

        assert fetched == 0
        assert asked == []


async def test_ensure_exact_no_gasta_peticion_si_ya_tiene_la_del_dia(test_engine) -> None:  # type: ignore[no-untyped-def]
    """Y con la tasa exacta ya en BD no pide nada — el cron diario no machaca."""
    async with await _session(test_engine) as db:
        await _seed_rate(db, _SIX_DAYS_LATER, "USD", "1.15")
        await db.commit()

        with patch(
            "app.modules.currency.client.fetch_rates",
            new_callable=AsyncMock,
            side_effect=AssertionError("no debería pedir nada"),
        ):
            fetched = await service.ensure_exact_rates_for_dates(
                db, [_SIX_DAYS_LATER], quotes=["USD"]
            )

        assert fetched == 0


async def test_ensure_exact_traga_el_fallo_de_frankfurter(test_engine) -> None:  # type: ignore[no-untyped-def]
    """Un domingo el BCE no publica: "sin tasa de hoy" es lo NORMAL, no un error.

    El job corre desatendido; propagar aquí tiraría el cron entero por algo que
    pasa 104 días al año.
    """
    async with await _session(test_engine) as db:
        with patch(
            "app.modules.currency.client.fetch_rates",
            new_callable=AsyncMock,
            side_effect=FrankfurterUnavailableError("offline"),
        ):
            fetched = await service.ensure_exact_rates_for_dates(
                db, [_SIX_DAYS_LATER], quotes=["USD"]
            )

        assert fetched == 0
