"""Queries a DB del catálogo de valores (PHASE-44.7).

`securities` es una tabla **GLOBAL** [Dec.11 / ADR-0007]: la identidad de un
valor de mercado es objetiva, no por-usuario. Por eso NINGUNA query de este
repositorio filtra por `user_id` — no existe esa columna.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.investment.catalog.directory_models import ListingDirectoryEntry
from app.modules.investment.catalog.firds import FirdsRecord
from app.modules.investment.catalog.models import Security
from app.modules.investment.catalog.ranking import MIN_FUZZY_QUERY


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


async def get_security_by_isin_exchange(
    db: AsyncSession, isin: str, exchange: str
) -> Security | None:
    """La clave de identidad de un alta desde el directorio (`ext:`): el mismo
    listing FIRDS no puede ocupar dos filas por mucho que el símbolo de pricing
    se haya resuelto distinto en dos intentos."""
    stmt = select(Security).where(
        Security.isin == isin.upper(),
        Security.exchange == exchange.upper(),
    )
    return (await db.execute(stmt)).scalars().first()


# ── Directorio oficial UE/UK (PHASE-44.14, ADR-0010) ──────────────────


async def get_listing(db: AsyncSession, isin: str, mic: str) -> ListingDirectoryEntry | None:
    return await db.get(ListingDirectoryEntry, (isin.upper(), mic.upper()))


async def directory_seeded_at(db: AsyncSession) -> datetime | None:
    """Fecha del último cambio sembrado, o `None` si el directorio está vacío.

    Es lo que la UI declara («directorio actualizado el X»): con un directorio
    sin sembrar, cero resultados europeos significa «no se ha mirado», no «no
    existe», y la pantalla no puede permitirse confundirlos."""
    return (await db.execute(select(func.max(ListingDirectoryEntry.seeded_at)))).scalar()


async def search_directory(db: AsyncSession, q: str, *, limit: int) -> list[ListingDirectoryEntry]:
    """Busca en el directorio por nombre (trigram + subcadena), ShrtNm e ISIN.

    El `short_name` importa tanto como el nombre: en ESMA suele llevar el ticker
    local (`ITX/AC 0.03` para Inditex), así que teclear `ITX` encuentra a
    Inditex por DATOS — sin la lista de alias que el plan original necesitaba.

    La tolerancia a erratas («Santandr», «Iberdola») es `word_similarity` de
    pg_trgm: la consulta contra las PALABRAS del nombre, no el nombre entero —
    «SANTANDR» se parece mucho a «SANTANDER» y poco a «BANCO SANTANDER S.A.»
    como cadena completa. El umbral va explícito a `0.45` y no con el operador
    `<%` (que usa el default 0.6): verificado contra el directorio real, una
    errata de letra interior («IBERDOLA» → «IBERDROLA») rompe más trigramas que
    un truncado y se queda en ~0.55 — con el default no salía. A 3K filas la
    función sin índice es irrelevante; el orden por similitud mantiene lo bueno
    arriba si el umbral deja pasar ruido. Se acota a consultas de
    `MIN_FUZZY_QUERY`+ caracteres, el mismo suelo que el fuzzy del índice SEC:
    corregir la ortografía de 3 letras es adivinar.

    El orden es por `similarity()` sobre el nombre, con el ISIN exacto primero:
    determinista.
    """
    term = q.strip().upper()
    if not term:
        return []
    pattern = f"%{term}%"
    matches = (
        (ListingDirectoryEntry.isin == term)
        | ListingDirectoryEntry.name.ilike(pattern)
        | ListingDirectoryEntry.short_name.ilike(pattern)
    )
    if len(term) >= MIN_FUZZY_QUERY:
        matches = matches | (func.word_similarity(literal(term), ListingDirectoryEntry.name) > 0.45)
    similarity = func.similarity(ListingDirectoryEntry.name, term)
    stmt = (
        select(ListingDirectoryEntry)
        .where(matches)
        .order_by(
            (ListingDirectoryEntry.isin == term).desc(),
            similarity.desc(),
            ListingDirectoryEntry.name,
            ListingDirectoryEntry.mic,
        )
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


@dataclass(frozen=True)
class DirectorySyncStats:
    """Lo que hizo una pasada del seed, para el informe del script."""

    inserted: int
    updated: int
    removed: int
    unchanged: int


#: Suelo de seguridad del borrado: si el lote nuevo de una fuente trae menos
#: filas que esto, NO se eliminan las ausentes. Un fichero truncado o una
#: descarga rota parecería «todo deslistado» y vaciaría el directorio en
#: silencio; con el suelo, degrada a un upsert normal y el script lo avisa.
MIN_ROWS_TO_PRUNE = 100


async def sync_directory_source(
    db: AsyncSession,
    records: dict[tuple[str, str], FirdsRecord],
    *,
    source: str,
    seeded_at: datetime,
) -> DirectorySyncStats:
    """Sincroniza las filas de UNA fuente (`ESMA` | `FCA`) con el lote nuevo.

    Semántica de espejo, no de acumulación: un FULINS *full* ES el universo
    completo de su registro, así que lo que ya no está en el fichero se elimina
    (deslistados) — con el suelo `MIN_ROWS_TO_PRUNE` como protección.

    La idempotencia es HONESTA: una fila sólo se escribe si algún campo cambió,
    y `seeded_at` sólo se toca en esas. Así «segundo run → 0 cambios» significa
    cero escrituras de verdad, no un upsert que reescribe lo mismo (y el gate
    del test de idempotencia detecta, no decora).
    """
    existing = {
        (row.isin, row.mic): row
        for row in (
            await db.execute(
                select(ListingDirectoryEntry).where(ListingDirectoryEntry.source == source)
            )
        )
        .scalars()
        .all()
    }

    inserted = updated = unchanged = 0
    for key, record in records.items():
        current = existing.get(key)
        if current is None:
            db.add(
                ListingDirectoryEntry(
                    isin=record.isin,
                    mic=record.mic,
                    name=record.name,
                    short_name=record.short_name,
                    currency=record.currency,
                    cfi=record.cfi,
                    lei=record.lei,
                    first_trade_date=record.first_trade_date,
                    termination_date=record.termination_date,
                    source=source,
                    seeded_at=seeded_at,
                )
            )
            inserted += 1
            continue
        changed = (
            current.name != record.name
            or current.short_name != record.short_name
            or current.currency != record.currency
            or current.cfi != record.cfi
            or current.lei != record.lei
            or current.first_trade_date != record.first_trade_date
            or current.termination_date != record.termination_date
        )
        if changed:
            current.name = record.name
            current.short_name = record.short_name
            current.currency = record.currency
            current.cfi = record.cfi
            current.lei = record.lei
            current.first_trade_date = record.first_trade_date
            current.termination_date = record.termination_date
            current.seeded_at = seeded_at
            updated += 1
        else:
            unchanged += 1

    removed = 0
    stale = [key for key in existing if key not in records]
    if stale and len(records) >= MIN_ROWS_TO_PRUNE:
        for key in stale:
            await db.delete(existing[key])
            removed += 1

    await db.flush()
    return DirectorySyncStats(
        inserted=inserted, updated=updated, removed=removed, unchanged=unchanged
    )
