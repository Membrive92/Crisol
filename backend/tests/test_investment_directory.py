"""Directorio UE/UK: sync, búsqueda unificada y alta validada (PHASE-44.14).

El resolver externo (ISIN→símbolo + validación por cotización) se inyecta como
doble vía `dependency_overrides`: cero red, y cada rama del flujo del alta —
feliz, sufijo↔MIC discrepante, `ticker_required`, cotización inválida — se
ejerce con un caso concreto.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.main import app
from app.modules.investment.catalog import repository as repo
from app.modules.investment.catalog.firds import FirdsRecord, collapse_records, parse_fulins
from app.modules.investment.catalog.models import Security
from app.modules.investment.catalog.service import get_listing_resolver
from app.modules.investment.pricing.adapters.base import Quote, QuoteError

FIXTURE = Path(__file__).parent / "fixtures" / "firds_fulins_e_sample.xml"
TODAY = date(2026, 8, 7)
SEEDED_AT = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def _fixture_records():  # type: ignore[no-untyped-def]
    with FIXTURE.open("rb") as fh:
        return collapse_records(parse_fulins(fh, today=TODAY))


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class _FakeResolver:
    """Doble de `ExternalListingResolver` con guion configurable."""

    def __init__(
        self,
        *,
        symbols: dict[str, list[str]] | None = None,
        quote: Quote | QuoteError | None = None,
    ) -> None:
        self._symbols = symbols or {}
        self._quote = quote or Quote(
            price=Decimal("10"), prev_close=None, currency="EUR", as_of=datetime.now(UTC)
        )
        self.probed: list[str] = []

    async def resolve_symbols(self, isin: str) -> list[str]:
        return self._symbols.get(isin, [])

    async def probe(self, symbol: str) -> Quote | QuoteError:
        self.probed.append(symbol)
        return self._quote

    def suffix_for(self, venue: str) -> str | None:
        from app.modules.investment.pricing.adapters.yfinance import suffix_for_venue

        return suffix_for_venue(venue)


def _use_resolver(resolver: _FakeResolver) -> None:
    app.dependency_overrides[get_listing_resolver] = lambda: resolver


@pytest.fixture
async def seeded_directory(test_engine):  # type: ignore[no-untyped-def]
    """Siembra el directorio desde el fixture FULINS y lo limpia al salir."""
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        await repo.sync_directory_source(db, _fixture_records(), source="ESMA", seeded_at=SEEDED_AT)
        await db.commit()
    yield
    from sqlalchemy import delete

    from app.modules.investment.catalog.directory_models import ListingDirectoryEntry

    async with factory() as db:
        await db.execute(delete(ListingDirectoryEntry))
        await db.commit()


# ── Sync del seed ─────────────────────────────────────────────────────


async def test_el_seed_es_idempotente_de_verdad(test_engine) -> None:  # type: ignore[no-untyped-def]
    """Segundo run sobre el mismo fixture → CERO escrituras.

    «Cero» honesto: la idempotencia compara campo a campo y sólo escribe lo que
    cambió, no un upsert que reescribe lo mismo y cuenta filas afectadas.
    """
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    records = _fixture_records()
    async with factory() as db:
        first = await repo.sync_directory_source(db, records, source="ESMA", seeded_at=SEEDED_AT)
        await db.commit()
    assert first.inserted == len(records) > 0
    assert first.updated == first.removed == 0

    async with factory() as db:
        second = await repo.sync_directory_source(
            db, records, source="ESMA", seeded_at=datetime(2026, 8, 8, tzinfo=UTC)
        )
        await db.commit()
    assert second.inserted == second.updated == second.removed == 0
    assert second.unchanged == len(records)

    from sqlalchemy import delete

    from app.modules.investment.catalog.directory_models import ListingDirectoryEntry

    async with factory() as db:
        # La fecha de seed no se movió: nada cambió, nada se reescribió.
        entry = await repo.get_listing(db, "ES0148396007", "XMAD")
        assert entry is not None and entry.seeded_at == SEEDED_AT
        await db.execute(delete(ListingDirectoryEntry))
        await db.commit()


async def test_un_lote_diminuto_no_vacia_el_directorio(test_engine) -> None:  # type: ignore[no-untyped-def]
    """Un fichero truncado parecería «todo deslistado». El suelo
    `MIN_ROWS_TO_PRUNE` degrada a upsert sin borrado en vez de arrasar."""
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    records = _fixture_records()
    async with factory() as db:
        await repo.sync_directory_source(db, records, source="ESMA", seeded_at=SEEDED_AT)
        await db.commit()

    one_key = next(iter(records))
    async with factory() as db:
        stats = await repo.sync_directory_source(
            db, {one_key: records[one_key]}, source="ESMA", seeded_at=SEEDED_AT
        )
        await db.commit()
    assert stats.removed == 0, "un lote sospechosamente pequeño no debe podar"

    from sqlalchemy import delete

    from app.modules.investment.catalog.directory_models import ListingDirectoryEntry

    async with factory() as db:
        still = await repo.get_listing(db, "GB00BP6MXD84", "XLON")
        assert still is not None, "las filas ausentes del lote pequeño deben sobrevivir"
        await db.execute(delete(ListingDirectoryEntry))
        await db.commit()


def _synthetic(n: int, *, name_suffix: str = "") -> dict[tuple[str, str], FirdsRecord]:
    """`n` registros con ISINs distintos, para superar `MIN_ROWS_TO_PRUNE`.

    Sintéticos a propósito: el fixture real tiene 5 filas y con él el borrado
    NUNCA se ejecuta — sólo se comprueba que el suelo salta. Un test que
    verifica la protección pero jamás lo protegido no prueba nada.
    """
    out: dict[tuple[str, str], FirdsRecord] = {}
    for i in range(n):
        isin = f"ES{i:010d}"
        out[(isin, "XMAD")] = FirdsRecord(
            isin=isin,
            mic="XMAD",
            segment_mic="XMAD",
            name=f"EMISOR SINTETICO {i}{name_suffix}",
            short_name=None,
            currency="EUR",
            cfi="ESVUFR",
            lei=None,
            first_trade_date=None,
            termination_date=None,
        )
    return out


async def test_un_lote_grande_si_elimina_los_deslistados(test_engine) -> None:  # type: ignore[no-untyped-def]
    """El otro lado del suelo: con un lote creíble, lo que ya no está en el
    fichero SE ELIMINA. Un FULINS *full* es el universo completo de su
    registro, así que una fila ausente es un deslistado, no un hueco."""
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    from sqlalchemy import delete

    from app.modules.investment.catalog.directory_models import ListingDirectoryEntry

    full = _synthetic(repo.MIN_ROWS_TO_PRUNE + 5)
    async with factory() as db:
        await repo.sync_directory_source(db, full, source="ESMA", seeded_at=SEEDED_AT)
        await db.commit()

    # El siguiente fichero ya no trae las 3 últimas: se han deslistado.
    dropped = sorted(full)[-3:]
    shrunk = {k: v for k, v in full.items() if k not in dropped}
    async with factory() as db:
        stats = await repo.sync_directory_source(db, shrunk, source="ESMA", seeded_at=SEEDED_AT)
        await db.commit()

    assert stats.removed == 3, "las ausentes de un lote creíble deben eliminarse"
    async with factory() as db:
        for isin, mic in dropped:
            assert await repo.get_listing(db, isin, mic) is None
        await db.execute(delete(ListingDirectoryEntry))
        await db.commit()


async def test_un_cambio_real_se_escribe_y_mueve_la_fecha(test_engine) -> None:  # type: ignore[no-untyped-def]
    """La otra mitad de la idempotencia honesta: cuando un campo SÍ cambia, se
    escribe y `seeded_at` avanza. Sin este test, «0 cambios» podría significar
    «no detecta cambios» en vez de «no había»."""
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    from sqlalchemy import delete

    from app.modules.investment.catalog.directory_models import ListingDirectoryEntry

    later = datetime(2026, 9, 1, tzinfo=UTC)
    async with factory() as db:
        await repo.sync_directory_source(
            db, _synthetic(repo.MIN_ROWS_TO_PRUNE), source="ESMA", seeded_at=SEEDED_AT
        )
        await db.commit()
    async with factory() as db:
        stats = await repo.sync_directory_source(
            db,
            _synthetic(repo.MIN_ROWS_TO_PRUNE, name_suffix=" SA"),
            source="ESMA",
            seeded_at=later,
        )
        await db.commit()

    assert stats.updated == repo.MIN_ROWS_TO_PRUNE
    assert stats.inserted == stats.removed == 0
    async with factory() as db:
        entry = await repo.get_listing(db, "ES0000000000", "XMAD")
        assert entry is not None
        assert entry.name.endswith(" SA")
        assert entry.seeded_at == later
        await db.execute(delete(ListingDirectoryEntry))
        await db.commit()


async def test_las_dos_fuentes_no_se_pisan(test_engine) -> None:  # type: ignore[no-untyped-def]
    """El sync es por fuente y la partición es jurisdiccional: sembrar ESMA no
    puede tocar las filas de la FCA.

    Es lo que reventó en el dry-run del seed real: el FULINS de la FCA trae
    también venues europeos (Commerzbank en XETR), y sin `partition_for_source`
    el mismo `(isin, mic)` entraba por las dos fuentes."""
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    from sqlalchemy import delete

    from app.modules.investment.catalog.directory_models import ListingDirectoryEntry

    esma = _synthetic(repo.MIN_ROWS_TO_PRUNE)
    uk_key = ("GB00BP6MXD84", "XLON")
    fca = {uk_key: _fixture_records()[uk_key]}
    async with factory() as db:
        await repo.sync_directory_source(db, esma, source="ESMA", seeded_at=SEEDED_AT)
        await repo.sync_directory_source(db, fca, source="FCA", seeded_at=SEEDED_AT)
        await db.commit()

    # Un refresco SÓLO de ESMA, con un lote creíble: la fila de la FCA sigue.
    async with factory() as db:
        stats = await repo.sync_directory_source(db, esma, source="ESMA", seeded_at=SEEDED_AT)
        await db.commit()
    assert stats.removed == 0

    async with factory() as db:
        assert await repo.get_listing(db, *uk_key) is not None
        await db.execute(delete(ListingDirectoryEntry))
        await db.commit()


# ── Búsqueda unificada ────────────────────────────────────────────────


async def test_inditex_sale_de_verdad(client: AsyncClient, seeded_directory: None) -> None:
    """El criterio de aceptación del plan: el aviso «ITX → Inditex» desaparece
    porque Inditex SALE. Por nombre y por su ticker local (que viaja en el
    `ShrtNm` de FIRDS)."""
    token = await _register(client, "dir1@example.com")

    for query in ("inditex", "ITX"):
        body = (
            await client.get(f"/investment/securities/search?q={query}", headers=_auth(token))
        ).json()
        hit = next((h for h in body["results"] if h["isin"] == "ES0148396007"), None)
        assert hit is not None, f"{query!r} no encontró a Inditex"
        assert hit["source"] == "eu_directory"
        assert hit["exchange"] == "XMAD"
        assert hit["currency"] == "EUR"
        assert hit["listing_key"] == "ext:XMAD:ES0148396007"
        assert hit["analysis_available"] is False, "sin CIK no hay análisis"
        assert body["notice"] is None, "el aviso de alias sobraría: hay resultados"
        assert body["directory_seeded_at"] is not None


async def test_una_errata_encuentra_por_trigram(
    client: AsyncClient, seeded_directory: None
) -> None:
    token = await _register(client, "dir2@example.com")
    body = (
        await client.get("/investment/securities/search?q=santandr", headers=_auth(token))
    ).json()
    assert any(h.get("isin") == "ES0113900J37" for h in body["results"])


async def test_suiza_sigue_explicandose(client: AsyncClient, seeded_directory: None) -> None:
    """La frontera documentada del ADR-0010: SIX no reporta a FIRDS."""
    token = await _register(client, "dir3@example.com")
    body = (await client.get("/investment/securities/search?q=NESN", headers=_auth(token))).json()
    assert body["results"] == []
    assert body["notice"] is not None and "SIX" in body["notice"]


async def test_sin_sembrar_la_respuesta_lo_declara(client: AsyncClient) -> None:
    """Directorio vacío → `directory_seeded_at: null`. Cero resultados europeos
    sin sembrar significa «no se ha mirado», no «no cotiza en Europa»."""
    token = await _register(client, "dir4@example.com")
    body = (
        await client.get("/investment/securities/search?q=inditex", headers=_auth(token))
    ).json()
    assert body["directory_seeded_at"] is None


# ── Alta validada ext: ────────────────────────────────────────────────


async def test_alta_feliz_desde_el_directorio(
    client: AsyncClient, seeded_directory: None, test_engine
) -> None:
    """El flujo del plan §4: identidad de FIRDS, símbolo del resolver, ticker
    sin sufijo, divisa registral."""
    token = await _register(client, "dir5@example.com")
    resolver = _FakeResolver(symbols={"ES0148396007": ["ITX.MC"]})
    _use_resolver(resolver)

    r = await client.post(
        "/investment/securities/adopt",
        json={"listing_key": "ext:XMAD:ES0148396007"},
        headers=_auth(token),
    )

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["ticker"] == "ITX"
    assert body["exchange"] == "XMAD"
    assert body["currency"] == "EUR"
    assert body["isin"] == "ES0148396007"
    assert body["cik"] is None
    assert body["analysis_available"] is False
    assert resolver.probed == ["ITX.MC"], "nada se persiste sin ver una cotización"


async def test_adoptar_dos_veces_no_duplica(
    client: AsyncClient, seeded_directory: None, test_engine
) -> None:
    token = await _register(client, "dir6@example.com")
    _use_resolver(_FakeResolver(symbols={"ES0148396007": ["ITX.MC"]}))

    first = await client.post(
        "/investment/securities/adopt",
        json={"listing_key": "ext:XMAD:ES0148396007"},
        headers=_auth(token),
    )
    second = await client.post(
        "/investment/securities/adopt",
        json={"listing_key": "ext:XMAD:ES0148396007"},
        headers=_auth(token),
    )
    assert first.json()["id"] == second.json()["id"]
    async with async_sessionmaker(bind=test_engine, expire_on_commit=False)() as db:
        count = len((await db.execute(select(Security))).scalars().all())
    assert count == 1


async def test_sin_resolucion_pide_el_ticker_con_la_identidad_prerellenada(
    client: AsyncClient, seeded_directory: None
) -> None:
    """La degradación diseñada (Unilever en el spike): 422 `ticker_required`
    con la identidad FIRDS para pre-rellenar el formulario."""
    token = await _register(client, "dir7@example.com")
    _use_resolver(_FakeResolver(symbols={}))

    r = await client.post(
        "/investment/securities/adopt",
        json={"listing_key": "ext:XLON:GB00BP6MXD84"},
        headers=_auth(token),
    )

    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["code"] == "ticker_required"
    assert detail["prefill"]["isin"] == "GB00BP6MXD84"
    assert detail["prefill"]["currency"] == "GBP"


async def test_el_ticker_manual_completa_el_alta(
    client: AsyncClient, seeded_directory: None
) -> None:
    token = await _register(client, "dir8@example.com")
    resolver = _FakeResolver(
        symbols={},
        quote=Quote(price=Decimal("28"), prev_close=None, currency="GBP", as_of=datetime.now(UTC)),
    )
    _use_resolver(resolver)

    r = await client.post(
        "/investment/securities/adopt",
        json={"listing_key": "ext:XLON:GB00BP6MXD84", "ticker": "SHEL"},
        headers=_auth(token),
    )

    assert r.status_code == 201, r.text
    assert r.json()["ticker"] == "SHEL"
    assert resolver.probed == ["SHEL.L"], "el símbolo validado lleva el sufijo de la plaza"


async def test_un_sufijo_ajeno_a_la_plaza_es_parada_no_autoalta(
    client: AsyncClient, seeded_directory: None
) -> None:
    """Cross-check §4.3: un sufijo que no casa con el MIC significa que el
    precio sería el de OTRO listing. Parada con mensaje, jamás auto-alta."""
    token = await _register(client, "dir9@example.com")
    _use_resolver(_FakeResolver(symbols={"ES0148396007": ["ITX.PA"]}))

    r = await client.post(
        "/investment/securities/adopt",
        json={"listing_key": "ext:XMAD:ES0148396007"},
        headers=_auth(token),
    )

    assert r.status_code == 422
    assert "ITX.PA" in str(r.json()["detail"])


async def test_sin_cotizacion_real_no_hay_alta(
    client: AsyncClient, seeded_directory: None, test_engine
) -> None:
    """La regla universal §4.4: nada se persiste sin ver una cotización."""
    token = await _register(client, "dir10@example.com")
    _use_resolver(
        _FakeResolver(
            symbols={"ES0148396007": ["ITX.MC"]},
            quote=QuoteError(reason="el proveedor no cubre este símbolo o no respondió"),
        )
    )

    r = await client.post(
        "/investment/securities/adopt",
        json={"listing_key": "ext:XMAD:ES0148396007"},
        headers=_auth(token),
    )

    assert r.status_code == 422
    async with async_sessionmaker(bind=test_engine, expire_on_commit=False)() as db:
        count = len((await db.execute(select(Security))).scalars().all())
    assert count == 0, "no puede haberse persistido nada"


async def test_un_listing_fuera_del_directorio_es_404(client: AsyncClient) -> None:
    token = await _register(client, "dir11@example.com")
    _use_resolver(_FakeResolver())
    r = await client.post(
        "/investment/securities/adopt",
        # ISIN válido (checksum correcto) que no está sembrado.
        json={"listing_key": "ext:XPAR:FR0000120271"},
        headers=_auth(token),
    )
    assert r.status_code == 404


async def test_un_isin_con_errata_es_422_de_clave(client: AsyncClient) -> None:
    """El checksum del ISIN se valida al parsear la clave: una errata no es
    «otro valor», es basura que acabaría en un 404 confuso."""
    token = await _register(client, "dir12@example.com")
    r = await client.post(
        "/investment/securities/adopt",
        json={"listing_key": "ext:XMAD:ES0148396008"},  # checksum roto
        headers=_auth(token),
    )
    assert r.status_code == 422
