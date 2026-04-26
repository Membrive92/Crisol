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
| POST | `/auth/login` | no | `{ email, password }` | `200` `TokenResponse` |
| POST | `/auth/refresh` | no | `{ refresh_token }` | `200` `TokenResponse` (rota el refresh) |
| POST | `/auth/logout` | sí | `{ refresh_token }` | `204` |
| GET  | `/auth/me` | sí | — | `200` `UserResponse` |

Reglas:
- Access token: 15 min. Refresh token: 7 días.
- Refresh hace **rotación** — el viejo se revoca, devuelve uno nuevo.
- Password hashing: argon2id.

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

## Transactions (`PHASE-2.1`)

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| GET | `/transactions` | sí | `category_id?`, `date_from?`, `date_to?`, `search?`, `limit` (1..200, def 50), `offset` (def 0) | `200` `{ items, total, limit, offset }` |
| GET | `/transactions/{id}` | sí | — | `200` `TransactionResponse` |
| POST | `/transactions` | sí | `{ amount, occurred_at, category_id?, currency?, description?, source? }` | `201` `TransactionResponse` |
| PUT | `/transactions/{id}` | sí | `Partial<TransactionCreate>` | `200` `TransactionResponse` |
| DELETE | `/transactions/{id}` | sí | — | `204` |

`source`: `manual | import | receipt` (default `manual`). Importes
positivos; el signo se infiere de `category.kind` en frontend.

---

## Dashboard (`PHASE-3.1`)

Todos GET, read-only, agregaciones SUM/COUNT/GROUP BY filtradas por
`user_id` y por `currency` (default `USD`).

| Método | Ruta | Query | Response |
|--------|------|-------|----------|
| GET | `/dashboard/summary` | `currency` (def `USD`), `date_from?`, `date_to?` | `{ income, expenses, balance, transaction_count, currency }` |
| GET | `/dashboard/by-category` | `currency`, `date_from?`, `date_to?`, `kind?` (`income\|expense`) | `[{ category_id, category_name, category_kind, total, count }]` |
| GET | `/dashboard/by-month` | `year` (def actual), `currency` | `[{ month: "YYYY-MM", income, expenses, balance }]` (12 buckets) |
| GET | `/dashboard/top-expenses` | `currency`, `date_from?`, `date_to?`, `limit` (1..50, def 10) | `[{ transaction_id, description, amount, occurred_at, category_id, category_name }]` |

Reglas relevantes:
- `summary.transaction_count` cuenta todas las transacciones del rango,
  incluso sin categoría.
- `summary.income` / `expenses` sólo cuentan transacciones con
  categoría (el signo lo decide `category.kind`).
- `by-category` incluye un bucket `{ category_id: null, category_name:
  "Sin categoría" }` que se excluye cuando se filtra por `kind`.
- `top-expenses` solo devuelve transacciones cuya categoría es
  `expense` (las sin categoría se excluyen).

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
