"""Tests del scheduler nocturno de tasas (PHASE-11.1)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.core import scheduler as scheduler_module
from app.core.config import settings


def test_create_scheduler_returns_none_when_disabled() -> None:
    """Con el flag off no se crea scheduler — útil para tests/cron externo."""
    with patch.object(settings, "enable_currency_cron", False):
        assert scheduler_module.create_scheduler() is None


def test_create_scheduler_registers_currency_job_when_enabled() -> None:
    """Con el flag on, el job de refresh de tasas queda registrado y el
    scheduler NO se arranca (la responsabilidad de start() es del lifespan)."""
    with patch.object(settings, "enable_currency_cron", True):
        scheduler = scheduler_module.create_scheduler()
    assert scheduler is not None
    job = scheduler.get_job(scheduler_module.CURRENCY_REFRESH_JOB_ID)
    assert job is not None
    # `create_scheduler()` no arranca — la responsabilidad de start()
    # vive en el lifespan de FastAPI. Llamarlo aquí en frío sin loop
    # corriendo no aplica.
    assert not scheduler.running


@pytest.mark.asyncio
async def test_refresh_currency_rates_job_calls_ensure_with_today_and_yesterday() -> None:
    """El job invoca `ensure_rates_for_dates([yesterday, today])` con fechas UTC.

    Mockeamos `ensure_rates_for_dates` y el engine para evitar tocar BD —
    aquí sólo verificamos el contrato de fechas.
    """
    today_fake = date(2026, 5, 5)
    yesterday_fake = today_fake - timedelta(days=1)

    mock_ensure = AsyncMock(return_value=2)

    with (
        patch.object(scheduler_module, "_today_utc", return_value=today_fake),
        patch.object(scheduler_module.currency_service, "ensure_rates_for_dates", mock_ensure),
        patch.object(scheduler_module, "create_async_engine") as mock_engine_factory,
    ):
        # Stub mínimo del engine: dispose() debe ser awaitable.
        mock_engine_factory.return_value.dispose = AsyncMock()
        await scheduler_module.refresh_currency_rates_job()

    assert mock_ensure.await_count == 1
    args, _ = mock_ensure.await_args
    # args[0] es el `db` (sessionmaker context). args[1] es la lista de fechas.
    dates_arg = args[1]
    assert list(dates_arg) == [yesterday_fake, today_fake]


@pytest.mark.asyncio
async def test_refresh_currency_rates_job_swallows_exceptions() -> None:
    """Errores del job no deben propagarse — un fallo no tira el scheduler."""
    mock_ensure = AsyncMock(side_effect=RuntimeError("boom"))

    with (
        patch.object(scheduler_module, "_today_utc", return_value=date(2026, 5, 5)),
        patch.object(scheduler_module.currency_service, "ensure_rates_for_dates", mock_ensure),
        patch.object(scheduler_module, "create_async_engine") as mock_engine_factory,
    ):
        mock_engine_factory.return_value.dispose = AsyncMock()
        # No debe lanzar — el except interno traga.
        await scheduler_module.refresh_currency_rates_job()


def test_today_utc_uses_utc_not_local_tz() -> None:
    """`_today_utc()` debe usar UTC siempre — coherente con el cron timezone."""
    today_utc = scheduler_module._today_utc()
    expected = datetime.now(UTC).date()
    assert today_utc == expected
