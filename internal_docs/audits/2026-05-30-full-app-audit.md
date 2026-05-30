# Auditoría completa de la app — 2026-05-30

> Auditoría de arquitectura, buenas prácticas, usabilidad, UX, accesibilidad,
> seguridad, corrección de datos, rendimiento y testing.
>
> **Método:** auditoría multi-agente (8 auditores especializados en paralelo) +
> **verificación adversarial** de cada hallazgo crítico/alto (un agente
> independiente intenta *refutar* leyendo el código) + un **crítico de
> completitud** que cazó puntos ciegos. 23 agentes, ~2M tokens, 61 hallazgos
> base + 11 puntos ciegos adicionales.
>
> **Las severidades de este informe son las AJUSTADAS por la verificación**, que
> recalibró el riesgo al contexto real del producto: **app local-first,
> monousuario, self-hosted, sin artefacto de despliegue productivo todavía**
> (docker-compose solo levanta postgres/minio/ollama; el backend corre en el
> host en dev). Por eso varias cosas etiquetadas inicialmente "critical/account
> takeover" bajan a high/medium: son *footguns* a cerrar **antes de cualquier
> despliegue real**, no exposiciones activas hoy.

---

## 1. Resumen ejecutivo

| Severidad (ajustada) | Nº |
|----------------------|----|
| 🔴 High               | 7  |
| 🟠 Medium             | 26 |
| 🟡 Low                | 18 |
| ⚪ Info               | 5  |
| **Total (deduplicado)** | **~56** + 11 puntos ciegos a verificar |

**Salud general:** la base es **sólida** — modularidad vertical respetada en su
mayoría, `Decimal` para dinero en todo el dominio, **aislamiento multi-tenant
correcto** (los auditores verificaron 6+ repositorios y NO encontraron IDOR de
lectura/mutación cross-tenant), bind params en todo el SQL (cero inyección),
rotación de refresh tokens, argon2id. No hay agujeros de robo de datos entre
usuarios.

**Los 5 frentes que más mueven la aguja (en orden):**

1. **El quality gate está roto en HEAD** — CI corre ruff/black/mypy como pasos
   *hard-fail* pero `main` falla los tres (27 errores mypy, 65 ruff, 86 ficheros
   sin formatear con black). El gate no distingue una regresión real del ruido.
   **Esto es lo primero.**
2. **Endurecimiento de auth pre-despliegue** — secreto JWT por defecto que
   *falla abierto*, sin rate limiting, y el lookup de refresh hace un escaneo
   O(N) con argon2 por fila (DoS no autenticado).
3. **Disponibilidad: I/O síncrono bloqueando el event loop** — pdfplumber /
   openpyxl / Pillow / MinIO se ejecutan síncronos dentro de handlers async, sin
   `run_in_threadpool` en ningún sitio: un XLSX/PDF grande o un MinIO lento
   congela **todo** el worker.
4. **Manejo de errores en el frontend** — sin error boundaries; varias páginas
   no tienen rama `isError` y **muestran el empty-state amistoso cuando la query
   falla** (le dicen al usuario "no tienes datos" durante una caída); los
   estados de error son texto muerto sin botón "Reintentar".
5. **Rendimiento del módulo deuda** — la página `/debt` es la más pesada:
   debt-history hace 3 queries SQL por mes (N+1), 4 endpoints recalculan
   balances/cuentas de forma redundante, y falta el índice sobre
   `transactions.occurred_at` que sostiene casi todas las agregaciones.

---

## 2. Cómo leer este informe

- Cada hallazgo tiene un **ID estable** para referenciarlo en commits/PRs.
- ✔︎ = **verificado adversarialmente** (crítico/alto). Los medium/low no se
  re-verificaron uno a uno pero todos citan `file:line` del código real.
- 🔎 = **puntos ciegos** surgidos del crítico de completitud: localizaciones
  citadas pero **conviene confirmarlos a nivel de código antes de actuar**.
- Severidad = la ajustada por la verificación al contexto del producto.

---

## 3. Prioridad P0/P1 — lo que abordaría primero

### P0 — el gate de calidad

- **`ci-gates-red-on-head`** 🔴✔︎ — `.github/workflows/ci.yml:92-99` corre
  `ruff check`, `black --check`, `mypy app` como pasos hard-fail, pero el HEAD
  commiteado (`a3b954e`) los falla (reproducido en worktree limpio: 27 errores
  mypy en 7 ficheros, 65 ruff, 86 black). Incluye el *hot path* de conversión
  (`dashboard/conversion.py:86-115` InstrumentedAttribute vs ColumnElement ×9),
  el query-builder de transactions (×8), e imports sin usar
  (`calendar`/`timedelta`/`EFFORT_BAND_*` en `debt/service.py`).
  **Fix:** `ruff check app tests --fix` + limpiar lo no auto-fixable, `black app
  tests`, y *narrowear* los tipos SQLAlchemy en `conversion.py`/`repository.py`;
  luego **branch protection** exigiendo CI verde. (Nota: parte de los imports
  sin usar de `debt/service.py` ya los limpié en PHASE-30.8; el resto de la base
  sigue rojo.)

### P1 — seguridad / disponibilidad / corrección (cerrar antes de exponer la app)

- **`weak-default-jwt-secret`** 🔴✔︎ *(fusiona el duplicado `weak-jwt-secret-default`)*
  — `core/config.py:41` el `jwt_secret_key` por defecto es la constante pública
  `"DEV-ONLY-CHANGE-ME-IN-DOT-ENV-PLEASE-32B"`; `Settings` carga `.env` con
  `extra='ignore'` y **todos** los campos tienen default → si falta `.env`, la
  app **arranca igualmente** firmando tokens HS256 con una clave conocida →
  cualquiera forja un token con `sub=<uuid víctima>` (`deps.py:37-66` confía en
  `payload["sub"]` sin `aud`/`iss`). Hoy el `.env` real tiene un secreto fuerte,
  por eso es high y no critical. **Fix:** validador Pydantic que *falle al
  arrancar* si `app_env != 'development'` y el secreto es el default o < 32
  bytes. Igual para `minio_access_key/secret_key` (`'minioadmin'`).
- **`refresh-token-full-table-argon2-scan`** 🔴✔︎ — `auth/service.py:202-214`
  `_find_matching_token` hace `SELECT … WHERE revoked=false` sobre **todos los
  usuarios** y corre `verify_refresh_token` (argon2id, 64 MiB/verify) por fila
  hasta encontrar match. En cada `/auth/refresh` y `/auth/logout`. La
  verificación encontró que **subestima** el problema: `/auth/refresh` no
  requiere auth y acepta cualquier `str`, así que un **atacante no autenticado**
  con basura dispara el peor caso (escaneo completo, un argon2 por fila, sin
  early-exit); además no hay limpieza de tokens expirados → N crece sin límite.
  **Fix:** token auto-identificable (`<token_id>.<secret>`, índice por
  `token_id`, un solo verify) **o** HMAC-SHA256 con clave (indexado) en vez de
  argon2. Añadir purga de expirados.
- **`no-rate-limiting-auth`** 🔴✔︎ — sin middleware ni throttle en
  `/auth/login|register|refresh` ni en los endpoints WebAuthn → fuerza bruta de
  password, credential stuffing, account-spam (register además ejecuta
  `seed_recommended` ~30 reglas = amplificación), y DoS por refresh. **Fix:**
  limiter IP+cuenta (slowapi/redis token-bucket), backoff/lockout por cuenta.
- 🔎 **WebAuthn / passkeys — superficie entera sin auditar (consumo de challenge
  con race)** — `webauthn/repository.py:54-81` `consume_authentication_challenge`
  hace match `purpose='authenticate' AND (user_id == X OR user_id IS NULL)`
  ordenado por `created_at DESC` **sin enlazar al challenge concreto emitido**:
  bajo logins *discoverable* concurrentes, la petición A puede consumir el
  challenge NULL-user de la B (confusión de challenge cross-sesión). Además
  `delete_expired_challenges` existe pero **no está programado** → la tabla crece
  sin límite. **Verificar y atar el challenge a su `id` emitido.**
- 🔎 **I/O síncrono bloqueando el event loop** *(clase de disponibilidad
  completa, ausente de los finders)* — `imports/parser.py` (openpyxl/pdfplumber),
  `ai/client.py:28-54` (Pillow), `core/storage.py:54-105` (MinIO put/get/bucket)
  corren **síncronos dentro de handlers async**, y un grep confirma **cero**
  `run_in_threadpool`/`asyncio.to_thread` en el backend. Un XLSX/PDF de varios MB
  o un MinIO lento **congela el worker entero** y bloquea a todos los usuarios
  concurrentes. **Fix:** envolver todo I/O bloqueante de terceros en
  `run_in_threadpool`/`to_thread` (o mover imports/receipts a una cola/worker).
- 🔎 **Sin security headers ni exception handler global** — `main.py:52-66` solo
  cablea CORS: no hay CSP/HSTS/X-Frame-Options/X-Content-Type-Options/
  Referrer-Policy ni un handler 500 genérico (con `app_debug` on, las
  excepciones devuelven traceback completo). `architecture.md` ya los marca
  "pendientes" y siguen sin implementar. **Fix:** middleware de headers + handler
  500 opaco en no-dev + log server-side.
- **Manejo de errores en frontend** (clúster de 3 hallazgos del mismo origen):
  - **`errors-masked-as-empty`** 🟠✔︎ — `transfers/page.tsx:206-222`,
    `budgets/page.tsx:106-120`, `fixed-expenses/page.tsx:254-269` ramifican
    `isLoading ? … : items.length===0 ? <Empty/> : <List/>` **sin rama
    `isError`** → al fallar la query, `data=undefined`, `?? []` → length 0 →
    **muestra el empty-state**, diciéndole al usuario "no tienes pares/
    presupuestos/gastos" durante una caída. (8 páginas pares SÍ tienen
    `isError`; estas 3 son las outliers.)
  - **`no-retry-on-error`** 🟠✔︎ — las 10 ramas `isError` de web son
    `<p>Error: …</p>` sin botón "Reintentar"; el `refetch()` que la query ya
    expone no se usa en ningún sitio (mobile sí). Dashboard pinta el error
    abajo del todo, fácil de no ver.
  - **`no-error-boundaries`** 🟠 — cero `error.tsx`/`global-error.tsx` (web) y
    cero ErrorBoundary (mobile): un throw en cualquier hoja tumba la ruta entera
    con pantalla en blanco. **Fix conjunto:** `ErrorState` compartido con
    "Reintentar" (`refetch`), `app/(app)/error.tsx` + `global-error.tsx`, y
    boundary en el navigator móvil. Empty-state **solo** cuando la query tuvo
    éxito con 0 filas.
- **`missing-occurred-at-index`** 🟠✔︎ — no hay índice sobre
  `transactions.occurred_at` (solo el parcial sobre `user_id`). Toda agregación
  de dashboard/deuda filtra por rango de `occurred_at` y la lista ordena por
  `occurred_at DESC LIMIT 20` sin índice → scan por-usuario + sort en memoria.
  **El fix backend de mayor palanca y menor esfuerzo.** **Fix:** `CREATE INDEX
  ix_transactions_user_occurred_active ON transactions (user_id, occurred_at
  DESC) WHERE deleted_at IS NULL` (Alembic + `__table_args__`).

---

## 4. Hallazgos por dimensión

### 4.1 Seguridad — AuthN / AuthZ / multi-tenant

| ID | Sev | Título | Ubicación | Fix breve |
|----|-----|--------|-----------|-----------|
| `weak-default-jwt-secret` ✔︎ | 🔴 | Secreto JWT default que falla-abierto | `core/config.py:41`, `security.py:47,91` | Validador fail-closed en `Settings` |
| `refresh-token-full-table-argon2-scan` ✔︎ | 🔴 | Lookup de refresh escanea toda la tabla con argon2/fila | `auth/service.py:202-214` | Token auto-identificable o HMAC indexado |
| `no-rate-limiting-auth` ✔︎ | 🔴 | Sin rate limiting en login/register/refresh/passkey | `auth/router.py`, `main.py` | Limiter IP+cuenta + lockout |
| `no-refresh-reuse-detection` ✔︎ | 🟠 | Rotación sin detección de robo/replay | `auth/service.py:111-159` | `family_id`/lineage; revocar familia al detectar replay |
| `login-account-enumeration-and-email-normalization` | 🟡 | Timing en login + WebAuthn delata cuentas; email sin normalizar | `auth/service.py:90-101,59-72`; `webauthn/service.py:156-168` | argon2 dummy en user-missing; lowercase email + índice CI; passkey-options genérico |
| `installment-paid-tx-unvalidated-cross-tenant-ref` | 🟡 | `paid_transaction_id` se persiste sin validar pertenencia | `accounts/service.py:645-663` | Validar con `get_transaction_by_id(…, user_id)` |
| `cors-wide-methods-headers-with-credentials` | 🟡 | CORS `*` métodos/headers + credentials, defensa solo en SameSite | `main.py:60-66`; `config.py:50` | `cors_origins` estricto, `auth_cookie_secure=True` por defecto, check Origin en refresh |
| `category-detail-foreign-id-no-404` | ⚪ | Drill-down acepta `category_id` ajeno y devuelve vacío en vez de 404 | `dashboard/router.py:148-174` | `get_category_by_id(…, user_id)` + 404 |

> **Aislamiento multi-tenant:** verificado correcto. Las queries filtran por
> `user_id` y los endpoints de detalle/update/delete validan pertenencia. El
> único caso es `category-detail` (above), que **no filtra por dueño de la
> categoría pero sí por `Transaction.user_id`**, así que no fuga datos —
> inconsistencia de defensa en profundidad, no IDOR.

### 4.2 Seguridad — Input / Inyección / Ficheros / IA

| ID | Sev | Título | Ubicación | Fix breve |
|----|-----|--------|-----------|-----------|
| `pillow-decompression-bomb-uncaught` | 🟠 | `DecompressionBombError` no es `OSError` → 500 + blob MinIO huérfano | `ai/client.py:38-54` | Capturar `Exception`/`DecompressionBombError`; mover `put_receipt` tras éxito |
| `xlsx-pdf-decompression-bomb` | 🟠 | Cap de 10 MB es *comprimido*; sin límite de celdas/páginas en parse | `imports/parser.py:122-327` | Cap filas×columnas / páginas; offload a threadpool con timeout |
| `fastapi-debug-flag-traceback-leak` | 🟡 | `debug=app_debug` + `echo` filtran traceback/SQL si se activa | `main.py:56`; `database.py:30` | Atar `app_debug` a `app_env=='development'` + handler 500 opaco |
| `verbose-thirdparty-error-leakage` | 🟡 | Texto crudo de openpyxl/pdfplumber/Ollama/MinIO en `detail` | `imports/parser.py`, `receipts/service.py:64`, `storage.py` | Mensajes genéricos al cliente, `logger.exception` server-side |
| `receipt-content-type-trusted` | 🟡 | `content_type` del cliente se confía para allow-list, MinIO y `/blob` | `receipts/service.py:31-53`; `storage.py:54-79` | Sniff de bytes (Pillow `.format`/magic); `X-Content-Type-Options: nosniff` |
| `ai-health-unauthenticated` | ⚪ | `/ai/health` sin auth revela modelo/estado | `ai/router.py:14-32` | Requerir auth o reducir el body |
| `weak-jwt-secret-default` | — | **DUPLICADO** de `weak-default-jwt-secret` | — | (fusionado en §4.1) |

🔎 *(completitud)* **`receipts/confirm` persiste `payload.currency.upper()` sin
validar ISO-4217** (`receipts/service.py:104-114`) — write-path; misma clase que
`unvalidated-target-currency` pero escribe moneda inválida en una `Transaction`
real.

### 4.3 Arquitectura

| ID | Sev | Título | Ubicación | Fix breve |
|----|-----|--------|-----------|-----------|
| `debt-feature-fragmented-across-modules` ✔︎ | 🟠 | "Deuda" partida en 2 módulos + 2 API + 2 hooks + 2 namespaces de keys | `debt/` vs `accounts/debt_health.py`+`debt_history.py` | Terminar la migración PHASE-30.x: mover a `debt/` |
| `auth-imports-domain-seed` ✔︎ | 🟠 | Infra (`auth`) importa el módulo de dominio `personal_finance.seed` (única inversión de dependencia del repo) | `auth/router.py:90-96` | Hook `on_user_created` cableado en `main.py` |
| `business-logic-in-routers` | 🟠 | ~140 líneas de lógica + `select()` crudo en routers | `imports/router.py:396-539`; `transactions/router.py:226-266` | Mover a service/repository |
| `duplicated-date-conversion-helpers` | 🟠 | `_today_utc`×5, `_convert_at_today`×3, etc. copiados | `debt_health.py`, `debt_history.py`, `debt/service.py`, `debt/repository.py` | Extraer a `core/dates.py` / `_shared/` |
| `services-imports-store` | 🟠 | `@crisol/services` importa `@crisol/store` (viola `services→types`) | `useTransactions.ts:12` | Sacar el toast al `onSuccess` de la app, o documentar la excepción |
| `dashboard-conversion-shared-hub` | 🟡 | `dashboard/conversion.py` es primitiva de todo el dominio, no read-only | importado por accounts/budgets/transactions/debt | Reubicar `converted_amount_expr` a `_shared/`/core |
| `module-structure-drift` | 🟡 | Estructura inconsistente; `accounts/` es un cajón de sastre | varios | Documentar excepciones; partir `accounts/` (installments/amortización) |

### 4.4 Corrección backend / integridad de datos

| ID | Sev | Título | Ubicación | Fix breve |
|----|-----|--------|-----------|-----------|
| `cross-rate-freshness-leg-independent-window` | 🟠 | Conversión cross (USD→GBP) puede componer 2 tasas de días distintos | `currency/service.py:123-152`; `conversion.py:93-99` | Exigir ambas patas EUR→X del mismo `rate_date` |
| `unvalidated-target-currency-silent-empty` | 🟡 | `target_currency` solo valida longitud → resultado todo-ceros silencioso | `debt/router.py:37-48` | Validar contra set ISO-4217; o exponer `unconvertible_count` |
| `convert-to-debt-no-rate-prefetch` | ⚪ | Deuda cross-currency depende de que el cron de tasas haya corrido | `transfers/service.py:596-610` | `ensure_rates_for_user_scope` o documentar best-effort |
| `list-pairs-orphan-partner-silent-drop` | 🟡 | Soft-delete de una pata deja la otra huérfana (en saldo, fuera de cashflow y de la UI) | `transfers/repository.py:79-121` | Anular `transfer_pair_id` del partner al borrar, o exponer huérfanos |
| `stale-source-kind-expense-default` | 🟡 | Código muerto `_source_kind` reintroduce el footgun EXPENSE que arregló PHASE-31.5 | `transfers/service.py:58-69` | Borrarlo |

> **Dinero:** sin `float` en rutas monetarias (verificado). `Decimal` +
> `quantize` consistente. La conversión per-tx histórica es correcta salvo el
> caso cross-pata (above).

### 4.5 Buenas prácticas frontend (TS/React/Next/Expo)

| ID | Sev | Título | Ubicación | Fix breve |
|----|-----|--------|-----------|-----------|
| `no-error-boundaries` | 🟠 | Sin error boundaries (web ni mobile) | `apps/web/app/**`, `apps/mobile/**` | `error.tsx`/`global-error.tsx` + boundary RN |
| `debt-summary-never-invalidated` | 🟠 | Ninguna mutación invalida `queryKeys.debt.all` → Capa 1 stale 60s | `keys.ts:47-62`; mutaciones tx/installment | `invalidateQueries({queryKey: debt.all})` en las mutaciones |
| `fixed-expenses-web-mobile-duplication` | 🟠 | Orquestación duplicada casi línea-a-línea web/mobile (498 vs 494 líneas) | `fixed-expenses/page.tsx` y `.tsx` | `useFixedExpenseActions()` compartido en services |
| `period-navigator-toggle-duplication` | 🟡 | El toggle del navegador de período diverge web/mobile | `period-navigator.tsx` (×2) | `DEBT_PERIOD_OPTIONS` compartido |
| `debt-liabilities-filter-inconsistency` | 🟡 | Filtro de liabilities memoizado en web, inline en mobile | `debt/page.tsx:68-74` vs `debt/index.tsx:79` | Unificar patrón |
| `mutation-variables-as-cast` | ⚪ | `mutation.variables as string` fuera de boundary | varias páginas | Helper `pendingId(mutation)` sin cast |
| `uncategorized-banner-dead-shortcut` | 🟡 | CTA "ver sin categorizar" hace `scrollTo(400)`, no filtra | `transactions/page.tsx:284-296` | Ocultar CTA hasta que el backend soporte `category_id=none` |

🔎 *(completitud)* **`packages/services/src/api/client.ts`** — singletons mutables
a nivel de módulo (`_accessToken`, `_isRefreshing`, `_refreshQueue`), cola de
refresh hecha a mano, **sin tests** del camino 401-concurrente. Es **el fichero
detrás de varios bugs documentados** (lessons.md: FormData boundary, content-type).
Prioritario para tests + revisión de la cola.

### 4.6 UX / Usabilidad / Accesibilidad

| ID | Sev | Título | Ubicación | Fix breve |
|----|-----|--------|-----------|-----------|
| `errors-masked-as-empty` ✔︎ | 🟠 | Páginas sin rama `isError` muestran empty-state al fallar | transfers/budgets/fixed-expenses | Rama `isError` + ErrorState |
| `no-retry-on-error` ✔︎ | 🟠 | Estados de error sin botón "Reintentar" | 10 páginas web | `ErrorState` con `refetch()` |
| `modal-no-focus-trap` ✔︎ | 🟠 | `ConfirmDialog` y drawer móvil sin focus-trap ni restauración de foco; links off-screen tabbables | `confirm-dialog.tsx`; `layout.tsx` | Trap de Tab + restaurar foco + `inert` en drawer cerrado |
| `no-skeletons-anywhere` | 🟠 | Todo loading es `<p>Cargando…</p>`; sin skeletons (peor con IA 60-120s) | ~13 páginas | Primitiva `Skeleton` |
| `search-input-no-label` | 🟠 | Buscador sin nombre accesible (solo placeholder) | `stitch-search-toolbar.tsx:156-171` | `aria-label="Buscar transacciones"` |
| `form-validation-not-inline` | 🟠 | Validación del form de transacción es un string global, sin `aria-invalid`/`describedby` | `transaction-form.tsx` | Errores por campo (la primitiva `Field` ya lo soporta) |
| `contrast-textsubtle-fails-aa` | 🟠 | `textSubtle #8a8a8a` ~3.5:1 (< AA 4.5:1) en texto pequeño | `tokens.ts:46` | Oscurecer a ~`#767676` |
| `no-skip-link-no-nav-landmark` | 🟡 | Sin "saltar al contenido"; tabs de sección sin `<nav>` | `layout.tsx`; `module-sections.tsx` | Skip-link + landmark |
| `disabled-modules-not-focusable` | 🟡 | Módulos bloqueados son `<div aria-disabled>` y el chip "Pronto" es `aria-hidden` | `app-sidebar.tsx:317-369` | Texto accesible "próximamente" |
| `fixed-grids-not-responsive` | 🟡 | Grids 2-col fijos en deuda/análisis no colapsan en viewport estrecho | `debt/page.tsx:133`; `analysis/page.tsx:136,153` | `repeat(auto-fit, minmax(...))` |
| `datatable-clickable-row-aria` | 🟡 | Filas `role=button` sin nombre + botones anidados (anti-patrón) | `data-table.tsx:147-160` | `aria-label` de fila o celda-enlace |
| `mobile-error-copy-and-rows-a11y` | 🟡 | Error móvil sin retry; filas sin `accessibilityRole`/hint de long-press | `transactions.tsx:200-201,105-114` | RefreshControl en error + labels |
| `hardcoded-copy-i18n` | ⚪ | Copy hardcoded ES + pluralización manual duplicada | pervasivo | Centralizar pluralización; i18n si entra en scope |

🔎 *(completitud)* **Flujos sin evaluar para a11y/UX:** onboarding
(`/onboarding/accounts`, bloqueante de primer uso), wizard de imports
(`/imports/new`, drag&drop + mapeo de columnas), captura de receipts (permisos
de cámara móvil, errores de subida web), `settings/categories/rules`.

### 4.7 Rendimiento

| ID | Sev | Título | Ubicación | Fix breve |
|----|-----|--------|-----------|-----------|
| `missing-occurred-at-index` ✔︎ | 🟠 | Sin índice en `occurred_at` (todas las agregaciones + sort) | `transactions/models.py:97-121` | Índice parcial compuesto (ver P1) |
| `debt-history-per-month-n-plus-1` ✔︎ | 🟠 | 3 queries SQL por mes (~36 round-trips/request) | `debt_history.py:144-204` | Queries agrupadas por `date_trunc('month')` + prefix-sum |
| `debt-page-redundant-recompute` | 🟠 | 4 endpoints recalculan balances/cuentas (get_balances ×2, account-list ×3-4) | `debt/page.tsx`; debt_health/history/service | Endpoint `/debt/overview` agregado, o memoizar por request |
| `per-item-currency-convert-loops` | 🟠 | `convert()` por item en cross-currency (1-2 queries × N) | `debt_health.py:494,560`; `debt/service.py:310,360` | Resolver tasas "hoy" una vez por divisa, convertir en memoria |
| `ensure-rates-repeated-per-endpoint` | 🟠 | `ensure_rates_for_user_scope` re-escanea fechas en cada endpoint dashboard | `dashboard/service.py:47-83` | Bulk-check de fechas faltantes; una vez por request |
| `imports-reconcile-per-row` | 🟠 | `reconcile_with_expected` por fila deduplicada | `imports/service.py:451-470` | Pre-cargar `expected` del account una vez |
| `recharts-no-code-splitting` | 🟠 | Recharts en import estático en 7 componentes de ruta | charts web | `next/dynamic(..., {ssr:false})` |
| `account-by-name-python-scan` | 🟡 | Carga todas las cuentas y compara en Python | `accounts/repository.py:41-51` | `WHERE func.lower(name)=…` |
| `transaction-list-no-memo-columns` | 🟡 | Rebuild de columns + `find()` lineal por fila cada render | `transaction-list.tsx` | `Map<id,Category>` + `useMemo` |

🔎 *(completitud)* **I/O síncrono bloqueando el event loop** — ver P1; es la
mayor brecha de disponibilidad y no estaba en los 9 hallazgos de perf.

### 4.8 Testing / Quality gates

| ID | Sev | Título | Ubicación | Fix breve |
|----|-----|--------|-----------|-----------|
| `ci-gates-red-on-head` ✔︎ | 🔴 | CI gate hard-fail pero HEAD rojo en ruff/black/mypy | `ci.yml:92-99` | Poner HEAD verde + branch protection (ver P0) |
| `packages-types-store-no-gate` ✔︎ | 🟠 | `types` y `store` sin scripts lint/typecheck/test → fuera de turbo | `package.json` (×2) | Añadir scripts + tests de la auth-store |
| `no-migration-model-parity-test` ✔︎ | 🟠 | Tests usan `create_all`, no Alembic → drift modelo/migración invisible | `conftest.py:100-101` | `alembic check` en CI o construir schema vía migraciones |
| `frontend-coverage-minimal` | 🟠 | 111 ficheros web / 9 tests; los 13 hooks de query sin test | `apps/web`, `packages/services` | Tests de hooks (invalidación) + endpoint-clients |
| `imports-parser-b023-closure` | 🟡 | Closure sobre variable de loop (`cleaned`) — latente, refactor-frágil | `imports/parser.py:229-247` | Pasar `cleaned` como parámetro/default |

🔎 *(completitud)* Sin tests de **aislamiento multi-tenant** para los módulos
nuevos (debt, transfers, accounts) pese a que las reglas lo exigen; sin tests de
**concurrencia** (refresh race, challenge WebAuthn, dedup de import en paralelo).

---

## 5. Puntos ciegos del crítico de completitud (verificar antes de actuar)

El crítico de completitud (que también leyó código y citó `file:line`) marcó que
la auditoría, sólida en lo que cubrió, **no tocó**:

1. **WebAuthn/passkeys** — race en consumo de challenge + sin cleanup (→ P1).
2. **I/O síncrono en el event loop** — clase de disponibilidad completa (→ P1).
3. **Pipeline imports/receipts como trabajo largo in-request** + blob MinIO
   escrito **antes** del row DB/commit → objeto huérfano si falla la DB
   (`receipts/service.py:41-75`). Sin cola/background para inferencias de hasta
   600s.
4. **Sin security headers ni handler 500 global** en `main.py` (→ P1).
5. **`api/client.ts`** — estado mutable global + cola de refresh sin tests (→ §4.5).
6. **Normalización de email** inconsistente (register no normaliza; webauthn sí
   hace `email.lower()`) + receipts persiste moneda sin validar.
7. **Crecimiento sin límite** de `refresh_tokens` (expirados), `webauthn_challenges`
   y transacciones soft-deleted (sin purga).
8. **Frankfurter** — única llamada saliente externa (tasas); evaluar manejo de
   fallo/validación y el límite de privacidad (las fechas/códigos son públicos,
   pero el principio "los datos nunca salen" merece una nota explícita).
9. Flujos UX sin evaluar (onboarding, imports wizard, receipts capture) (→ §4.6).
10. Tests de aislamiento/concurrencia/migración para módulos nuevos (→ §4.8).

---

## 6. Duplicados fusionados

- `weak-jwt-secret-default` ≡ `weak-default-jwt-secret` → **uno** (§4.1).
- `unvalidated-target-currency-silent-empty` + moneda en `receipts/confirm` →
  un solo "validar códigos de moneda en todas las fronteras".
- `no-retry-on-error` + `errors-masked-as-empty` + `no-error-boundaries` →
  un **clúster de manejo de errores** (fix compartido).
- `debt-feature-fragmented` + `duplicated-date-conversion-helpers` +
  `debt-summary-never-invalidated` + `services-imports-store` → **epic de
  consolidación del módulo deuda**.
- CORS + (futuro) security-headers → clúster "hardening HTTP en `main.py`".

---

## 7. Roadmap de remediación sugerido

**Sprint 1 — desbloquear el gate y cerrar auth (P0/P1, esfuerzo bajo-medio):**
1. Poner HEAD verde (ruff/black/mypy) + branch protection. *(`ci-gates-red-on-head`)*
2. Validador fail-closed del secreto JWT (+ minio). *(`weak-default-jwt-secret`)*
3. Índice parcial sobre `(user_id, occurred_at)`. *(`missing-occurred-at-index`)*
4. Rama `isError` + `ErrorState` con retry + error boundaries. *(clúster errores)*
5. `aria-label` del buscador + contraste `textSubtle`. *(quick a11y wins)*

**Sprint 2 — disponibilidad y DoS (P1, esfuerzo medio):**
6. `run_in_threadpool` para pdfplumber/openpyxl/Pillow/MinIO. *(I/O bloqueante)*
7. Rate limiting en auth + refresh auto-identificable + purga de expirados.
8. Atar el challenge WebAuthn a su `id` + programar `delete_expired_challenges`.
9. Caps de decompression-bomb (XLSX/PDF/Pillow) + capturar `DecompressionBombError`.

**Sprint 3 — consolidación y perf (P2, esfuerzo medio-alto):**
10. Epic deuda: mover `debt_health`/`debt_history` a `debt/`, unificar
    keys/hooks, invalidar `debt.all`, extraer helpers de fecha. *(toca también
    la Fase B del navegador de período en curso)*
11. debt-history queries agrupadas + `/debt/overview` agregado + tasas batcheadas.
12. Sacar lógica de routers a service/repository; `services→store` fuera.
13. Code-split de recharts.

**Continuo — testing/calidad:**
14. Scripts de gate en `types`/`store`; `alembic check` en CI; tests de hooks,
    aislamiento y concurrencia; security headers + handler 500.

---

## 8. Notas de método y limitaciones

- Severidades **ajustadas al contexto** (local-first/monousuario/self-hosted, sin
  prod). Antes de un despliegue multiusuario en internet, varias "high" vuelven a
  "critical" (secreto JWT, rate limiting, refresh scan).
- Los hallazgos 🔎 (completitud) citan `file:line` pero **no pasaron por la
  verificación adversarial**: confirmar a nivel de código antes de invertir.
- No se ejecutó análisis dinámico (DAST/fuzzing) ni revisión de dependencias
  (SCA) — recomendable como siguiente capa.
- Aislamiento multi-tenant, uso de `Decimal`, bind-params SQL y rotación de
  refresh: **verificados y correctos** — la base es buena; esto es endurecimiento.
