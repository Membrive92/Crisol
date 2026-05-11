# Crisol

Aplicación de finanzas personales multiportfolio, multi-usuario, con IA local
para extracción automática de tickets mediante visión por computador.

Web + móvil desde un monorepo. Todo local, sin dependencias de servicios
externos: la privacidad de los datos financieros es un principio no negociable.

> 🚧 En desarrollo activo — actualmente en fase de bootstrap.
> Consulta [internal_docs/README.md](internal_docs/README.md) para el estado actual.

---

## Stack

- **Frontend**: Next.js (web) + Expo/React Native (móvil) + Turborepo + pnpm + TypeScript estricto
- **Backend**: FastAPI + SQLAlchemy 2.0 (async) + Python 3.12
- **BD**: PostgreSQL 16 + pgvector
- **IA local**: Ollama + qwen2.5-vl:7b (visión)
- **Blob storage**: MinIO
- **Auth**: JWT propio (access + refresh) + argon2id

---

## Requisitos

- Node.js 20+ y [pnpm](https://pnpm.io/) 9+
- Python 3.12+
- Docker + Docker Compose
- Make (opcional, facilita los comandos)
- GPU compatible con Ollama para el módulo de IA (CPU funciona pero lento)

---

## Arranque rápido

```bash
# 1. Instalar dependencias
make setup

# 2. Levantar servicios (Postgres, MinIO, Ollama)
make docker-up

# 3. Aplicar migraciones
make db-upgrade

# 4. Descargar modelo de visión (solo la primera vez)
docker exec -it crisol-ollama ollama pull qwen2.5-vl:7b

# 5. Arrancar frontend y backend
make dev
```

Servicios disponibles:
- Web: http://localhost:3000
- Móvil: Expo DevTools (escanea QR)
- Backend API: http://localhost:8000
- Backend docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001
- Ollama API: http://localhost:11434

---

## Comandos habituales

```bash
make dev              # Frontend + backend
make dev-web          # Solo web
make dev-mobile       # Solo móvil
make dev-backend      # Solo backend
make verify           # Lint + typecheck + tests (obligatorio antes de PR)
make test             # Tests frontend + backend
make db-migrate MSG="descripcion"   # Nueva migración
make db-upgrade       # Aplicar migraciones pendientes
make docker-up        # Levantar servicios
make docker-down      # Parar servicios
```

`make help` muestra todos los comandos disponibles.

---

## Documentación

- [CLAUDE.md](CLAUDE.md) — reglas de código obligatorias
- [CONTRIBUTING.md](CONTRIBUTING.md) — workflow de contribución
- [internal_docs/README.md](internal_docs/README.md) — índice y estado de fases
- [internal_docs/architecture.md](internal_docs/architecture.md) — arquitectura del sistema
- [internal_docs/development-spec.md](internal_docs/development-spec.md) — metodología y fases
- [internal_docs/lessons.md](internal_docs/lessons.md) — lecciones aprendidas

---

## Licencia

Propiedad privada. Todos los derechos reservados. Ver [LICENSE](LICENSE).
