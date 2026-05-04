"""Router del módulo currency."""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.currency import repository, service
from app.modules.currency.exceptions import (
    FrankfurterInvalidResponseError,
    FrankfurterUnavailableError,
)
from app.modules.currency.schemas import (
    ConvertResponse,
    ExchangeRateRow,
    RatesResponse,
)

router = APIRouter(prefix="/currency", tags=["currency"])

# Para fechas más antiguas que esto no triggereamos lazy fetch — un
# request con `?date=1995-01-01` no debe golpear la API externa. La
# ventana cubre con margen los rangos del dashboard (1 año + holgura).
_LAZY_FETCH_HORIZON_DAYS = 400


def _today_utc() -> date_type:
    return datetime.utcnow().date()


async def _maybe_lazy_fetch(
    db: AsyncSession, *, target_date: date_type, base: str
) -> None:
    """Pide tasas a frankfurter para `target_date` si está dentro del horizonte.

    Hook detrás del endpoint `/currency/rates` para que la primera
    petición de una fecha aún no vista se traiga del ECB en lugar de
    devolver lista vacía. Best-effort: si el cliente falla, swallow —
    el endpoint sigue funcionando con lo que haya en BD.
    """
    today = _today_utc()
    delta_past = (today - target_date).days
    delta_future = (target_date - today).days
    if delta_past > _LAZY_FETCH_HORIZON_DAYS:
        return
    if delta_future > 0:
        # frankfurter trata las fechas futuras como "latest" — no
        # persistimos para no contaminar la BD con tasas atribuidas a
        # una fecha que aún no existe.
        return

    try:
        await service.refresh_rates(
            db,
            target_date=target_date,
            quotes=service.COMMON_QUOTES,
            base=base,
        )
        await db.commit()
    except (FrankfurterUnavailableError, FrankfurterInvalidResponseError):
        # Sin red u API caída — el caller ya gestiona la ausencia
        # devolviendo `missing` en `service.convert`.
        return


@router.get("/rates", response_model=RatesResponse)
async def list_rates(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    rate_date: Annotated[date_type | None, Query(alias="date")] = None,
    base: str = Query(default="EUR", min_length=3, max_length=3),
) -> RatesResponse:
    """Devuelve todas las tasas para una fecha y base.

    Las tasas son datos públicos globales (ECB) — no aplica filtro por
    `user_id`. La autenticación se exige sólo para evitar que el
    endpoint sea totalmente abierto sin autenticar.

    Si la fecha pedida no tiene tasas en BD pero está dentro del
    horizonte razonable, se hace un fetch lazy a frankfurter.app y se
    re-consulta antes de responder. Esto evita que el frontend
    aterrice en `missing` la primera vez que ve una fecha (típico:
    día actual antes del primer cron de refresco).
    """
    target_date = rate_date or _today_utc()
    base_norm = base.upper()
    rows = await repository.list_rates_for_date(
        db, rate_date=target_date, base=base_norm
    )
    if not rows:
        await _maybe_lazy_fetch(db, target_date=target_date, base=base_norm)
        rows = await repository.list_rates_for_date(
            db, rate_date=target_date, base=base_norm
        )
    return RatesResponse(
        rate_date=target_date,
        base=base_norm,
        rates=[ExchangeRateRow(quote=r.quote, rate=r.rate) for r in rows],
    )


@router.get("/convert", response_model=ConvertResponse)
async def convert_amount(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    amount: str = Query(min_length=1, description="Importe en formato decimal"),
    from_currency: str = Query(min_length=3, max_length=3, alias="from"),
    to_currency: str = Query(min_length=3, max_length=3, alias="to"),
    at_date: Annotated[date_type | None, Query(alias="date")] = None,
) -> ConvertResponse:
    """Convierte un importe puntual.

    Útil para integraciones / debug. La UI principal del frontend
    espera consumir `/currency/rates` y hacer la conversión client-side
    (cache eficiente cuando se cambia la moneda activa), pero este
    endpoint cubre flujos batch y verificación manual.
    """
    try:
        amount_decimal = Decimal(amount)
    except InvalidOperation as e:
        raise HTTPException(
            status_code=422, detail="amount debe ser un decimal válido"
        ) from e

    target_date = at_date or _today_utc()
    # Si la fecha aún no se ha visto, intentar precargarla. Mismo hook
    # que /rates: idempotente y best-effort.
    existing = await repository.get_rate_with_fallback(
        db, rate_date=target_date, base="EUR", quote="USD"
    )
    if existing is None:
        await _maybe_lazy_fetch(db, target_date=target_date, base="EUR")
    result = await service.convert(
        db,
        amount=amount_decimal,
        from_currency=from_currency,
        to_currency=to_currency,
        at_date=target_date,
    )
    return ConvertResponse.model_validate(result.model_dump())
