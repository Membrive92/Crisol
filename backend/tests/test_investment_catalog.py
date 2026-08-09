"""Tests del catálogo de valores (PHASE-44.7).

El mapeo SIC→sector se testea puro; los endpoints con un `FundamentalsAdapter`
falso inyectado por `dependency_overrides`, para no tocar la SEC.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.main import app
from app.modules.investment.catalog.sic_mapping import sic_to_sector
from app.modules.investment.enums import SectorInternal
from app.modules.investment.fundamentals.adapters.base import SecurityIdentity
from app.modules.investment.fundamentals.adapters.edgar import EdgarUnavailableError
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
    """Doble de `FundamentalsAdapter`: devuelve una identidad fija sin red."""

    def __init__(self, identity: SecurityIdentity) -> None:
        self._identity = identity

    async def resolve(self, ticker: str) -> SecurityIdentity:
        return self._identity

    async def fetch_facts(self, identity: SecurityIdentity, *, refresh: bool = False) -> tuple[()]:
        return ()


def _override_adapter(identity: SecurityIdentity) -> None:
    app.dependency_overrides[get_fundamentals_adapter] = lambda: _FakeAdapter(identity)


_MCD = SecurityIdentity(
    ticker="MCD",
    cik="0000063908",
    name="MCDONALDS CORP",
    sic="5812",
    is_reit=False,
    is_financial=False,
    annual_report_count=33,
    foreign_annual_report_count=0,
)
_O = SecurityIdentity(
    ticker="O",
    cik="0000726728",
    name="REALTY INCOME CORP",
    sic="6798",
    is_reit=True,
    is_financial=True,
)
# Recuentos reales, verificados ejecutando `edgartools` contra la SEC:
#   MCD  10-K=33  20-F=0   | SPY 10-K=0 20-F=0 | SAN 10-K=0 20-F=25
_SPY = SecurityIdentity(
    ticker="SPY",
    cik="0000884394",
    name="SPDR S&P 500 ETF TRUST",
    sic=None,
    annual_report_count=0,
    foreign_annual_report_count=0,
)
_SAN = SecurityIdentity(
    ticker="SAN",
    cik="0000891478",
    name="Banco Santander, S.A.",
    sic="6029",
    is_financial=True,
    annual_report_count=0,
    foreign_annual_report_count=25,
)


# ── Mapeo SIC → sector (puro) ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("sic", "expected"),
    [
        ("5812", SectorInternal.CONSUMER_DISCRETIONARY),  # restaurantes (MCD)
        ("6798", SectorInternal.REAL_ESTATE),  # REIT (O)
        ("2834", SectorInternal.HEALTHCARE),  # farma (JNJ)
        ("7372", SectorInternal.TECHNOLOGY),  # software
        ("6021", SectorInternal.FINANCIALS),  # banca comercial
        ("4911", SectorInternal.UTILITIES),  # eléctricas
        ("1311", SectorInternal.ENERGY),  # petróleo y gas
        ("5411", SectorInternal.CONSUMER_STAPLES),  # supermercados
        (None, SectorInternal.UNKNOWN),
        ("no-numérico", SectorInternal.UNKNOWN),
    ],
)
def test_sic_to_sector(sic: str | None, expected: SectorInternal) -> None:
    assert sic_to_sector(sic) == expected


# ── Endpoints ─────────────────────────────────────────────────────────


async def test_resolve_crea_el_security(client: AsyncClient) -> None:
    token = await _register(client, "cat1@example.com")
    _override_adapter(_MCD)

    r = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "mcd", "exchange": "nyse"},
        headers=_auth(token),
    )

    assert r.status_code == 201, r.text
    data = r.json()
    assert data["ticker"] == "MCD"
    assert data["exchange"] == "NYSE"
    assert data["cik"] == "0000063908"
    assert data["sector"] == "consumer_discretionary"
    assert data["accounting_std"] == "GAAP"
    assert data["is_financial"] is False
    assert data["analysis_available"] is True


async def test_resolve_es_idempotente(client: AsyncClient) -> None:
    token = await _register(client, "cat2@example.com")
    _override_adapter(_MCD)

    first = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )
    second = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


async def test_resolve_reit_marca_sector_y_flag(client: AsyncClient) -> None:
    token = await _register(client, "cat3@example.com")
    _override_adapter(_O)

    r = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "O", "exchange": "NYSE"},
        headers=_auth(token),
    )

    data = r.json()
    assert data["sector"] == "real_estate"
    assert data["is_reit"] is True


async def test_search_encuentra_por_ticker_y_nombre(client: AsyncClient) -> None:
    token = await _register(client, "cat4@example.com")
    _override_adapter(_MCD)
    await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )

    by_ticker = await client.get("/investment/securities/search?q=mc", headers=_auth(token))
    by_name = await client.get("/investment/securities/search?q=mcdonald", headers=_auth(token))

    assert by_ticker.status_code == 200
    assert [h["ticker"] for h in by_ticker.json()["results"]] == ["MCD"]
    assert by_ticker.json()["results"][0]["analysis_available"] is True
    assert by_ticker.json()["external_search_available"] is False
    assert [h["ticker"] for h in by_name.json()["results"]] == ["MCD"]


async def test_get_por_id_y_404(client: AsyncClient) -> None:
    token = await _register(client, "cat5@example.com")
    _override_adapter(_MCD)
    created = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )
    security_id = created.json()["id"]

    ok = await client.get(f"/investment/securities/{security_id}", headers=_auth(token))
    missing = await client.get(
        "/investment/securities/00000000-0000-0000-0000-000000000000", headers=_auth(token)
    )

    assert ok.status_code == 200
    assert ok.json()["ticker"] == "MCD"
    assert missing.status_code == 404


async def test_endpoints_exigen_autenticacion(client: AsyncClient) -> None:
    r = await client.get("/investment/securities/search?q=mcd")
    assert r.status_code == 401


# ── El cliente ya no decide el mercado (PHASE-44.8 E1) ────────────────


async def test_un_pais_en_exchange_no_se_persiste_como_plaza(client: AsyncClient) -> None:
    """`'US'` es lo que mandaba `security-search.tsx` y lo que sigue mandando el
    móvil legacy. Se guarda `UNKNOWN` —"no lo sé"— en vez de afirmar una plaza
    inexistente que luego colisiona con la real."""
    token = await _register(client, "cat6@example.com")
    _override_adapter(_MCD)

    r = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "US"},
        headers=_auth(token),
    )

    assert r.status_code == 201, r.text
    assert r.json()["exchange"] == "UNKNOWN"


async def test_el_mismo_valor_pedido_con_dos_plazas_no_se_duplica(client: AsyncClient) -> None:
    """El bug que motiva la fase: la restricción única es `(ticker, exchange)`, así
    que un cliente que decía `'US'` y otro `'NYSE'` creaban DOS filas del mismo
    valor — dos ingestas, dos `AnalysisRun` y los lotes de cartera repartidos
    entre dos ids. La idempotencia real es por `(cik, ticker)`.

    Y de paso la fila converge: la plaza pasa de `UNKNOWN` a la real en cuanto
    alguien la aporta, sin crear nada nuevo.
    """
    token = await _register(client, "cat7@example.com")
    _override_adapter(_MCD)

    con_pais = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "US"},
        headers=_auth(token),
    )
    con_plaza = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )

    assert con_pais.json()["id"] == con_plaza.json()["id"]
    assert con_pais.json()["exchange"] == "UNKNOWN"
    assert con_plaza.json()["exchange"] == "NYSE"

    # Y sigue habiendo UNA sola fila para MCD.
    listado = await client.get("/investment/securities/search?q=MCD", headers=_auth(token))
    assert [h["ticker"] for h in listado.json()["results"]] == ["MCD"]


async def test_resolve_sin_exchange_es_valido(client: AsyncClient) -> None:
    """El campo es opcional desde E1: el frontend deja de inventarlo y el
    servidor no exige que el cliente sepa algo que no sabe."""
    token = await _register(client, "cat8@example.com")
    _override_adapter(_MCD)

    r = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD"},
        headers=_auth(token),
    )

    assert r.status_code == 201, r.text
    assert r.json()["exchange"] == "UNKNOWN"


async def test_una_plaza_conocida_no_se_degrada_a_desconocida(client: AsyncClient) -> None:
    """La convergencia va en un solo sentido. Si la fila ya tiene NYSE y llega una
    petición sin plaza (o con `'US'`), NO se pierde el dato bueno."""
    token = await _register(client, "cat9@example.com")
    _override_adapter(_MCD)

    await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )
    despues = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD"},
        headers=_auth(token),
    )

    assert despues.json()["exchange"] == "NYSE"


async def test_un_ticker_que_la_sec_no_conoce_devuelve_404(client: AsyncClient) -> None:
    """El adapter traduce `CompanyNotFoundError` de la librería a
    `EdgarUnavailableError`, y el router a 404 — que es lo que su docstring
    promete. Antes de E1 esto era un 500."""

    class _NotFoundAdapter:
        async def resolve(self, ticker: str) -> SecurityIdentity:
            raise EdgarUnavailableError(f"La SEC no conoce el ticker '{ticker}'.")

        async def fetch_facts(
            self, identity: SecurityIdentity, *, refresh: bool = False
        ) -> tuple[()]:
            return ()

    token = await _register(client, "cat10@example.com")
    app.dependency_overrides[get_fundamentals_adapter] = _NotFoundAdapter

    r = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "NOSUCHTICKER"},
        headers=_auth(token),
    )

    assert r.status_code == 404, r.text
    assert "NOSUCHTICKER" in r.json()["detail"]


async def test_un_etf_entra_en_el_catalogo_pero_no_como_analizable(client: AsyncClient) -> None:
    """El callejón de SPY. Tiene CIK y ficha en la SEC pero presenta 24F-2NT y
    N-CSR, cero 10-K (verificado en sus `submissions`), así que salía marcado como
    analizable; al elegirlo, la ingesta fallaba y el análisis contestaba "lanza la
    ingesta primero" — el mensaje mandaba a hacer lo que acababa de fallar.

    Lo que NO se hace es negarse a crearlo: SPY es una posición perfectamente
    legítima de tener en cartera. Se crea y se marca.
    """
    token = await _register(client, "cat-etf@example.com")
    _override_adapter(_SPY)

    r = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "SPY"},
        headers=_auth(token),
    )

    assert r.status_code == 201, r.text
    data = r.json()
    assert data["ticker"] == "SPY"  # existe: la cartera puede usarlo
    assert data["analysis_status"] == "no_annual"
    assert data["analysis_available"] is False
    assert "fondo" in data["analysis_reason"]


async def test_un_adr_europeo_dice_que_publica_en_ifrs_no_que_no_publica(
    client: AsyncClient,
) -> None:
    """Santander presenta 25 veintiefes y cero diez-kás. Meterlo en el mismo saco
    que SPY sería falso: publica cuentas anuales perfectamente, lo que falta es el
    mapa IFRS. El motivo tiene que decir eso."""
    token = await _register(client, "cat-adr@example.com")
    _override_adapter(_SAN)

    r = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "SAN"},
        headers=_auth(token),
    )

    data = r.json()
    assert data["analysis_status"] == "non_gaap"
    assert data["analysis_available"] is False
    assert "IFRS" in data["analysis_reason"]
    # Y la norma contable sale de esa MISMA evidencia, no de un literal. Con el
    # `GAAP` fijo que había antes, el día que `ANNUAL_FORMS` admitiera 20-F
    # estas cuentas se juzgarían con cortes US-GAAP sin que nada lo dijera:
    # `IFRS` es lo que hace que sus umbrales nazcan `uncalibrated`.
    assert data["accounting_std"] == "IFRS"


async def test_la_evidencia_se_refresca_al_volver_a_resolver(client: AsyncClient) -> None:
    """`analysis_status` es una foto, no una verdad eterna: quien hoy no presenta
    10-K puede presentarlo el año que viene. Si no se refrescara, sería una
    premisa que caduca en silencio (lección PHASE-43) con forma de columna."""
    token = await _register(client, "cat-refresh@example.com")

    _override_adapter(_SPY)
    primero = await client.post(
        "/investment/securities/resolve", json={"ticker": "SPY"}, headers=_auth(token)
    )
    assert primero.json()["analysis_status"] == "no_annual"

    # El mismo emisor, ahora presentando anuales.
    _override_adapter(
        SecurityIdentity(
            ticker="SPY",
            cik="0000884394",
            name="SPDR S&P 500 ETF TRUST",
            annual_report_count=1,
            foreign_annual_report_count=0,
        )
    )
    segundo = await client.post(
        "/investment/securities/resolve", json={"ticker": "SPY"}, headers=_auth(token)
    )

    assert segundo.json()["id"] == primero.json()["id"]  # sigue siendo la misma fila
    assert segundo.json()["analysis_status"] == "ok"
    assert segundo.json()["analysis_available"] is True


async def test_la_norma_contable_viaja_con_la_evidencia(client: AsyncClient) -> None:
    """Si la etiqueta no se refrescara con el veredicto, un emisor que empieza a
    presentar 10-K se quedaría marcado IFRS para siempre — exactamente la
    premisa caducada que derivarla viene a evitar."""
    token = await _register(client, "cat-std@example.com")

    _override_adapter(_SAN)
    primero = await client.post(
        "/investment/securities/resolve", json={"ticker": "SAN"}, headers=_auth(token)
    )
    assert primero.json()["accounting_std"] == "IFRS"

    # El mismo emisor, ahora presentando 10-K.
    _override_adapter(
        SecurityIdentity(
            ticker="SAN",
            cik="0000891478",
            name="Banco Santander, S.A.",
            sic="6022",
            is_financial=True,
            annual_report_count=1,
            foreign_annual_report_count=25,
        )
    )
    segundo = await client.post(
        "/investment/securities/resolve", json={"ticker": "SAN"}, headers=_auth(token)
    )

    assert segundo.json()["id"] == primero.json()["id"]
    assert segundo.json()["analysis_status"] == "ok"
    assert segundo.json()["accounting_std"] == "GAAP"


async def test_un_recuento_fallido_no_pisa_el_veredicto_anterior(client: AsyncClient) -> None:
    """Si el adapter no pudo contar (`None`), no sabemos nada nuevo: dejar el
    valor como estaba es lo correcto. Sobrescribir con "desconocido" perdería
    evidencia buena por un fallo de red."""
    token = await _register(client, "cat-nocount@example.com")

    _override_adapter(_SPY)
    await client.post(
        "/investment/securities/resolve", json={"ticker": "SPY"}, headers=_auth(token)
    )

    _override_adapter(
        SecurityIdentity(ticker="SPY", cik="0000884394", name="SPDR S&P 500 ETF TRUST")
    )
    despues = await client.post(
        "/investment/securities/resolve", json={"ticker": "SPY"}, headers=_auth(token)
    )

    assert despues.json()["analysis_status"] == "no_annual"


async def test_el_motivo_viaja_en_la_respuesta(client: AsyncClient) -> None:
    """`analysis_reason` existe para poder decir en la fila POR QUÉ algo no se
    puede analizar, en vez de dejar que falle después del clic. Con CIK no hay
    motivo que dar."""
    token = await _register(client, "cat11@example.com")
    _override_adapter(_MCD)

    r = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )

    assert r.json()["analysis_available"] is True
    assert r.json()["analysis_reason"] is None
