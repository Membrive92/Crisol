# API endpoints

> Catálogo del backend. Se actualiza cada vez que una fase añade o
> modifica endpoints. Última actualización: PHASE-44.9 (módulo `investment`
> documentado por primera vez — 28 endpoints; cubre también la deuda documental
> de 44.7 y 44.8).

Convenciones generales:

- Todos los endpoints (excepto `/health`, `/ai/health`, `/auth/register`,
  `/auth/login`, `/auth/refresh`) requieren `Authorization: Bearer <access_token>`.
- Todas las queries de dominio filtran por `user_id` extraído del JWT.
- Importes en `Decimal` serializados como string (`"25.50"`) para
  preservar precisión.
- Fechas en ISO 8601 con timezone (`2026-04-15T12:00:00Z`).
- Status `204` se devuelve con body vacío (delete/logout).

---

## System

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/health` | no | Liveness — devuelve `{ status, env }` sin tocar BD. |
| GET | `/ai/health` | no | Estado de Ollama y modelo de visión configurado. |

---

## Auth (`PHASE-1.1`)

| Método | Ruta | Auth | Body | Response |
|--------|------|------|------|----------|
| POST | `/auth/register` | no | `{ email, password, display_name }` | `201` `{ access_token, refresh_token, token_type }` |
| POST | `/auth/login` | no | `{ email, password, remember_me? }` | `200` `TokenResponse` |
| POST | `/auth/refresh` | no | `{ refresh_token? }` (cookie en web) | `200` `TokenResponse` (rota el refresh) |
| POST | `/auth/logout` | sí | `{ refresh_token? }` (cookie en web) | `204` |
| GET  | `/auth/me` | sí | — | `200` `UserResponse` |

Reglas:
- Access token: 15 min. Refresh token: 7 días por defecto, **30 días si
  `remember_me=true`** en el login. Web también recibe el refresh en
  cookie `httpOnly` con el mismo TTL.
- Refresh hace **rotación** — el viejo se revoca, devuelve uno nuevo. La
  rotación preserva el "remember_me-ness": un refresh con TTL extendido
  rota a otro refresh con TTL extendido.
- Password hashing: argon2id.

## WebAuthn / Passkeys

| Método | Ruta | Auth | Body | Response |
|--------|------|------|------|----------|
| POST   | `/auth/webauthn/register-options` | sí | — | `200` `{ options }` (PublicKeyCredentialCreationOptionsJSON) |
| POST   | `/auth/webauthn/register-verify` | sí | `{ credential, label? }` | `201` `PasskeyResponse` |
| POST   | `/auth/webauthn/authenticate-options` | no | `{ email? }` | `200` `{ options }` |
| POST   | `/auth/webauthn/authenticate-verify` | no | `{ email?, credential }` | `200` `TokenResponse` (+ cookie) |
| GET    | `/auth/webauthn` | sí | — | `200` `PasskeyResponse[]` |
| PATCH  | `/auth/webauthn/{id}` | sí | `{ label }` | `200` `PasskeyResponse` |
| DELETE | `/auth/webauthn/{id}` | sí | — | `204` |

Reglas:
- El backend solo guarda **clave pública** + `credential_id` + `sign_count`.
  La privada vive en la secure enclave del dispositivo (Touch ID / Windows
  Hello / llave física).
- Los `challenges` viven 5 minutos y se borran al verificar (un solo uso).
- `authenticate-verify` emite los mismos JWT que el login normal y setea
  la cookie `httpOnly`.
- **Dos modos de autenticación**:
  - **Email-driven** (botón "Entrar con passkey"): cliente manda `email`,
    backend filtra credenciales del usuario en `allowCredentials`.
  - **Conditional UI** (autocompletado del input): cliente omite `email`,
    backend devuelve options sin `allowCredentials`. Al verificar, el
    `credential_id` identifica al usuario; el challenge se persistió con
    `user_id=NULL` y el de auth admite ambos casos.
- Aislamiento por usuario: si llega `email`, el `credential_id` debe
  pertenecer a ese usuario. Si no llega, el usuario sale del propio
  `credential_id`.

---

## Categories (`PHASE-2.1`)

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| GET | `/categories` | sí | — | `200` `CategoryResponse[]` |
| GET | `/categories/{id}` | sí | — | `200` `CategoryResponse` |
| POST | `/categories` | sí | `{ name, kind, icon?, color? }` | `201` `CategoryResponse` |
| PUT | `/categories/{id}` | sí | `Partial<CategoryCreate>` | `200` `CategoryResponse` |
| DELETE | `/categories/{id}` | sí | — | `204` |

`kind`: `income | expense`. Borrado de categoría: las transacciones
asociadas conservan `category_id = NULL` (`ON DELETE SET NULL`).

---

## Transactions (`PHASE-2.1` + `PHASE-8.4` + `PHASE-10.1` + `PHASE-21.2` + `PHASE-21.3` + `PHASE-34` + `PHASE-37.3`)

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| GET | `/transactions` | sí | `account_id?` (PHASE-21.3), `category_id?`, `uncategorized?` (bool, PHASE-31.3 — filtra las sin categoría; ignora `category_id` si llegan ambos), `date_from?`, `date_to?`, `search?`, `target_currency?` (3 letras, PHASE-8.4), `limit` (1..200, def 50), `offset` (def 0) | `200` `{ items, total, limit, offset }` (sólo activas) |
| GET | `/transactions/trash` | sí | `limit` (1..200, def 50), `offset` (def 0) | `200` `{ items, total, limit, offset }` — soft-deleted, `deleted_at DESC` (PHASE-10.1) |
| GET | `/transactions/{id}` | sí | — | `200` `TransactionResponse` (404 si trasheada) |
| POST | `/transactions` | sí | `{ account_id, amount, occurred_at, category_id?, currency?, description?, source?, flow?, is_exceptional? }` (PHASE-21.2: `account_id` obligatorio; PHASE-34: `flow` = `IN\|OUT\|TRANSFER_IN\|TRANSFER_OUT`, si se omite se deriva de la categoría; PHASE-37.3: `is_exceptional` tri-estado `null`/`true`/`false`) | `201` `TransactionResponse` (puede traer `budget_alert`, PHASE-14.5) |
| PUT | `/transactions/{id}` | sí | `Partial<TransactionCreate>` (acepta cambiar `account_id` a otra cuenta del mismo usuario) | `200` `TransactionResponse` |
| DELETE | `/transactions/{id}` | sí | — | `204` (soft-delete, PHASE-10.1: mueve a papelera) |
| POST | `/transactions/{id}/restore` | sí | — | `200` `TransactionResponse` (404 si no está en papelera) — PHASE-10.1 |
| DELETE | `/transactions/{id}/purge` | sí | — | `204` (DELETE real; 404 si no está en papelera — forzar soft-delete previo) — PHASE-10.1 |
| POST | `/transactions/reassign-account` | sí | `{ target_account_id, account_id?, category_id?, date_from?, date_to?, search? }` (PHASE-32; filtros = los de `GET /transactions`) | `200 { reassigned_count, skipped_other_currency }` — mueve en bloque las tx **activas** que matchean a `target_account_id`. Excluye transferencias internas, las ya en destino y (HIGH#3) las de **otra divisa** que la cuenta destino (moverlas las sacaría del saldo); estas se cuentan en `skipped_other_currency`. 404 si la cuenta destino no es del usuario |
| POST | `/transactions/trash/restore` | sí | — | `200 { restored_count }` — restaura TODAS las tx en papelera del usuario (idempotente) — PHASE-10.2 |
| DELETE | `/transactions/trash` | sí | — | `200 { purged_count }` — DELETE real de TODAS las tx en papelera (IRREVERSIBLE, idempotente) — PHASE-10.2 |
| GET | `/transactions/available-periods` | sí | — | `200 { periods: [{ year, months[] }] }` — años + meses con tx activas, para el selector temporal (PHASE-27) |
| GET | `/transactions/uncategorized-summary` | sí | — | `200 { count, total_amount, currency }` — conteo + suma de tx activas sin categoría (banner UX, PHASE-31.3) |
| DELETE | `/transactions` | sí | `account_id?`, `category_id?`, `date_from?`, `date_to?`, `search?` (filtros = `GET /transactions`) | `200 { deleted_count }` — mueve a papelera en bloque las tx activas que matchean; sin filtros, todas. Idempotente |
| POST | `/transactions/bulk-categorize` | sí | `{ transaction_ids[], category_id }` | `200 { updated }` — relabel puro de categoría de las tx seleccionadas; NO toca el dinero (`flow`/par). `400` si `category_id` ajeno (PHASE-34) |

`source`: `manual | import | receipt | expected` (default `manual`).
Importes positivos.

`flow` (PHASE-34) — fuente de verdad de la dirección del dinero
(`IN | OUT | TRANSFER_IN | TRANSFER_OUT`). Siempre presente en
respuestas. El saldo y el cashflow derivan de `flow` + `account.nature`,
no de la categoría (ADR-0004). El signo YA NO se infiere de
`category.kind` en frontend.

`is_exceptional` (PHASE-37.3) — override tri-estado de la clasificación
estructural/puntual del gasto (`null` = heurística, `true` = puntual,
`false` = estructural). Presente en respuestas; lo consume
`/analytics/expense-structure`.

`is_debt_pair` (PHASE-35) — `true` cuando la tx es una pata de un par
de conversión a deuda (activo↔pasivo); sólo lo computa el endpoint de
LISTADO, el resto devuelve `false`.

`account_id` (PHASE-21.2) — obligatorio en `POST` y siempre
presente en respuestas. Validado contra ownership: un `account_id`
ajeno devuelve `404` (no `403`, para no filtrar existencia).

`transfer_pair_id` (PHASE-21.3) — siempre presente en respuestas
(`null` o `UUID`). Cuando no es `null`, esta tx forma parte de una
transferencia interna y se EXCLUYE de cashflow / donut /
top-expenses / budgets, pero SÍ cuenta al saldo de su cuenta. Se
gestiona vía `/transfers/*` — no se asigna directamente desde
estos endpoints.

`target_currency` (PHASE-8.4) — cuando se pasa, cada item de la
respuesta gana `converted_amount: Decimal | null` y
`converted_currency: string | null` con la conversión a la moneda
destino usando la tasa **del día de su `occurred_at`** (misma
política y ventana de fallback de 14 días que el dashboard). El
endpoint dispara `ensure_rates_for_dates` por cada fecha distinta de
transacciones del scope antes de listar — backfill on-demand desde
frankfurter, idéntico al dashboard. `null` cuando no hay tasa
disponible (la UI puede pintar "≈ —"). En lecturas individuales
(`GET /transactions/{id}`) y modo legacy ambos campos son `null`.

---

## Dashboard (`PHASE-3.1` + `PHASE-8.3`)

Todos GET, read-only, agregaciones SUM/COUNT/GROUP BY filtradas por
`user_id`. Modo de moneda: dos parámetros mutuamente excluyentes —
gana `target_currency` si llegan ambos. Sin ninguno, default a
`currency=USD` (legacy).

- `?currency=EUR` (legacy) — filtra por esa moneda y agrega importes
  crudos.
- `?target_currency=EUR` (`PHASE-8.3`) — no filtra. Convierte cada
  transacción al destino con la tasa **del día de su `occurred_at`**
  (subquery correlacionada en `exchange_rates` con ventana de
  fallback de 14 días) y agrega después. Las transacciones sin tasa
  disponible se excluyen del SUM y se cuentan en
  `summary.unconvertible_count`.

| Método | Ruta | Query | Response |
|--------|------|-------|----------|
| GET | `/dashboard/currencies` | — | `string[]` con las monedas distintas presentes en las transacciones del usuario (ordenadas alfabéticamente). |
| GET | `/dashboard/summary` | `currency` (def `USD` legacy), `target_currency?` (cross-currency), `date_from?`, `date_to?` | `{ income, expenses, balance, transaction_count, currency, unconvertible_count, previous_period_income, previous_period_expenses, previous_period_balance }` |
| GET | `/dashboard/by-category` | `currency` o `target_currency`, `date_from?`, `date_to?`, `kind?` (`income\|expense`) | `[{ category_id, category_name, category_kind, total, count }]` |
| GET | `/dashboard/by-month` | `year` (def actual), `currency` o `target_currency`, `date_from?`/`date_to?` (PHASE-42) | `[{ month: "YYYY-MM", income, expenses, balance }]` — 12 buckets del año, o (con `date_from`+`date_to`) **un bucket por mes tocado por el rango**, con los meses de borde PARCIALES para cuadrar con los KPIs de flujo del mismo rango |
| GET | `/dashboard/top-expenses` | `currency` o `target_currency`, `date_from?`, `date_to?`, `limit` (1..50, def 10) | `[{ transaction_id, description, amount, occurred_at, category_id, category_name, original_amount, original_currency }]` (PHASE-8.4: `original_*` siempre presentes; `amount` es el convertido en cross-currency, original en legacy) |
| GET | `/dashboard/category/{category_id}` | `currency` o `target_currency`, `date_from?`, `date_to?`, `months_back` (1..36, def 12) | `200 CategoryDetailResponse` — drill-down de una categoría: KPIs del rango + evolución mensual + top 10 tx (PHASE-25) |
| GET | `/dashboard/category/{category_id}/available-periods` | — | `200 CategoryAvailablePeriodsResponse` — años + meses con tx activas de la categoría, para el selector temporal del drill-down (PHASE-27) |

Reglas relevantes:
- `summary.transaction_count` cuenta todas las transacciones del rango,
  incluso sin categoría.
- `summary.income` / `expenses` sólo cuentan transacciones con
  categoría (el signo lo decide `category.kind`).
- `summary.unconvertible_count` (PHASE-8.3) es siempre 0 en modo
  legacy; en modo cross-currency cuenta las transacciones sin tasa
  histórica disponible (ni exacta ni en ventana de 14 días).
- `summary.previous_period_*` se computa cuando llegan `date_from` y
  `date_to` (PHASE-42, `_previous_period`): si el rango es un **mes
  natural** completo → el mes natural anterior; si es un **año** completo
  → el año anterior; en otro caso (rango libre) → una **ventana de igual
  longitud** inmediatamente anterior. Si no llega rango, los tres campos
  son `null` y el frontend no pinta delta.
- `currencies` permite al frontend hidratar el selector de moneda con
  valores reales del usuario en lugar de hardcodear `USD`/`EUR`.
- `by-category` incluye un bucket `{ category_id: null, category_name:
  "Sin categoría" }` que se excluye cuando se filtra por `kind`.
- `top-expenses` solo devuelve transacciones cuya categoría es
  `expense` (las sin categoría se excluyen).
- En modo cross-currency, antes de agregar el endpoint dispara un
  lazy fetch a `frankfurter.dev/v1/{date}` para cada fecha distinta
  de transacciones del scope que aún no tenga tasa en BD. Tras el
  primer hit las tasas quedan persistidas y los siguientes requests
  no triggerean fetch.

---

## Analytics (`PHASE-37.3` + `PHASE-37.4`)

Read-only. Mismo modo de moneda que el dashboard: `currency` (legacy,
filtra + agrega crudo) o `target_currency` (convierte por fecha y
agrega). Sin ninguno, default legacy `USD`.

| Método | Ruta | Auth | Query | Response |
|--------|------|------|-------|----------|
| GET | `/analytics/expense-structure` | sí | `currency` o `target_currency`, `date_from?`, `date_to?` | `200 ExpenseStructureResponse { reference_currency, income_total, structural_total, exceptional_total, structural_monthly_avg, savings_rate_gross, savings_rate_structural, top_exceptional[], exceptional_by_category[] }` |
| GET | `/analytics/month-outlook` | sí | `currency` o `target_currency` | `200 MonthOutlookResponse { reference_currency, committed_remaining, committed_items[], days_remaining, liquid_balance, runway_months }` |

Reglas:
- `expense-structure` (PHASE-37.3) separa el gasto en estructural vs
  puntual usando `Transaction.is_exceptional` (override tri-estado) +
  heurística de recurrencia. `structural_monthly_avg` es la media
  mensual del gasto estructural en la ventana (base estable del runway).
  `savings_rate_gross`/`savings_rate_structural` = tasa de ahorro bruta
  y estructural (`null` si no hay ingresos).
- `month-outlook` (PHASE-37.4) proyecta el fin de mes:
  `committed_remaining` = gastos fijos confirmados + cuotas de deuda que
  aún se cargarán en lo que queda de mes (más los atrasados sin pagar).
  `runway_months` = `liquid_balance / structural_monthly_avg`;
  `liquid_balance` = Σ saldo de cuentas líquidas (bank/savings/cash) no
  archivadas. `runway_months` = `null` si no hay base estructural.

---

## Budgets (`PHASE-12.1`)

Presupuestos mensuales por categoría (o globales). El status compara
spent del mes actual UTC contra el límite y devuelve `ok | warning |
over` (umbrales 80% / 100%).

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| GET    | `/budgets` | sí | — | `200 BudgetResponse[]` (sólo activos: `effective_to IS NULL OR >= today`) |
| GET    | `/budgets/status` | sí | — | `200 { items: BudgetStatusItem[], month_start, month_end }` |
| GET    | `/budgets/{id}` | sí | — | `200 BudgetResponse` |
| POST   | `/budgets` | sí | `{ category_id?, amount, currency, effective_from, convert_other_currencies? }` | `201 BudgetResponse`. `409` si ya hay activo para esa categoría (o global). PHASE-16: `convert_other_currencies` default `false` |
| PUT    | `/budgets/{id}` | sí | `{ amount?, currency?, convert_other_currencies? }` | `200 BudgetResponse`. `effective_from` y `category_id` son inmutables. PHASE-16: el flag se puede toggle |
| DELETE | `/budgets/{id}` | sí | — | `204`. Cierra (`effective_to=today`); si ya estaba cerrado en pasado, DELETE real |

`BudgetStatusItem`: `{ budget, spent_this_month, remaining,
percent_used, status: 'ok'|'warning'|'over', unconvertible_count }`.
`spent_this_month` es la suma de `Transaction.amount` activas en el
mes calendario UTC actual con `kind='expense'`. Si
`budget.convert_other_currencies = false` (default) sólo suma txs
de la misma `currency` y `unconvertible_count` es siempre `0`. Si
`= true` (PHASE-16), suma todas las txs de gasto convertidas a
`budget.currency` con la tasa del día de cada tx; las que no tienen
tasa disponible quedan fuera del SUM y se cuentan en
`unconvertible_count`. Para budgets globales (`category_id IS NULL`)
suma todas las categorías de gasto. Excluye soft-deleted (PHASE-10.1).

---

## Fixed expenses (`PHASE-13.1`, renombrado en `PHASE-17.1`)

Antes "subscriptions". Gastos fijos recurrentes (suscripciones,
hipotecas, préstamos, gym, seguros…) detectados automáticamente
a partir de patrones de transacciones (mismo merchant + amount +
currency con cadencia regular en últimos 6 meses). Sin IA por
ahora — heurística basada en agrupación + análisis de gaps.

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| GET    | `/fixed-expenses` | sí | `status?` (`pending\|confirmed\|paused\|cancelled\|dismissed`) | `200 FixedExpenseResponse[]` ordenado `next_due ASC` |
| POST   | `/fixed-expenses/scan` | sí | — | `200 { created, updated, total_active_after }`. Re-ejecuta el detector ahora; el cron diario (04:00 UTC) hace lo mismo automáticamente. |
| GET    | `/fixed-expenses/{id}` | sí | — | `200 FixedExpenseResponse` |
| PUT    | `/fixed-expenses/{id}` | sí | `{ auto_post? }` | `200 FixedExpenseResponse`. PHASE-17.2 — toggle del flag opt-in de autoposteo. |
| POST   | `/fixed-expenses/autopost` | sí | — | `200 { created, advanced }`. PHASE-17.2 — fuerza el cron de autoposteo manualmente; el cron diario lo ejecuta automáticamente 30min después del scan. |
| POST   | `/fixed-expenses/{id}/confirm` | sí | — | `200 FixedExpenseResponse`. Marca como `confirmed`. Uno `dismissed` confirmado se reactiva. |
| POST   | `/fixed-expenses/{id}/dismiss` | sí | — | `200 FixedExpenseResponse`. El detector NO lo vuelve a sugerir aunque siga el patrón. |
| POST   | `/fixed-expenses/{id}/pause` | sí | — | `200 FixedExpenseResponse`. `confirmed` → `paused`. 409 desde otros estados (PHASE-15.2). |
| POST   | `/fixed-expenses/{id}/resume` | sí | — | `200 FixedExpenseResponse`. `paused` → `confirmed`. 409 si no está paused (PHASE-15.2). |
| POST   | `/fixed-expenses/{id}/cancel` | sí | — | `200 FixedExpenseResponse`. Aceptable desde pending/confirmed/paused. 409 desde dismissed (PHASE-15.2). |
| DELETE | `/fixed-expenses/{id}` | sí | — | `204`. Si el patrón persiste, el siguiente scan lo vuelve a crear como `pending`. |

`FixedExpenseResponse`: `{ id, user_id, merchant (normalizado),
raw_description (sample legible), amount, currency, cadence_days
(7/14/30/90/180/365), next_due, status, category_id, first_seen_at,
last_seen_at, occurrence_count, confidence (0..1), created_at,
updated_at }`.

Cadencias detectadas: semanal (7±1), quincenal (14±1), mensual
(30±5), trimestral (90±5), semestral (180±10), anual (365±10).
Mínimo 3 ocurrencias en 180 días, desviación relativa de gaps
≤ 30%. Lookback fijo en 180 días (no expuesto como param).

---

## Imports (`PHASE-4.1`, `PHASE-4.3`, `PHASE-17.3`, `PHASE-20`, `PHASE-21.2`)

PHASE-17.3 — el pipeline reconcilia con tx `source=expected`
existentes antes de crear duplicadas. Si una fila del CSV tiene
mismo `amount + currency`, `occurred_at` ±3 días y prefijo común
de `description ≥ 6 chars`, se asigna el `import_hash` a la
`expected` (que pasa a estar conciliada con el banco) en lugar de
crear una nueva. Las reconciliadas se cuentan en `rows_ok`. Desde
PHASE-21.2 la reconciliación restringe el match a la misma cuenta.

PHASE-20 añade el flujo en dos pasos `preview` → `commit` con
sugerencias por concepto del banco (saved_mapping → rule → AI
fallback) y endpoint dedicado `/imports/{id}/ai-suggest`.

PHASE-39 añade la captura de la columna **Saldo** del extracto
(`statement_balance`, rol propio del smart-parser + campo opcional del
mapping) y el **auto-anclaje del saldo**: al confirmar, el
`opening_balance` de la cuenta (solo ASSET) se ancla al saldo del
movimiento más reciente del fichero — misma semántica que "Cuadrar
saldo", a la fecha del extracto. Un extracto más viejo que el ancla
vigente NO la pisa (re-deriva el opening para preservar
`saldo(fecha_ancla)`). El resultado viaja en
`ImportJobResponse.balance_anchor { balance, date }` (null si no se
ancló). El saldo NO entra en el hash de dedup: reimportar ficheros ya
importados backfillea `transactions.statement_balance` sin duplicar.

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| POST | `/imports` | sí | multipart: `file`, `account_id` (PHASE-21.2), `column_mappings` (JSON), `currency` (def `EUR`), `default_category_id?` | `201` `ImportJobResponse` (job ya finalizado) |
| POST | `/imports/preview` | sí | multipart: `file`, `account_id`, `column_mappings`, `currency`, `default_category_id?`, `force_vision?` (PHASE-20) | `200` `ImportPreviewResponse { job_id, source, total_rows, rows, bank_concept_groups, error_sample, warnings }`. PHASE-47.A: `warnings[]` avisa de que el fichero puede no ser de la cuenta elegida — `header_matches_other_account` (el formato es el de otra cuenta y nunca ha entrado en ésta) y `rows_exist_in_other_account` (>20 % de las filas ya existen allí) |
| POST | `/imports/{id}/commit` | sí | `{ category_overrides?: { bank_concept: category_id }, acknowledged_warnings?: ImportWarningKey[] }` | `200` `ImportJobResponse` (los overrides se persisten como `bank_category_mappings`). **`409`** si el preview emitió avisos y falta reconocer alguno; el `detail` trae `{ message, warnings[] }` con los pendientes (PHASE-47.A) |
| POST | `/imports/{id}/ai-suggest` | sí | — | `200 AiSuggestionResponse` (PHASE-20) |
| GET  | `/imports` | sí | `limit` (1..200, def 50), `offset` (def 0) | `200` `{ items, total, limit, offset }` |
| GET  | `/imports/{id}` | sí | — | `200` `ImportJobResponse` |

Reglas:
- Formatos: CSV (auto-detect delimitador), XLSX y PDF (extracción de
  tablas vía `pdfplumber`; PDFs sin tablas → job `failed`). Tamaño
  máx 10 MB.
- `column_mappings`: `{ amount, occurred_at, description?, category_name?, statement_balance? }` —
  obligatorios sólo `amount` y `occurred_at` (PHASE-39 añade `statement_balance`).
- Pipeline **síncrono**: parse → map → validate → SHA-256 dedup
  intra/inter-batch → persist `source=import`.
- Hash de dedup: SHA-256 de
  `user_id|amount(2dp)|currency|occurred_at_iso|description.casefold().strip()`.
- `error_log` capado a 100 entradas; `rows_failed` cuenta todas las
  filas inválidas.
- Estado del job: `pending | processing | preview | completed | failed`
  (PHASE-20 añade `preview`).
- `account_id` se persiste en `import_jobs.account_id` y se
  propaga a cada `Transaction` creada (PHASE-21.2).
- Asignación de categoría por nombre: case-insensitive, no se crean
  categorías nuevas. Si no matchea → `default_category_id` (o `null`).

---

## Receipts (`PHASE-5.1` + `PHASE-21.2`)

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| POST   | `/receipts/extract` | sí | multipart `file` (image/jpeg\|png\|webp\|heic\|heif, ≤8 MB) | `201` `{ receipt, extraction }` |
| POST   | `/receipts/{id}/confirm` | sí | `{ account_id, amount, occurred_at, currency, description?, category_id? }` (PHASE-21.2: `account_id` obligatorio) | `200` `ReceiptResponse` |
| POST   | `/receipts/{id}/reject` | sí | — | `200` `ReceiptResponse` |
| GET    | `/receipts` | sí | `limit` (1..200, def 50), `offset` (def 0) | `200` `{ items, total, limit, offset }` |
| GET    | `/receipts/{id}` | sí | — | `200` `ReceiptResponse` |
| GET    | `/receipts/{id}/blob` | sí | — | `200` bytes (Content-Type del original; cache `private,max-age=300`) |

Reglas:
- La imagen va a MinIO (`<user_id>/<YYYYMMDD>/<uuid>.<ext>`); el blob
  no se devuelve por API (en MVP).
- La extracción usa Ollama con `qwen2.5-vl:7b` (configurable). Si
  Ollama no responde o devuelve algo no parseable, se devuelve **502**
  y se borra el blob para no dejar huérfanos.
- `confirm` solo acepta receipts en estado `pending` (si no, **409**).
  Crea una transacción con `source=receipt` enlazada al receipt.
- `reject` solo acepta receipts en estado `pending`. No crea
  transacción.
- `ReceiptStatus`: `pending | confirmed | rejected` (irreversible
  desde `confirmed`/`rejected`).
- Las `line_items` se persisten en `extraction` (JSON) pero **no** se
  crean como transacciones individuales — el MVP crea una sola
  transacción con el total.

---

## Bank mappings (`PHASE-19`)

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| GET    | `/bank-mappings` | sí | — | `200 list[BankCategoryMapping]` |
| POST   | `/bank-mappings` | sí | `{ bank_concept, category_id }` | `201 BankCategoryMapping` (UPSERT por concepto normalizado) |
| DELETE | `/bank-mappings/{id}` | sí | — | `204` |

Reglas:
- `bank_concept` se normaliza con `casefold() + trim`. Conceptos
  equivalentes generan la misma fila.
- El upsert se invoca implícitamente en `POST /imports/{id}/commit`
  con los `category_overrides` aceptados — el endpoint REST es
  para gestión manual.

## Category rules (`PHASE-20`)

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| GET    | `/category-rules` | sí | `?enabled_only=true|false` | `200 list[CategoryRule]` |
| POST   | `/category-rules` | sí | `{ pattern, match_type, field, category_id, priority?, enabled? }` | `201 CategoryRule` |
| PUT    | `/category-rules/{id}` | sí | `{ pattern?, match_type?, field?, priority?, enabled? }` | `200 CategoryRule` |
| DELETE | `/category-rules/{id}` | sí | — | `204` |
| POST   | `/seed/recommended` | sí | — | `200 SeedResult` (idempotente) |
| POST   | `/imports/{id}/ai-suggest` | sí | — | `200 AiSuggestionResponse { suggestions: { concept_norm: category_id|null } }` |

Reglas:
- `priority` ascendente: 10 gana a 100. Las del seed van 10-79;
  las custom 100 por defecto.
- `field` decide contra qué se evalúa: `CONCEPT`, `DESCRIPTION` o
  `BOTH` (cualquiera matchea).
- `seed/recommended` puebla ~18 categorías + ~30 reglas; ejecutado
  varias veces no duplica (UPSERT por nombre / por tupla
  `(pattern, match_type, field, category_id)`). Si la categoría
  existe sin `color`/`icon`, los rellena.
- `ai-suggest` consulta Ollama local con el listado de categorías
  del usuario y devuelve sugerencias para los conceptos sin
  `saved_mapping` ni regla matching. Sólo aplica a jobs en
  `PREVIEW`. Latencia 30-90s en CPU.

## Accounts (`PHASE-21.2`)

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| GET    | `/accounts` | sí | `?include_archived=` | `200 list[Account]` |
| GET    | `/accounts/{id}` | sí | — | `200 Account` |
| GET    | `/accounts/balances` | sí | `?target_currency=` (opc, AUDIT-2026-06) | `200 AccountBalancesResponse { items, total_assets, total_liabilities, net_worth, mixed_currencies, reference_currency }` (PHASE-21.3). Con `target_currency` cada saldo se convierte con la tasa de hoy y las cuentas sin tasa se excluyen del agregado; sin él, suma cruda + `mixed_currencies` |
| GET    | `/accounts/debt-health` | sí | `?target_currency=` (opc, PHASE-30.6) | `200 DebtHealthKpis { total_liabilities, total_assets, net_worth, debt_to_assets_ratio, dti_ratio, dti_status, monthly_debt_payment, monthly_income_avg, debt_by_type[], interest_paid_ytd, interest_scheduled_total, interest_remaining, weighted_apr, time_to_payoff_months, reference_currency }` (PHASE-22; PHASE-37: `debt_by_type` = deuda viva por tipo para el donut, `interest_paid_ytd` sale del cuadro —MUX por pasivo, no de tx—, `interest_scheduled_total`/`interest_remaining` = interés contractual total y pendiente) |
| GET    | `/accounts/debt-history` | sí | `months_back` (1..36, def 12), `months_ahead` (0..36, def 12), `?target_currency=` (opc, PHASE-30.6) | `200 DebtHistoryResponse { items[], reference_currency, months_historical, months_projected }` — serie mensual de deuda: histórico (meses cerrados) + proyección por cuadro; cada punto `{ month, total_debt, principal_paid, interest_paid, kind }` (PHASE-22.1) |
| GET    | `/accounts/position-history` | sí | `months_back` (1..36, def 12), `months_forward` (0..36, def 0) | `200 PositionHistoryResponse { reference_currency, points[], delta_period, delta_period_pct }` — serie mensual de patrimonio (activos/pasivos/neto), histórico + proyección; mono-divisa. `delta_period` = Δ neto del rango (PHASE-37.1) |
| GET    | `/accounts/position-as-of` | sí | `date_from`, `date_to` (obligatorios) | `200 PositionAsOfResponse { reference_currency, total_assets, total_liabilities, net_worth, delta_assets, delta_net_worth }` — patrimonio **a fecha `date_to`** (apertura + Σ mov. firmados ≤ `date_to`) + Δ de activos/neto **durante** `[date_from, date_to]`; excluye archivadas y brokerage/crypto; mono-divisa de referencia; mismo `signed_amount_expr` que balances/position-history (PHASE-42) |
| POST   | `/accounts/reconcile-debt` | sí | `?dry_run=` (bool, def `true`) | `200 ReconcilePlanResponse` — reconcilia aportaciones (amortización de préstamo, cuotas de op. financiada) contra el cuadro de cada deuda: genera el cuadro que falte, ancla cuotas previas y marca pagadas las que cada aportación liquida. `dry_run=true` sólo devuelve el plan; `false` lo aplica (idempotente) (PHASE-36) |
| GET    | `/accounts/{id}/amortization-schedule` | sí | — | `200 AmortizationScheduleResponse { account_id, principal, apr, term_months, start_date, monthly_payment, total_interest, total_paid, rows[] }` (`400` si la cuenta no es loan/mortgage, falta APR/plazo/start_date o `opening_balance <= 0`) (PHASE-22) |
| POST   | `/accounts/{id}/amortization-schedule/regenerate` | sí | — | `200 AmortizationScheduleResponse` — borra y regenera el cuadro con `apr`/`term`/`start` actuales. PIERDE el estado de pago (`paid_at`) de las cuotas (PHASE-24.3) |
| PATCH  | `/accounts/installments/{installment_id}` | sí | `{ payment?, due_date? }` | `200 AmortizationRowResponse` — override puntual de importe/fecha de una cuota; no recomputa las siguientes (PHASE-24.1) |
| POST   | `/accounts/installments/{installment_id}/pay` | sí | `{ paid_at?, paid_transaction_id? }` | `200 AmortizationRowResponse` — marca la cuota como pagada (PHASE-24.1) |
| DELETE | `/accounts/installments/{installment_id}/pay` | sí | — | `200 AmortizationRowResponse` — revierte la cuota a pendiente (PHASE-24.1) |
| POST   | `/accounts/{id}/pay-installments` | sí | `{ principal_amount, paid_at?, paid_transaction_id? }` | `200 InstallmentBulkPayResponse { marked_count, covered_principal, uncovered_principal, schedule_outstanding }` — marca las cuotas que un pago de principal cubre, de la más antigua pendiente hacia adelante (AUDIT-2026-07 H-05) |
| POST   | `/accounts/{id}/reconcile` | sí | `{ current_balance }` | `200 Account` — "Cuadrar saldo": fija el saldo real de una cuenta de **activo** ajustando `opening_balance`. `400` si la cuenta no es de activo (PHASE-34) |
| GET    | `/accounts/{id}/settlement-candidate` | sí | — | `200 SettlementCandidateResponse { account_id, account_name, reason, matches, total }` — desde qué cuenta de activo PARECE cobrarse este pasivo, contando los cargos que el usuario ya enlazó (PHASE-45). Sin evidencia o con empate devuelve todo a `null`/`0`: propone, no adivina. No escribe nada (PHASE-47.A, [ADR-0011](../decisions/0011-system-initiated-debt-event-translation.md)) |
| POST   | `/accounts` | sí | `{ name, type, currency?, color?, icon?, opening_balance?, opening_balance_date?, apr?, tae?, term_months?, start_date?, total_to_pay?, interest_only_first_payment?, display_order?, is_default?, category_id?, parent_account_id?, settlement_account_id? }` | `201 Account` (`409` si nombre duplicado; `400` si `type` no soportado, `category_id` inválido, `parent_account_id` no es una `credit_card` del usuario / falta plan de la compra a plazos, o `settlement_account_id` no es una cuenta de activo del usuario / la cuenta no es de deuda / se apunta a sí misma) |
| PUT    | `/accounts/{id}` | sí | partial (incluye `apr`, `term_months`, `start_date`, `is_default`) | `200 Account` |
| DELETE | `/accounts/{id}` | sí | — | `204` (`409` si la cuenta tiene transacciones — usar `PUT { is_archived: true }`) |

Reglas:
- `type` permitido: `bank | savings | brokerage | crypto | cash`
  (assets) + `credit_card | loan | mortgage` (liabilities, PHASE-22).
- `nature` se asigna automáticamente según el `type` (no se envía
  desde el cliente).
- `apr`, `term_months`, `start_date` sólo aplican a `loan` /
  `mortgage`. Para otros tipos el backend los ignora.
- `category_id` (PHASE-30.4): vinculación opcional contrato↔categoría.
  Sólo aceptable en liabilities cuya categoría tiene
  `role IN (DEBT_PAYMENT, DEBT_INTEREST)`; otro caso devuelve 400.
  Enviar `null` desvincula. La categoría borrada hace `SET NULL` en la
  cuenta (FK con `ON DELETE SET NULL`).
- `is_default` (PHASE-32): cuenta principal del usuario, pre-seleccionada
  en formularios (transacción, import, ticket). **Única por usuario**: el
  service desmarca las demás al marcar una. Su `current_balance` refleja
  **ahorro neto** — excluye las transferencias internas (`is_transfer`),
  a diferencia del resto de cuentas (modo cash, PHASE-23.1).
- Tras el wipe de PHASE-21.2, todo usuario empieza sin cuentas y
  el frontend bloquea en `/onboarding/accounts` hasta declarar al
  menos una.
- `current_balance` para assets: `opening_balance +
  Σ(income−expense)`. Para liabilities el signo se invierte:
  `opening_balance + Σ(expense−income)` (un gasto sube la deuda,
  un ingreso/transferencia la baja). Excluye papelera.
- `mixed_currencies=true` cuando las cuentas activas no comparten
  moneda — los totales son suma cruda sin conversión.
- Cada item de `/accounts/balances` (`AccountBalance`) incluye además
  `monthly_payment` (PHASE-37 — cuota mensual del cuadro para liabilities
  con schedule; `null` en activos y liabilities sin cuadro),
  `parent_account_id` (PHASE-35 — tarjeta padre si es una compra a plazos,
  para agrupar) e `is_unvalued` (PHASE-31.4 — `true` para brokerage/crypto,
  que aparecen pero NO suman al patrimonio neto agregado).
- `/accounts/debt-health` opera sólo en la `reference_currency`
  (primera cuenta no archivada por `display_order`). Cuentas en
  otras divisas se ignoran silenciosamente.
- `dti_status` (recalibrado en PHASE-30.2): `healthy` (<0.30) ·
  `caution` (0.30–0.35) · `stressed` (>0.35) · `unknown` (sin
  ingresos o sin pagos de deuda registrados). Bandas BdE
  ("tasa de esfuerzo" sobre ingresos netos); reemplazan a las
  estadounidenses 36%/43% sobre ingresos brutos.
- `time_to_payoff_months` (recalibrado en PHASE-30.2): cuando la
  liability tiene cuadro (`apr + term_months + start_date`), usa
  las cuotas restantes del schedule; fallback a proyección
  lineal sólo para tarjetas o liabilities sin cuadro. Devuelve
  el máximo individual.

## Debt (Capa 1) (`PHASE-30.2`)

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| GET    | `/debt/category-summary` | sí | `?range=month|year|custom` (def `year`; `quarter` retirado en PHASE-42), `?anchor=YYYY-MM-DD` (opc, PHASE-30.8: día dentro del período objetivo para navegar a períodos pasados; se ignora con `custom`), `?date_from=`/`?date_to=` (obligatorios con `range=custom`, PHASE-42: rango libre day-exact; 422 si faltan o están cruzados), `?target_currency=` (opc, PHASE-30.6) | `200 DebtCategorySummary { reference_currency, range, range_start, range_end, total_payments, interests_and_fees, capital_amortized, by_type[], monthly_series[], daily_series[]?, monthly_income_avg, monthly_debt_payment_avg, effort_ratio_strict, effort_ratio_strict_status, effort_ratio_extended, effort_ratio_extended_status, recurring_quotas[] }` (`daily_series` sólo con `range=month`, PHASE-30.9: `{ day, emitida, amortizado, interest, balance? }` por día) |

Reglas:
- Capa 1 = KPIs derivados del flujo de transacciones con
  `category.role IN (DEBT_PAYMENT, DEBT_INTEREST)`. No requiere
  liability accounts — basta con que el usuario categorice sus pagos.
- `total_payments` = `interests_and_fees + capital_amortized`.
- `by_type` clasifica por nombre de la categoría (hipoteca / tarjeta
  / préstamo / other) para el donut de composición.
- `monthly_series` tiene longitud determinista por rango: 12 puntos
  para `12m`, 1 para `month`, `mes_actual` para `ytd`. Meses sin
  actividad caen en 0.
- `effort_ratio_strict` = `monthly_debt_payment / monthly_income_avg`
  sobre los últimos 6 meses cerrados (independiente del `range_`).
  `effort_ratio_extended` añade al numerador los `fixed_expenses`
  confirmados con cadencia mensual cuya categoría NO sea de deuda
  (evita doble cómputo).
- `recurring_quotas` lista `fixed_expenses` confirmados con
  `category.role` de deuda — la UI los presenta como "Cuotas
  recurrentes detectadas".
- `target_currency` (PHASE-30.6): cuando se pasa, todos los importes
  vienen convertidos a esa divisa con la tasa **del día de cada
  transacción** (`converted_amount_expr`, mismo patrón que dashboard).
  Para `recurring_quotas` y agregados de gastos fijos, la conversión
  usa la tasa de hoy. `reference_currency` de la respuesta = target.
  Txs / gastos en divisas sin tasa quedan excluidos silenciosamente.

## Transfers (`PHASE-21.3`)

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| POST   | `/transfers/link` | sí | `{ out_transaction_id, in_transaction_id }` | `201 TransferPair` (`400` si misma cuenta o importe distinto, `409` si ya hay par, `404` si tx ajena) |
| DELETE | `/transfers/{transaction_id}` | sí | — | `204` — deshace el par |
| GET    | `/transfers/misclassified` | sí | — | `200 list[MisclassifiedTransfer]` — tx `is_transfer` cuyo `kind` no encaja con la dirección del texto (RECIBIDA en categoría EXPENSE). Candidatas a recategorización en bloque (PHASE-31.2) |
| GET    | `/transfers/financing-matches` | sí | — | `200 list[FinancingMatchResponse]` — abonos que parecen una financiación (el banco aplaza un recibo y nace deuda) y encajan con el CAPITAL del cuadro de un pasivo que aún no tiene registrado su origen. Sólo propone: el enlace lo confirma el usuario con `from-source-debt`. `counted_as_income` dice si hoy está sumando en la gráfica de ingresos (PHASE-46) |
| POST   | `/transfers/reclassify-bulk` | sí | `{ transaction_ids[], target_category_id? }` | `200 ReclassifyBulkResponse` — recategoriza en bloque; sin `target_category_id`, cada tx va a la categoría `is_transfer` del kind opuesto (PHASE-31.2) |
| POST   | `/transfers/from-source` | sí | `{ source_transaction_id, originating_account_id, beneficiary_account_id }` | `201 TransferPairResponse` — convierte una tx en transferencia interna creando la contraparte y emparejando ambas; dirección EXPLÍCITA (PHASE-23.1/28) |
| POST   | `/transfers/from-source-debt` | sí | `{ source_transaction_id, destination_account_id?, new_liability? }` | `201 TransferPairResponse` — convierte una tx en operación financiada: crea la contraparte en una liability (existente o nueva al vuelo) y empareja; la deuda sube por el importe (PHASE-24) |
| POST   | `/transfers/amortization` | sí | `{ source_transaction_id, liability_account_id, counts_as_expense?, dry_run? }` | `200 AmortizationEffect` — declara que un cargo del banco amortiza una deuda (PHASE-45). Con `dry_run:true` no escribe nada y devuelve el efecto exacto + la sugerencia de si cuenta como gasto **con su motivo**; al aplicar, `counts_as_expense` es obligatorio (`400` si falta). `400` si la tx no es una salida, si la cuenta no es de deuda, si es la propia cuenta del movimiento o si es de otra divisa; `409` si ya está registrada o si la tx está emparejada; `404` si la tx o la cuenta son ajenas |
| GET    | `/transfers/amortization/{transaction_id}` | sí | — | `200 AmortizationEffect` con el registro ya aplicado; `404` si la tx no está registrada (estado normal de la pantalla, no error) |
| DELETE | `/transfers/amortization/{transaction_id}` | sí | — | `204` — deshace el registro: desmarca las cuotas y manda la contrapartida a la papelera. La deuda vuelve a subir. `404` si no estaba registrada |

> PHASE-41 (ADR-0005) retiró el emparejado heurístico: `GET /transfers`,
> `/candidates`, `POST /match`, `GET /suspects` y `POST /mark` **ya no
> existen**. La verdad del dinero vive en `transactions.flow` (ADR-0004).

**`AmortizationEffect`** (PHASE-45) — el previsto y el ya aplicado comparten
forma. `mode` dice CÓMO baja la deuda y lo decide el pasivo, no el usuario:

- `schedule` — el pasivo tiene cuadro, así que se marcan cuotas pagadas y **no
  se crea ningún movimiento** (uno sería invisible para el saldo, que manda el
  cuadro desde PHASE-36). `principal_covered` es Σ del capital de las cuotas
  cubiertas: **no** el importe pagado, porque los intereses no amortizan.
  `installments_marked: 0` significa que el pago no llega a completar la cuota
  pendiente más antigua y la deuda NO baja — se declara, no se esconde.
- `movement` — sin cuadro (tarjeta con saldo arrastrado): se crea la
  contrapartida en la cuenta de deuda (`counterpart_transaction_id`) y baja por
  el importe entero.

`counts_as_expense` lo declara el usuario y sólo cambia el `flow` de la pata del
banco (`OUT` vs `TRANSFER_OUT`). Emparejar (`paired`) ocurre **sólo** cuando es
neutro: `budgets` y las queries de gasto de deuda filtran `transfer_pair_id IS
NULL`, así que emparejar una pata declarada como gasto la borraría de las dos.

Reglas:
- Bidireccional: al enlazar A↔B, ambas filas apuntan mutuamente.
- Las txs con `transfer_pair_id IS NOT NULL` se EXCLUYEN de los
  agregados (cashflow, donut, top-expenses, budgets) pero SÍ
  cuentan al saldo individual de su cuenta.

## Currency (`PHASE-8.1`)

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| GET    | `/currency/rates` | sí | `?date=YYYY-MM-DD` (def hoy UTC), `?base=EUR` (def `EUR`, 3 letras) | `200` `RatesResponse` `{ rate_date, base, rates: [{ quote, rate }] }` |
| GET    | `/currency/convert` | sí | `?amount=&from=&to=&date=` (`from`/`to` 3 letras; `date` def hoy UTC) | `200` `ConvertResponse` `{ amount, rate, rate_date, fallback }` |

Reglas:
- `fallback` ∈ `exact | previous | same | missing`. `same` cuando
  `from == to`; `missing` cuando no hay tasa ni en la ventana de
  fallback (14 días) — el endpoint devuelve el importe sin
  convertir y `rate=1`, no falla con 4xx.
- Las tasas son datos públicos globales (ECB vía
  `frankfurter.app`). No se filtra por `user_id`. Se exige
  autenticación sólo para evitar dejar el endpoint totalmente
  abierto.
- Convención `base='EUR'`: las tasas se almacenan EUR→quote y las
  conversiones X→Y se componen vía EUR en `currency.service`.
- `amount` es `Decimal` serializado como string. El endpoint lo
  parsea con `Decimal(...)` y rechaza con 422 si no encaja.

---

## Investment (`PHASE-44.1` … `PHASE-44.9`)

Módulo de inversión: catálogo de valores, ingesta de fundamentales desde EDGAR,
motor de análisis forense y cartera. **28 endpoints**, todos con auth.

Alcance de datos: `securities`, `financial_statements`, `scoring_thresholds` y
los precios son **globales** (ADR-0007 — un 10-K es el mismo para todos); los
`analysis_runs`, los lotes y las ventas son **scoped por usuario**.

### Catálogo de valores

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/investment/securities/search` | **(44.13, ampliado en 44.14)** Busca en TRES capas locales, sin red: el catálogo del usuario, el índice de los ~10.400 emisores de la SEC y el directorio FIRDS UE/UK. `q` mínimo 2 caracteres. Cada hit trae `listing_key`, `source` (`catalog`/`sec_index`/`eu_directory`), `cik`, `isin`, `currency`, `exchange_label` y `analysis_reason`; la respuesta, `index_ready`, `notice` y `directory_seeded_at`. |
| POST | `/investment/securities/adopt` | **(44.13, ampliado en 44.14)** Materializa un resultado del buscador desde su `listing_key` opaca (`cat:`/`idx:`/`ext:`/`typed:`). El servidor la re-resuelve: el cliente no manda plaza ni CIK. Para `ext:` (directorio FIRDS) el alta es **validada**: resolución ISIN→símbolo, cross-check sufijo↔plaza y una cotización real antes de persistir. `422` con `detail.code='ticker_required'` y la identidad pre-rellenada cuando el proveedor no reconoce el ISIN — el cliente reintenta con `ticker`. `422` con motivo si la clave está mal formada o el ISIN no valida el checksum. |
| POST | `/investment/securities/resolve` | Crea (o reutiliza) un `Security` desde su ticker. La plaza la decide el servidor, no el cliente (ADR-0008). 404 si EDGAR no lo reconoce. Se conserva como escotilla; el buscador usa `/adopt`, que además NO pierde la plaza. |
| GET | `/investment/securities/{security_id}` | Un valor por id, con `analysis_available` y su motivo. |

### Fundamentales

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/investment/fundamentals/items` | **(44.9)** Las 49 partidas canónicas con etiqueta ES, `statement` (balance/income/cashflow) y `group`. Estático. |
| POST | `/investment/fundamentals/{security_id}/ingest` | `202` — descarga y persiste los últimos `filings_back` ejercicios vía job síncrono. |
| GET | `/investment/fundamentals/jobs/{job_id}` | Estado del job (polling). |
| GET | `/investment/fundamentals/{security_id}/statements` | Estados por ejercicio, ascendente. `view=latest\|all`. |
| GET | `/investment/fundamentals/{security_id}/restatements` | Reexpresiones detectadas entre filings. |

### Análisis

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/investment/analysis/metrics` | **(44.9)** Las métricas del engine con `label`, `family`, `unit`, `direction`, los 4 cortes por defecto y su `note`. Estático; el recuento sale del propio catálogo. |
| POST | `/investment/analysis/{security_id}/run` | Ejecuta las 6 capas y persiste el `AnalysisRun`. `409` si no hay estados ingeridos; `422` con motivo si el valor **no es analizable** (sin CIK, sin 10-K…). |
| GET | `/investment/analysis/{security_id}/runs/latest` | **(44.9)** El último run con todo el desglose. `404` si no hay ninguno. |
| GET | `/investment/analysis/{security_id}/valuation` | **(44.12)** Múltiplos de valoración (PER, P/ventas, P/VC, P/FCF, EV/EBITDA + valor contable por acción y rentabilidad de la caja libre) cruzando la cotización viva con el último ejercicio cerrado. `?price=` simula otro precio y cubre los valores sin cobertura del proveedor. **No sale del `AnalysisRun` y no se persiste**: un múltiplo se mueve con el precio y el run tiene que poder reejecutarse dando lo mismo. Nunca falla por falta de cotización — responde `200` con `available:false` y el motivo. `provider_status` (`live`/`cached`/`unreachable`) alimenta el semáforo: «no lo he preguntado» no es «está bien». |
| GET | `/investment/analysis/{security_id}/runs` | Histórico ligero (sin los JSONB). |
| GET | `/investment/analysis/runs/{run_id}` | Un run por id con todo el desglose. `404` si es de otro usuario. |

Notas del `AnalysisRun`:

- `thresholds_version` es un SHA-256 del juego de umbrales: **detecta** deriva,
  no la reconstruye. Para eso está `thresholds_used` (44.9), que trae los cortes
  efectivos `metric_key → spec`. Vacío `{}` en los runs anteriores a 44.9.
- `verdict.questions[].signals[]` (44.9) trae **todas** las señales candidatas de
  cada pregunta con `key`, `label`, `kind`, `band`, `value`, `counted` y el
  `reason` de las que no puntuaron, más `evaluated_count` /
  `unavailable_count`. Sin esos contadores, «sano» y «no hay evidencia» son
  indistinguibles: en una financiera los 8 forenses salen `not_computable` y la
  pregunta de contabilidad cae en verde por ausencia de prueba.
- `band: null` **no significa sana**: significa que no hay banda que aplicar.

### Cartera y precios

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET · POST | `/investment/portfolio/lots` | Lotes de compra. |
| DELETE | `/investment/portfolio/lots/{lot_id}` | Borra un lote. |
| GET · POST | `/investment/portfolio/sales` | Ventas; el POST casa contra los lotes vía FIFO (`409` si vendes más de lo que tienes). |
| DELETE | `/investment/portfolio/sales/{sale_id}` | Borra la venta; sus allocations caen en cascada. |
| GET · POST | `/investment/portfolio/dividends` | Dividendos cobrados. |
| DELETE | `/investment/portfolio/dividends/{dividend_id}` | Borra un dividendo. |
| GET · POST | `/investment/portfolio/corporate-actions` | Acciones corporativas registradas (el POST **no** las aplica). |
| POST | `/investment/portfolio/corporate-actions/{action_id}/apply` | Aplica split / stock dividend a los lotes, auditado. `400` para los tipos no soportados. |
| GET | `/investment/portfolio/positions` | Posiciones derivadas (lotes − allocations): cantidad, coste base y P&L. |
| GET | `/investment/portfolio/summary` | Resumen con valor de mercado, en divisa nativa **y en EUR** (`*_base`, tipos del BCE vía `currency` — ADR-0009) con `fx_as_of` por posición, descomposición precio/divisa y exposición por divisa. Una posición sin cotización **o sin tipo de cambio** queda fuera de los totales con su `exclusion_reason`; nunca se estima. |
| POST | `/investment/pricing/refresh` | Fuerza el refresco de cotizaciones ignorando el TTL. `pricing_enabled` refleja si el proveedor ACTIVO puede cotizar: con `PRICE_PROVIDER=yfinance` (default) siempre; con `finnhub`, sólo si hay `FINNHUB_API_KEY`. |

---

## Convenciones de errores

| Código | Cuándo |
|--------|--------|
| 400 | Body malformado (JSON inválido, UUID inválido, fichero vacío). |
| 401 | Token ausente, inválido o expirado. |
| 403 | Token válido pero el recurso no pertenece al usuario (raro — normalmente devolvemos 404 para no filtrar existencia). |
| 404 | Recurso no existe **o** pertenece a otro usuario. |
| 413 | Upload supera el tamaño máximo. |
| 422 | Validación Pydantic (campos requeridos, formatos). |
| 500 | Error inesperado. Solo se loguea el detalle, no se devuelve al cliente en prod. |

Todos los errores siguen el formato FastAPI estándar:
`{ "detail": "..." }` o `{ "detail": [{ loc, msg, type }, ...] }`.
