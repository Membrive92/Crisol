# Arquitectura — Finanzas App

> Documento vivo. Se actualiza cuando una fase introduce cambios arquitectónicos.
> Última actualización: PHASE-0.0 (setup inicial).

---

## 1. Visión general

Finanzas App es una aplicación de finanzas personales "multiportfolio" modular,
multi-usuario, con IA local para extracción de tickets mediante visión por
computador. Se entrega como monorepo con **web (Next.js)** y **móvil (Expo)**
compartiendo lógica, tipos y UI.

El MVP entrega **un único módulo** (Finanzas Personales) pero la arquitectura
está diseñada para que añadir módulos futuros (crypto, inversiones, inmuebles)
sea **sumar carpetas**, no refactorizar.

---

## 2. Principios arquitectónicos

1. **Modularidad vertical**. Cada feature vive en su propio módulo
   (backend + frontend) con fronteras claras. Los módulos no se importan entre
   sí directamente — se comunican vía DB o eventos.
2. **Privacidad por diseño**. Ningún dato del usuario sale del equipo donde
   corre la app. IA 100% local vía Ollama. Imágenes de tickets se guardan en
   MinIO local y nunca se envían a servicios externos.
3. **Aislamiento multi-tenant**. Toda query a tablas de dominio filtra por
   `user_id`. Tests de aislamiento obligatorios.
4. **Typescript/Python estrictos**. Sin `any`, sin `float` para dinero, sin
   `@ts-ignore`. Ver [CLAUDE.md](../CLAUDE.md) para reglas completas.
5. **Desarrollo incremental**. Cada fase es entregable, verificable y
   documentada antes de avanzar. Ver [development-spec.md](development-spec.md).
6. **IA como herramienta, nunca autoridad**. La IA sugiere y extrae, pero
   **nunca persiste en BD sin confirmación humana**.

---

## 3. Stack

| Capa              | Tecnología                                      |
|-------------------|-------------------------------------------------|
| Web               | Next.js 14+ (App Router)                        |
| Móvil             | Expo SDK 50+ (React Native)                     |
| Monorepo          | Turborepo + pnpm workspaces                     |
| Lenguaje FE       | TypeScript 5.x estricto                         |
| Estilos           | NativeWind / Tailwind CSS                       |
| Estado cliente    | Zustand                                         |
| Estado servidor   | TanStack Query                                  |
| Backend           | FastAPI + SQLAlchemy 2.0 (async)                |
| Lenguaje BE       | Python 3.12+                                    |
| DB                | PostgreSQL 16 + extensión pgvector              |
| Migraciones       | Alembic                                         |
| Blob storage      | MinIO (S3-compatible, local)                    |
| IA local          | Ollama (runtime) + qwen2.5-vl:7b (visión)       |
| Auth              | JWT propio (access + refresh) + argon2id        |
| Tests FE          | Vitest + Testing Library                        |
| Tests BE          | Pytest + httpx                                  |
| Lint/Format FE    | ESLint + Prettier                               |
| Lint/Format BE    | Ruff + Black + Mypy                             |
| CI                | GitHub Actions                                  |
| Containerización  | Docker Compose                                  |

---

## 4. Topología de servicios

```
                    ┌──────────────┐     ┌──────────────┐
                    │  Web (Next)  │     │ Mobile (Expo)│
                    └──────┬───────┘     └──────┬───────┘
                           │                    │
                           └────────┬───────────┘
                                    │ HTTPS / JSON
                           ┌────────▼────────┐
                           │ Backend FastAPI │
                           │  (modular)      │
                           └────────┬────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
      ┌───────▼────────┐   ┌────────▼────────┐   ┌────────▼────────┐
      │ Postgres 16    │   │ MinIO           │   │ Ollama          │
      │ + pgvector     │   │ (blob storage)  │   │ (visión local)  │
      └────────────────┘   └─────────────────┘   └─────────────────┘
```

Todos los servicios se levantan con `docker compose up -d`. El backend corre
normalmente en el host durante desarrollo (hot reload), pero tiene su propia
imagen para despliegue.

---

## 5. Estructura del monorepo

```
finanzas-app/
├── apps/
│   ├── web/                # Next.js App Router
│   └── mobile/             # Expo Router
├── packages/
│   ├── ui/                 # Componentes compartidos (sin data fetching)
│   ├── features/           # Feature modules (auth, transactions, receipts…)
│   ├── hooks/              # Hooks genéricos
│   ├── services/           # Cliente API + TanStack Query hooks
│   ├── store/              # Zustand stores globales
│   ├── types/              # Tipos del dominio compartidos
│   ├── utils/              # Helpers, formatters
│   └── config/             # ESLint, Tailwind, tsconfig compartidos
├── tooling/
│   ├── eslint/
│   └── typescript/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/           # Config, DB, security, exceptions
│   │   └── modules/        # Un directorio por módulo de dominio
│   ├── alembic/            # Migraciones
│   ├── tests/
│   └── pyproject.toml
├── docker-compose.yml
├── Makefile
├── CLAUDE.md
└── internal_docs/
    ├── README.md
    ├── architecture.md
    ├── development-spec.md
    ├── lessons.md
    └── ai-context/
```

Reglas de imports entre packages (ver [skill frontend-best-practices](../.claude/skills/frontend-best-practices/SKILL.md)):

```
types  →  (sin deps internas)
utils  →  types
hooks  →  types, utils
services → types, utils
store  →  types, utils, services
ui     →  types, utils, hooks   (NUNCA services ni store)
features → cualquiera excepto otros features
apps/* →  cualquier package
```

---

## 6. Backend — estructura modular

Cada módulo vive en `backend/app/modules/{nombre}/` y sigue exactamente:

```
modules/{nombre}/
├── __init__.py
├── router.py       # APIRouter con prefix y tags
├── service.py      # Lógica de negocio (async)
├── repository.py   # Queries a DB (async, bind params)
├── models.py       # SQLAlchemy models
└── schemas.py      # Pydantic v2 request/response
```

**Reglas no negociables**:
- Ningún módulo importa de otro módulo directamente. Si necesitan compartir
  algo, va a `app/core/` o se comunica por DB.
- `repository.py` **nunca** usa string interpolation en SQL — siempre bind params.
- `service.py` recibe `db` y `user_id` como parámetros, nunca accede al `Request`.
- Todas las queries de dominio filtran por `user_id`.
- `Decimal` para todo importe monetario. `float` está prohibido.

### Módulos del MVP

| Módulo           | Responsabilidad                                                       |
|------------------|-----------------------------------------------------------------------|
| `users`          | CRUD de usuarios, perfil                                              |
| `auth`           | Registro, login, refresh token, logout                                |
| `categories`     | Categorías de gasto/ingreso por usuario                               |
| `transactions`   | CRUD de transacciones, filtros, aislamiento                           |
| `imports`        | Importación de CSV/Excel bancarios                                    |
| `ai`             | Cliente Ollama, prompts, extracción estructurada — **uso interno**    |
| `receipts`       | Pipeline de tickets: upload → ai → confirmación → persistencia        |
| `dashboard`      | Agregaciones y KPIs (sin estado propio)                               |

---

## 7. Autenticación y seguridad

- **JWT propio**:
  - Access token: 15 min, en memoria (frontend) / Authorization header.
  - Refresh token: 7 días, rotación en cada uso.
- **Storage de refresh token**:
  - Web: cookie `httpOnly`, `Secure`, `SameSite=Strict`.
  - Mobile: `expo-secure-store`.
- **Password hashing**: argon2id (`argon2-cffi`).
- **Rate limiting**: futuro. No bloqueante para MVP.
- **CORS**: estricto por entorno.
- **Headers de seguridad**: CSP, HSTS, X-Frame-Options (gestión en Next.js middleware y reverse proxy futuro).

---

## 8. Flujo de IA — extracción de ticket

Este es el flujo diferenciador del MVP.

```
 ┌──────────┐   1. subir imagen   ┌──────────────┐
 │ Frontend │────────────────────▶│ receipts API │
 └──────────┘                     └──────┬───────┘
      ▲                                  │ 2. store blob
      │                                  ▼
      │                             ┌─────────┐
      │                             │  MinIO  │
      │                             └─────────┘
      │                                  │
      │                                  │ 3. ai.service.extract_receipt(bytes)
      │                                  ▼
      │                             ┌────────────┐
      │                             │ ai.service │
      │                             └─────┬──────┘
      │                                   │ 4. POST /api/generate
      │                                   ▼
      │                             ┌──────────┐
      │                             │  Ollama  │
      │                             │ qwen2.5  │
      │                             │  -vl:7b  │
      │                             └─────┬────┘
      │                                   │ 5. JSON con líneas
      │                                   ▼
      │                             ┌────────────┐
      │                             │ Pydantic   │
      │                             │ validation │
      │                             └─────┬──────┘
      │  6. ReceiptExtraction             │
      └───────────────────────────────────┘
             │
             │ 7. usuario edita y confirma
             ▼
      ┌──────────────┐
      │ transactions │  ← se crean las transacciones
      └──────────────┘
```

**Invariantes**:
1. La imagen nunca sale del equipo.
2. Ninguna transacción se crea sin confirmación explícita del usuario.
3. El estado `Receipt` (`pending | confirmed | rejected`) es auditable.
4. Si Ollama no responde, la extracción devuelve un error claro y el usuario
   puede añadir el ticket manualmente.

Las reglas de implementación del módulo `ai/` se detallarán en una skill
`local-ai-integration` que se creará en PHASE-5.1 junto con el código.

---

## 9. Modelo de datos (MVP)

Convenciones:
- Todas las tablas tienen `id UUID PRIMARY KEY`, `created_at`, `updated_at`.
- Todas las tablas de dominio tienen `user_id UUID NOT NULL` con FK a `users`.
- Importes en `NUMERIC(14, 2)` (Decimal, nunca float).
- Fechas en `TIMESTAMPTZ`.
- FK con `ON DELETE CASCADE` en relaciones hijas del usuario.

### Entidades iniciales

```
users
├── id, email (unique), password_hash, display_name
└── created_at, updated_at

categories
├── id, user_id, name, icon, color
├── kind: ENUM('income', 'expense')
└── created_at, updated_at

transactions
├── id, user_id, category_id, amount NUMERIC(14,2), currency CHAR(3)
├── occurred_at TIMESTAMPTZ, description TEXT
├── source: ENUM('manual', 'import', 'receipt')
├── receipt_id FK NULLABLE
└── created_at, updated_at

receipts
├── id, user_id, blob_key, mime_type
├── status: ENUM('pending', 'confirmed', 'rejected')
├── extracted_json JSONB, extracted_at, model_version
└── created_at, updated_at

import_jobs
├── id, user_id, filename, status
├── rows_ok, rows_failed, error_log JSONB
└── created_at, updated_at
```

Se documentará en detalle en `internal_docs/data-model/schema.md` a medida
que se implementen las migraciones (archivo se crea en PHASE-1.1).

---

## 10. Infraestructura local

`docker-compose.yml` levanta:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports: ["9000:9000", "9001:9001"]
    volumes: [miniodata:/data]

  ollama:
    image: ollama/ollama
    ports: ["11434:11434"]
    volumes: [ollamadata:/root/.ollama]
    # En máquinas con GPU NVIDIA: añadir runtime: nvidia + deploy.resources

volumes:
  pgdata:
  miniodata:
  ollamadata:
```

El backend corre en el host durante desarrollo. En despliegue futuro se añade
un servicio `app` al compose con su Dockerfile.

---

## 11. Estrategia de despliegue futuro

No bloqueante para MVP. La arquitectura permite:
- Despliegue en VPS con el mismo `docker-compose.yml` + reverse proxy (Caddy/Traefik).
- Build de frontend web estático desde `apps/web`.
- Móvil: distribución por EAS Build (Expo).
- Ollama puede ejecutarse en el mismo host si tiene GPU, o en host separado.

Decisiones formales de despliegue irán a `internal_docs/decisions/` cuando toque.

---

## 12. Referencias

- [CLAUDE.md](../CLAUDE.md) — reglas de código obligatorias
- [development-spec.md](development-spec.md) — fases y metodología
- [README.md](README.md) — estado actual
- [frontend-best-practices/](../.claude/skills/frontend-best-practices/) — convenciones frontend
