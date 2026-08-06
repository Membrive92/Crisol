"""Endpoint de valoración (PHASE-44.12) — la capa impura.

Comprueba lo que el módulo puro no puede: que el precio llega, que la divisa se
convierte, y que la falta de cotización responde 200 con motivo en vez de un
error. Cero red: adapter de precios mockeado y tasas sembradas a mano.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.main import app
from app.modules.currency.models import ExchangeRate
from app.modules.investment.enums import AccountingStd, PeriodType, StatementSource
from app.modules.investment.fundamentals.adapters.base import SecurityIdentity
from app.modules.investment.fundamentals.adapters.factory import get_fundamentals_adapter
from app.modules.investment.fundamentals.models import FinancialStatement
from app.modules.investment.pricing.adapters.base import Quote, QuoteError, QuoteRequest
from app.modules.investment.pricing.adapters.factory import get_price_adapter


class _FundAdapter:
    async def resolve(self, ticker: str) -> SecurityIdentity:
        return SecurityIdentity(
            ticker=ticker.upper(),
            cik="0000063908",
            name="MCDONALDS CORP",
            sic="5812",
            is_reit=False,
            is_financial=False,
        )

    async def fetch_facts(self, identity: SecurityIdentity, *, refresh: bool = False) -> tuple[()]:
        return ()


class _PriceAdapter:
    def __init__(self, quote: Quote | None) -> None:
        self._quote = quote

    async def quotes(self, requests: Sequence[QuoteRequest]) -> dict[str, Quote | QuoteError]:
        if self._quote is None:
            return {
                r.key: QuoteError(reason="el proveedor no cubre este símbolo") for r in requests
            }
        return {r.key: self._quote for r in requests}


def _quote(price: str, currency: str = "USD") -> Quote:
    return Quote(
        price=Decimal(price),
        prev_close=None,
        currency=currency,
        as_of=datetime.now(UTC),
    )


def _use(quote: Quote | None) -> None:
    app.dependency_overrides[get_fundamentals_adapter] = _FundAdapter
    app.dependency_overrides[get_price_adapter] = lambda: _PriceAdapter(quote)


@pytest_asyncio.fixture(autouse=True)
async def _seed_rates(test_engine) -> AsyncIterator[None]:  # type: ignore[no-untyped-def]
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        today = datetime.now(UTC).date()
        for quote, rate in (("USD", "1.10"), ("GBP", "0.85")):
            db.add(
                ExchangeRate(
                    rate_date=today,
                    base="EUR",
                    quote=quote,
                    rate=Decimal(rate),
                    source="test",
                    fetched_at=datetime.now(UTC),
                )
            )
        await db.commit()
    yield


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _mcd_with_statement(client: AsyncClient, token: str, test_engine) -> str:  # type: ignore[no-untyped-def]
    """MCD en catálogo + su FY2025 real (cifras de la SEC)."""
    resolved = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )
    security_id = resolved.json()["id"]

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        db.add(
            FinancialStatement(
                security_id=security_id,
                fiscal_year=2025,
                fiscal_year_end=date(2025, 12, 31),
                period_type=PeriodType.ANNUAL,
                filing_accession="0000063908-26-000035",
                is_latest_view=True,
                filing_date=date(2026, 2, 24),
                source=StatementSource.EDGAR_XBRL,
                accounting_std=AccountingStd.GAAP,
                currency="USD",
                revenue=Decimal("26885000000"),
                net_income=Decimal("8563000000"),
                equity=Decimal("-1791000000"),
                cfo=Decimal("10551000000"),
                capex=Decimal("3365000000"),
                ebit=Decimal("12393000000"),
                depreciation_amortization=Decimal("457000000"),
                short_term_debt=Decimal("798000000"),
                ltd_current_portion=Decimal("725000000"),
                long_term_debt=Decimal("39973000000"),
                cash=Decimal("774000000"),
                current_financial_assets=Decimal("0"),
                shares_outstanding_eop=Decimal("710398642"),
                raw_source_ref={},
            )
        )
        await db.commit()
    return security_id


def _by_key(payload: dict) -> dict[str, dict]:
    return {m["key"]: m for m in payload["metrics"]}


# ── Camino feliz ──────────────────────────────────────────────────────


async def test_valoracion_con_cotizacion_del_proveedor(client: AsyncClient, test_engine) -> None:
    token = await _register(client, "val1@example.com")
    _use(_quote("298.40"))
    sid = await _mcd_with_statement(client, token, test_engine)

    r = await client.get(f"/investment/analysis/{sid}/valuation", headers=_auth(token))
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["available"] is True
    assert data["price_is_override"] is False
    assert Decimal(data["market_cap"]) == Decimal("211982954772.80")

    metrics = _by_key(data)
    assert round(Decimal(metrics["V1"]["value"]), 2) == Decimal("24.76")
    assert round(Decimal(metrics["V5"]["value"]), 2) == Decimal("19.67")
    # El patrimonio de MCD es negativo: el P/VC no existe y se dice por qué.
    assert metrics["V3"]["status"] == "not_computable"
    assert "patrimonio" in metrics["V3"]["reason"]


async def test_las_dos_fechas_viajan_para_el_doble_staleness(
    client: AsyncClient, test_engine
) -> None:
    """Un PER con precio de hoy sobre cuentas de hace meses no es falso, pero
    la pantalla tiene que poder decirlo."""
    token = await _register(client, "val2@example.com")
    _use(_quote("298.40"))
    sid = await _mcd_with_statement(client, token, test_engine)

    data = (await client.get(f"/investment/analysis/{sid}/valuation", headers=_auth(token))).json()

    assert data["fiscal_year_end"] == "2025-12-31"
    assert data["quote_as_of"] is not None
    assert data["days_since_fiscal_year_end"] > 0


# ── Sin cotización ────────────────────────────────────────────────────


async def test_sin_cotizacion_responde_200_con_motivo(client: AsyncClient, test_engine) -> None:
    """No es un error del sistema: es un múltiplo que no se puede calcular, y
    la pantalla enseña el motivo con la salida (introducir precio a mano)."""
    token = await _register(client, "val3@example.com")
    _use(None)
    sid = await _mcd_with_statement(client, token, test_engine)

    r = await client.get(f"/investment/analysis/{sid}/valuation", headers=_auth(token))

    assert r.status_code == 200
    data = r.json()
    assert data["available"] is False
    assert data["metrics"] == []
    assert "a mano" in data["reason"]
    assert data["provider_status"] == "unreachable"


async def test_precio_manual_permite_valorar_sin_proveedor(
    client: AsyncClient, test_engine
) -> None:
    """El override cubre dos casos: simular una entrada y los valores que el
    proveedor no cotiza."""
    token = await _register(client, "val4@example.com")
    _use(None)
    sid = await _mcd_with_statement(client, token, test_engine)

    r = await client.get(f"/investment/analysis/{sid}/valuation?price=250", headers=_auth(token))
    data = r.json()

    assert data["available"] is True
    assert data["price_is_override"] is True, "un precio inventado debe declararse"
    # 250 x 710.398.642 / 8.563.000.000 = 20,74
    assert round(Decimal(_by_key(data)["V1"]["value"]), 2) == Decimal("20.74")


async def test_sin_ejercicios_lo_dice_en_vez_de_romper(client: AsyncClient) -> None:
    token = await _register(client, "val5@example.com")
    _use(_quote("298.40"))
    resolved = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )

    r = await client.get(
        f"/investment/analysis/{resolved.json()['id']}/valuation", headers=_auth(token)
    )

    assert r.status_code == 200
    assert r.json()["available"] is False
    assert "ingerido" in r.json()["reason"]


# ── Divisa ────────────────────────────────────────────────────────────


async def test_cotizacion_en_otra_divisa_se_convierte_a_la_de_las_cuentas(
    client: AsyncClient, test_engine
) -> None:
    """Las cuentas de MCD están en USD. Si el proveedor devolviera GBP, el
    precio hay que convertirlo o el múltiplo mezclaría divisas en silencio."""
    token = await _register(client, "val6@example.com")
    _use(_quote("230.00", currency="GBP"))
    sid = await _mcd_with_statement(client, token, test_engine)

    data = (await client.get(f"/investment/analysis/{sid}/valuation", headers=_auth(token))).json()

    assert data["available"] is True
    assert data["fx_rate"] is not None, "debe declarar que hubo conversión"
    assert data["fx_as_of"] is not None
    # GBP->USD compuesto por EUR: 230 x (1,10/0,85) = 297,65
    assert round(Decimal(data["market_cap"]) / Decimal("710398642"), 2) == Decimal("297.65")


async def test_sin_tipo_de_cambio_no_se_mezclan_divisas(client: AsyncClient, test_engine) -> None:
    """`convert` con `fallback='missing'` devuelve el importe SIN convertir y
    rate=1 (ADR-0009). Darlo por bueno mezclaría divisas dentro del múltiplo."""
    token = await _register(client, "val7@example.com")
    _use(_quote("230.00", currency="XAF"))  # fuera de la cobertura del BCE
    sid = await _mcd_with_statement(client, token, test_engine)

    data = (await client.get(f"/investment/analysis/{sid}/valuation", headers=_auth(token))).json()

    assert data["available"] is False
    assert "tipo de cambio" in data["reason"]


# ── Nada se persiste ──────────────────────────────────────────────────


async def test_la_valoracion_no_crea_ningun_analysis_run(client: AsyncClient, test_engine) -> None:
    """El motor forense es reproducible porque no depende del precio. Si la
    valoración se guardara en un run, reejecutarlo daría otro número."""
    from sqlalchemy import func, select

    from app.modules.investment.analysis.models import AnalysisRun

    token = await _register(client, "val8@example.com")
    _use(_quote("298.40"))
    sid = await _mcd_with_statement(client, token, test_engine)
    await client.get(f"/investment/analysis/{sid}/valuation", headers=_auth(token))

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        total = (await db.execute(select(func.count()).select_from(AnalysisRun))).scalar_one()

    assert total == 0


async def test_cotizacion_caducada_no_bloquea_pero_se_marca(
    client: AsyncClient, test_engine
) -> None:
    from sqlalchemy import update

    from app.modules.investment.pricing.models import PriceQuote

    token = await _register(client, "val9@example.com")
    _use(_quote("298.40"))
    sid = await _mcd_with_statement(client, token, test_engine)
    await client.get(f"/investment/analysis/{sid}/valuation", headers=_auth(token))

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(
            update(PriceQuote).values(fetched_at=datetime.now(UTC) - timedelta(days=30))
        )
        await db.commit()

    _use(None)  # el proveedor ya no responde: se conserva la última
    data = (await client.get(f"/investment/analysis/{sid}/valuation", headers=_auth(token))).json()

    assert data["available"] is True
    assert data["quote_stale"] is True
    assert data["provider_status"] == "unreachable"
    assert any(
        "no ha respondido" in n for n in data["notes"]
    ), "cuando el proveedor falla hay que decirlo, no sólo marcar la quote como vieja"


# ── Estado del proveedor ──────────────────────────────────────────────


async def test_proveedor_vivo_se_declara_live(client: AsyncClient, test_engine) -> None:
    token = await _register(client, "val10@example.com")
    _use(_quote("298.40"))
    sid = await _mcd_with_statement(client, token, test_engine)

    data = (await client.get(f"/investment/analysis/{sid}/valuation", headers=_auth(token))).json()

    assert data["provider_status"] == "live"


async def test_dentro_del_ttl_no_se_afirma_que_el_proveedor_este_vivo(
    client: AsyncClient, test_engine
) -> None:
    """La segunda consulta no le pide nada al proveedor porque la cotización
    sigue fresca. Pintarla en verde sería afirmar una comprobación que no se ha
    hecho, así que el estado es `cached` y no `live`."""
    token = await _register(client, "val11@example.com")
    _use(_quote("298.40"))
    sid = await _mcd_with_statement(client, token, test_engine)

    primera = (
        await client.get(f"/investment/analysis/{sid}/valuation", headers=_auth(token))
    ).json()
    segunda = (
        await client.get(f"/investment/analysis/{sid}/valuation", headers=_auth(token))
    ).json()

    assert primera["provider_status"] == "live"
    assert segunda["provider_status"] == "cached"
    # El precio es el mismo: no se ha perdido nada por no volver a preguntar.
    assert segunda["market_cap"] == primera["market_cap"]


async def test_precio_a_mano_no_afirma_nada_del_proveedor(client: AsyncClient, test_engine) -> None:
    token = await _register(client, "val12@example.com")
    _use(None)
    sid = await _mcd_with_statement(client, token, test_engine)

    data = (
        await client.get(f"/investment/analysis/{sid}/valuation?price=250", headers=_auth(token))
    ).json()

    assert data["available"] is True
    assert data["provider_status"] == "cached", "con precio manual no se consulta a nadie"
