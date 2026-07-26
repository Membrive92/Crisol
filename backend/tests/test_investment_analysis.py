"""Tests del análisis end-to-end (PHASE-44.7).

resolve → ingest (adapter falso, hechos sintéticos) → run → veredicto persistido.
El engine puro ya tiene sus 188 tests; aquí se prueba el CABLEADO (builder
BD→engine, serialización a JSONB, persistencia y scoping).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from httpx import AsyncClient

from app.main import app
from app.modules.investment.fundamentals.adapters.base import SecurityIdentity, XbrlFact
from app.modules.investment.fundamentals.adapters.factory import get_fundamentals_adapter


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _bal(concept: str, value: object, year: int, accession: str) -> XbrlFact:
    return XbrlFact(
        taxonomy="us-gaap",
        concept=concept,
        value=Decimal(str(value)),
        unit="USD",
        period_end=date(year, 12, 31),
        period_start=None,
        form_type="10-K",
        fiscal_period="FY",
        fiscal_year=year,
        accession=accession,
        filing_date=date(year + 1, 2, 20),
    )


def _flow(concept: str, value: object, year: int, accession: str) -> XbrlFact:
    return XbrlFact(
        taxonomy="us-gaap",
        concept=concept,
        value=Decimal(str(value)),
        unit="USD",
        period_end=date(year, 12, 31),
        period_start=date(year, 1, 1),
        form_type="10-K",
        fiscal_period="FY",
        fiscal_year=year,
        accession=accession,
        filing_date=date(year + 1, 2, 20),
    )


def _year(year: int, accession: str, revenue: int) -> list[XbrlFact]:
    return [
        _bal("Assets", revenue * 2, year, accession),
        _bal("StockholdersEquity", revenue, year, accession),
        _bal("LiabilitiesCurrent", revenue // 4, year, accession),
        _bal("AssetsCurrent", revenue // 2, year, accession),
        _flow("Revenues", revenue, year, accession),
        _flow("OperatingIncomeLoss", int(revenue * 0.4), year, accession),
        _flow("NetIncomeLoss", int(revenue * 0.3), year, accession),
        _flow("NetCashProvidedByUsedInOperatingActivities", int(revenue * 0.35), year, accession),
    ]


_FACTS = _year(2022, "a-22", 24000) + _year(2023, "a-23", 25000) + _year(2024, "a-24", 26000)

_MCD = SecurityIdentity(
    ticker="MCD",
    cik="0000063908",
    name="MCDONALDS CORP",
    sic="5812",
    is_reit=False,
    is_financial=False,
)


class _FakeAdapter:
    async def resolve(self, ticker: str) -> SecurityIdentity:
        return _MCD

    async def fetch_facts(
        self, identity: SecurityIdentity, *, refresh: bool = False
    ) -> tuple[XbrlFact, ...]:
        return tuple(_FACTS)


def _override() -> None:
    app.dependency_overrides[get_fundamentals_adapter] = _FakeAdapter


async def _resolve_and_ingest(client: AsyncClient, token: str) -> str:
    resolved = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )
    security_id = resolved.json()["id"]
    await client.post(
        f"/investment/fundamentals/{security_id}/ingest",
        json={"filings_back": 5},
        headers=_auth(token),
    )
    return security_id


async def test_run_sin_datos_da_409(client: AsyncClient) -> None:
    token = await _register(client, "an1@example.com")
    _override()
    resolved = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )
    security_id = resolved.json()["id"]

    run = await client.post(
        f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token)
    )
    assert run.status_code == 409
    assert "ingesta" in run.json()["detail"].lower()


async def test_un_valor_sin_cik_da_422_con_motivo_no_409(client: AsyncClient) -> None:
    """Un 409 dice "falta un paso": lanza la ingesta. Pero para un valor sin CIK la
    ingesta NO puede funcionar nunca —no hay filing en EDGAR—, así que el usuario
    la lanzaba, fallaba y no había forma de entender por qué. 422 + motivo
    (PHASE-44.8 E1).
    """

    class _NoCikAdapter:
        async def resolve(self, ticker: str) -> SecurityIdentity:
            # Un listing no-US: sin CIK. Es lo que producirá la capa externa de la
            # Entrega 5 al adoptar Inditex o Iberdrola para llevarlas en cartera.
            return SecurityIdentity(ticker=ticker, cik="", name="INDUSTRIA DE DISENO TEXTIL")

        async def fetch_facts(
            self, identity: SecurityIdentity, *, refresh: bool = False
        ) -> tuple[XbrlFact, ...]:
            return ()

    token = await _register(client, "an-sin-cik@example.com")
    app.dependency_overrides[get_fundamentals_adapter] = _NoCikAdapter
    resolved = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "ITX"},
        headers=_auth(token),
    )
    security_id = resolved.json()["id"]
    assert resolved.json()["analysis_available"] is False

    run = await client.post(
        f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token)
    )

    assert run.status_code == 422, run.text
    detalle = run.json()["detail"]
    assert "ITX" in detalle
    assert "cartera" in detalle


async def test_run_produce_veredicto(client: AsyncClient) -> None:
    token = await _register(client, "an2@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token)

    run = await client.post(
        f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token)
    )
    assert run.status_code == 200, run.text
    data = run.json()

    assert data["engine_version"]
    assert len(data["thresholds_version"]) == 64
    assert data["years_covered"] == [2022, 2023, 2024]
    # confianza ∈ [0,1]
    assert Decimal("0") <= Decimal(data["confidence"]) <= Decimal("1")
    # las 4 preguntas de la síntesis salen con su semáforo
    questions = data["verdict"]["questions"]
    assert {q["key"] for q in questions} == {"accounting", "cash", "dividend", "resilience"}
    assert all(q["verdict"] in {"healthy", "caution", "stressed"} for q in questions)
    # el desglose viaja completo
    assert "forensic" in data["scores_detail"]
    assert "base_ratios" in data["scores_detail"]
    assert data["dividend_verdict"] in {"healthy", "caution", "stressed", "not_applicable"}


async def test_run_con_stress_params(client: AsyncClient) -> None:
    token = await _register(client, "an3@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token)

    run = await client.post(
        f"/investment/analysis/{security_id}/run",
        json={"stress_params": {"revenue_drops": ["0.15", "0.25"], "pct_variable_debt": "0.5"}},
        headers=_auth(token),
    )
    assert run.status_code == 200, run.text
    assert "stress" in run.json()["verdict"]


async def test_historico_y_scoping(client: AsyncClient) -> None:
    token_a = await _register(client, "an4a@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token_a)
    created = await client.post(
        f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token_a)
    )
    run_id = created.json()["id"]

    history = await client.get(f"/investment/analysis/{security_id}/runs", headers=_auth(token_a))
    assert [r["id"] for r in history.json()["items"]] == [run_id]

    detail = await client.get(f"/investment/analysis/runs/{run_id}", headers=_auth(token_a))
    assert detail.status_code == 200

    token_b = await _register(client, "an4b@example.com")
    theirs = await client.get(f"/investment/analysis/runs/{run_id}", headers=_auth(token_b))
    assert theirs.status_code == 404
