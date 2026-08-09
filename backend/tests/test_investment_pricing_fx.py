"""Valoración en divisa base y política de refresco (PHASE-44.11.D/E).

Cero red: el adapter de precios es un doble y las tasas se siembran en
`exchange_rates` a mano (el cliente de Frankfurter no se toca — `convert` no
hace red, sólo lee la tabla; ADR-0009).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.main import app
from app.modules.currency.models import ExchangeRate
from app.modules.investment.fundamentals.adapters.base import SecurityIdentity
from app.modules.investment.fundamentals.adapters.factory import get_fundamentals_adapter
from app.modules.investment.pricing.adapters.base import Quote, QuoteError, QuoteRequest
from app.modules.investment.pricing.adapters.factory import get_price_adapter

#: CIK distinto por ticker: el catálogo deduplica por `(cik, ticker)`
#: (ADR-0008), así que dos valores del mismo test necesitan identidades
#: distintas o la segunda alta colapsaría sobre la primera.
_CIKS = {"MCD": "0000063908", "SAP": "0001000184", "XXX": "0000320193"}


class _FundAdapter:
    async def resolve(self, ticker: str) -> SecurityIdentity:
        return SecurityIdentity(
            ticker=ticker.upper(),
            cik=_CIKS.get(ticker.upper(), "0000000001"),
            name=f"{ticker.upper()} Test Co",
            sic="5812",
            is_reit=False,
            is_financial=False,
        )

    async def fetch_facts(self, identity: SecurityIdentity, *, refresh: bool = False) -> tuple[()]:
        return ()


class _Adapter:
    """Doble parametrizable: precio + divisa por ticker, o error."""

    def __init__(self, by_ticker: dict[str, Quote | QuoteError]) -> None:
        self._by_ticker = by_ticker
        self.calls = 0

    async def quotes(self, requests: Sequence[QuoteRequest]) -> dict[str, Quote | QuoteError]:
        self.calls += 1
        return {
            r.key: self._by_ticker.get(
                r.ticker.upper(), QuoteError(reason="sin cobertura del proveedor")
            )
            for r in requests
        }


def _quote(price: str, currency: str, prev: str | None = None) -> Quote:
    return Quote(
        price=Decimal(price),
        prev_close=Decimal(prev) if prev else None,
        currency=currency,
        as_of=datetime.now(UTC),
    )


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _use(adapter: _Adapter) -> None:
    app.dependency_overrides[get_fundamentals_adapter] = _FundAdapter
    app.dependency_overrides[get_price_adapter] = lambda: adapter


async def _seed_rate(test_engine, quote: str, rate: str, on: date) -> None:  # type: ignore[no-untyped-def]
    """Tasa EUR→quote. `convert` compone por EUR, que es la base canónica.

    Se siembra a mano para que ningún test toque Frankfurter: `convert` sólo lee
    la tabla, así que con la fila puesta no hay red por ningún lado.
    """
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        db.add(
            ExchangeRate(
                rate_date=on,
                base="EUR",
                quote=quote,
                rate=Decimal(rate),
                source="test",
                fetched_at=datetime.now(UTC),
            )
        )
        await db.commit()


async def _add_position(
    client: AsyncClient, token: str, ticker: str, *, qty: str, price: str
) -> str:
    resolved = await client.post(
        "/investment/securities/resolve",
        json={"ticker": ticker, "exchange": "NYSE"},
        headers=_auth(token),
    )
    sid = resolved.json()["id"]
    await client.post(
        "/investment/portfolio/lots",
        json={"security_id": sid, "trade_date": "2022-01-01", "quantity": qty, "price": price},
        headers=_auth(token),
    )
    return sid


# --------------------------------------------------------------------------
# E — valoración en base
# --------------------------------------------------------------------------


async def test_valor_en_base_usa_la_tasa_y_publica_su_fecha(
    client: AsyncClient, test_engine
) -> None:
    """El contrato que estaba declarado y sin alimentar desde PHASE-44.7."""
    today = datetime.now(UTC).date()
    await _seed_rate(test_engine, "USD", "1.25", today)  # 1 EUR = 1,25 USD

    token = await _register(client, "fx1@example.com")
    _use(_Adapter({"MCD": _quote("150", "USD")}))
    await _add_position(client, token, "MCD", qty="10", price="100")

    data = (await client.get("/investment/portfolio/summary", headers=_auth(token))).json()
    pos = data["positions"][0]

    assert data["base_currency"] == "EUR"
    assert Decimal(pos["market_value"]) == Decimal(1500)  # nativa (USD)
    # 1500 USD / 1,25 = 1200 EUR
    assert Decimal(pos["market_value_base"]) == Decimal(1200)
    assert Decimal(data["total_market_value_base"]) == Decimal(1200)
    assert pos["fx_as_of"] == today.isoformat()
    assert Decimal(pos["fx_rate"]) == Decimal("0.8")


async def test_fx_as_of_refleja_la_fecha_efectiva_no_la_de_hoy(
    client: AsyncClient, test_engine
) -> None:
    """Un lunes se usa la tasa del viernes, y el payload lo dice.

    Es la diferencia entre "convertido con datos de hoy" y "convertido con lo
    último que publicó el BCE", que no es lo mismo cuando el mercado se mueve.
    """
    today = datetime.now(UTC).date()
    stale_day = today - timedelta(days=3)
    await _seed_rate(test_engine, "USD", "1.25", stale_day)

    token = await _register(client, "fx2@example.com")
    _use(_Adapter({"MCD": _quote("150", "USD")}))
    await _add_position(client, token, "MCD", qty="10", price="100")

    data = (await client.get("/investment/portfolio/summary", headers=_auth(token))).json()
    pos = data["positions"][0]

    assert pos["fx_as_of"] == stale_day.isoformat()
    assert pos["fx_as_of"] != today.isoformat()
    assert Decimal(pos["market_value_base"]) == Decimal(1200)


async def test_sin_tasa_la_posicion_sale_de_totales_con_motivo(client: AsyncClient) -> None:
    """La trampa del ADR-0009: `convert` con `fallback='missing'` devuelve el
    importe SIN convertir y `rate=1`. Tomarlo por bueno sumaría la divisa
    extranjera como si fuera euros, en silencio.

    Se usa una divisa **fuera de la cobertura del BCE** (`XAF`) porque el
    snapshot offline de `currency` ya trae USD, GBP y las demás comunes: "no
    sembrar ninguna tasa" no basta para provocar el caso.
    """
    token = await _register(client, "fx3@example.com")
    _use(_Adapter({"MCD": _quote("150", "XAF")}))
    await _add_position(client, token, "MCD", qty="10", price="100")

    data = (await client.get("/investment/portfolio/summary", headers=_auth(token))).json()
    pos = data["positions"][0]

    assert Decimal(pos["market_value"]) == Decimal(1500)  # el nativo sí se enseña
    assert pos["market_value_base"] is None
    assert Decimal(data["total_market_value_base"]) == Decimal(0)  # NO 1500
    assert data["quoted_count"] == 0
    assert data["unquoted_count"] == 1
    assert "tipo de cambio" in (pos["exclusion_reason"] or "")


async def test_posicion_en_base_no_necesita_tasa(client: AsyncClient) -> None:
    """Un valor ya en EUR no depende de que haya tasa ninguna."""
    token = await _register(client, "fx4@example.com")
    _use(_Adapter({"MCD": _quote("150", "EUR")}))
    await _add_position(client, token, "MCD", qty="10", price="100")

    data = (await client.get("/investment/portfolio/summary", headers=_auth(token))).json()
    pos = data["positions"][0]

    assert Decimal(pos["market_value_base"]) == Decimal(1500)
    assert Decimal(pos["fx_rate"]) == Decimal(1)


async def test_price_effect_y_fx_effect_suman_el_pnl_en_base(
    client: AsyncClient, test_engine
) -> None:
    """La descomposición tiene que CUADRAR, no sólo existir.

    price_effect + fx_effect == market_value_base − coste_en_base. Si no cuadra,
    la pantalla estaría atribuyendo a la divisa algo que hizo el precio.
    """
    today = datetime.now(UTC).date()
    await _seed_rate(test_engine, "USD", "1.25", today)

    token = await _register(client, "fx5@example.com")
    _use(_Adapter({"MCD": _quote("150", "USD")}))
    await _add_position(client, token, "MCD", qty="10", price="100")

    data = (await client.get("/investment/portfolio/summary", headers=_auth(token))).json()
    pos = data["positions"][0]

    price_effect = Decimal(pos["price_effect"])
    fx_effect = Decimal(pos["fx_effect"])
    market_base = Decimal(pos["market_value_base"])

    # Contra el coste a tipo de COMPRA (`cost_basis_base`), no a tipo de hoy:
    # usar el de hoy escondería el efecto divisa entero, que es justo lo que la
    # descomposición existe para enseñar.
    assert price_effect + fx_effect == market_base - Decimal(pos["cost_basis_base"])
    assert Decimal(pos["unrealized_pnl_base"]) == market_base - Decimal(pos["cost_basis_base"])


async def test_el_fx_de_compra_se_deriva_del_bce_si_no_se_declara(
    client: AsyncClient, test_engine
) -> None:
    """Decisión del usuario (2026-08-02): omitir el FX significa "no lo sé".

    Antes el schema ponía `1`, que afirma paridad con el euro. Con FX vivo eso
    producía un efecto divisa inventado — el único lote real del usuario (JNJ en
    USD) estaba exactamente así.
    """
    trade_day = date(2026, 7, 24)
    await _seed_rate(test_engine, "USD", "1.25", trade_day)
    await _seed_rate(test_engine, "USD", "1.25", datetime.now(UTC).date())

    token = await _register(client, "fx8@example.com")
    _use(_Adapter({"MCD": _quote("150", "USD")}))
    resolved = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )
    sid = resolved.json()["id"]
    created = await client.post(
        "/investment/portfolio/lots",
        # Sin `fx_rate_at_trade`: es el caso que producía el dato ficticio.
        json={
            "security_id": sid,
            "trade_date": trade_day.isoformat(),
            "quantity": "10",
            "price": "100",
        },
        headers=_auth(token),
    )

    assert created.status_code == 201, created.text
    assert Decimal(created.json()["fx_rate_at_trade"]) == Decimal("0.8")  # 1/1,25, no 1

    data = (await client.get("/investment/portfolio/summary", headers=_auth(token))).json()
    pos = data["positions"][0]
    # Coste 1000 USD a 0,8 = 800 EUR; valor 1500 USD a 0,8 = 1200 EUR.
    assert Decimal(pos["cost_basis_base"]) == Decimal(800)
    assert Decimal(pos["unrealized_pnl_base"]) == Decimal(400)
    # Mismo tipo en compra y hoy → la divisa no movió nada. Antes salía −200 €.
    assert Decimal(pos["fx_effect"]) == Decimal(0)


async def test_no_se_conforma_con_una_tasa_dentro_de_la_ventana_de_fallback(
    client: AsyncClient, test_engine, monkeypatch
) -> None:
    """Regresión del hallazgo del 2026-08-02.

    `ensure_rates_for_dates` da por buena cualquier tasa dentro de su ventana de
    14 días y no pide nada. Verificado contra la BD real: con la última tasa a
    15 días, convertir "ayer" resolvía con la del 18 de julio — precio de hoy ×
    tipo de hace dos semanas. La cartera exige tasa EXACTA del día y la pide si
    falta; este test comprueba que la PIDE, no que la política de `currency`
    haya cambiado (no ha cambiado).
    """
    today = datetime.now(UTC).date()
    # Sólo hay tasa de hace 5 días: dentro de la ventana de fallback, así que el
    # canario de `ensure_rates_for_dates` se habría dado por satisfecho.
    await _seed_rate(test_engine, "USD", "1.10", today - timedelta(days=5))

    asked: list[tuple[date, list[str]]] = []

    async def fake_refresh(db, *, target_date, quotes, base="EUR", timeout=None):  # type: ignore[no-untyped-def]
        asked.append((target_date, sorted(quotes)))
        return 0

    monkeypatch.setattr(
        "app.modules.investment.pricing.service.currency_service.refresh_rates", fake_refresh
    )

    token = await _register(client, "fx10@example.com")
    _use(_Adapter({"MCD": _quote("150", "USD")}))
    await _add_position(client, token, "MCD", qty="10", price="100")
    await client.get("/investment/portfolio/summary", headers=_auth(token))

    assert (today, ["USD"]) in asked, "no se pidió la tasa del día pese a faltar la exacta"


async def test_no_pide_tasa_si_ya_esta_la_del_dia(
    client: AsyncClient, test_engine, monkeypatch
) -> None:
    """Y no gasta una petición cuando ya la tiene."""
    today = datetime.now(UTC).date()
    await _seed_rate(test_engine, "USD", "1.25", today)

    called = False

    async def fake_refresh(db, *, target_date, quotes, base="EUR", timeout=None):  # type: ignore[no-untyped-def]
        nonlocal called
        called = True
        return 0

    monkeypatch.setattr(
        "app.modules.investment.pricing.service.currency_service.refresh_rates", fake_refresh
    )

    token = await _register(client, "fx11@example.com")
    _use(_Adapter({"MCD": _quote("150", "USD")}))
    await _add_position(client, token, "MCD", qty="10", price="100")
    await client.get("/investment/portfolio/summary", headers=_auth(token))

    assert called is False


async def test_si_el_proveedor_de_tasas_cae_se_sigue_con_lo_que_haya(
    client: AsyncClient, test_engine, monkeypatch
) -> None:
    """Un domingo no hay tasa del BCE, y eso no puede tumbar la cartera."""
    from app.modules.currency.exceptions import FrankfurterUnavailableError

    stale_day = datetime.now(UTC).date() - timedelta(days=2)
    await _seed_rate(test_engine, "USD", "1.25", stale_day)

    async def boom(db, *, target_date, quotes, base="EUR", timeout=None):  # type: ignore[no-untyped-def]
        raise FrankfurterUnavailableError("sin red")

    monkeypatch.setattr(
        "app.modules.investment.pricing.service.currency_service.refresh_rates", boom
    )

    token = await _register(client, "fx12@example.com")
    _use(_Adapter({"MCD": _quote("150", "USD")}))
    await _add_position(client, token, "MCD", qty="10", price="100")

    response = await client.get("/investment/portfolio/summary", headers=_auth(token))
    assert response.status_code == 200
    pos = response.json()["positions"][0]
    assert Decimal(pos["market_value_base"]) == Decimal(1200)  # con la tasa vieja
    assert pos["fx_as_of"] == stale_day.isoformat()  # y diciendo de cuándo es


async def test_se_puede_cotizar_un_valor_sin_tenerlo_en_cartera(
    client: AsyncClient, test_engine
) -> None:
    """PHASE-44.12: tener posición no puede ser requisito para cotizar.

    El refresco de la cartera filtra por `quantity > 0`, que es correcto para
    valorar lo que tienes. Pero la pestaña de Análisis mira valores ANTES de
    comprarlos: si el precio dependiera de tener el valor, los múltiplos sólo
    existirían cuando ya no sirven para decidir la compra.
    """
    from sqlalchemy import select

    from app.modules.investment.catalog.models import Security
    from app.modules.investment.pricing.service import quote_security

    token = await _register(client, "noposicion@example.com")
    adapter = _Adapter({"MCD": _quote("298.40", "USD")})
    _use(adapter)

    # Alta en catálogo SIN comprar ni una acción.
    resolved = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )
    assert resolved.status_code in (200, 201), resolved.text

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        security = (await db.execute(select(Security).where(Security.ticker == "MCD"))).scalar_one()
        outcome = await quote_security(db, adapter, security)
        quote = outcome.quote
        # Los atributos se leen DENTRO de la sesión: fuera, el objeto queda
        # detached y el acceso intentaría una carga perezosa desde código
        # síncrono (lección PHASE-4.1, `MissingGreenlet`).
        found = quote is not None
        price = quote.price if quote else None
        currency = quote.currency if quote else None
        status = outcome.provider_status
        await db.commit()

    assert found, "un valor sin posición debe poder cotizarse"
    assert price == Decimal("298.40")
    assert currency == "USD"
    assert status == "live", "se le ha pedido al proveedor y ha respondido"


async def test_valor_sin_cobertura_del_proveedor_no_revienta_el_analisis(
    client: AsyncClient, test_engine
) -> None:
    """Sin cotización se devuelve `None`, no una excepción: el análisis forense
    sigue siendo válido aunque no se puedan calcular los múltiplos."""
    from sqlalchemy import select

    from app.modules.investment.catalog.models import Security
    from app.modules.investment.pricing.service import quote_security

    token = await _register(client, "sincobertura@example.com")
    adapter = _Adapter({})  # todo devuelve QuoteError
    _use(adapter)
    await client.post(
        "/investment/securities/resolve",
        json={"ticker": "XXX", "exchange": "NYSE"},
        headers=_auth(token),
    )

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        security = (await db.execute(select(Security).where(Security.ticker == "XXX"))).scalar_one()
        outcome = await quote_security(db, adapter, security)
        found = outcome.quote is not None
        status = outcome.provider_status

    assert found is False
    assert status == "unreachable", "se le ha pedido y ha fallado"


async def test_el_fx_declarado_por_el_usuario_manda(client: AsyncClient, test_engine) -> None:
    """Su bróker le da el cambio real de la operación, que es mejor dato que la
    referencia del BCE. Si lo declara, no se toca."""
    await _seed_rate(test_engine, "USD", "1.25", datetime.now(UTC).date())

    token = await _register(client, "fx9@example.com")
    _use(_Adapter({"MCD": _quote("150", "USD")}))
    resolved = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )
    created = await client.post(
        "/investment/portfolio/lots",
        json={
            "security_id": resolved.json()["id"],
            "trade_date": "2026-07-24",
            "quantity": "10",
            "price": "100",
            "fx_rate_at_trade": "0.95",
        },
        headers=_auth(token),
    )

    assert Decimal(created.json()["fx_rate_at_trade"]) == Decimal("0.95")


async def test_exposicion_por_divisa(client: AsyncClient, test_engine) -> None:
    today = datetime.now(UTC).date()
    await _seed_rate(test_engine, "USD", "1.25", today)

    token = await _register(client, "fx6@example.com")
    _use(_Adapter({"MCD": _quote("150", "USD"), "SAP": _quote("100", "EUR")}))
    await _add_position(client, token, "MCD", qty="10", price="100")  # 1200 EUR
    await _add_position(client, token, "SAP", qty="10", price="80")  # 1000 EUR

    data = (await client.get("/investment/portfolio/summary", headers=_auth(token))).json()
    exposure = {row["currency"]: row for row in data["currency_exposure"]}

    assert Decimal(exposure["USD"]["market_value_base"]) == Decimal(1200)
    assert Decimal(exposure["EUR"]["market_value_base"]) == Decimal(1000)
    total = sum(Decimal(row["weight_pct"]) for row in data["currency_exposure"])
    assert total == Decimal(1)
    # Los pesos de posición también se calculan en base, no en nativa.
    assert sum(Decimal(p["weight_pct"]) for p in data["positions"]) == Decimal(1)


async def test_una_posicion_excluida_no_infla_la_exposicion(
    client: AsyncClient, test_engine
) -> None:
    today = datetime.now(UTC).date()
    await _seed_rate(test_engine, "USD", "1.25", today)

    token = await _register(client, "fx7@example.com")
    _use(
        _Adapter(
            {
                "MCD": _quote("150", "USD"),
                "XXX": QuoteError(reason="el proveedor sólo cubre mercados de EE. UU."),
            }
        )
    )
    await _add_position(client, token, "MCD", qty="10", price="100")
    await _add_position(client, token, "XXX", qty="5", price="50")

    data = (await client.get("/investment/portfolio/summary", headers=_auth(token))).json()

    assert Decimal(data["total_market_value_base"]) == Decimal(1200)
    assert len(data["currency_exposure"]) == 1
    excluded = next(p for p in data["positions"] if p["ticker"] == "XXX")
    assert excluded["exclusion_reason"] == "el proveedor sólo cubre mercados de EE. UU."


# --------------------------------------------------------------------------
# D — política de refresco
# --------------------------------------------------------------------------


async def test_quote_fresca_no_vuelve_a_pedirse(client: AsyncClient, test_engine) -> None:
    """TTL: dentro de ventana no se molesta al proveedor."""
    today = datetime.now(UTC).date()
    await _seed_rate(test_engine, "USD", "1.25", today)

    token = await _register(client, "ttl1@example.com")
    adapter = _Adapter({"MCD": _quote("150", "USD")})
    _use(adapter)
    await _add_position(client, token, "MCD", qty="10", price="100")

    await client.get("/investment/portfolio/summary", headers=_auth(token))
    calls_after_first = adapter.calls
    await client.get("/investment/portfolio/summary", headers=_auth(token))

    # La segunda vista no vuelve a llamar: el lote sale vacío y ni se invoca.
    assert adapter.calls == calls_after_first


async def test_refresh_manual_ignora_el_ttl(client: AsyncClient, test_engine) -> None:
    today = datetime.now(UTC).date()
    await _seed_rate(test_engine, "USD", "1.25", today)

    token = await _register(client, "ttl2@example.com")
    adapter = _Adapter({"MCD": _quote("150", "USD")})
    _use(adapter)
    await _add_position(client, token, "MCD", qty="10", price="100")

    await client.get("/investment/portfolio/summary", headers=_auth(token))
    before = adapter.calls

    first = await client.post("/investment/pricing/refresh", json={}, headers=_auth(token))
    second = await client.post("/investment/pricing/refresh", json={}, headers=_auth(token))

    assert first.json()["refreshed"] == 1
    assert second.json()["refreshed"] == 1  # idempotente: mismo resultado
    assert adapter.calls == before + 2  # y sí vuelve a pedir, pese al TTL


async def test_fallo_del_proveedor_conserva_la_ultima_y_la_marca_stale(
    client: AsyncClient, test_engine
) -> None:
    """Nunca se bloquea la cartera: se sirve lo último con su antigüedad."""
    today = datetime.now(UTC).date()
    await _seed_rate(test_engine, "USD", "1.25", today)

    token = await _register(client, "ttl3@example.com")
    good = _Adapter({"MCD": _quote("150", "USD")})
    _use(good)
    sid = await _add_position(client, token, "MCD", qty="10", price="100")
    await client.get("/investment/portfolio/summary", headers=_auth(token))

    # La cotización envejece más allá del TTL y ahora el proveedor falla.
    from sqlalchemy import update

    from app.modules.investment.pricing.models import PriceQuote

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(
            update(PriceQuote)
            .where(PriceQuote.security_id == uuid.UUID(sid))
            .values(fetched_at=datetime.now(UTC) - timedelta(days=30))
        )
        await db.commit()

    _use(_Adapter({}))  # todo devuelve QuoteError
    data = (await client.get("/investment/portfolio/summary", headers=_auth(token))).json()
    pos = data["positions"][0]

    assert pos["has_quote"] is True  # se conserva
    assert pos["quote_stale"] is True  # y se dice que es vieja
    assert Decimal(pos["market_value_base"]) == Decimal(1200)
