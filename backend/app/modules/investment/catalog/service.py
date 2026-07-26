"""Lógica de negocio del catálogo de valores (PHASE-44.7).

Resolver un ticker crea (o reutiliza) un `Security`. La resolución delega en un
`FundamentalsAdapter` (EDGAR por defecto) que aporta CIK, nombre, SIC y los flags
`is_reit`/`is_financial`; de ahí derivamos el sector interno para los umbrales.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.investment.catalog import repository as repo
from app.modules.investment.catalog.capabilities import capabilities_for, status_from_evidence
from app.modules.investment.catalog.models import Security
from app.modules.investment.catalog.sic_mapping import sic_to_sector
from app.modules.investment.catalog.venues import UNKNOWN, normalize_venue
from app.modules.investment.enums import AccountingStd, SecurityType
from app.modules.investment.fundamentals.adapters.base import FundamentalsAdapter


async def get_security(db: AsyncSession, security_id: uuid.UUID) -> Security:
    """Un valor del catálogo por id, o 404."""
    security = await repo.get_security_by_id(db, security_id)
    if security is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Valor no encontrado en el catálogo.",
        )
    return security


async def search_securities(db: AsyncSession, *, q: str, limit: int) -> list[Security]:
    """Busca en el catálogo local. Cadena vacía → sin resultados (no listar
    todo el catálogo por accidente)."""
    q = q.strip()
    if not q:
        return []
    return await repo.search_securities(db, q, limit=limit)


def _blocks_analysis(analysis_status: str | None) -> bool:
    """Si el veredicto guardado impide analizar, y por tanto merece re-verificarse.

    `None` (no comprobado) no bloquea: se comporta como antes de existir la
    columna, así que tampoco desencadena una petición.
    """
    if analysis_status is None:
        return False
    return not capabilities_for(cik="present", analysis_status=analysis_status).analysis_available


async def resolve_security(
    db: AsyncSession,
    *,
    ticker: str,
    exchange: str | None = None,
    adapter: FundamentalsAdapter,
) -> Security:
    """Crea el `Security` del ticker, o devuelve el que ya existe.

    Idempotente por la identidad REAL del instrumento —`(cik, ticker)`— y no por
    la clave de la tabla. La diferencia es el bug que motivó PHASE-44.8: el
    frontend mandaba `exchange='US'` (un país, no una plaza) y el móvil sigue
    haciéndolo, así que `MCD/US` y `MCD/NYSE` eran dos filas del mismo valor con
    dos ingestas y los lotes de cartera repartidos entre dos ids.

    `exchange` pasa a ser **opcional y no vinculante**: se normaliza contra el
    vocabulario (`venues.normalize_venue`) y sólo sirve como etiqueta. Si llega
    una plaza real para una fila que estaba en `UNKNOWN`, se aprovecha para
    completarla; nunca se degrada una plaza conocida ni se crea una fila nueva por
    discrepar en la etiqueta.

    El adapter resuelve la identidad contra la SEC; con la identidad ya cacheada
    no hay red. Sus excepciones (`EdgarUnavailableError`,
    `EdgarIdentityMissingError`) las traduce el router a HTTP.
    """
    ticker_upper = ticker.strip().upper()
    venue = normalize_venue(exchange)

    # Camino rápido: la misma clave ya conocida no cuesta ni una petición.
    #
    # Con una excepción deliberada: si el veredicto guardado BLOQUEA el análisis,
    # se vuelve a preguntar. Es una foto que puede haber caducado —quien no
    # presentaba 10-K puede presentarlo el año que viene— y reintentar sobre un
    # valor bloqueado es justo el momento en que al usuario le importa. Un `ok`
    # no se re-verifica: un emisor no deja de publicar cuentas de un día para
    # otro, y no vale la pena pagar una petición en cada alta.
    existing = await repo.get_security_by_ticker_exchange(db, ticker_upper, venue)
    if existing is not None and not _blocks_analysis(existing.analysis_status):
        return existing

    identity = await adapter.resolve(ticker_upper)
    resolved_ticker = (identity.ticker or ticker_upper).upper()

    status = status_from_evidence(
        cik=identity.cik,
        annual_report_count=identity.annual_report_count,
        foreign_annual_report_count=identity.foreign_annual_report_count,
    )

    if identity.cik:
        twin = await repo.get_security_by_cik_ticker(db, identity.cik, resolved_ticker)
        if twin is not None:
            changed = False
            if twin.exchange == UNKNOWN and venue != UNKNOWN:
                twin.exchange = venue
                changed = True
            # La evidencia se refresca al volver a resolver: quien no presentaba
            # 10-K puede presentarlo el año que viene. `None` (no comprobado) no
            # pisa un veredicto anterior.
            if status is not None and twin.analysis_status != status:
                twin.analysis_status = status
                changed = True
            if changed:
                await db.flush()
                await db.refresh(twin)
            return twin

    security = Security(
        ticker=resolved_ticker,
        exchange=venue,
        name=identity.name,
        cik=identity.cik,
        isin=None,
        sector=sic_to_sector(identity.sic),
        # EDGAR sólo tiene filers de la SEC, así que USD/GAAP es correcto para la
        # cotización estadounidense que se resuelve aquí. NO se afina en esta
        # entrega: distinguir un ADR que presenta 20-F con `ifrs-full` (SAN,
        # ASML, SAP) exige contar filings —o sea red—, y etiquetarlo IFRS "por
        # si acaso" sería un no-op numérico que además movería el
        # `thresholds_hash` de los runs ya guardados (los cortes de
        # `thresholds/seed.py` son los mismos para las tres normas; sólo cambia
        # `model_variant`). Lo resuelve la Entrega 2 con `analysis_status`.
        accounting_std=AccountingStd.GAAP,
        currency="USD",
        security_type=SecurityType.STOCK,
        is_financial=identity.is_financial,
        is_reit=identity.is_reit,
        analysis_status=status,
    )
    return await repo.add_security(db, security)
