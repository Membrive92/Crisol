"""Cliente HTTP async contra frankfurter.app.

frankfurter.app es un proxy open-source del feed diario del Banco
Central Europeo. No requiere API key, no impone user-agent, no tracea
peticiones — encaja con el principio "los datos del usuario nunca
salen del equipo": las peticiones contienen sólo fechas y códigos de
moneda públicos.

Este es el ÚNICO archivo del proyecto que conoce la URL de
frankfurter. Ningún otro módulo importa httpx para hablar con esa
API; usan `currency.service` como interfaz tipada.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

import httpx

from app.core.config import settings
from app.modules.currency.exceptions import (
    FrankfurterInvalidResponseError,
    FrankfurterUnavailableError,
)


def _format_path(target_date: date, base: str, quotes: Iterable[str]) -> tuple[str, dict[str, str]]:
    """Construye `(path, params)` para `GET /{date}?from=&to=`.

    El endpoint `latest` se usa cuando la fecha pedida es la actual
    (frankfurter no acepta fechas futuras). Lo decide el caller.
    """
    quotes_csv = ",".join(sorted({q.upper() for q in quotes}))
    return f"/{target_date.isoformat()}", {"from": base, "to": quotes_csv}


async def fetch_rates(
    *,
    target_date: date,
    base: str = "EUR",
    quotes: Iterable[str],
) -> dict[str, Decimal]:
    """Pide las tasas `base→quote` para una fecha concreta.

    Devuelve un diccionario `{quote: rate}` con `Decimal` (no `float`)
    para evitar pérdida de precisión. Si frankfurter no puede dar la
    fecha exacta (fin de semana, festivo), responde con la fecha
    publicada más cercana — devolvemos las tasas tal cual y dejamos al
    caller decidir si guardarlas para `target_date` o para la fecha
    devuelta. Frankfurter expone esa fecha en el campo `date`.

    Esta función no escribe en BD: es responsabilidad del caller
    (`service.refresh_rates`).

    Raises:
        FrankfurterUnavailableError: la API no responde / 5xx.
        FrankfurterInvalidResponseError: payload inesperado.
    """
    quotes_list = sorted({q.upper() for q in quotes if q.upper() != base.upper()})
    if not quotes_list:
        return {}

    path, params = _format_path(target_date, base.upper(), quotes_list)

    try:
        async with httpx.AsyncClient(
            base_url=settings.frankfurter_base_url,
            timeout=float(settings.frankfurter_timeout_seconds),
            follow_redirects=True,
        ) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            data = response.json()
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        raise FrankfurterUnavailableError("frankfurter no responde") from e
    except httpx.ReadTimeout as e:
        raise FrankfurterUnavailableError("Timeout leyendo frankfurter") from e
    except httpx.HTTPStatusError as e:
        raise FrankfurterUnavailableError(
            f"frankfurter error {e.response.status_code}"
        ) from e

    if not isinstance(data, dict):
        raise FrankfurterInvalidResponseError(
            f"Payload no es un objeto JSON: {data!r:.100}"
        )
    raw_rates = data.get("rates")
    if not isinstance(raw_rates, dict) or not raw_rates:
        raise FrankfurterInvalidResponseError(
            f"Payload sin tasas válidas: {data!r}"
        )

    out: dict[str, Decimal] = {}
    for quote, value in raw_rates.items():
        try:
            # Convertimos vía str para evitar el ruido binario de float.
            out[quote.upper()] = Decimal(str(value))
        except (ArithmeticError, TypeError, ValueError) as e:
            raise FrankfurterInvalidResponseError(
                f"Tasa inválida para {quote}: {value!r}"
            ) from e
    return out


async def fetch_actual_rate_date(
    *, target_date: date, base: str = "EUR", quote: str = "USD"
) -> date | None:
    """Devuelve la fecha real publicada por frankfurter para `target_date`.

    Útil para conocer qué fecha publicó el ECB cuando la pedida cae en
    fin de semana o festivo. Devuelve `None` si la API falla — caller
    puede caer en otro fallback.
    """
    try:
        async with httpx.AsyncClient(
            base_url=settings.frankfurter_base_url,
            timeout=float(settings.frankfurter_timeout_seconds),
            follow_redirects=True,
        ) as client:
            response = await client.get(
                f"/{target_date.isoformat()}",
                params={"from": base.upper(), "to": quote.upper()},
            )
            response.raise_for_status()
            data = response.json()
            actual = data.get("date")
            if isinstance(actual, str):
                return date.fromisoformat(actual)
            return None
    except (httpx.HTTPError, ValueError):
        return None
