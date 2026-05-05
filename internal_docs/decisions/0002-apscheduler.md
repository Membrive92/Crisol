# ADR-0002 — APScheduler para jobs background del backend

**Estado**: aceptada
**Fecha**: 2026-05-05
**Fase**: PHASE-11.1

## Contexto

PHASE-11.1 introduce el primer job recurrente del backend: refresh
nocturno de exchange rates. Hace falta un mecanismo que dispare la
función a una hora fija cada día sin acoplarlo a peticiones HTTP.

Las opciones evaluadas:

1. **APScheduler in-process** — librería Python que registra jobs
   con triggers (cron, interval, date) y los ejecuta dentro del
   event loop existente del proceso.
2. **Celery + Celery beat** — broker (Redis/RabbitMQ) + worker
   pool + scheduler aparte.
3. **Cron del SO + endpoint HTTP** — un cron del host hace `curl
   POST /admin/refresh-rates` a las 3:00.
4. **Cluster scheduler externo** (k8s CronJob, ECS Scheduled Task,
   GitHub Actions schedule).

## Decisión

**APScheduler in-process** con `AsyncIOScheduler` integrado en el
lifespan de FastAPI.

## Razones

- **Single-process, single-host**. La app vive en una máquina (la
  del usuario). Un broker / cluster scheduler añadiría
  infraestructura para una funcionalidad que sólo necesita "una
  vez al día llamar esta función".
- **No requiere componentes externos**. Cero dependencias nuevas
  más allá de la propia librería — sin Redis/RabbitMQ, sin
  configurar cron del SO, sin tocar Docker compose.
- **Integración nativa con asyncio**. `AsyncIOScheduler` corre en
  el mismo event loop que FastAPI; los jobs son corutinas normales.
  No hay puente sync↔async ni pool de threads.
- **Lifespan de FastAPI ya gestiona arranque/apagado limpio**. El
  scheduler arranca en startup y se cierra en shutdown — sin
  procesos huérfanos.
- **Coste de fallo bajo**. Si un job falla, lo logueamos y el
  siguiente día se reintenta. La consecuencia real de perder un
  cron es "el lazy-fetch on-request cubre el primer uso del día",
  estado pre-PHASE-11.1.

## Trade-offs

- **No funciona en multi-worker**. Si la app pasa a `uvicorn
  --workers 4`, cada worker arranca su propio scheduler y el job
  se ejecuta N veces. Aceptable hoy (single-worker dev/MVP). Si
  llega multi-worker: o bien cambiar a Celery/cluster scheduler,
  o bien usar `apscheduler` con `JobStore` persistente +
  coordinación por DB lock.
- **No persiste jobs**. Si el proceso se reinicia justo antes de
  la hora del cron, el job de hoy NO se ejecuta — pero el
  `misfire_grace_time=60min` cubre el caso de "arranca 30min
  después de la hora". Para garantías más fuertes habría que usar
  `SQLAlchemyJobStore`. No compensa por ahora.
- **APScheduler no publica type stubs (PEP 561)**. Los imports en
  `app/core/scheduler.py` llevan `# type: ignore[import-untyped]`.
  Aceptable; el resto del módulo sí está tipado.

## Alternativas descartadas

- **Celery + beat**: pesado para "una función al día". Requiere
  broker, worker, configuración de serialización.
- **Cron del SO + endpoint HTTP**: introduce un endpoint admin que
  habría que proteger (auth, rate limit, idempotencia) y acopla la
  lógica al sistema operativo del despliegue.
- **Cluster scheduler**: aún no hay despliegue cluster.

## Reversibilidad

Cambiar a Celery/cluster es localizado: `app/core/scheduler.py`
sería el único punto a tocar (más el lifespan de `main.py`). Los
módulos de dominio no saben qué dispara sus jobs — sólo exponen
funciones puras.
