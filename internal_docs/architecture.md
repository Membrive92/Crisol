# Arquitectura — Crisol

> Documento vivo. Se actualiza cuando una fase introduce cambios arquitectónicos.
> Última actualización: refactor a `personal_finance/` — los sub-features de
> finanzas personales (categorías, transacciones, dashboard, imports, receipts)
> viven bajo un único módulo de dominio. `auth/`, `users/` y `ai/` siguen
> top-level como infraestructura transversal.

---

## 1. Visión general

Crisol es una aplicación de finanzas personales "multiportfolio" modular,
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
crisol/
├── apps/
│   ├── web/                # Next.js App Router (apps/web/components/* solo-web)
│   └── mobile/             # Expo Router (apps/mobile/components/* solo-mobile)
├── packages/
│   ├── types/              # Tipos del dominio compartidos
│   ├── ui/                 # Design tokens + formatters puros (ADR 0001)
│   ├── services/           # Cliente API + TanStack Query hooks + query keys
│   └── store/              # Zustand stores (auth)
├── tooling/
│   ├── eslint/
│   └── typescript/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/           # Config, DB, security, deps
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
    ├── api/                # endpoints.md (PHASE-4.1)
    ├── data-model/         # schema.md (PHASE-4.1)
    ├── decisions/          # ADRs (0001-ui-tokens-only)
    ├── phases/             # 1 doc por fase completada
    └── ai-context/
```

Notas sobre el monorepo actual:

- `packages/ui` contiene **solo design tokens y formatters** —
  no componentes RN/web (ver [ADR 0001](decisions/0001-ui-tokens-only.md)).
  Los componentes UI viven en cada app (`apps/web/components/`,
  `apps/mobile/components/`).
- `packages/utils`, `packages/hooks`, `packages/features` y
  `packages/config` están planeados en la spec original pero **no se
  han creado todavía**: las apps no los han necesitado y no tiene
  sentido crear paquetes vacíos.
- Desde PHASE-6.1, las apps tienen una **shell de módulos**: web bajo
  `apps/web/app/(app)/<module-id>/...` y mobile bajo
  `apps/mobile/app/(modules)/<module-id>/...`. Sólo `personal-finance`
  está activo; el registro `MODULES` en `@crisol/types/registry/modules.ts`
  declara el resto como `enabled: false`. Settings sigue cross-cutting
  (`apps/web/app/(app)/settings/`).

Reglas de imports vigentes:

```
types     →  (sin deps internas)
ui        →  (sin deps internas — solo tokens y funciones puras)
services  →  types
store     →  types
apps/*    →  cualquier package
```

---

## 6. Backend — estructura modular

Hay dos niveles:

1. **Módulos de dominio** (`personal_finance/`, en el futuro `crypto/`,
   `inversiones/`, `inmuebles/`…). Cada uno agrupa los sub-features que
   pertenecen a esa "cartera". Son **sumar carpetas** — el MVP entrega
   sólo `personal_finance/`.
2. **Módulos transversales** (`auth/`, `users/`, `ai/`). Servicios de
   infraestructura que cualquier módulo de dominio puede usar.

```
backend/app/modules/
├── auth/                    # cross-cutting
├── users/                   # cross-cutting
├── ai/                      # cross-cutting (cliente Ollama, prompts)
└── personal_finance/        # módulo de dominio
    ├── __init__.py
    ├── categories/
    ├── transactions/
    ├── dashboard/
    ├── imports/
    └── receipts/
```

Cada sub-módulo sigue siempre la misma estructura interna:

```
{sub-módulo}/
├── __init__.py
├── router.py       # APIRouter con prefix y tags
├── service.py      # Lógica de negocio (async)
├── repository.py   # Queries a DB (async, bind params)
├── models.py       # SQLAlchemy models
└── schemas.py      # Pydantic v2 request/response
```

**Reglas no negociables**:
- Los sub-módulos dentro de `personal_finance/` pueden importar entre sí
  por ser parte del mismo dominio (`transactions` enlaza `categories`).
  **Distintos módulos de dominio** (cuando existan) no se importan entre
  sí — comparten vía core o eventos.
- `repository.py` **nunca** usa string interpolation en SQL — siempre bind params.
- `service.py` recibe `db` y `user_id` como parámetros, nunca accede al `Request`.
- Todas las queries de dominio filtran por `user_id`.
- `Decimal` para todo importe monetario. `float` está prohibido.

### Módulos del MVP

| Módulo                            | Estado | Responsabilidad                                                |
|-----------------------------------|--------|----------------------------------------------------------------|
| `users`                           | ✅     | CRUD de usuarios, perfil                                       |
| `auth`                            | ✅     | Registro, login, refresh token con rotación, logout, `/me`, "Recordarme 30 días" |
| `auth.webauthn`                   | ✅     | Passkeys (Touch ID / Windows Hello / llaves físicas) — registro y login sin password |
| `ai`                              | ✅     | Cliente Ollama + `/ai/health` + extract_receipt + extract_bank_statement_page |
| `personal_finance.categories`     | ✅     | Categorías de gasto/ingreso por usuario                        |
| `personal_finance.transactions`   | ✅     | CRUD de transacciones, filtros, aislamiento, `import_hash`     |
| `personal_finance.dashboard`      | ✅     | Agregaciones y KPIs (read-only sobre transactions/categories)  |
| `personal_finance.imports`        | ✅     | Importación CSV/XLSX/PDF con dedup por hash, jobs auditables   |
| `personal_finance.receipts`       | ✅     | Pipeline de tickets: upload → ai → confirmación → persistencia |

---

## 7. Autenticación y seguridad

- **JWT propio**:
  - Access token: 15 min, en memoria (frontend) / Authorization header.
  - Refresh token: 7 días, rotación en cada uso (revocación marcada en BD).
- **Storage de refresh token**:
  - Web: cookie `httpOnly` `SameSite=Lax` (`Secure` configurable, off
    en dev HTTP). Same-origin garantizado vía Next.js rewrites
    (`/api/*` → backend). XSS no puede leerla.
  - Mobile: `expo-secure-store`. El backend acepta el refresh tanto en
    cookie (web) como en body (mobile); si llegan ambos, gana la
    cookie.
- **Password hashing**: argon2id (`argon2-cffi`).
- **Rate limiting**: futuro. No bloqueante para MVP.
- **CORS**: estricto por entorno (`settings.cors_origins_list`).
- **Headers de seguridad**: CSP, HSTS, X-Frame-Options pendientes
  (Next.js middleware + reverse proxy en despliegue).

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

### Entidades

Estado actual del schema documentado en detalle en
[`data-model/schema.md`](data-model/schema.md). Tablas implementadas:

```
users               (PHASE-1.1) ✅
refresh_tokens      (PHASE-1.1) ✅
categories          (PHASE-2.1) ✅
transactions        (PHASE-2.1, PHASE-4.1: + import_hash) ✅
import_jobs         (PHASE-4.1) ✅
receipts            (PHASE-5.1) ✅
```

Resumen rápido:

```
users ─┬─< refresh_tokens
       ├─< categories ──┐
       ├─< transactions ┘   (category_id ON DELETE SET NULL)
       ├─< import_jobs
       └─< receipts ───┐
                       │
                       └─→ transactions   (receipts.transaction_id ON DELETE SET NULL)

transactions.import_hash → unique partial index (user_id, import_hash)
                           para deduplicar imports sin afectar a manual.
transactions.receipt_id  → UUID sin FK formal; consistencia mantenida
                           por receipts.service.confirm_receipt.
```

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
