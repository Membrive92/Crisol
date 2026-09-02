# Arquitectura — Crisol

> Documento vivo. Se actualiza cuando una fase introduce cambios arquitectónicos.
> Última actualización: 2026-09-02 — puesta al día contrastada con el árbol real
> (`app/main.py`, `modules/`, `packages/`, registro de módulos): el documento
> describía el MVP de un solo módulo y seis tablas; hoy hay cuatro módulos
> activos, dos dominios y una treintena de tablas. Antes: PHASE-44.11
> ([ADR-0009](decisions/0009-single-fx-source-currency-transversal.md)),
> `currency/` declarado transversal.
>
> Visión de conjunto para quien llega nuevo: [`PROJECT-GUIDE.md`](PROJECT-GUIDE.md).

---

## 1. Visión general

Crisol es una aplicación de finanzas personales modular, _local-first_, con IA
local para extracción de tickets por visión. Se entrega como monorepo con
**web (Next.js)** y **móvil (Expo)** compartiendo tipos, servicios, estado y la
lógica pura de presentación.

Hoy tiene **dos dominios** y cuatro módulos activos en la shell:

- **Finanzas domésticas** (`personal-finance` + `debt` en la UI; un solo
  módulo backend `personal_finance/`): cuentas, transacciones, imports de
  extractos, tickets, categorías, presupuestos, gastos fijos, deuda y análisis.
- **Inversión** (`investments`): análisis fundamental forense sobre 10-K de la
  SEC + cartera. Espacio separado, **no reconciliado** con el patrimonio de
  Finanzas domésticas (decisión del usuario, PHASE-44.7).
- **Dashboard**: agregación de módulos (balance / stocks, ADR-0006).

`crypto` y `real-estate` existen en el registro como `enabled: false`. Añadir
un módulo sigue siendo **sumar carpetas**: un directorio en
`backend/app/modules/`, sus rutas bajo `apps/*/…/<módulo>/`, y una entrada en
`packages/types/src/registry/modules.ts`.

---

## 2. Principios arquitectónicos

1. **Modularidad vertical**. Cada feature vive en su propio módulo
   (backend + frontend) con fronteras claras. Los módulos de dominio no se
   importan entre sí — comparten vía `core/` o vía los transversales.
2. **Privacidad por diseño**. Ningún dato del usuario sale del equipo donde
   corre la app. IA 100 % local vía Ollama. Las imágenes de tickets se guardan
   en MinIO local. Lo único que sale son peticiones a fuentes públicas (SEC,
   BCE, cotizaciones).
3. **Aislamiento multi-tenant**. Toda query a tablas de dominio filtra por
   `user_id` (salvo las tablas GLOBALES del módulo Inversión, ADR-0007, que
   no contienen datos del usuario). Tests de aislamiento obligatorios.
4. **TypeScript/Python estrictos**. Sin `any`, sin `float` para dinero, sin
   `@ts-ignore`. Ver [CLAUDE.md](../CLAUDE.md) para las reglas completas.
5. **Desarrollo incremental**. Cada fase es entregable, verificable y
   documentada antes de avanzar. Ver [development-spec.md](development-spec.md).
6. **IA como herramienta, nunca autoridad**. La IA sugiere y extrae, pero
   **nunca persiste en BD sin confirmación humana**. Generalizado en
   [ADR-0011](decisions/0011-system-initiated-debt-event-translation.md): el
   sistema **propone** traducciones (un cargo → un evento de deuda) y el
   usuario **declara**.
7. **La verdad del dinero vive en la transacción** (`flow`), no en la
   categoría ([ADR-0004](decisions/0004-transaction-level-money-truth.md)); y
   **el extracto del banco es la autoridad** sobre la dirección de un
   movimiento (PHASE-47.G). Ver §9.1.
8. **Fuente única**. Un tipo de cambio (`exchange_rates`, ADR-0009), una
   definición de «qué es un mes» (`user_month`), una declaración por
   redacción bancaria, un catálogo de métricas. Si dos módulos deben coincidir
   en «qué es X», hay UNA declaración y un gate que ata a los consumidores.

---

## 3. Stack

| Capa               | Tecnología                                                                |
| ------------------ | ------------------------------------------------------------------------- |
| Web                | Next.js (App Router)                                                      |
| Móvil              | Expo (React Native, Expo Router)                                          |
| Monorepo           | Turborepo + pnpm workspaces                                               |
| Lenguaje FE        | TypeScript estricto (`exactOptionalPropertyTypes` incluido)               |
| Estilos            | Tokens de diseño (`packages/ui`, `DESIGN.md`) + estilos inline / RN       |
| Estado cliente     | Zustand                                                                   |
| Estado servidor    | TanStack Query                                                            |
| Charts             | Recharts (web) · react-native-gifted-charts (móvil) · SVG propio (informe) |
| Backend            | FastAPI + SQLAlchemy 2.0 (async, asyncpg)                                 |
| Lenguaje BE        | Python 3.12 (`backend/.venv`, el mismo que CI)                            |
| DB                 | PostgreSQL 16 + pgvector + pg_trgm                                        |
| Migraciones        | Alembic (aditivas y reversibles; `alembic check` en CI)                   |
| Jobs               | APScheduler en proceso ([ADR-0002](decisions/0002-apscheduler.md))        |
| Blob storage       | MinIO (S3-compatible, local)                                              |
| IA local           | Ollama + qwen2.5-vl (visión)                                              |
| Auth               | JWT propio (access + refresh rotado) + argon2id + WebAuthn (passkeys)     |
| Datos externos     | EDGAR (`edgartools`), Frankfurter (BCE), yfinance / Finnhub, FIRDS (ESMA/FCA) |
| Tests FE           | Vitest + Testing Library (web, packages) · jest-expo (móvil)              |
| Tests BE           | Pytest + httpx (una sola BD de test compartida)                           |
| Lint/Format FE     | ESLint + Prettier + knip (código muerto)                                  |
| Lint/Format BE     | Ruff + Black + Mypy                                                       |
| Docs               | `scripts/check_docs.py` (enlaces, migraciones citadas, números volátiles) |
| CI                 | GitHub Actions (`.github/workflows/ci.yml`)                               |
| Containerización   | Docker Compose (postgres · minio · ollama; el backend corre en el host)    |

---

## 4. Topología de servicios

```
                    ┌──────────────┐     ┌──────────────┐
                    │  Web (Next)  │     │ Mobile (Expo)│
                    └──────┬───────┘     └──────┬───────┘
                           │ /api/* rewrite      │ EXPO_PUBLIC_API_URL
                           └────────┬───────────┘
                                    │ HTTP / JSON
                           ┌────────▼────────┐        ┌──────────────────────┐
                           │ Backend FastAPI │───────▶│ SEC EDGAR · BCE ·     │
                           │  (modular)      │        │ yfinance/Finnhub      │
                           └────────┬────────┘        └──────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
      ┌───────▼────────┐   ┌────────▼────────┐   ┌────────▼────────┐
      │ Postgres 16    │   │ MinIO           │   │ Ollama          │
      │ + pgvector     │   │ (blob storage)  │   │ (visión local)  │
      └────────────────┘   └─────────────────┘   └─────────────────┘
```

Los tres contenedores se levantan con `docker compose up -d`. El backend
corre en el host durante desarrollo; en Windows, `dev.ps1` arranca todo y
**deriva el puerto del backend de `apps/web/.env.local`** (`BACKEND_ORIGIN`),
que es el que manda sobre el rewrite de Next — hoy 8002, no el 8000 del
Makefile. No hay imagen del backend todavía (ver §11).

---

## 5. Estructura del monorepo

```
crisol/
├── apps/
│   ├── web/                # Next.js App Router · app/(app)/<módulo>/… · components/ solo-web
│   └── mobile/             # Expo Router · app/(modules)/<módulo>/… · components/ solo-móvil
├── packages/
│   ├── types/              # modelos + DTOs del dominio + registro de módulos
│   ├── ui/                 # tokens + formatters + capas PURAS de presentación (sin componentes, ADR-0001)
│   ├── services/           # cliente API (axios + interceptor de refresh) · endpoints · hooks TanStack Query
│   │                       #   · query keys · helpers de período (`period/user-month.ts`)
│   └── store/              # Zustand: auth · currency · toast (storage.native.ts para RN)
├── tooling/                # eslint · typescript compartidos
├── backend/
│   ├── app/
│   │   ├── main.py         # registra los 20 routers
│   │   ├── core/           # config · database · deps · security · storage · scheduler · civil_dates · rate_limit
│   │   └── modules/        # ver §6
│   ├── alembic/            # migraciones
│   ├── scripts/            # data-fix y seeds con --dry-run
│   ├── tests/              # pytest (ficheros planos test_*.py)
│   └── data/edgar_cache/   # caché local de hechos XBRL
├── scripts/check_docs.py   # podredumbre documental
├── dev.ps1 · Makefile · docker-compose.yml · knip.config.ts · CLAUDE.md · DESIGN.md
└── internal_docs/          # ver README.md (índice) y PROJECT-GUIDE.md (guía)
```

Notas sobre el monorepo actual:

- `packages/ui` sigue **sin componentes** React ([ADR-0001](decisions/0001-ui-tokens-only.md)):
  los componentes viven en cada app. Lo que SÍ contiene, además de tokens y
  formatters, es la **lógica pura de presentación** que las dos apps
  comparten: qué filas pinta una matriz, en qué orden, con qué rótulo y qué
  texto explicativo (`investment-*.ts`, `cycle-copy.ts`, `deferred-copy.ts`,
  `breakdown-structure.ts`…). Es deliberado: una lista de «qué se muestra»
  diverge entre web y móvil igual que una fórmula (lección PHASE-44.13).
- `packages/utils`, `packages/hooks`, `packages/features` y `packages/config`
  de la spec original **no existen**: las apps no los han necesitado.
- **Shell de módulos** (desde PHASE-6.1): el registro `MODULES` en
  `packages/types/src/registry/modules.ts` declara `dashboard`,
  `personal-finance`, `debt` e `investments` como activos. Settings es
  transversal (`apps/web/app/(app)/settings/`, incluye el ciclo del usuario).
- Los filtros de las pantallas web viajan en la URL (PHASE-27); el informe de
  Inversión también (`?tab=`, `?run=`, `?print=1`).

Reglas de imports vigentes:

```
types     →  (sin deps internas)
ui        →  (sin deps internas — tokens y funciones puras)
services  →  types
store     →  types
apps/*    →  cualquier package
```

---

## 6. Backend — estructura modular

Hay dos niveles:

1. **Módulos de dominio**: `personal_finance/` e `investment/`. Cada uno
   agrupa los sub-features de su «cartera». **No se importan entre sí** —
   comparten vía `core/` o vía los transversales.
2. **Módulos transversales**: `auth/`, `users/`, `ai/`, `currency/`.
   Servicios de infraestructura que cualquier módulo de dominio puede usar,
   **siempre a través de su `service.py`** (nunca importando sus `models`
   ni sus clientes HTTP). Consumir `currency.service` desde un módulo de
   dominio es lo esperado, no una excepción ([ADR-0009](decisions/0009-single-fx-source-currency-transversal.md)).

```
backend/app/modules/
├── auth/  (+ webauthn/)         # JWT + refresh rotado + passkeys + rate limit
├── users/                       # perfil y preferencias (cycle_start_day)
├── ai/                          # cliente Ollama, prompts, extract_receipt, extract_bank_statement_page
├── currency/                    # BCE vía Frankfurter → exchange_rates (ÚNICA fuente de FX) + cron estricto
├── personal_finance/
│   ├── accounts/                # cuentas, saldos, ancla del extracto, position_history
│   ├── transactions/            # CRUD, papelera, flow, import_hash, recategorización
│   ├── transfers/               # pares, link/unlink, from-source/from-debt, classify_import_flow
│   ├── imports/                 # parsers CSV/XLSX/PDF, fingerprint de cabecera, preview → confirm
│   ├── receipts/                # tickets: MinIO → ai → confirmación
│   ├── categories/ · category_rules/ · bank_mappings/ · categorization.py
│   ├── budgets/ · fixed_expenses/
│   ├── debt/                    # health · history · amortization · installments · reconciliation · deferral · attribution
│   ├── dashboard/ · analytics/  # balance vs cuenta de resultados (ADR-0006)
│   ├── seed/                    # categorías + reglas de bancos ES
│   └── user_month.py            # «qué es un mes para este usuario» (PHASE-48)
└── investment/
    ├── catalog/                 # securities, venues (MIC), capabilities, buscador en 3 capas, directorio FIRDS
    ├── fundamentals/ (adapters/)# EDGAR → 49 partidas canónicas, reexpresiones
    ├── analysis/
    │   ├── engine/              # PURO: 6 capas + valuation + catálogo + glosario + sector_profiles + version
    │   ├── presentation/        # PURO: distancia, orden, evidencia, narrativa, diff, rehydrate
    │   └── service/repository/router
    ├── thresholds/              # seed convergente de bandas por sector × norma
    ├── portfolio/               # lotes, FIFO, dividendos, acciones corporativas, resumen en EUR
    └── pricing/ (adapters/)     # yfinance (default) · finnhub
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

- Los sub-módulos dentro de `personal_finance/` pueden importar entre sí por
  ser parte del mismo dominio. Los seis sub-módulos de deuda viven en `debt/`
  desde PHASE-47.A y un test de capas por AST impide que el ciclo
  `accounts ↔ debt` vuelva; las URLs `/accounts/debt-*` se conservan por
  contrato.
- `repository.py` **nunca** usa string interpolation en SQL — siempre bind params.
- `service.py` recibe `db` y `user_id` como parámetros, nunca accede al `Request`.
- Todas las queries de dominio filtran por `user_id`.
- `Decimal` para todo importe monetario. `float` está prohibido.
- El `engine/` de Inversión es **puro**: sin BD, red ni reloj (test por AST).
  Toda la impureza vive en los `service.py`.

### Módulos y responsabilidades

| Módulo                          | Responsabilidad                                                                                                                                       |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `users`                         | Perfil y preferencias; `cycle_start_day` redefine «mes» y «año» en toda la app (PHASE-48)                                                              |
| `auth` · `auth.webauthn`        | Registro, login, refresh con rotación por familia, logout, «recordarme 30 días», passkeys, rate limit en login                                          |
| `ai`                            | Cliente Ollama, `/ai/health`, extracción de ticket y de página de extracto bancario; sugerencia de categoría (PHASE-20)                                 |
| `currency`                      | Tipos del BCE, cron nocturno estricto, `convert` con exclusión estándar cuando falta tasa. Única fuente de FX (ADR-0009)                                |
| `personal_finance.accounts`     | Cuentas activo/pasivo, saldos derivados de `flow`, ancla del extracto, patrimonio a fecha, `settlement_account_id`, `counts_as_debt`                    |
| `personal_finance.transactions` | CRUD, filtros por URL, papelera atómica del par, `flow` + `flow_declared_at`, `is_exceptional`, recategorización en bloque                              |
| `personal_finance.transfers`    | Pares internos, dirección explícita, `classify_import_flow` (texto + signo + categoría + cadena de saldos), conversión a deuda                          |
| `personal_finance.imports`      | CSV/XLSX/PDF con smart-parsers por rol, dedup por hash civil, guardarraíl de cuenta equivocada (409), auto-anclaje, declaraciones que sobreviven        |
| `personal_finance.receipts`     | Ticket → MinIO → visión → confirmación → una transacción                                                                                                |
| `personal_finance.categories` + rules + mappings | kind · role · is_transfer · expense_nature; motor de reglas + seed ES + autoaprendizaje (salta conceptos de dirección ambigua)         |
| `personal_finance.budgets`      | Presupuesto mensual por categoría en el mes del usuario; cross-currency opt-in; avisos proactivos                                                       |
| `personal_finance.fixed_expenses` | Detector de recurrentes, pausa/cancela, auto-post, reconciliación con `expected`                                                                     |
| `personal_finance.debt`         | Cuadro francés persistido, «el cuadro manda» (MUX), reconciliación desde el extracto, recibo aplazado, atribución de cargos, DTI con bandas BdE         |
| `personal_finance.dashboard`    | Balance/stocks: patrimonio, serie histórica, tarjetas de módulo (ADR-0006)                                                                             |
| `personal_finance.analytics`    | Cuenta de resultados/flujos: estructural vs puntual, tasa de ahorro dual, proyección de fin de mes, runway, insights, top movimientos con signo         |
| `investment.catalog`            | Identidad sobre registros oficiales (EDGAR + FIRDS, ADR-0008/0010), buscador local-first en tres capas, analizabilidad con motivo                       |
| `investment.fundamentals`       | Ingesta EDGAR por job síncrono, 49 partidas canónicas, corrección de escala con testigo, reexpresiones                                                  |
| `investment.analysis`           | Motor de 6 capas + valoración, `AnalysisRun` inmutable con cortes efectivos, presentación (narrativa en servidor, diff, tolerancia a runs viejos)        |
| `investment.thresholds`         | Bandas por sector × norma; seed convergente; `applies` y `model_variant`                                                                                |
| `investment.portfolio`          | Lotes, ventas FIFO, dividendos, acciones corporativas auditadas, resumen en divisa nativa y EUR                                                          |
| `investment.pricing`            | Cotizaciones por lote con TTL; la divisa la declara el proveedor                                                                                        |

---

## 7. Autenticación y seguridad

- **JWT propio**:
  - Access token: 15 min, en memoria (frontend) / Authorization header.
  - Refresh token: 7 días (30 con «recordarme»), rotación en cada uso con
    familia identificable (`refresh_tokens.token_id` / `family_id`).
- **Storage de refresh token**:
  - Web: cookie `httpOnly` `SameSite=Lax` con `Path=/` (`Secure`
    configurable, off en dev HTTP). Same-origin garantizado vía Next.js
    rewrites (`/api/*` → backend). XSS no puede leerla.
  - Mobile: `expo-secure-store`. El backend acepta el refresh tanto en cookie
    (web) como en body (mobile); si llegan ambos, gana la cookie.
- **Passkeys** (WebAuthn): registro y login sin contraseña.
- **Password hashing**: argon2id (`argon2-cffi`).
- **Rate limiting**: en login (`core/rate_limit.py`).
- **CORS**: estricto por entorno (`settings.cors_origins_list`).
- **Headers de seguridad**: CSP, HSTS, X-Frame-Options pendientes
  (reverse proxy en despliegue).
- Auditoría completa de seguridad y remediación en
  [`audits/2026-05-30-full-app-audit.md`](audits/2026-05-30-full-app-audit.md).

---

## 8. Flujo de IA — extracción de ticket

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
      │                             │   -vl    │
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
      │ transactions │  ← se crea UNA transacción con el total (line_items se persisten, no se materializan)
      └──────────────┘
```

**Invariantes**:

1. La imagen nunca sale del equipo.
2. Ninguna transacción se crea sin confirmación explícita del usuario.
3. El estado `Receipt` (`pending | confirmed | rejected`) es auditable.
4. Si Ollama no responde, la extracción devuelve un error claro y el usuario
   puede añadir el ticket manualmente.

El mismo módulo ofrece `extract_bank_statement_page` (fallback de visión para
PDFs sin texto) y la sugerencia de categoría del motor de reglas (PHASE-20).
Sólo `backend/app/modules/ai/` importa el cliente HTTP de Ollama; el resto
consume `ai.service.<función>` y recibe tipos del dominio. No hay una skill
aparte: las reglas están en la sección «IA local» de [CLAUDE.md](../CLAUDE.md).

---

## 9. Modelo de datos

Convenciones:

- `id UUID PRIMARY KEY`, `created_at`, `updated_at` en las tablas mutables.
- Toda tabla de dominio tiene `user_id UUID NOT NULL` con FK a `users`
  (`ON DELETE CASCADE`), **salvo las tablas globales del módulo Inversión**
  (`securities`, `financial_statements`, `restatement_flags`,
  `scoring_thresholds`, `price_quotes`, `listing_directory`) y
  `exchange_rates` — datos objetivos que no pertenecen a nadie
  ([ADR-0007](decisions/0007-investment-global-tables.md)).
- Importes en `NUMERIC(14, 2)` (Decimal, nunca float).
- Fechas en `TIMESTAMPTZ`; **las fechas civiles (extracto) se anclan en UTC
  en la frontera de entrada** (`core/civil_dates.py`, PHASE-47.J).
- Migraciones aditivas y reversibles; un backfill reproduce el comportamiento
  previo, nunca corrige datos (la corrección va en `backend/scripts/` con
  `--dry-run`, lección PHASE-34).

Detalle completo, migración a migración y columna a columna, en
[`data-model/schema.md`](data-model/schema.md). El head de Alembic se consulta
con `alembic heads`, nunca se escribe en un documento.

Resumen relacional (Finanzas domésticas):

```
users ─┬─< accounts ──────────┬─< transactions ──┬─ transfer_pair_id → transactions (par interno)
       │   ├─ parent_account_id (compra a plazos bajo tarjeta)      ├─ amortization_source_id → transactions (cargo que amortiza)
       │   ├─ settlement_account_id (activo que cobra el pasivo)    ├─ deferred_by_account_id → accounts (recibo aplazado)
       │   └─< liability_installments (cuadro de amortización)      └─ category_id → categories (SET NULL)
       ├─< categories (kind · role · is_transfer · expense_nature)
       ├─< category_rules · bank_category_mappings
       ├─< budgets · fixed_expenses
       ├─< import_jobs (header_fingerprint, preview_payload)
       ├─< receipts ─→ transactions
       └─< refresh_tokens · webauthn_credentials
```

Resumen relacional (Inversión):

```
securities (GLOBAL) ─┬─< financial_statements (GLOBAL, por ejercicio y filing, is_latest_view)
                     ├─< restatement_flags (GLOBAL)
                     ├─< price_quotes (GLOBAL, TTL)
                     ├─< ingestion_jobs (user)
                     ├─< analysis_runs (user; JSONB: scores_detail · dividend_analysis · evolution · flags · verdict · thresholds_used)
                     └─< inv_lots ─< inv_sale_allocations >─ inv_sales   (user; posición = lotes − allocations)
                          inv_dividends_received · inv_corporate_actions ─< inv_lot_adjustments
scoring_thresholds (GLOBAL: sector × norma × métrica) · listing_directory (GLOBAL: FIRDS, PK (isin, mic))
```

### 9.1 Invariantes del dominio (los que gobiernan cualquier cambio)

| Invariante                                                                                                     | Fase / ADR    |
| -------------------------------------------------------------------------------------------------------------- | ------------- |
| La dirección y la transfer-ness del dinero están en `transactions.flow`; saldo = Σ signo(`flow`, `nature`); la categoría es descriptiva | 34 · ADR-0004 |
| Una transferencia interna no es ingreso ni gasto; sus dos patas se borran y restauran juntas                    | 21.3 · 41     |
| El extracto manda: la cadena de saldos gobierna la dirección; la convención de signos es del fichero, no de la fila | 46 · 47.G     |
| `anchored_statement_balance` es un testigo externo: se re-deriva `opening_balance` y se audita (`make audit-balances`) | 39 · 47.G     |
| Una declaración manual de dirección lleva firma (`flow_declared_at`) y sobrevive a la reimportación             | 47.I          |
| Una fecha de extracto es civil: se ancla en UTC; el `import_hash` se calcula sin zona                            | 47.J          |
| Una devolución es gasto negativo, no ingreso; el neto no se mueve                                               | 47.H          |
| Dashboard = balance (stocks) · Análisis = cuenta de resultados (flujos)                                         | 43 · ADR-0006 |
| Estructural vs puntual: `tx.is_exceptional` > `category.expense_nature` > heurística                            | 37.3 · 43.2   |
| El saldo vivo de una deuda con cuadro sale del cuadro (MUX por pasivo, nunca suma de fuentes)                    | 36 · 45       |
| La cuota de una compra a plazos es gasto de caja; la liquidación de tarjeta y la creación de deuda son neutras   | 38 · 47.F     |
| Una compra aplazada sale del resultado del mes (caja) y se queda en el desglose (gasto)                          | 47.E          |
| El sistema propone la traducción movimiento→evento de deuda; el usuario declara                                 | ADR-0011      |
| `cycle_start_day` REDEFINE el mes y el año del usuario en toda la app (no es un preset)                         | 48            |
| `exchange_rates` es la única fuente de FX; sin tasa, exclusión con motivo, nunca estimación                      | ADR-0009      |
| El engine de Inversión es puro; el run es inmutable y lleva sus cortes efectivos; el tipo del run es la unión de versiones | 44.2 · 44.9 · 44.16 |
| Identidad de valores sólo sobre registros oficiales; precios sobre capas tolerantes                              | ADR-0008 · 0010 |
| Una definición de métrica vive junto a la fórmula y viaja por el catálogo; nunca se escribe en la pantalla       | 44.23 · 44.24 |

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

El backend corre en el host durante desarrollo (`dev.ps1` en Windows; `make
dev-backend` en otros). Los tests de backend usan `crisol_test` en el mismo
Postgres — **una sola base compartida**, por lo que nunca se lanzan dos suites
a la vez.

---

## 11. Estrategia de despliegue futuro

No bloqueante. La arquitectura permite:

- Despliegue en VPS con el mismo `docker-compose.yml` + reverse proxy (Caddy/Traefik)
  añadiendo un servicio `app` con su Dockerfile (no existe todavía).
- Build de frontend web desde `apps/web` (CI ya lo compila).
- Móvil: distribución por EAS Build (Expo).
- Ollama puede ejecutarse en el mismo host si tiene GPU, o en host separado.

Antes de cualquier despliegue: reset de contraseña, headers de seguridad y
secreto JWT de producción (ver `backlog.md`).

---

## 12. Referencias

- [PROJECT-GUIDE.md](PROJECT-GUIDE.md) — guía maestra para entender y continuar el proyecto
- [HANDOFF.md](HANDOFF.md) — estado de hoy
- [CLAUDE.md](../CLAUDE.md) — reglas de código obligatorias
- [development-spec.md](development-spec.md) — metodología y plantilla de fase
- [README.md](README.md) — índice y tabla de fases
- [decisions/](decisions/) — ADRs 0001-0011
- [frontend-best-practices/](../.claude/skills/frontend-best-practices/) — convenciones frontend
