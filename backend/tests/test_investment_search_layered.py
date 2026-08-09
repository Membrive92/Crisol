"""Buscador por capas y adopción (PHASE-44.8 E2) — extremo a extremo.

El índice de la SEC se **inyecta** con filas conocidas (`set_index_for_tests`):
las de verdad son 10.365 y cualquier aserción sobre «qué sale primero» se
rompería con un bump de `edgartools` por motivos ajenos a este código. El
contrato con la librería lo verifica `test_investment_symbol_index.py`, que sí la
llama de verdad.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.main import app
from app.modules.investment.catalog import repository as repo
from app.modules.investment.catalog import symbol_index
from app.modules.investment.catalog.firds import FirdsRecord
from app.modules.investment.catalog.models import Security
from app.modules.investment.catalog.ranking import IndexRow, tokenize
from app.modules.investment.fundamentals.adapters.base import SecurityIdentity
from app.modules.investment.fundamentals.adapters.factory import get_fundamentals_adapter


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class _FakeAdapter:
    """Doble de `FundamentalsAdapter`. Cuenta las resoluciones para poder
    afirmar que `cat:` NO llama a EDGAR."""

    def __init__(self, identity: SecurityIdentity) -> None:
        self._identity = identity
        self.calls: list[str] = []

    async def resolve(self, ticker: str) -> SecurityIdentity:
        self.calls.append(ticker)
        return self._identity

    async def fetch_facts(self, identity: SecurityIdentity, *, refresh: bool = False) -> tuple[()]:
        return ()


_MCD_IDENTITY = SecurityIdentity(
    ticker="MCD",
    cik="0000063908",
    name="MCDONALDS CORP",
    sic="5812",
    is_reit=False,
    is_financial=False,
    annual_report_count=33,
    foreign_annual_report_count=0,
)


def _use_adapter(identity: SecurityIdentity) -> _FakeAdapter:
    adapter = _FakeAdapter(identity)
    app.dependency_overrides[get_fundamentals_adapter] = lambda: adapter
    return adapter


def _row(cik: int, ticker: str, venue: str, name: str) -> IndexRow:
    return IndexRow(
        cik=cik,
        ticker=ticker,
        venue=venue,
        name=name,
        name_upper=name.upper(),
        tokens=tokenize(name),
    )


# El mismo emisor (cik 891478) en su cotización principal y en su línea OTC.
_SAN = _row(891478, "SAN", "NYSE", "Banco Santander, S.A.")
_BCDRF = _row(891478, "BCDRF", "OTC", "Banco Santander, S.A.")
_MCD_ROW = _row(63908, "MCD", "NYSE", "MCDONALDS CORP")


@pytest.fixture
def seeded_index() -> None:
    symbol_index.set_index_for_tests((_MCD_ROW, _SAN, _BCDRF))


async def test_el_indice_aporta_valores_que_no_estan_en_el_catalogo(
    client: AsyncClient, seeded_index: None
) -> None:
    """La deuda que abrió esta entrega: sin índice, buscar por nombre sólo
    encontraba lo que ya habías dado de alta."""
    token = await _register(client, "srch1@example.com")

    body = (
        await client.get("/investment/securities/search?q=santander", headers=_auth(token))
    ).json()

    assert body["index_ready"] is True
    hit = next(h for h in body["results"] if h["ticker"] == "SAN")
    assert hit["in_catalog"] is False
    assert hit["id"] is None
    assert hit["source"] == "sec_index"
    assert hit["listing_key"] == "idx:NYSE:SAN"
    assert hit["exchange_label"] == "NYSE"


async def test_un_emisor_no_sale_dos_veces_aunque_este_en_las_dos_capas(
    client: AsyncClient, seeded_index: None
) -> None:
    """Dedup entre capas por **CIK**, no por `(ticker, plaza)`.

    Es la parte contraintuitiva: la fila del catálogo puede tener la plaza en
    `UNKNOWN` y el índice decir `NYSE`, así que el par no coincide y el mismo
    emisor saldría dos veces — pulsando la segunda se crearía un `Security`
    duplicado, que es justo el daño que este buscador viene a evitar.
    """
    token = await _register(client, "srch2@example.com")
    _use_adapter(_MCD_IDENTITY)
    await client.post(
        "/investment/securities/resolve", json={"ticker": "MCD"}, headers=_auth(token)
    )

    body = (
        await client.get("/investment/securities/search?q=mcdonalds", headers=_auth(token))
    ).json()

    mcd_hits = [h for h in body["results"] if h["ticker"] == "MCD"]
    assert len(mcd_hits) == 1
    assert mcd_hits[0]["in_catalog"] is True, "gana la del catálogo"


async def test_adoptar_una_fila_del_indice_guarda_su_plaza_real(
    client: AsyncClient, seeded_index: None, test_engine
) -> None:
    """Lo que aporta `adopt` sobre `resolve`: el ticker tecleado no lleva plaza,
    así que MCD entraba como `UNKNOWN`. La clave del índice sí la lleva."""
    token = await _register(client, "srch3@example.com")
    _use_adapter(_MCD_IDENTITY)

    r = await client.post(
        "/investment/securities/adopt",
        json={"listing_key": "idx:NYSE:MCD"},
        headers=_auth(token),
    )

    assert r.status_code == 201
    assert r.json()["exchange"] == "NYSE"
    async with async_sessionmaker(bind=test_engine, expire_on_commit=False)() as db:
        rows = (await db.execute(select(Security))).scalars().all()
        assert [s.exchange for s in rows] == ["NYSE"]


async def test_adoptar_la_linea_otc_de_un_cik_ya_adoptado_no_crea_otra_fila(
    client: AsyncClient, seeded_index: None, test_engine
) -> None:
    """Criterio de aceptación del plan. `SAN` y `BCDRF` son el mismo emisor."""
    token = await _register(client, "srch4@example.com")
    san_identity = SecurityIdentity(
        ticker="SAN",
        cik="0000891478",
        name="Banco Santander, S.A.",
        sic="6022",
        is_reit=False,
        is_financial=True,
        annual_report_count=0,
        foreign_annual_report_count=25,
    )
    _use_adapter(san_identity)

    await client.post(
        "/investment/securities/adopt",
        json={"listing_key": "idx:NYSE:SAN"},
        headers=_auth(token),
    )
    # El adapter devuelve la MISMA identidad (ticker SAN, cik 891478) porque es
    # el mismo emisor: es lo que hace EDGAR con la línea OTC de un ADR.
    second = await client.post(
        "/investment/securities/adopt",
        json={"listing_key": "idx:OTC:BCDRF"},
        headers=_auth(token),
    )

    assert second.status_code == 201
    async with async_sessionmaker(bind=test_engine, expire_on_commit=False)() as db:
        count = len((await db.execute(select(Security))).scalars().all())
    assert count == 1, "el mismo emisor no puede ocupar dos filas"


async def test_adoptar_algo_que_ya_esta_en_el_catalogo_no_llama_a_edgar(
    client: AsyncClient, seeded_index: None
) -> None:
    """`cat:` no necesita red: la fila ya existe. Gastar una petición por cada
    clic sobre un valor conocido sería tirar la cuota de la SEC."""
    token = await _register(client, "srch5@example.com")
    adapter = _use_adapter(_MCD_IDENTITY)
    created = await client.post(
        "/investment/securities/resolve", json={"ticker": "MCD"}, headers=_auth(token)
    )
    security_id = created.json()["id"]
    adapter.calls.clear()

    r = await client.post(
        "/investment/securities/adopt",
        json={"listing_key": f"cat:{security_id}"},
        headers=_auth(token),
    )

    assert r.status_code == 201
    assert r.json()["id"] == security_id
    assert adapter.calls == [], "no debía preguntarle a EDGAR"


async def test_una_clave_mal_formada_es_un_422_con_motivo(client: AsyncClient) -> None:
    """Y no un 500, ni un fallback a «trátalo como un ticker»: ese fallback
    convertiría un error del cliente en un 404 que habla de un ticker que el
    usuario nunca escribió."""
    token = await _register(client, "srch6@example.com")
    _use_adapter(_MCD_IDENTITY)

    for bad in ("idx:NYSE", "cat:no-es-un-uuid", "vete-a-saber:MCD"):
        r = await client.post(
            "/investment/securities/adopt", json={"listing_key": bad}, headers=_auth(token)
        )
        assert r.status_code == 422, bad
        assert r.json()["detail"], "un 422 mudo no le dice nada a nadie"


async def test_el_vacio_suizo_se_explica(client: AsyncClient, seeded_index: None) -> None:
    """Cero resultados para `NESN` no es «esa empresa no existe», es «SIX no
    reporta a los registros que cubrimos» (ADR-0010 §5). Un desplegable en
    blanco dice lo primero. (Antes el ejemplo era Inditex, pero desde
    PHASE-44.14 Inditex SALE del directorio FIRDS y su alias se retiró.)"""
    token = await _register(client, "srch7@example.com")

    body = (await client.get("/investment/securities/search?q=NESN", headers=_auth(token))).json()

    assert body["results"] == []
    assert body["notice"] is not None
    assert "SIX" in body["notice"]


async def test_sin_indice_cargado_la_respuesta_lo_declara(client: AsyncClient) -> None:
    """Cero resultados significan dos cosas distintas —«no hay coincidencias» y
    «el índice no está disponible»— y la segunda no se puede presentar como la
    primera. El `conftest` deja el índice vacío por defecto."""
    token = await _register(client, "srch8@example.com")

    body = (
        await client.get("/investment/securities/search?q=mcdonalds", headers=_auth(token))
    ).json()

    assert body["index_ready"] is False
    assert body["results"] == []


async def test_una_sola_letra_no_busca(client: AsyncClient) -> None:
    """Con un carácter la lista sería medio catálogo; el suelo es 2."""
    token = await _register(client, "srch9@example.com")
    r = await client.get("/investment/securities/search?q=m", headers=_auth(token))
    assert r.status_code == 422


def _allianz_record() -> FirdsRecord:
    """Allianz tal y como la publica FIRDS: segmento `XETA`, ya normalizado."""
    return FirdsRecord(
        isin="DE0008404005",
        mic="XETR",
        segment_mic="XETA",
        name="Allianz SE vink.Namens-Aktien o.N.",
        short_name="ALLIANZ SE/AKT VNAM O.N.",
        currency="EUR",
        cfi="ESVUFR",
        lei=None,
        first_trade_date=None,
        termination_date=None,
    )


SEEDED_AT = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


async def test_una_correccion_ortografica_no_desplaza_a_una_coincidencia_literal(
    client: AsyncClient, test_engine
) -> None:  # type: ignore[no-untyped-def]
    """El defecto que sólo apareció al USAR la app (PHASE-44.15).

    `allianz` no tiene NINGUNA coincidencia exacta en el índice de la SEC, así
    que su fuzzy proponía `ALLIANT`, `RALLIANT` y `ALLIANCE` —otras empresas— y
    esas filas llenaban el cupo **antes** de que el directorio pudiera ofrecer
    `Allianz SE`, que casa exacto por nombre. El fuzzy es un último recurso, y
    tiene que serlo entre TODAS las capas, no dentro de la suya.
    """
    token = await _register(client, "dir13@example.com")
    symbol_index.set_index_for_tests(
        (
            _row(63908, "MCD", "NYSE", "MCDONALDS CORP"),
            # La clase de ruido que produce el fuzzy sobre «ALLIANZ».
            _row(352541, "LNT", "NASDAQ", "ALLIANT ENERGY CORP"),
        )
    )
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        await repo.sync_directory_source(
            db,
            {("DE0008404005", "XETR"): _allianz_record()},
            source="ESMA",
            seeded_at=SEEDED_AT,
        )
        await db.commit()

    body = (
        await client.get("/investment/securities/search?q=allianz&limit=3", headers=_auth(token))
    ).json()

    assert body["results"], "no devolvió nada"
    assert (
        body["results"][0]["isin"] == "DE0008404005"
    ), "la corrección ortográfica del índice SEC adelantó al match literal del directorio"

    from sqlalchemy import delete

    from app.modules.investment.catalog.directory_models import ListingDirectoryEntry

    async with factory() as db:
        await db.execute(delete(ListingDirectoryEntry))
        await db.commit()


async def test_un_ticker_tecleado_entero_manda_sobre_el_orden_de_capas(
    client: AsyncClient,
) -> None:
    """El segundo defecto de la misma familia, también preexistente.

    Con McDonald's ya en el catálogo, teclear `MC` devolvía `MCD` —un match por
    PREFIJO de la capa 1— y dejaba fuera a Moelis, cuyo ticker es exactamente
    `MC`. El orden de capas es deliberado, pero no puede pisar la calidad de la
    coincidencia.
    """
    token = await _register(client, "dir14@example.com")
    _use_adapter(_MCD_IDENTITY)
    await client.post(
        "/investment/securities/resolve", json={"ticker": "MCD"}, headers=_auth(token)
    )
    symbol_index.set_index_for_tests((_row(1596967, "MC", "NYSE", "Moelis & Co"),))

    body = (
        await client.get("/investment/securities/search?q=MC&limit=3", headers=_auth(token))
    ).json()

    assert body["results"][0]["ticker"] == "MC", "el prefijo del catálogo adelantó al ticker exacto"
