# Crisol — Comandos de desarrollo
# Usa: make <comando>

.PHONY: dev dev-web dev-mobile dev-backend setup lint typecheck test verify format db-migrate db-upgrade docker-up docker-down clean

# ═══════════════════════════════════════
# SETUP
# ═══════════════════════════════════════

setup: ## Instalar todo desde cero
	pnpm install
	cd backend && pip install -e ".[dev]" --break-system-packages
	cp .env.example .env 2>/dev/null || true
	make docker-up
	cd backend && alembic upgrade head
	@echo "✅ Setup completo. Ejecuta 'make dev' para empezar."

# ═══════════════════════════════════════
# DESARROLLO
# ═══════════════════════════════════════

dev: ## Arrancar todo (frontend + backend)
	pnpm dev

dev-web: ## Solo web (Next.js)
	pnpm dev:web

dev-mobile: ## Solo móvil (Expo)
	pnpm dev:mobile

dev-backend: ## Solo backend (FastAPI)
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ═══════════════════════════════════════
# CALIDAD
# ═══════════════════════════════════════

lint: ## Lint frontend + backend
	pnpm lint
	cd backend && ruff check app/

typecheck: ## TypeScript + mypy
	pnpm typecheck
	cd backend && mypy app/

test: ## Todos los tests
	pnpm test
	cd backend && pytest tests/ -v

test-backend: ## Solo tests backend
	cd backend && pytest tests/ -v --tb=short

test-module: ## Tests de un módulo. Uso: make test-module MOD=auth
	cd backend && pytest tests/modules/test_$(MOD).py -v

format: ## Formatear todo
	pnpm format
	cd backend && black app/ tests/

verify: ## Verificación completa (lint + typecheck + tests)
	@echo "🔍 Ejecutando verificación completa..."
	@make lint
	@make typecheck
	@make test
	@echo "✅ Todo OK — fase lista para documentar y commitear."

# ═══════════════════════════════════════
# BASE DE DATOS
# ═══════════════════════════════════════

db-migrate: ## Crear migración. Uso: make db-migrate MSG="create users table"
	cd backend && alembic revision --autogenerate -m "$(MSG)"

db-upgrade: ## Aplicar migraciones pendientes
	cd backend && alembic upgrade head

db-downgrade: ## Revertir última migración
	cd backend && alembic downgrade -1

db-history: ## Ver historial de migraciones
	cd backend && alembic history

# ═══════════════════════════════════════
# DOCKER
# ═══════════════════════════════════════

docker-up: ## Levantar servicios (DB, MinIO)
	docker compose up -d

docker-down: ## Parar servicios
	docker compose down

docker-logs: ## Ver logs del backend
	docker compose logs -f app

docker-reset: ## Reset completo (⚠️ borra datos)
	docker compose down -v
	docker compose up -d
	cd backend && alembic upgrade head

# ═══════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════

clean: ## Limpiar artefactos de build
	rm -rf apps/web/.next apps/mobile/.expo
	rm -rf packages/*/dist
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

help: ## Mostrar esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
