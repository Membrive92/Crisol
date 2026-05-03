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
from app.modules.currency.schemas import (
    ConvertResponse,
    ExchangeRateRow,
    RatesResponse,
)

router = APIRouter(prefix="/currency", tags=["currency"])


def _today_utc() -> date_type:
    return datetime.utcnow().date()


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
    """
    target_date = rate_date or _today_utc()
    rows = await repository.list_rates_for_date(
        db, rate_date=target_date, base=base.upper()
    )
    return RatesResponse(
        rate_date=target_date,
        base=base.upper(),
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
    result = await service.convert(
        db,
        amount=amount_decimal,
        from_currency=from_currency,
        to_currency=to_currency,
        at_date=target_date,
    )
    return ConvertResponse.model_validate(result.model_dump())
