"""Servicio de precios + `/portfolio/summary` (PHASE-44.7, FX en 44.11.D/E).

El summary parte de las posiciones de la cartera (coste, realizado, dividendos) y
les añade el valor de mercado desde `price_quotes` (refrescadas on-access). Una
posición sin cotización sale con `market_value=null`, su MOTIVO y FUERA de los
totales — nunca valorada a coste como sustituto silencioso (principio
anti-dato-ficticio de PHASE-31.4).

Descomposición del P&L (decisión del usuario, opción A):
    price_effect = qty·(precio_actual − coste_medio)·fx_actual
    fx_effect    = qty·coste_medio·(fx_actual − fx_de_compra)
Desde PHASE-44.11 el `fx_actual` es real: sale del módulo transversal `currency`
(ADR-0009), así que `fx_effect` deja de ser 0 y la suma de ambos cuadra con el
P&L latente **en base**.

Tres reglas de FX, todas del ADR-0009:

1. Los tipos salen de `currency.service`. Este módulo **no** consulta
   `exchange_rates` ni conoce a Frankfurter.
2. `ensure_rates_for_dates` se llama ANTES de tocar nada persistible, porque
   hace `commit()` por dentro: en mitad del refresco confirmaría escrituras a
   medias.
3. `convert()` con `fallback="missing"` devuelve el importe **sin convertir** y
   `rate=1`. Sumar eso a los totales serían dólares contados como euros, así que
   una posición sin tasa cae a la exclusión estándar igual que una sin precio.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.currency import service as currency_service
from app.modules.currency.exceptions import (
    FrankfurterInvalidResponseError,
    FrankfurterUnavailableError,
)
from app.modules.investment.catalog.models import Security
from app.modules.investment.portfolio.service import PositionCore, compute_position_cores
from app.modules.investment.pricing import repository as repo
from app.modules.investment.pricing.adapters.base import PriceAdapter
from app.modules.investment.pricing.models import PriceQuote
from app.modules.investment.pricing.refresh import RefreshTarget, refresh_quotes

logger = logging.getLogger(__name__)

ProviderStatus = Literal["live", "cached", "unreachable"]
"""Cómo se ha obtenido una cotización. Ver `QuoteOutcome`."""

_ZERO = Decimal(0)
_ONE = Decimal(1)

#: Divisa en la que se agregan los totales de la cartera. EUR es la base
#: canónica de `currency` (todas las tasas del BCE se publican contra ella), así
#: que agregar en otra cosa añadiría una composición sin ganar nada hoy.
BASE_CURRENCY = "EUR"


@dataclass(frozen=True)
class PositionSummary:
    security_id: uuid.UUID
    ticker: str
    name: str
    currency: str
    quantity: Decimal
    avg_cost: Decimal | None
    cost_basis: Decimal
    realized_pnl: Decimal
    dividends_gross: Decimal
    dividends_net: Decimal
    has_quote: bool
    exclusion_reason: str | None
    """Por qué esta posición no entra en los totales. `None` si sí entra.

    Siempre acompaña a `has_quote=False`: "sin cotización" a secas obliga al
    usuario a adivinar si el problema es el proveedor, la plaza o su cartera."""
    last_price: Decimal | None
    prev_close: Decimal | None
    quote_as_of: datetime | None
    quote_stale: bool
    quote_currency: str | None
    currency_mismatch: bool
    """La divisa del proveedor no coincide con la del catálogo (PHASE-44.11 D4).

    Se valora con la del proveedor —es quien ha emitido el precio— pero la
    discrepancia se muestra: significa que el catálogo afirma una plaza/divisa
    que el mercado contradice, y silenciarlo es cómo un precio en peniques pasa
    por libras."""
    market_value: Decimal | None
    market_value_base: Decimal | None
    """Valor de mercado convertido a `BASE_CURRENCY`. `None` si falta la tasa."""
    cost_basis_base: Decimal
    """Coste en base, al tipo de la FECHA DE COMPRA (no al de hoy).

    Es lo que hace que `unrealized_pnl_base` separe de verdad lo que movió el
    precio de lo que movió la divisa: comparar el valor de hoy contra el coste
    reexpresado a tipo de hoy escondería el efecto divisa entero."""
    unrealized_pnl_base: Decimal | None
    fx_rate: Decimal | None
    fx_as_of: date | None
    """Fecha EFECTIVA de la tasa aplicada (`ConversionResult.rate_date`), que no
    tiene por qué ser hoy: un lunes se usa la del viernes. Un valor de mercado
    con precio de hoy y tasa de hace tres días debe poder decirlo."""
    unrealized_pnl: Decimal | None
    unrealized_pnl_pct: Decimal | None
    price_effect: Decimal | None
    fx_effect: Decimal | None
    daily_change: Decimal | None
    total_return: Decimal | None
    yield_on_cost: Decimal | None
    weight_pct: Decimal | None


@dataclass(frozen=True)
class CurrencyExposure:
    """Cuánto de la cartera está expuesto a cada divisa, en base."""

    currency: str
    market_value_base: Decimal
    weight_pct: Decimal


@dataclass(frozen=True)
class PortfolioSummary:
    pricing_enabled: bool
    base_currency: str
    base_note: str
    total_cost_basis: Decimal
    """Suma en divisa NATIVA de cada posición. Sólo tiene sentido si la cartera
    es monodivisa; para agregar usa `total_cost_basis_base`."""
    total_cost_basis_base: Decimal
    total_market_value: Decimal
    total_market_value_base: Decimal
    total_unrealized_pnl: Decimal
    total_unrealized_pnl_base: Decimal
    total_realized_pnl: Decimal
    total_dividends_net: Decimal
    daily_pnl: Decimal
    quoted_count: int
    unquoted_count: int
    currency_exposure: list[CurrencyExposure]
    positions: list[PositionSummary]


def _targets(cores: list[PositionCore]) -> list[RefreshTarget]:
    return [
        RefreshTarget(
            security_id=c.security_id,
            ticker=c.ticker,
            exchange=c.exchange,
            currency=c.currency,
        )
        for c in cores
        if c.quantity > 0 and c.ticker
    ]


async def refresh_portfolio(
    db: AsyncSession,
    adapter: PriceAdapter,
    user_id: uuid.UUID,
    *,
    security_ids: Collection[uuid.UUID] | None = None,
) -> int:
    """Fuerza el refresh (botón manual). Devuelve cuántas cotizaciones se
    trajeron.

    Mismo camino de código que el refresco on-access: sólo cambia `force`. Dos
    rutas distintas divergirían y el botón acabaría trayendo algo distinto a lo
    que la vista muestra.
    """
    now = datetime.now(UTC)
    cores = await compute_position_cores(db, user_id)
    targets = [t for t in _targets(cores) if security_ids is None or t.security_id in security_ids]
    await _ensure_fx_rates(db, cores, on=now.date())
    outcome = await refresh_quotes(
        db, adapter, targets, ttl_hours=settings.price_ttl_hours, now=now, force=True
    )
    return outcome.refreshed


@dataclass(frozen=True)
class QuoteOutcome:
    """La cotización y **cómo se ha conseguido**.

    `provider_status` distingue tres situaciones que un solo `quote_stale` no
    separa, y la diferencia importa para no afirmar lo que no se ha comprobado:

    - `live` — se le ha pedido al proveedor y ha respondido. Es lo único que
      permite decir "el servicio está en pie" ahora mismo.
    - `cached` — no se le ha pedido nada porque la cotización guardada seguía
      dentro del TTL. El precio es bueno, pero del estado del proveedor no
      sabemos nada: pintarlo en verde sería inventar una comprobación.
    - `unreachable` — se le ha pedido y ha fallado. Se sirve la última guardada,
      que es lo que hace que la pantalla no se quede en blanco.
    """

    quote: PriceQuote | None
    provider_status: ProviderStatus


async def quote_security(
    db: AsyncSession,
    adapter: PriceAdapter,
    security: Security,
    *,
    force: bool = False,
) -> QuoteOutcome:
    """Cotización de UN valor, **tenga o no posición en cartera**.

    El refresco de la cartera (`_targets`) filtra por `quantity > 0`, que es
    correcto para valorar lo que tienes pero deja fuera el caso normal de la
    pestaña de Análisis: se analiza un valor ANTES de comprarlo. Sin este
    camino, los múltiplos sólo existirían para lo que ya está en cartera —
    justo cuando ya no sirven para decidir la compra.

    Devuelve `QuoteOutcome`: la cotización (o `None` si nunca hubo ninguna) y
    cómo se ha conseguido. Que el proveedor no cubra un símbolo no es un error
    del sistema — es un múltiplo que no se puede calcular y que debe decirlo.

    ⚠️ **Esta función COMMITEA** la sesión, por transitividad: el aseguramiento
    de tipos llama a `currency.service.refresh_rates`, que escribe y confirma
    (deuda declarada en ADR-0009). No la invoques en mitad de una unidad de
    trabajo propia sin haberla cerrado, o se confirmará a medias.

    Por eso los datos del `security` se copian a escalares ANTES: ese commit
    expira los objetos de la sesión, y leer `security.ticker` después dispararía
    una recarga perezosa desde código síncrono (`MissingGreenlet`). No es
    hipotético — fue el primer fallo al escribir esta función.
    """
    security_id = security.id
    target = RefreshTarget(
        security_id=security_id,
        ticker=security.ticker,
        exchange=security.exchange,
        currency=security.currency,
    )
    now = datetime.now(UTC)
    await _ensure_fx_rates_for_currencies(db, {target.currency}, on=now.date())
    outcome = await refresh_quotes(
        db, adapter, [target], ttl_hours=settings.price_ttl_hours, now=now, force=force
    )

    # El estado sale de lo que YA sabe el refresco, sin preguntar dos veces:
    # si trajo algo, el proveedor respondió; si registró un error para este
    # valor, se le pidió y falló; si no hizo ni lo uno ni lo otro, es que la
    # cotización seguía fresca y no se le ha preguntado nada.
    if outcome.refreshed > 0:
        status: ProviderStatus = "live"
    elif security_id in outcome.errors:
        status = "unreachable"
    else:
        status = "cached"

    return QuoteOutcome(quote=await repo.get_quote(db, security_id), provider_status=status)


async def _ensure_fx_rates(db: AsyncSession, cores: list[PositionCore], *, on: date) -> None:
    """Garantiza la tasa **del día** para las divisas presentes en la cartera.

    Se llama ANTES del refresco de precios a propósito: `refresh_rates` escribe
    y `ensure_rates_for_dates` hace `commit()` por dentro (ADR-0009), así que
    invocarlo en mitad del upsert de cotizaciones confirmaría trabajo a medias.

    **Por qué no basta `ensure_rates_for_dates`** (decisión del usuario,
    2026-08-02): su canario da por buena cualquier tasa dentro de la ventana de
    fallback de 14 días y hace `continue` sin pedir nada. Esa política es
    correcta para lo que `currency` hacía hasta ahora —convertir transacciones
    PASADAS, donde el último día hábil publicado *es* el dato bueno— y no lo es
    para valorar a día de hoy: verificado contra la BD real, con la última tasa
    a 15 días la conversión de "ayer" resolvía con la del 18 de julio, así que
    la cartera habría mostrado precio de hoy × tipo de hace dos semanas sin
    intentar actualizarlo.

    Aquí se exige tasa EXACTA de `on` y, si falta, se pide. No se cambia la
    política de `currency` —eso movería números de Deuda, Análisis y Dashboard,
    que comparten esa ventana— sino que se usa su API pública desde el módulo
    que necesita otra frescura.

    Es best-effort: si Frankfurter no responde, se sigue con lo que haya. La
    posición dirá con qué fecha se valoró (`fx_as_of`) o quedará excluida si no
    hay ninguna tasa utilizable.

    `quotes=` va explícito y no se deja al default `COMMON_QUOTES`: una divisa
    fuera de esa tupla caería al `fallback="missing"` sin que nadie hubiera
    intentado traer su tasa.
    """
    needed = {c.currency for c in cores if c.quantity > 0 and c.currency}
    await _ensure_fx_rates_for_currencies(db, needed, on=on)


async def _ensure_fx_rates_for_currencies(
    db: AsyncSession, currencies: Collection[str], *, on: date
) -> None:
    """Núcleo de lo anterior, reutilizable por quien no parta de posiciones."""
    needed = {c.strip().upper() for c in currencies if c and c.strip()}
    needed.discard(BASE_CURRENCY)
    if not needed:
        return

    missing = await currency_service.missing_exact_rates(db, on=on, quotes=sorted(needed))
    if not missing:
        return

    try:
        await currency_service.refresh_rates(db, target_date=on, quotes=missing)
        await db.commit()
    except (FrankfurterInvalidResponseError, FrankfurterUnavailableError):
        # El BCE no publica fines de semana ni festivos, así que "no hay tasa de
        # hoy" es lo NORMAL un domingo. Se cae al fallback de `convert`, que
        # devuelve la última con su `rate_date` — y la pantalla lo declara.
        logger.info("pricing: sin tasas nuevas para %s (%s)", on, ", ".join(missing))
        await db.rollback()


async def compute_portfolio_summary(
    db: AsyncSession, adapter: PriceAdapter, user_id: uuid.UUID
) -> PortfolioSummary:
    now = datetime.now(UTC)
    cores = await compute_position_cores(db, user_id)
    await _ensure_fx_rates(db, cores, on=now.date())
    outcome = await refresh_quotes(
        db, adapter, _targets(cores), ttl_hours=settings.price_ttl_hours, now=now
    )
    quotes = await repo.list_quotes(db, [c.security_id for c in cores])
    ttl = timedelta(hours=settings.price_ttl_hours)

    partials: list[PositionSummary] = []
    total_market_value = _ZERO
    total_market_value_base = _ZERO
    total_unrealized = _ZERO
    total_unrealized_base = _ZERO
    total_realized = _ZERO
    total_dividends_net = _ZERO
    total_cost_basis = _ZERO
    total_cost_basis_base = _ZERO
    daily_pnl = _ZERO
    quoted = 0
    unquoted = 0
    exposure: dict[str, Decimal] = {}

    for core in cores:
        total_cost_basis += core.cost_basis
        total_realized += core.realized_pnl
        total_dividends_net += core.dividends_net

        quote = quotes.get(core.security_id)
        has_quote = quote is not None and core.quantity > 0
        conversion = await _convert_to_base(db, quote, core, on=now.date()) if has_quote else _NO_FX
        summary = _position_summary(
            core,
            quote,
            has_quote=has_quote,
            now=now,
            ttl=ttl,
            fx=conversion,
            reason=outcome.errors.get(core.security_id),
        )
        partials.append(summary)

        if has_quote and summary.market_value_base is not None:
            quoted += 1
            total_market_value += summary.market_value or _ZERO
            total_market_value_base += summary.market_value_base
            total_cost_basis_base += summary.cost_basis_base
            total_unrealized += summary.unrealized_pnl or _ZERO
            total_unrealized_base += summary.unrealized_pnl_base or _ZERO
            daily_pnl += summary.daily_change or _ZERO
            key = (summary.quote_currency or core.currency).upper()
            exposure[key] = exposure.get(key, _ZERO) + summary.market_value_base
        elif core.quantity > 0:
            unquoted += 1

    # Segundo pase: peso de cada posición sobre el valor de mercado total. Se
    # calcula en BASE, no en nativa: sumar dólares con euros para sacar un
    # porcentaje daría pesos que no suman 100 en una cartera multidivisa.
    positions = [_with_weight(summary, total_market_value_base) for summary in partials]
    currency_exposure = _exposure_rows(exposure, total_market_value_base)

    return PortfolioSummary(
        pricing_enabled=pricing_enabled(),
        base_currency=BASE_CURRENCY,
        base_note=(
            f"Los totales agregados van en {BASE_CURRENCY}, convertidos con los tipos "
            "del BCE de la fecha que indica cada posición. Los importes por posición "
            "se muestran también en su divisa nativa."
        ),
        total_cost_basis=total_cost_basis,
        total_cost_basis_base=total_cost_basis_base,
        total_market_value=total_market_value,
        total_market_value_base=total_market_value_base,
        total_unrealized_pnl=total_unrealized,
        total_unrealized_pnl_base=total_unrealized_base,
        total_realized_pnl=total_realized,
        total_dividends_net=total_dividends_net,
        daily_pnl=daily_pnl,
        quoted_count=quoted,
        unquoted_count=unquoted,
        currency_exposure=currency_exposure,
        positions=positions,
    )


def _exposure_rows(exposure: dict[str, Decimal], total_base: Decimal) -> list[CurrencyExposure]:
    """Exposición por divisa, de mayor a menor. Sólo cuenta lo VALORADO: una
    posición excluida no infla ninguna divisa."""
    if total_base <= 0:
        return []
    rows = [
        CurrencyExposure(
            currency=currency,
            market_value_base=value,
            weight_pct=value / total_base,
        )
        for currency, value in exposure.items()
    ]
    rows.sort(key=lambda r: (-r.market_value_base, r.currency))
    return rows


def pricing_enabled() -> bool:
    """Si el proveedor activo puede cotizar algo.

    yfinance no pide credencial, así que con él el pricing está SIEMPRE
    disponible — que es la razón del cambio de default en PHASE-44.11. Finnhub
    sigue dependiendo de su key: sin ella el módulo funciona igual, pero todas
    las posiciones salen "sin cotización" y la UI lo dice en vez de aparentar un
    fallo de datos."""
    provider = settings.price_provider.strip().lower()
    if provider == "finnhub":
        return bool(settings.finnhub_api_key.strip())
    return True


@dataclass(frozen=True)
class _Fx:
    """Tasa nativa→base aplicada a una posición, con su fecha efectiva."""

    rate: Decimal | None
    as_of: date | None


_NO_FX = _Fx(rate=None, as_of=None)


async def _convert_to_base(db: AsyncSession, quote: object, core: PositionCore, *, on: date) -> _Fx:
    """Tasa de la divisa de la posición a `BASE_CURRENCY`.

    Se pide sobre 1 unidad y se guarda la TASA, no un importe convertido: así la
    misma tasa vale para el valor de mercado, el coste y los efectos precio/FX
    sin pedirla cuatro veces.

    `fallback="missing"` devuelve `rate=1` y el importe SIN convertir
    (ADR-0009). Tomarlo por bueno sumaría dólares como euros, así que se traduce
    a "no hay tasa" y la posición queda fuera de los totales.
    """
    currency = ((getattr(quote, "currency", None) or core.currency) or "").strip().upper()
    if not currency:
        return _NO_FX
    if currency == BASE_CURRENCY:
        return _Fx(rate=_ONE, as_of=on)

    result = await currency_service.convert(
        db, amount=_ONE, from_currency=currency, to_currency=BASE_CURRENCY, at_date=on
    )
    if result.fallback == "missing":
        return _NO_FX
    return _Fx(rate=result.rate, as_of=result.rate_date)


def _position_summary(
    core: PositionCore,
    quote: object,
    *,
    has_quote: bool,
    now: datetime,
    ttl: timedelta,
    fx: _Fx,
    reason: str | None,
) -> PositionSummary:
    last_price: Decimal | None = None
    prev_close: Decimal | None = None
    quote_as_of: datetime | None = None
    quote_stale = False
    quote_currency: str | None = None
    currency_mismatch = False
    market_value: Decimal | None = None
    market_value_base: Decimal | None = None
    cost_basis_base = _ZERO
    unrealized_base: Decimal | None = None
    unrealized: Decimal | None = None
    unrealized_pct: Decimal | None = None
    price_effect: Decimal | None = None
    fx_effect: Decimal | None = None
    daily_change: Decimal | None = None
    total_return: Decimal | None = None
    exclusion_reason: str | None = None

    if has_quote and quote is not None:
        last_price = quote.price  # type: ignore[attr-defined]
        prev_close = quote.prev_close  # type: ignore[attr-defined]
        quote_as_of = quote.as_of  # type: ignore[attr-defined]
        quote_stale = (now - quote.fetched_at) >= ttl  # type: ignore[attr-defined]
        quote_currency = quote.currency  # type: ignore[attr-defined]
        currency_mismatch = bool(quote_currency) and quote_currency != core.currency
        market_value = core.quantity * last_price
        unrealized = market_value - core.cost_basis
        unrealized_pct = unrealized / core.cost_basis if core.cost_basis > 0 else None
        if prev_close is not None:
            daily_change = core.quantity * (last_price - prev_close)
        total_return = unrealized + core.realized_pnl + core.dividends_net

        if fx.rate is not None:
            market_value_base = market_value * fx.rate
            # El coste va al tipo de la FECHA DE COMPRA (`cost_fx`, derivado del
            # BCE al dar de alta el lote), no al de hoy: reexpresarlo a tipo de
            # hoy escondería justamente el efecto divisa que se quiere aislar.
            avg_cost = core.avg_cost or _ZERO
            cost_fx = core.cost_fx or fx.rate
            cost_basis_base = core.cost_basis * cost_fx
            unrealized_base = market_value_base - cost_basis_base
            # Descomposición del P&L latente EN BASE. Los dos términos suman
            # exactamente `market_value_base − cost_basis·cost_fx`.
            price_effect = core.quantity * (last_price - avg_cost) * fx.rate
            fx_effect = core.quantity * avg_cost * (fx.rate - cost_fx)
        else:
            # Hay precio pero no tasa: no se puede agregar. Se enseña el valor
            # nativo y se dice por qué no entra en el total.
            exclusion_reason = (
                f"sin tipo de cambio {core.currency}→{BASE_CURRENCY} para valorar en la "
                "divisa de la cartera"
            )
    elif core.quantity > 0:
        exclusion_reason = reason or "el proveedor de precios no ha devuelto cotización"

    yield_on_cost = core.dividends_gross / core.cost_basis if core.cost_basis > 0 else None

    return PositionSummary(
        security_id=core.security_id,
        ticker=core.ticker,
        name=core.name,
        currency=core.currency,
        quantity=core.quantity,
        avg_cost=core.avg_cost,
        cost_basis=core.cost_basis,
        realized_pnl=core.realized_pnl,
        dividends_gross=core.dividends_gross,
        dividends_net=core.dividends_net,
        has_quote=has_quote,
        exclusion_reason=exclusion_reason,
        last_price=last_price,
        prev_close=prev_close,
        quote_as_of=quote_as_of,
        quote_stale=quote_stale,
        quote_currency=quote_currency,
        currency_mismatch=currency_mismatch,
        market_value=market_value,
        market_value_base=market_value_base,
        cost_basis_base=cost_basis_base,
        unrealized_pnl_base=unrealized_base,
        fx_rate=fx.rate,
        fx_as_of=fx.as_of,
        unrealized_pnl=unrealized,
        unrealized_pnl_pct=unrealized_pct,
        price_effect=price_effect,
        fx_effect=fx_effect,
        daily_change=daily_change,
        total_return=total_return,
        yield_on_cost=yield_on_cost,
        weight_pct=None,
    )


def _with_weight(summary: PositionSummary, total_base: Decimal) -> PositionSummary:
    if summary.market_value_base is None or total_base <= 0:
        return summary
    weight = summary.market_value_base / total_base
    return PositionSummary(**{**summary.__dict__, "weight_pct": weight})
