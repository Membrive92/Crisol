"""Tests de ingesta de fundamentales (PHASE-44.7).

`restatements` se testea puro; la ingesta end-to-end con un `FundamentalsAdapter`
falso que devuelve hechos sintéticos, sin tocar la SEC.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from httpx import AsyncClient

from app.main import app
from app.modules.investment.fundamentals.adapters.base import SecurityIdentity, XbrlFact
from app.modules.investment.fundamentals.adapters.edgar import EdgarUnavailableError
from app.modules.investment.fundamentals.adapters.factory import get_fundamentals_adapter
from app.modules.investment.fundamentals.restatements import detect_restatements


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── Hechos sintéticos ─────────────────────────────────────────────────


def _bal(
    concept: str, value: object, year: int, accession: str, *, fy: int | None = None
) -> XbrlFact:
    return XbrlFact(
        taxonomy="us-gaap",
        concept=concept,
        value=Decimal(str(value)),
        unit="USD",
        period_end=date(year, 12, 31),
        period_start=None,
        form_type="10-K",
        fiscal_period="FY",
        fiscal_year=fy or year,
        accession=accession,
        filing_date=date(year + 1, 2, 20),
    )


def _flow(
    concept: str, value: object, year: int, accession: str, *, fy: int | None = None
) -> XbrlFact:
    return XbrlFact(
        taxonomy="us-gaap",
        concept=concept,
        value=Decimal(str(value)),
        unit="USD",
        period_end=date(year, 12, 31),
        period_start=date(year, 1, 1),
        form_type="10-K",
        fiscal_period="FY",
        fiscal_year=fy or year,
        accession=accession,
        filing_date=date(year + 1, 2, 20),
    )


def _year_facts(
    year: int, accession: str, *, assets: int, equity: int, revenue: int
) -> list[XbrlFact]:
    return [
        _bal("Assets", assets, year, accession),
        _bal("StockholdersEquity", equity, year, accession),
        _flow("Revenues", revenue, year, accession),
        _flow("OperatingIncomeLoss", int(revenue * 0.4), year, accession),
        _flow("NetIncomeLoss", int(revenue * 0.3), year, accession),
    ]


_CLEAN_FACTS = _year_facts(2023, "a-23", assets=56000, equity=4000, revenue=25000) + _year_facts(
    2024, "a-24", assets=59000, equity=4200, revenue=26000
)


class _FakeAdapter:
    def __init__(self, identity: SecurityIdentity, facts: Sequence[XbrlFact]) -> None:
        self._identity = identity
        self._facts = tuple(facts)

    async def resolve(self, ticker: str) -> SecurityIdentity:
        return self._identity

    async def fetch_facts(
        self, identity: SecurityIdentity, *, refresh: bool = False
    ) -> tuple[XbrlFact, ...]:
        return self._facts


class _FailingAdapter:
    def __init__(self, identity: SecurityIdentity) -> None:
        self._identity = identity

    async def resolve(self, ticker: str) -> SecurityIdentity:
        return self._identity

    async def fetch_facts(self, identity: SecurityIdentity, *, refresh: bool = False) -> tuple[()]:
        raise EdgarUnavailableError("la SEC no respondió")


def _override(adapter: object) -> None:
    app.dependency_overrides[get_fundamentals_adapter] = lambda: adapter


_MCD = SecurityIdentity(
    ticker="MCD",
    cik="0000063908",
    name="MCDONALDS CORP",
    sic="5812",
    is_reit=False,
    is_financial=False,
)
_NO_CIK = SecurityIdentity(
    ticker="XX", cik=None, name="FOREIGN CO", sic=None, is_reit=False, is_financial=False
)


async def _resolve(
    client: AsyncClient, token: str, ticker: str = "MCD", exchange: str = "NYSE"
) -> str:
    r = await client.post(
        "/investment/securities/resolve",
        json={"ticker": ticker, "exchange": exchange},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── restatements (puro) ───────────────────────────────────────────────


def test_detect_restatements_marca_divergencia_sobre_umbral() -> None:
    facts = [
        _flow("Revenues", 25000, 2023, "a-23"),
        _bal("Assets", 56000, 2023, "a-23"),
        # El 10-K de 2024 reexpresa 2023: 25000 → 24000 (4% > 1%).
        _flow("Revenues", 24000, 2023, "a-24", fy=2024),
        _bal("Assets", 56000, 2023, "a-24", fy=2024),
    ]
    result = detect_restatements(facts)
    assert len(result) == 1
    comp = result[0]
    assert comp.fiscal_year == 2023
    assert comp.filing_a == "a-23"
    assert comp.filing_b == "a-24"
    concepts = {d["concept"] for d in comp.divergences}
    assert "us-gaap:Revenues" in concepts
    assert "us-gaap:Assets" not in concepts  # no cambió


def test_detect_restatements_ignora_cambios_pequenos() -> None:
    facts = [
        _flow("Revenues", 25000, 2023, "a-23"),
        _flow("Revenues", 25100, 2023, "a-24", fy=2024),  # 0,4% < 1%
    ]
    assert detect_restatements(facts) == []


# ── Ingesta E2E ───────────────────────────────────────────────────────


async def test_ingesta_persiste_estados(client: AsyncClient) -> None:
    token = await _register(client, "fund1@example.com")
    _override(_FakeAdapter(_MCD, _CLEAN_FACTS))
    security_id = await _resolve(client, token)

    ingest = await client.post(
        f"/investment/fundamentals/{security_id}/ingest",
        json={"filings_back": 5},
        headers=_auth(token),
    )
    assert ingest.status_code == 202, ingest.text
    job = ingest.json()
    assert job["status"] == "done"
    assert job["progress"]["filings_done"] == 2

    statements = await client.get(
        f"/investment/fundamentals/{security_id}/statements", headers=_auth(token)
    )
    items = statements.json()["items"]
    assert [s["fiscal_year"] for s in items] == [2023, 2024]
    s2023 = items[0]
    assert s2023["total_assets"] == "56000.0000"
    assert s2023["ebit"] == "10000.0000"  # OperatingIncomeLoss sourced (25000*0.4)
    # total_liabilities derivado = activo - patrimonio = 56000 - 4000
    assert s2023["total_liabilities"] == "52000.0000"
    assert s2023["is_latest_view"] is True


async def test_ingesta_detecta_reexpresion(client: AsyncClient) -> None:
    token = await _register(client, "fund2@example.com")
    facts = [
        *_CLEAN_FACTS,
        _flow("Revenues", 24000, 2023, "a-24", fy=2024),
        _bal("Assets", 56000, 2023, "a-24", fy=2024),
    ]
    _override(_FakeAdapter(_MCD, facts))
    security_id = await _resolve(client, token)

    await client.post(
        f"/investment/fundamentals/{security_id}/ingest",
        json={"filings_back": 5},
        headers=_auth(token),
    )
    restatements = await client.get(
        f"/investment/fundamentals/{security_id}/restatements", headers=_auth(token)
    )
    items = restatements.json()["items"]
    assert len(items) == 1
    assert items[0]["fiscal_year"] == 2023
    assert items[0]["filing_a"] == "a-23"


async def test_ingesta_fallida_deja_job_failed_no_500(client: AsyncClient) -> None:
    token = await _register(client, "fund3@example.com")
    _override(_FailingAdapter(_MCD))
    security_id = await _resolve(client, token)

    ingest = await client.post(
        f"/investment/fundamentals/{security_id}/ingest",
        json={"filings_back": 5},
        headers=_auth(token),
    )
    assert ingest.status_code == 202
    job = ingest.json()
    assert job["status"] == "failed"
    assert "SEC" in job["error"]


async def test_ingesta_sin_cik_falla_legible(client: AsyncClient) -> None:
    token = await _register(client, "fund4@example.com")
    _override(_FakeAdapter(_NO_CIK, ()))
    security_id = await _resolve(client, token, ticker="XX", exchange="LSE")

    ingest = await client.post(
        f"/investment/fundamentals/{security_id}/ingest",
        json={"filings_back": 5},
        headers=_auth(token),
    )
    job = ingest.json()
    assert job["status"] == "failed"
    assert "CIK" in job["error"]


async def test_ingest_404_si_no_existe_el_valor(client: AsyncClient) -> None:
    token = await _register(client, "fund5@example.com")
    _override(_FakeAdapter(_MCD, _CLEAN_FACTS))
    r = await client.post(
        "/investment/fundamentals/00000000-0000-0000-0000-000000000000/ingest",
        json={"filings_back": 5},
        headers=_auth(token),
    )
    assert r.status_code == 404


async def test_job_es_scoped_por_usuario(client: AsyncClient) -> None:
    token_a = await _register(client, "fund6a@example.com")
    _override(_FakeAdapter(_MCD, _CLEAN_FACTS))
    security_id = await _resolve(client, token_a)
    ingest = await client.post(
        f"/investment/fundamentals/{security_id}/ingest",
        json={"filings_back": 5},
        headers=_auth(token_a),
    )
    job_id = ingest.json()["id"]

    token_b = await _register(client, "fund6b@example.com")
    mine = await client.get(f"/investment/fundamentals/jobs/{job_id}", headers=_auth(token_a))
    theirs = await client.get(f"/investment/fundamentals/jobs/{job_id}", headers=_auth(token_b))

    assert mine.status_code == 200
    assert mine.json()["status"] == "done"
    assert theirs.status_code == 404
