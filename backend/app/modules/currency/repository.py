"""Queries a DB del módulo currency.

EUR es la base canónica almacenada — `base` está en el schema porque
podríamos cambiarla en el futuro, pero por ahora todas las filas
tienen `base='EUR'`. Las funciones aquí no asumen ese invariante;
filtran por `base` explícitamente.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.currency.models import ExchangeRate

# Ventana de fallback para la búsqueda hacia atrás de la última tasa
# conocida. 14 días cubre fines de semana, festivos, e incluso periodos
# vacacionales bancarios sin tener que llamar a la fuente externa.
_FALLBACK_WINDOW_DAYS = 14


async def get_rate(
    db: AsyncSession, *, rate_date: date, base: str, quote: str
) -> ExchangeRate | None:
    """Devuelve la tasa exacta para `(rate_date, base, quote)` o None."""
    result = await db.execute(
        select(ExchangeRate).where(
            ExchangeRate.rate_date == rate_date,
            ExchangeRate.base == base,
            ExchangeRate.quote == quote,
        )
    )
    return result.scalar_one_or_none()


async def get_rate_with_fallback(
    db: AsyncSession, *, rate_date: date, base: str, quote: str
) -> ExchangeRate | None:
    """Devuelve la tasa para esa fecha o la última conocida en una ventana.

    Si la tasa exacta existe, la devuelve. Si no, busca la última tasa
    estrictamente anterior dentro de `_FALLBACK_WINDOW_DAYS` días. Si no
    hay ninguna, devuelve None — el caller decide cómo señalizar el
    fallo.
    """
    floor = rate_date - timedelta(days=_FALLBACK_WINDOW_DAYS)
    result = await db.execute(
        select(ExchangeRate)
        .where(
            ExchangeRate.base == base,
            ExchangeRate.quote == quote,
            ExchangeRate.rate_date >= floor,
            ExchangeRate.rate_date <= rate_date,
        )
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_rates_for_date(
    db: AsyncSession, *, rate_date: date, base: str = "EUR"
) -> list[ExchangeRate]:
    """Lista todas las tasas para una fecha y base concretas."""
    result = await db.execute(
        select(ExchangeRate)
        .where(
            ExchangeRate.rate_date == rate_date,
            ExchangeRate.base == base,
        )
        .order_by(ExchangeRate.quote)
    )
    return list(result.scalars().all())


async def upsert_rates(
    db: AsyncSession,
    rows: Iterable[tuple[date, str, str, Decimal, str]],
) -> int:
    """Inserta o actualiza un lote de tasas.

    `rows` es un iterable de `(rate_date, base, quote, rate, source)`.
    Si el `(rate_date, base, quote)` ya existe, se actualiza `rate` y
    `source`. `fetched_at` se refresca al `now()` por trigger del
    server_default cuando es nuevo; para updates lo seteamos manual.

    Devuelve el número de filas afectadas.
    """
    payload = [
        {
            "rate_date": rd,
            "base": base,
            "quote": quote,
            "rate": rate,
            "source": source,
        }
        for rd, base, quote, rate, source in rows
    ]
    if not payload:
        return 0

    stmt = pg_insert(ExchangeRate).values(payload)
    stmt = stmt.on_conflict_do_update(
        index_elements=["rate_date", "base", "quote"],
        set_={
            "rate": stmt.excluded.rate,
            "source": stmt.excluded.source,
        },
    )
    await db.execute(stmt)
    await db.flush()
    return len(payload)


async def list_distinct_quotes(
    db: AsyncSession, *, since: date | None = None
) -> list[str]:
    """Devuelve todos los `quote` distintos almacenados.

    Útil para construir la lista de monedas que el cliente HTTP debe
    refrescar diariamente.
    """
    stmt = select(ExchangeRate.quote).distinct().order_by(ExchangeRate.quote)
    if since is not None:
        stmt = stmt.where(ExchangeRate.rate_date >= since)
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]
