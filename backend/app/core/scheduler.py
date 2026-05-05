"""Scheduler de jobs background del backend (PHASE-11.1).

Infraestructura cross-cutting — vive en `core/` porque cualquier módulo
de dominio puede registrar jobs aquí. Por ahora sólo hay uno: refresh
nocturno de exchange rates.

Decisión: APScheduler en lugar de Celery beat / cron del SO. Ver
`internal_docs/decisions/0002-apscheduler.md`.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

# APScheduler no publica stubs (PEP 561) — añadirlos como dep dev sería
# pesado para 2 imports. Silenciamos el warning de mypy aquí; el resto
# del módulo sí tiene tipos propios.
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.modules.currency import service as currency_service

logger = logging.getLogger("app.scheduler")

# ID estable del job — usado para inspección desde tests y para evitar
# duplicados si el scheduler se re-arranca por hot reload.
CURRENCY_REFRESH_JOB_ID = "refresh_currency_rates"


def _today_utc() -> date:
    """`date.today()` de Python usa la TZ local del proceso. El cron corre en
    UTC y queremos coherencia: la fecha de "hoy" para el job es la UTC."""
    return datetime.now(UTC).date()


async def refresh_currency_rates_job() -> None:
    """Llama a `ensure_rates_for_dates([yesterday, today])`.

    Garantiza que las fechas más recientes tienen tasas en BD para que
    el dashboard cross-currency no dependa del lazy-fetch on-request
    cuando el usuario abre la app por primera vez del día.

    Crea su propia `AsyncSession` — el job corre fuera del request
    context de FastAPI, así que no puede usar `get_db()`.
    """
    engine = create_async_engine(settings.database_url, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    today = _today_utc()
    yesterday = today - timedelta(days=1)
    try:
        async with session_factory() as db:
            fetched = await currency_service.ensure_rates_for_dates(
                db, [yesterday, today]
            )
        logger.info(
            "currency cron: %s fechas refrescadas (yesterday=%s, today=%s)",
            fetched,
            yesterday,
            today,
        )
    except Exception:
        # Best-effort — si falla un día, el siguiente lo reintenta. Un
        # error no debe tirar el scheduler ni el proceso.
        logger.exception("currency cron failed")
    finally:
        await engine.dispose()


def create_scheduler() -> AsyncIOScheduler | None:
    """Crea (sin arrancar) el scheduler con los jobs configurados.

    Devuelve `None` cuando `settings.enable_currency_cron=False` —
    útil para tests y para entornos donde el cron lo gestiona algo
    externo (cron del SO, cluster scheduler).

    El job se registra con `replace_existing=True` para que un
    arranque tras hot reload no acumule duplicados.
    """
    if not settings.enable_currency_cron:
        return None

    scheduler = AsyncIOScheduler(timezone=UTC)
    scheduler.add_job(
        refresh_currency_rates_job,
        trigger=CronTrigger(
            hour=settings.currency_cron_hour,
            minute=settings.currency_cron_minute,
            timezone=UTC,
        ),
        id=CURRENCY_REFRESH_JOB_ID,
        replace_existing=True,
        # Si el server estaba apagado a la hora del cron y arranca
        # 30min después, queremos que el job se ejecute igualmente
        # (los días con feed ya publicado se saltan vía
        # `ensure_rates_for_dates` — coste real cero).
        misfire_grace_time=60 * 60,
    )
    return scheduler
