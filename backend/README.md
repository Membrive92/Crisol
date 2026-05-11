# Crisol — Backend

FastAPI + SQLAlchemy 2.0 async + PostgreSQL 16 (pgvector).

## Requisitos

- Python 3.12+
- Docker (para Postgres local)

## Arranque rápido

Desde la raíz del monorepo:

```bash
# 1. Levantar Postgres
docker compose up -d postgres

# 2. Crear entorno virtual e instalar dependencias
cd backend
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/python -m pip install -e ".[dev]"

# 3. Aplicar migraciones
.venv/Scripts/python -m alembic upgrade head

# 4. Arrancar el servidor
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

Servicios:
- API: http://localhost:8000
- Docs OpenAPI: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Comandos de desarrollo

```bash
# Tests
.venv/Scripts/python -m pytest -v

# Lint + format
.venv/Scripts/python -m ruff check app tests
.venv/Scripts/python -m black --check app tests

# Typecheck
.venv/Scripts/python -m mypy app

# Nueva migración
.venv/Scripts/python -m alembic revision --autogenerate -m "descripción"

# Aplicar migraciones
.venv/Scripts/python -m alembic upgrade head
```

## Estructura

```
backend/
├── app/
│   ├── main.py           # FastAPI app + routers
│   ├── core/             # Config, DB, seguridad (futuro)
│   └── modules/          # Módulos de dominio (se añaden por fase)
├── alembic/              # Migraciones
├── tests/
└── pyproject.toml
```

Cada módulo en `app/modules/` sigue el patrón
`router.py → service.py → repository.py → models.py → schemas.py`.
Ver [CLAUDE.md](../CLAUDE.md) para las reglas completas.
