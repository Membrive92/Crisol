# API endpoints

> Catálogo del backend. Se actualiza cada vez que una fase añade o
> modifica endpoints. Última actualización: PHASE-4.1.

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

## Transactions (`PHASE-2.1` + `PHASE-8.4`)

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| GET | `/transactions` | sí | `category_id?`, `date_from?`, `date_to?`, `search?`, `target_currency?` (3 letras, PHASE-8.4), `limit` (1..200, def 50), `offset` (def 0) | `200` `{ items, total, limit, offset }` |
| GET | `/transactions/{id}` | sí | — | `200` `TransactionResponse` |
| POST | `/transactions` | sí | `{ amount, occurred_at, category_id?, currency?, description?, source? }` | `201` `TransactionResponse` |
| PUT | `/transactions/{id}` | sí | `Partial<TransactionCreate>` | `200` `TransactionResponse` |
| DELETE | `/transactions/{id}` | sí | — | `204` |

`source`: `manual | import | receipt` (default `manual`). Importes
positivos; el signo se infiere de `category.kind` en frontend.

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
| GET | `/dashboard/by-month` | `year` (def actual), `currency` o `target_currency` | `[{ month: "YYYY-MM", income, expenses, balance }]` (12 buckets) |
| GET | `/dashboard/top-expenses` | `currency` o `target_currency`, `date_from?`, `date_to?`, `limit` (1..50, def 10) | `[{ transaction_id, description, amount, occurred_at, category_id, category_name, original_amount, original_currency }]` (PHASE-8.4: `original_*` siempre presentes; `amount` es el convertido en cross-currency, original en legacy) |

Reglas relevantes:
- `summary.transaction_count` cuenta todas las transacciones del rango,
  incluso sin categoría.
- `summary.income` / `expenses` sólo cuentan transacciones con
  categoría (el signo lo decide `category.kind`).
- `summary.unconvertible_count` (PHASE-8.3) es siempre 0 en modo
  legacy; en modo cross-currency cuenta las transacciones sin tasa
  histórica disponible (ni exacta ni en ventana de 14 días).
- `summary.previous_period_*` se computa cuando llegan `date_from` y
  `date_to`. Es el rango previo de igual longitud, terminando justo
  antes de `date_from` (rango actual `[2026-02-01, 2026-02-28]` →
  rango previo `[2026-01-04, 2026-02-01]`). Si no llega rango, los
  tres campos son `null` y el frontend no pinta delta.
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

## Imports (`PHASE-4.1`, `PHASE-4.3`)

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| POST | `/imports` | sí | multipart: `file`, `column_mappings` (JSON), `currency` (def `EUR`), `default_category_id?` | `201` `ImportJobResponse` (job ya finalizado) |
| GET  | `/imports` | sí | `limit` (1..200, def 50), `offset` (def 0) | `200` `{ items, total, limit, offset }` |
| GET  | `/imports/{id}` | sí | — | `200` `ImportJobResponse` |

Reglas:
- Formatos: CSV (auto-detect delimitador), XLSX y PDF (extracción de
  tablas vía `pdfplumber`; PDFs sin tablas → job `failed`). Tamaño
  máx 10 MB.
- `column_mappings`: `{ amount, occurred_at, description?, category_name? }` —
  obligatorios sólo `amount` y `occurred_at`.
- Pipeline **síncrono**: parse → map → validate → SHA-256 dedup
  intra/inter-batch → persist `source=import`.
- Hash de dedup: SHA-256 de
  `user_id|amount(2dp)|currency|occurred_at_iso|description.casefold().strip()`.
- `error_log` capado a 100 entradas; `rows_failed` cuenta todas las
  filas inválidas.
- Estado del job: `pending | processing | completed | failed`.
- Asignación de categoría por nombre: case-insensitive, no se crean
  categorías nuevas. Si no matchea → `default_category_id` (o `null`).

---

## Receipts (`PHASE-5.1`)

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| POST   | `/receipts/extract` | sí | multipart `file` (image/jpeg\|png\|webp\|heic\|heif, ≤8 MB) | `201` `{ receipt, extraction }` |
| POST   | `/receipts/{id}/confirm` | sí | `{ amount, occurred_at, currency, description?, category_id? }` | `200` `ReceiptResponse` |
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
