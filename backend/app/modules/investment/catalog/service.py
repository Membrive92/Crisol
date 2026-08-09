"""Lógica de negocio del catálogo de valores (PHASE-44.7).

Resolver un ticker crea (o reutiliza) un `Security`. La resolución delega en un
`FundamentalsAdapter` (EDGAR por defecto) que aporta CIK, nombre, SIC y los flags
`is_reit`/`is_financial`; de ahí derivamos el sector interno para los umbrales.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.investment.catalog import repository as repo
from app.modules.investment.catalog.capabilities import (
    accounting_std_from_status,
    capabilities_for,
    status_from_evidence,
)
from app.modules.investment.catalog.directory_models import ListingDirectoryEntry
from app.modules.investment.catalog.listing_key import (
    catalog_key,
    external_key,
    index_key,
    normalize_cik,
    parse_listing_key,
)
from app.modules.investment.catalog.models import Security
from app.modules.investment.catalog.ranking import IndexRow, missing_issuer_notice
from app.modules.investment.catalog.schemas import SecuritySearchHit
from app.modules.investment.catalog.sic_mapping import sic_to_sector
from app.modules.investment.catalog.symbol_index import index_ready, search_index
from app.modules.investment.catalog.venues import UNKNOWN, normalize_venue, venue_label
from app.modules.investment.enums import AccountingStd, SecurityType
from app.modules.investment.fundamentals.adapters.base import FundamentalsAdapter
from app.modules.investment.pricing.adapters.base import Quote, QuoteError

logger = logging.getLogger(__name__)


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


class ExternalListingResolver(Protocol):
    """La comodidad y la red de seguridad del alta `ext:` (PHASE-44.14).

    La IDENTIDAD del alta viene de FIRDS; esto resuelve el símbolo de pricing
    por ISIN y comprueba que cotiza. Es un Protocol para que los tests inyecten
    un doble — la implementación real (Yahoo) vive en el adapter de yfinance,
    el único fichero que conoce esa librería.
    """

    async def resolve_symbols(self, isin: str) -> list[str]: ...

    async def probe(self, symbol: str) -> Quote | QuoteError: ...

    def suffix_for(self, venue: str) -> str | None: ...


class YahooListingResolver:
    """Implementación por defecto, sobre el adapter de yfinance."""

    async def resolve_symbols(self, isin: str) -> list[str]:
        from app.modules.investment.pricing.adapters.yfinance import search_symbols_by_isin

        return await asyncio.to_thread(search_symbols_by_isin, isin)

    async def probe(self, symbol: str) -> Quote | QuoteError:
        from app.modules.investment.pricing.adapters.yfinance import probe_symbol

        return await asyncio.to_thread(probe_symbol, symbol)

    def suffix_for(self, venue: str) -> str | None:
        from app.modules.investment.pricing.adapters.yfinance import suffix_for_venue

        return suffix_for_venue(venue)


def get_listing_resolver() -> ExternalListingResolver:
    """Dependencia FastAPI — los tests la sustituyen por un doble."""
    return YahooListingResolver()


@dataclass(frozen=True)
class LayeredSearch:
    """Resultado del buscador por capas: catálogo primero, índice de la SEC
    después, directorio UE/UK al final, más lo que hay que decirle al usuario
    sobre lo que NO salió."""

    hits: list[SecuritySearchHit]
    index_ready: bool
    notice: str | None
    directory_seeded_at: datetime | None


def _hit_from_security(security: Security) -> SecuritySearchHit:
    caps = capabilities_for(cik=security.cik, analysis_status=security.analysis_status)
    return SecuritySearchHit(
        id=security.id,
        ticker=security.ticker,
        exchange=security.exchange,
        exchange_label=venue_label(security.exchange),
        name=security.name,
        in_catalog=True,
        source="catalog",
        cik=security.cik,
        listing_key=catalog_key(security.id),
        analysis_available=caps.analysis_available,
        analysis_reason=caps.reason,
    )


def _hit_from_index(row: IndexRow) -> SecuritySearchHit:
    # El índice de la SEC da CIK, así que la fila es analizable MIENTRAS no se
    # demuestre lo contrario — y demostrarlo exige contar filings, o sea red, que
    # es justo lo que un buscador local no puede hacer. La evidencia se cuenta al
    # adoptar y se persiste; hasta entonces `analysis_status` es NULL y
    # `capabilities_for` responde lo mismo que respondía el proyecto entero antes
    # de que esta columna existiera.
    cik = normalize_cik(row.cik)
    caps = capabilities_for(cik=cik, analysis_status=None)
    return SecuritySearchHit(
        id=None,
        ticker=row.ticker,
        exchange=row.venue,
        exchange_label=venue_label(row.venue),
        name=row.name,
        in_catalog=False,
        source="sec_index",
        cik=cik,
        listing_key=index_key(row.venue, row.ticker),
        analysis_available=caps.analysis_available,
        analysis_reason=caps.reason,
    )


def _hit_from_listing(listing: ListingDirectoryEntry) -> SecuritySearchHit:
    # Sin ticker a propósito: FIRDS no lo publica y el `ShrtNm` no lo lleva de
    # forma fiable (en Inditex sí — `ITX/AC 0.03` —, en Kingfish es el nombre
    # truncado). Inventarlo aquí sería un dato falso; el ticker real lo pone la
    # resolución del alta, o el usuario.
    caps = capabilities_for(cik=None)
    return SecuritySearchHit(
        id=None,
        ticker="",
        exchange=listing.mic,
        exchange_label=venue_label(listing.mic),
        name=listing.name,
        in_catalog=False,
        source="eu_directory",
        cik=None,
        isin=listing.isin,
        currency=listing.currency,
        listing_key=external_key(listing.mic, listing.isin),
        analysis_available=caps.analysis_available,
        analysis_reason=caps.reason,
    )


async def search_layered(db: AsyncSession, *, q: str, limit: int) -> LayeredSearch:
    """Tres capas locales, ninguna con red: catálogo, índice SEC, directorio UE/UK.

    El orden no es estético: lo que el usuario ya tiene en su catálogo va
    primero porque es lo que probablemente busca, y además evita que elija la
    fila del índice y cree un duplicado de algo que ya tenía. El directorio va
    al final: es el universo más grande y el menos probable.

    La deduplicación entre capas 1↔2 es por **CIK** (`normalize_cik` en ambos
    lados: el catálogo guarda `'0000063908'` y el índice trae `63908`; en crudo
    es un `False` silencioso y McDonald's salía dos veces). Entre 1↔3 es por
    `(isin, plaza)` — la identidad del listing FIRDS.

    El índice se carga en un hilo aparte: son ~0,9 s la primera vez y bloquear
    el event loop pararía todas las peticiones en vuelo.
    """
    query = q.strip()
    seeded_at = await repo.directory_seeded_at(db)
    if not query:
        return LayeredSearch(
            hits=[], index_ready=index_ready(), notice=None, directory_seeded_at=seeded_at
        )

    catalog_rows = await repo.search_securities(db, query, limit=limit)
    hits = [_hit_from_security(s) for s in catalog_rows]
    seen_ciks = {c for s in catalog_rows if (c := normalize_cik(s.cik))}
    seen_listings = {(s.isin, s.exchange) for s in catalog_rows if s.isin}

    def take_index(rows: list[IndexRow]) -> None:
        for row in rows:
            if len(hits) >= limit:
                return
            cik = normalize_cik(row.cik)
            if cik is not None and cik in seen_ciks:
                continue
            hits.append(_hit_from_index(row))
            if cik is not None:
                seen_ciks.add(cik)

    # Capa 2a: lo que el índice de la SEC casa de forma EXACTA.
    if len(hits) < limit:
        take_index(await asyncio.to_thread(search_index, query, limit=limit, allow_fuzzy=False))

    # Capa 3: el directorio UE/UK.
    if len(hits) < limit:
        for listing in await repo.search_directory(db, query, limit=limit - len(hits)):
            if (listing.isin, listing.mic) in seen_listings:
                continue
            hits.append(_hit_from_listing(listing))
            if len(hits) >= limit:
                break

    # Capa 2b: el fuzzy del índice, ÚLTIMO recurso y sólo si aún sobra sitio.
    #
    # Va después del directorio por un caso concreto que sólo apareció al usar
    # la app: `allianz` no tiene NINGUNA coincidencia exacta en la SEC, así que
    # el fuzzy proponía `ALLIANT`/`ALLIANCE` —otras empresas— y esas filas
    # llenaban el cupo antes de que el directorio pudiera ofrecer `Allianz SE`,
    # que casa exacto. Una corrección ortográfica jamás debe desplazar a una
    # coincidencia literal de otra capa.
    if len(hits) < limit:
        take_index(await asyncio.to_thread(search_index, query, limit=limit, allow_fuzzy=True))

    return LayeredSearch(
        hits=_exact_ticker_first(hits, query),
        index_ready=index_ready(),
        notice=missing_issuer_notice(query) if not hits else None,
        directory_seeded_at=seeded_at,
    )


def _exact_ticker_first(hits: list[SecuritySearchHit], query: str) -> list[SecuritySearchHit]:
    """Un ticker tecleado ENTERO manda, venga de la capa que venga.

    Las capas van en un orden deliberado (lo tuyo primero, luego la SEC, luego
    el directorio), pero ese orden no puede pisar la calidad de la coincidencia.
    El caso que lo destapó al usar la app: con McDonald's en el catálogo,
    teclear `MC` devolvía `MCD` —un match por PREFIJO de la capa 1— y dejaba
    fuera a Moelis, cuyo ticker es exactamente `MC`. Quien escribe un ticker
    completo sabe lo que busca.

    Estable en todo lo demás: sólo adelanta lo que casa al 100 %, sin reordenar
    el resto.
    """
    term = query.strip().upper()
    if not term:
        return hits
    exact = [h for h in hits if h.ticker.upper() == term]
    if not exact:
        return hits
    return exact + [h for h in hits if h.ticker.upper() != term]


async def adopt_listing(
    db: AsyncSession,
    *,
    listing_key: str,
    adapter: FundamentalsAdapter,
    resolver: ExternalListingResolver | None = None,
    ticker: str | None = None,
) -> Security:
    """Materializa un resultado del buscador como `Security` del catálogo.

    Re-resuelve la clave EN SERVIDOR (ver `listing_key.py`): el cliente no manda
    plaza ni CIK, así que no los puede inventar.

    Lo que aporta cada origen es CUÁNTA verdad se le puede dar de entrada:

    - `cat:` no llama a nada: la fila ya existe.
    - `idx:` aporta la **plaza real**, que si no se perdería, y pasa por EDGAR:
      sin esa llamada no hay SIC, y sin SIC un banco entraría con
      `is_financial=False` y los ocho scores forenses correrían sobre una
      financiera — lo que la regla dura del engine prohíbe.
    - `ext:` aporta la identidad registral COMPLETA de FIRDS (nombre, divisa,
      plaza) y sigue el flujo validado de `_adopt_external` — sin EDGAR: un
      listing europeo no tiene CIK que consultar.
    - `typed:` no aporta nada más que el ticker; la escotilla.

    `ticker` sólo aplica a `ext:`: es el bypass manual cuando la resolución
    ISIN→símbolo no encuentra nada (Unilever en el spike del 2026-08-07).
    """
    parsed = parse_listing_key(listing_key)

    if parsed.source == "catalog":
        assert parsed.security_id is not None  # lo garantiza el parser
        return await get_security(db, parsed.security_id)

    if parsed.source == "external":
        assert parsed.isin is not None and parsed.venue is not None  # lo garantiza el parser
        return await _adopt_external(
            db,
            isin=parsed.isin,
            mic=parsed.venue,
            resolver=resolver or YahooListingResolver(),
            manual_ticker=ticker,
        )

    assert parsed.ticker is not None  # lo garantiza el parser
    return await resolve_security(db, ticker=parsed.ticker, exchange=parsed.venue, adapter=adapter)


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
            # pisa un veredicto anterior. Y la norma contable viaja CON la
            # evidencia: si dejara de hacerlo, un emisor que empieza a presentar
            # 10-K se quedaría etiquetado IFRS para siempre — la etiqueta
            # caducada que esta derivación viene a evitar.
            if status is not None and twin.analysis_status != status:
                twin.analysis_status = status
                twin.accounting_std = accounting_std_from_status(status)
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
        # La norma contable sale de la EVIDENCIA contada en la SEC, no de un
        # literal: un ADR que presenta 20-F con `ifrs-full` (SAN, ASML, SAP)
        # entra como IFRS, y eso hace que sus umbrales se siembren con
        # `model_variant='uncalibrated'`. Ver `accounting_std_from_status`.
        accounting_std=accounting_std_from_status(status),
        # USD sí es un literal correcto, y por una razón concreta: las cuatro
        # plazas que resuelve EDGAR (NYSE, Nasdaq, CBOE, OTC) cotizan en
        # dólares. Un listing europeo no llega por aquí — entra por `ext:`, que
        # toma la divisa del registro FIRDS.
        currency="USD",
        security_type=SecurityType.STOCK,
        is_financial=identity.is_financial,
        is_reit=identity.is_reit,
        analysis_status=status,
    )
    return await repo.add_security(db, security)


def _split_symbol(symbol: str) -> tuple[str, str]:
    """`'ITX.MC'` → `('ITX', '.MC')`; `'KO'` → `('KO', '')`."""
    base, dot, suffix = symbol.partition(".")
    return base, (dot + suffix if dot else "")


async def _adopt_external(
    db: AsyncSession,
    *,
    isin: str,
    mic: str,
    resolver: ExternalListingResolver,
    manual_ticker: str | None,
) -> Security:
    """Alta validada desde el directorio FIRDS (plan E5 §4, ADR-0010).

    La identidad (nombre, divisa, plaza) es la del registro — nada de eso lo
    decide un proveedor de precios. El proveedor sólo aporta dos comodidades,
    ambas con red y ambas con salida digna si fallan:

    1. **Resolución ISIN→símbolo.** Si no encuentra nada, 422 con
       `code='ticker_required'` y la identidad pre-rellenada: el formulario pide
       el ticker a mano. Degradación diseñada, no fallo (Unilever en el spike).
    2. **Validación por cotización** (regla universal): nada se persiste sin
       haber visto una cotización real del símbolo. Y si el sufijo del símbolo
       no casa con el MIC elegido → parada con mensaje, jamás auto-alta: un
       sufijo ajeno significa que el precio sería el de OTRO listing.

    La divisa del proveedor puede discrepar de la registral (se loguea y se
    sigue): la regla D4 vigente la marca en la posición, que es donde el usuario
    la ve con contexto.
    """
    listing = await repo.get_listing(db, isin, mic)
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Ese listing ya no está en el directorio. Vuelve a buscar — si el "
                "directorio se ha refrescado, puede haber cambiado o deslistado."
            ),
        )

    existing = await repo.get_security_by_isin_exchange(db, isin, mic)
    if existing is not None:
        return existing

    suffix = resolver.suffix_for(mic)
    if suffix is None:
        # No debería pasar: el seed sólo siembra MICs con sufijo (hay un test
        # que ata ambas tablas). Si pasa, el dato es más nuevo que el código.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"La plaza {mic} no tiene equivalencia en el proveedor de precios.",
        )

    if manual_ticker:
        base, manual_suffix = _split_symbol(manual_ticker.strip().upper())
        if manual_suffix and manual_suffix != suffix:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"El sufijo «{manual_suffix}» no corresponde a {venue_label(mic)} "
                    f"(esperaba «{suffix}»). Escribe el ticker sin sufijo."
                ),
            )
        if not base:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El ticker no puede estar vacío.",
            )
        symbol = base + suffix
    else:
        candidates = await resolver.resolve_symbols(isin)
        # Si el proveedor devuelve varios, vale el que cotiza EN la plaza
        # elegida; los demás son el mismo ISIN en otros mercados.
        chosen = next((c for c in candidates if _split_symbol(c)[1] == suffix), None)
        if chosen is None and candidates:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"El proveedor resuelve este ISIN como {', '.join(candidates[:3])}, "
                    f"que no cotiza en {venue_label(mic)}. Comprueba la plaza elegida "
                    "o escribe el ticker a mano."
                ),
            )
        if chosen is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "ticker_required",
                    "message": (
                        "El proveedor de precios no reconoce este ISIN. Escribe el "
                        "símbolo local (p. ej. «ITX») para completar el alta."
                    ),
                    "prefill": {
                        "isin": listing.isin,
                        "mic": listing.mic,
                        "name": listing.name,
                        "currency": listing.currency,
                    },
                },
            )
        symbol = chosen
        base, _ = _split_symbol(symbol)

    probe = await resolver.probe(symbol)
    if isinstance(probe, QuoteError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"No se pudo validar «{symbol}» con una cotización real: {probe.reason}. "
                "Nada se da de alta sin verla — corrige el ticker o reinténtalo."
            ),
        )
    if probe.currency is not None and probe.currency != listing.currency:
        # No bloquea: la identidad registral manda, y la regla D4 vigente
        # marcará la discrepancia en la posición — donde se ve con contexto.
        logger.info(
            "adopt ext: divisa del proveedor (%s) != registral (%s) para %s/%s",
            probe.currency,
            listing.currency,
            isin,
            mic,
        )

    security = Security(
        ticker=base,
        exchange=mic,
        name=listing.name,
        cik=None,
        isin=listing.isin,
        sector=sic_to_sector(None),
        # Descriptivo: el análisis lo bloquea `analysis_status='not_supported'`
        # (sin CIK no hay filings), así que este valor no alimenta ningún corte.
        accounting_std=AccountingStd.IFRS,
        currency=listing.currency,
        security_type=SecurityType.STOCK,
        is_financial=False,
        is_reit=False,
        analysis_status=status_from_evidence(cik=None, annual_report_count=None),
    )
    return await repo.add_security(db, security)
