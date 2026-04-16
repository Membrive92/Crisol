# PHASE-0.2 — Bootstrap backend

**Estado**: 🚧 en curso
**Rama**: `feat/phase-0.2-bootstrap-backend`
**PR**: (pendiente)
**Fecha de merge**: (pendiente)

## Objetivo

Arrancar el backend FastAPI con un endpoint `/health`, Postgres+pgvector en
docker-compose, Alembic configurado en modo async, primer test de integración
pasando contra una DB real y CI con job backend verde.

## Qué se implementó

- **`backend/`** — proyecto Python con `pyproject.toml` (editable install):
  - FastAPI 0.135, SQLAlchemy 2.0 async, asyncpg, Alembic, Pydantic v2,
    pydantic-settings, uvicorn.
  - Dev deps: pytest + pytest-asyncio + httpx, ruff, black, mypy.
- **`backend/app/core/config.py`** — `Settings` con Pydantic, lee `.env`.
- **`backend/app/core/database.py`** — engine async + `SessionLocal` +
  `get_db` dependency + `Base` declarativa.
- **`backend/app/main.py`** — FastAPI app con middleware CORS y endpoint
  `GET /health`.
- **`backend/alembic/`** — Alembic configurado en modo **async**:
  - `env.py` usa `async_engine_from_config` y `async with connectable.connect()`.
  - Lee la URL desde `settings.database_url`, no desde `alembic.ini`.
  - `script.py.mako` compatible con Python 3.12 (sin `typing.Optional`).
- **`backend/tests/conftest.py`** — fixtures globales:
  - `test_engine` — engine compartido para toda la sesión de tests.
  - `db_session` — sesión con transacción rolleada por test.
  - `client` — `AsyncClient` de httpx con `ASGITransport` inyectando la
    sesión de test vía `dependency_overrides[get_db]`.
- **`backend/tests/test_health.py`** — smoke test de `/health`.
- **`docker-compose.yml`** en la raíz con servicio `postgres`
  (imagen `pgvector/pgvector:pg16`, volumen persistente, healthcheck).
- **`.github/workflows/ci.yml`** — nuevo job `backend`:
  - Service container `pgvector/pgvector:pg16`.
  - `ruff check` → `black --check` → `mypy` → `alembic upgrade head` → `pytest`.
- **`backend/README.md`** — instrucciones de arranque local y comandos dev.

## Flujo técnico

```
.env  ──▶  Settings (pydantic-settings)
                │
                ▼
        database.py
     ┌──────┴───────┐
     │              │
  engine      SessionLocal
     │              │
     └──────┬───────┘
            ▼
      get_db() dep
            │
            ▼
      FastAPI routes (/health)

Tests:
  conftest.engine  ──▶  conftest.db_session (tx rolleada)
                                │
                                ▼
                    dependency_overrides[get_db]
                                │
                                ▼
                           AsyncClient
                                │
                                ▼
                           assert 200
```

## Archivos clave

- [backend/pyproject.toml](../../backend/pyproject.toml) — deps + config de tools
- [backend/app/main.py](../../backend/app/main.py) — FastAPI app
- [backend/app/core/config.py](../../backend/app/core/config.py) — Settings
- [backend/app/core/database.py](../../backend/app/core/database.py) — engine + get_db
- [backend/alembic/env.py](../../backend/alembic/env.py) — Alembic async
- [backend/tests/conftest.py](../../backend/tests/conftest.py) — fixtures
- [docker-compose.yml](../../docker-compose.yml) — postgres
- [.github/workflows/ci.yml](../../.github/workflows/ci.yml) — CI con job backend

## Endpoints añadidos

- `GET /health` — smoke test, no toca DB. Devuelve `{"status": "ok", "env": ...}`.

## Migraciones

Ninguna todavía. `alembic upgrade head` solo crea la tabla `alembic_version`
— es el smoke test del env async. La primera migración real con tablas viene
en PHASE-1.1 con `users`.

## Verificación

- [x] `pip install -e ".[dev]"` limpio
- [x] `ruff check app tests` verde
- [x] `black --check app tests` verde
- [x] `mypy app` verde (strict + pydantic plugin)
- [x] `docker compose up -d postgres` arriba y healthy
- [x] `alembic upgrade head` verde (env async conecta a Postgres)
- [x] `pytest -v` verde (1 passed, `test_health_ok`)
- [ ] CI en GitHub Actions verde tras el push (job backend)

## Decisiones tomadas

- **pip + pyproject.toml** en lugar de uv — menos dependencias externas, más
  simple para empezar. Migrable a uv en el futuro sin cambios en el código.
- **Una sola base de datos** en lugar de `finanzas` + `finanzas_test` —
  los tests usan transacción rolleada, así que nunca contaminan datos reales.
- **Alembic en modo async puro** en vez de sync con wrapper — evita tener
  que duplicar el engine.
- **`Base` declarativa en `core/database.py`** y no en un archivo aparte —
  se mantiene junto al engine; mover a `core/base.py` solo si crece.
- **CORS estricto desde día 1** vía `settings.cors_origins`.
- **`test_health` no toca la DB** — verifica que la app carga y responde,
  no la conexión. Cuando haya endpoints reales con queries, tests sí abrirán
  sesión via la fixture.

## Limitaciones conocidas

- No hay Dockerfile del backend. En desarrollo se corre con uvicorn en host.
  El Dockerfile llegará cuando preparemos el despliegue.
- No hay Ollama ni MinIO todavía — PHASE-0.3 y PHASE-5.1 respectivamente.
- No hay rate limiting ni headers de seguridad (HSTS, CSP). Llegan cuando
  pongamos el reverse proxy en fase de despliegue.
- El test actual es un smoke; los tests de módulos reales llegan en PHASE-1.1.

## Próxima fase

PHASE-0.3 — Bootstrap Ollama: servicio `ollama` en docker-compose, modelo
visión descargado, módulo `app/modules/ai/` con cliente mínimo y endpoint
`GET /ai/health` que pinguea Ollama.
