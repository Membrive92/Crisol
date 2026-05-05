# PHASE-11.1 — Cron nocturno de exchange rates (APScheduler)

**Estado**: ✅ completada
**Rama**: `feat/phase-11.1-currency-cron`
**PR**: —
**Fecha de merge**: 2026-05-05

## Objetivo

Hasta ahora las tasas de cambio se refrescaban sólo on-demand: la
primera petición que las necesitara para una fecha sin tasa
disparaba un fetch a frankfurter (lazy fetch). Si la app pasaba
días sin abrirse, las tasas se quedaban atrás. Esta fase añade un
job nocturno que mantiene las fechas más recientes cubiertas
proactivamente, manteniendo el lazy fetch como red de seguridad
para fechas históricas.

## Qué se implementó

### Dependencia nueva — APScheduler 3.11.x

`backend/pyproject.toml`: añadida `apscheduler>=3.10.4`. Decisión
documentada en [ADR-0002](../decisions/0002-apscheduler.md) — la
alternativa Celery/cluster scheduler no compensa para single-host.

### `app/core/scheduler.py` (nuevo)

Módulo cross-cutting (no de dominio) que centraliza la creación y
gestión de jobs background.

- **`refresh_currency_rates_job()`**: corutina que llama a
  `currency_service.ensure_rates_for_dates([yesterday, today])`.
  Crea su propio `AsyncSession` (los jobs corren fuera del request
  context, no pueden usar `get_db()`). `today`/`yesterday` se
  calculan en UTC (`_today_utc`) para coherencia con el timezone
  del cron.
- **`create_scheduler()`**: factory que devuelve un
  `AsyncIOScheduler` con el job registrado vía `CronTrigger(hour=3,
  minute=0, timezone=UTC)`. Devuelve `None` cuando
  `settings.enable_currency_cron=False` — útil para tests y para
  entornos donde el cron lo gestiona algo externo (cron del SO,
  cluster scheduler).
- **`misfire_grace_time=60*60`** (1h): si el server estaba apagado
  a la hora del cron y arranca 30min después, el job se ejecuta
  igual. Los días con feed ya publicado en BD se saltan
  silenciosamente vía `ensure_rates_for_dates` — coste cero.
- **Try/except con log estructurado**: errores del job no propagan
  (`logger.exception` los registra y el día siguiente reintenta).
  Un fallo no debe tirar el scheduler ni el proceso.

### `app/main.py`

Migrado a `lifespan` async context manager (la API moderna; los
deprecados `@app.on_event("startup"/"shutdown")` quedaron fuera).

- En startup: `create_scheduler()` y, si no es `None`,
  `scheduler.start()` y stash en `app.state.scheduler` para
  inspección.
- En shutdown: `scheduler.shutdown(wait=False)` — corte limpio.
- Sólo afecta cuando el flag está on. En tests el conftest no
  propaga lifespan a `ASGITransport`, así que el código lifespan
  no se ejecuta en CI.

### `app/core/config.py`

Tres campos nuevos:

- `enable_currency_cron: bool = True` — flag global. Default on.
- `currency_cron_hour: int = 3` — hora UTC del job.
- `currency_cron_minute: int = 0`.

### Tests `backend/tests/test_currency_cron.py` (5)

- `test_create_scheduler_returns_none_when_disabled` — flag off →
  `None`.
- `test_create_scheduler_registers_currency_job_when_enabled` —
  flag on → scheduler con el job registrado bajo el ID estable
  `CURRENCY_REFRESH_JOB_ID`. No se arranca (responsabilidad del
  lifespan).
- `test_refresh_currency_rates_job_calls_ensure_with_today_and_yesterday`
  — mockea `ensure_rates_for_dates` y `create_async_engine`,
  verifica que se llama con `[yesterday, today]` en orden.
- `test_refresh_currency_rates_job_swallows_exceptions` — un
  `RuntimeError` interno NO debe propagar.
- `test_today_utc_uses_utc_not_local_tz` — `_today_utc()` coincide
  con `datetime.now(UTC).date()`.

## Flujo técnico

```
 Proceso uvicorn arranca
    │
    ▼ FastAPI lifespan startup
 create_scheduler()
    ├── settings.enable_currency_cron == False → return None → skip
    └── settings.enable_currency_cron == True
            │
            ▼
        AsyncIOScheduler(timezone=UTC)
        scheduler.add_job(
            refresh_currency_rates_job,
            trigger=CronTrigger(hour=3, minute=0, timezone=UTC),
            id="refresh_currency_rates",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        scheduler.start()
        app.state.scheduler = scheduler

 ... el proceso atiende requests ...

 03:00 UTC tick
    ▼
 refresh_currency_rates_job()
    ├── engine = create_async_engine(database_url)
    ├── async with sessionmaker() as db:
    │       fetched = await currency_service.ensure_rates_for_dates(
    │           db, [yesterday, today]
    │       )
    │       — internal: por cada fecha, salta si ya hay tasa con
    │         fallback dentro de ventana; si no, fetch a frankfurter
    │         + commit. Errores de red por fecha se tragan.
    ├── logger.info("currency cron: N fechas refrescadas")
    └── engine.dispose()

 SIGTERM al proceso
    ▼ FastAPI lifespan shutdown
 scheduler.shutdown(wait=False)
```

## Archivos clave

- `backend/pyproject.toml` (apscheduler dep)
- `backend/app/core/config.py` (3 campos: enable + hour + minute)
- `backend/app/core/scheduler.py` (nuevo, factory + job)
- `backend/app/main.py` (lifespan + scheduler start/shutdown)
- `backend/tests/test_currency_cron.py` (nuevo, 5 tests)
- `internal_docs/decisions/0002-apscheduler.md` (nuevo ADR)

## Endpoints

Ninguno nuevo. El job es interno y no expone superficie HTTP.

## Migraciones

Ninguna.

## Verificación

- [x] `pytest backend/tests/` — 178/178 (5 nuevos en
      `test_currency_cron.py`).
- [x] `mypy app/` — 12 errores pre-existentes en `ai/client.py` y
      `dashboard/conversion.py`; **0 introducidos por esta fase**.
- [x] `ruff check app/ tests/` verde.
- [ ] Smoke manual: arrancar el backend con `uvicorn app.main:app`
      y verificar que aparece en logs algo como
      `Scheduler started`. El job sólo se ejecuta a las 03:00 UTC,
      así que para validarlo ya, temporalmente bajar
      `currency_cron_minute` al valor actual + 1 y observar.

## Decisiones tomadas

- **APScheduler in-process** en lugar de Celery / cluster
  scheduler / cron del SO. Razones completas en
  [ADR-0002](../decisions/0002-apscheduler.md). Resumen: la app es
  single-host single-worker; añadir broker / coordinador externo
  no compensa para "una función al día".
- **Refresh `[yesterday, today]`** en lugar de sólo `today`.
  Frankfurter publica el feed del ECB con cierto retraso para
  algunas monedas; cubrir el día anterior reduce el riesgo de
  agujeros. `ensure_rates_for_dates` salta fechas ya cubiertas →
  coste cero si el cron de ayer fue bien.
- **UTC para todo el cron y para el cálculo de "today"**. El
  servidor puede correr en cualquier timezone; usar UTC siempre
  evita ambigüedades cuando la hora local cambia (DST). El usuario
  no nota — las tasas son del día calendario UTC, lo que coincide
  con cómo el ECB / frankfurter publican.
- **Job swallows exceptions** dentro de un único try/except. Un
  fallo de red, una migración pendiente o un import error no debe
  tirar el scheduler ni el proceso. El log estructurado deja
  rastro para diagnosticar después.
- **`enable_currency_cron` flag**. Necesario para tests (acoplar
  el suite a un timer es flake garantizado) y útil para entornos
  donde el cron lo gestiona algo externo. Default `True` en prod.
- **Lifespan en lugar de `@app.on_event`**. La API deprecada
  desde FastAPI 0.93. Migrar ahora vs cuando otra fase lo necesite
  es lo mismo en esfuerzo y deja `main.py` actualizado.

## Limitaciones conocidas

- **Single-process only**. Con `uvicorn --workers N` cada worker
  arranca su propio scheduler y el job se ejecuta N veces.
  Aceptable hoy (MVP single-worker). Si llega multi-worker:
  cambiar a Celery beat o `SQLAlchemyJobStore` con coordinación
  por DB lock.
- **Sin persistencia de jobs**. Si el proceso se reinicia justo
  antes de la hora del cron, el job de hoy NO se ejecuta — pero
  `misfire_grace_time=1h` cubre el caso de "arranca 30min
  después". Para garantías más fuertes: `SQLAlchemyJobStore`.
- **Sin métricas / observabilidad estructuradas**. Sólo
  `logger.info / logger.exception`. Si algún día llega Prometheus
  o similar, contar `currency_cron_runs_total` /
  `currency_cron_failures_total` es trivial.
- **Sin auto-purge de papelera** (tampoco tocada en esta fase). Si
  se prioriza, sigue el mismo patrón: nuevo job en
  `app/core/scheduler.py`.

## Próxima fase

PHASE-11.2 — `useCurrencyStore` cross-platform. Pre-requisito
para que mobile herede el toggle `convertAll` y la moneda activa
del web. Sustituye `localStorage` por un adapter que use
`AsyncStorage` en RN y `localStorage` en web.
