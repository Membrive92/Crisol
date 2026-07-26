"""Queries a DB del catálogo de valores (PHASE-44.7).

`securities` es una tabla **GLOBAL** [Dec.11 / ADR-0007]: la identidad de un
valor de mercado es objetiva, no por-usuario. Por eso NINGUNA query de este
repositorio filtra por `user_id` — no existe esa columna.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.investment.catalog.models import Security


async def get_security_by_id(db: AsyncSession, security_id: uuid.UUID) -> Security | None:
    return await db.get(Security, security_id)


async def get_security_by_ticker_exchange(
    db: AsyncSession, ticker: str, exchange: str
) -> Security | None:
    stmt = select(Security).where(
        Security.ticker == ticker.upper(),
        Security.exchange == exchange.upper(),
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_security_by_cik(db: AsyncSession, cik: str) -> Security | None:
    """Primer valor con ese CIK. Un mismo emisor puede cotizar en varios
    mercados; devolvemos el primero para reutilizar sus fundamentales."""
    stmt = select(Security).where(Security.cik == cik).order_by(Security.created_at)
    return (await db.execute(stmt)).scalars().first()


async def get_security_by_cik_ticker(db: AsyncSession, cik: str, ticker: str) -> Security | None:
    """El valor de ese emisor con ESE ticker, sea cual sea la plaza guardada.

    Es la clave de identidad real de un instrumento y la que evita el duplicado
    que motivó PHASE-44.8: un cliente que decía `exchange='US'` y otro que decía
    `'NYSE'` creaban DOS filas del mismo valor (la restricción única es
    `(ticker, exchange)`), con dos ingestas y los lotes de cartera repartidos.

    Deliberadamente **no** se deduplica sólo por CIK: un mismo emisor tiene
    varios tickers legítimos y distinguibles (CIK 1652044 → GOOGL, GOOG, GOOGM,
    GOOGN), y colapsarlos haría que quien tenga GOOG en cartera viese GOOGL. El
    colapso por CIK a secas es para PINTAR resultados, no para persistirlos.
    """
    stmt = select(Security).where(
        Security.cik == cik,
        Security.ticker == ticker.upper(),
    )
    return (await db.execute(stmt)).scalars().first()


async def search_securities(db: AsyncSession, q: str, *, limit: int) -> list[Security]:
    """Busca por ticker o nombre (case-insensitive). El ticker matchea por
    prefijo (lo que teclea el usuario), el nombre por substring."""
    stmt = (
        select(Security)
        .where(Security.ticker.ilike(f"{q}%") | Security.name.ilike(f"%{q}%"))
        .order_by(Security.ticker)
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def add_security(db: AsyncSession, security: Security) -> Security:
    db.add(security)
    await db.flush()
    await db.refresh(security)
    return security
