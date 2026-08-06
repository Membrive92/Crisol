"""Tests del cliente HTTP de currency contra frankfurter.app — todo
mockeado, no se hace ninguna petición real."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.modules.currency import client
from app.modules.currency.exceptions import (
    FrankfurterInvalidResponseError,
    FrankfurterUnavailableError,
)

#: Este módulo prueba el cliente HTTP en sí, así que el bloqueo global de
#: `fetch_rates` (conftest) le parchearía justo lo que quiere verificar. No hay
#: red: `httpx` está mockeado dentro de cada test.
pytestmark = pytest.mark.real_fx_client


def _build_mock_client(*, status: int = 200, body: dict | None = None) -> MagicMock:
    """Construye un AsyncClient mockeado con un .get que devuelve body."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status
    response.json.return_value = body or {}

    if status >= 400:
        # raise_for_status debe lanzar HTTPStatusError.
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "boom", request=MagicMock(spec=httpx.Request), response=response
        )
    else:
        response.raise_for_status.return_value = None

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


async def test_fetch_rates_parses_decimal() -> None:
    body = {
        "amount": 1.0,
        "base": "EUR",
        "date": "2026-04-01",
        "rates": {"USD": 1.0987654, "GBP": 0.8519},
    }
    with patch(
        "app.modules.currency.client.httpx.AsyncClient",
        return_value=_build_mock_client(body=body),
    ):
        result = await client.fetch_rates(target_date=date(2026, 4, 1), quotes=["USD", "GBP"])

    assert result == {"USD": Decimal("1.0987654"), "GBP": Decimal("0.8519")}


async def test_fetch_rates_skips_base_in_quotes() -> None:
    """Pedir EUR como quote (con base EUR) no debe llamar a la API."""
    with patch(
        "app.modules.currency.client.httpx.AsyncClient",
    ) as mock_class:
        result = await client.fetch_rates(target_date=date(2026, 4, 1), quotes=["EUR"])
    assert result == {}
    mock_class.assert_not_called()


async def test_fetch_rates_raises_on_http_error() -> None:
    with (
        patch(
            "app.modules.currency.client.httpx.AsyncClient",
            return_value=_build_mock_client(status=502, body={}),
        ),
        pytest.raises(FrankfurterUnavailableError),
    ):
        await client.fetch_rates(target_date=date(2026, 4, 1), quotes=["USD"])


async def test_fetch_rates_raises_on_missing_rates_field() -> None:
    body = {"amount": 1.0, "base": "EUR", "date": "2026-04-01"}
    with (
        patch(
            "app.modules.currency.client.httpx.AsyncClient",
            return_value=_build_mock_client(body=body),
        ),
        pytest.raises(FrankfurterInvalidResponseError),
    ):
        await client.fetch_rates(target_date=date(2026, 4, 1), quotes=["USD"])


async def test_fetch_rates_raises_on_invalid_rate_value() -> None:
    body = {"rates": {"USD": "not-a-number"}}
    with (
        patch(
            "app.modules.currency.client.httpx.AsyncClient",
            return_value=_build_mock_client(body=body),
        ),
        pytest.raises(FrankfurterInvalidResponseError),
    ):
        await client.fetch_rates(target_date=date(2026, 4, 1), quotes=["USD"])
