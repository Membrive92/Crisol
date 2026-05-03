# Schema de base de datos

> Estado actual del modelo de datos. Se actualiza cuando una fase
> introduce migraciones. Última actualización: PHASE-5.1.

## Convenciones

- PostgreSQL 16 + extensión `pgvector` (esta última se usará en PHASE-5.x).
- PK: `id UUID DEFAULT uuid_generate_v4()` (o cliente).
- Toda tabla de dominio tiene `user_id UUID NOT NULL` con FK a `users`
  (`ON DELETE CASCADE`).
- Importes en `NUMERIC(14, 2)` — nunca `float`.
- Fechas en `TIMESTAMPTZ`.
- `created_at`, `updated_at` en todas las tablas mutables.

## Migraciones aplicadas

| Revisión | Fase | Descripción |
|----------|------|-------------|
| `4698c02a5861` | 1.1, 2.1 | Initial schema — `users`, `refresh_tokens`, `categories`, `transactions`. |
| `7c3a91f4d2b8` | 4.1 | `import_jobs` + `transactions.import_hash` + índice único parcial. |
| `a91d8f4c2e10` | 5.1 | `receipts` + índices por `user_id` y `transaction_id`. |
| `d18a4c75b2e9` | 1.1 | `webauthn_credentials` + `webauthn_challenges`. |
| `b27e391fa4c8` | 1.1 | `webauthn_challenges.user_id` nullable + relax FK para conditional UI. |
| `c5d28e7f3b91` | 8.1 | `exchange_rates` + carga de snapshot offline embebido. |

---

## Tablas

### `users` (`PHASE-1.1`)

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `email` | `VARCHAR(255)` UNIQUE | índice único, lower-cased en service. |
| `password_hash` | `VARCHAR(512)` | argon2id. |
| `display_name` | `VARCHAR(100)` | |
| `is_active` | `BOOLEAN` | default `TRUE`. Soft-disable para futuros flujos de baja. |
| `created_at` | `TIMESTAMPTZ` | `now()`. |
| `updated_at` | `TIMESTAMPTZ` | `now()`, `onupdate=now()`. |

### `refresh_tokens` (`PHASE-1.1`)

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → `users.id` `ON DELETE CASCADE` | índice. |
| `token_hash` | `VARCHAR(512)` UNIQUE | SHA-256 del refresh token. |
| `expires_at` | `TIMESTAMPTZ` | 7 días. |
| `revoked` | `BOOLEAN` | rotación marca el viejo. |
| `created_at` | `TIMESTAMPTZ` | |

### `categories` (`PHASE-2.1`)

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → `users.id` `ON DELETE CASCADE` | índice. |
| `name` | `VARCHAR(100)` | |
| `icon` | `VARCHAR(50)` NULLABLE | identificador de icono (frontend lo resuelve). |
| `color` | `VARCHAR(7)` NULLABLE | hex `#RRGGBB`. |
| `kind` | `ENUM('income','expense')` | tipo `categorykind`. |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

### `transactions` (`PHASE-2.1` + `PHASE-4.1`)

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → `users.id` `ON DELETE CASCADE` | índice. |
| `category_id` | `UUID` FK → `categories.id` `ON DELETE SET NULL` | índice, nullable. |
| `amount` | `NUMERIC(14,2)` | siempre positivo. Signo lo decide `category.kind`. |
| `currency` | `CHAR(3)` | ISO 4217. Default `EUR`. |
| `occurred_at` | `TIMESTAMPTZ` | fecha de la transacción. |
| `description` | `TEXT` NULLABLE | |
| `source` | `ENUM('manual','import','receipt')` | tipo `transactionsource`. |
| `receipt_id` | `UUID` NULLABLE | (PHASE-5.1, FK aún no creada). |
| `import_hash` | `VARCHAR(64)` NULLABLE | SHA-256 — solo presente si `source='import'`. |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

**Índices**:
- `ix_transactions_user_id`.
- `ix_transactions_category_id`.
- `uq_transactions_user_import_hash` UNIQUE PARTIAL `(user_id, import_hash) WHERE import_hash IS NOT NULL`.

### `import_jobs` (`PHASE-4.1`)

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → `users.id` `ON DELETE CASCADE` | índice. |
| `filename` | `VARCHAR(255)` | nombre original del fichero subido. |
| `status` | `ENUM('pending','processing','completed','failed')` | tipo `importjobstatus`. |
| `rows_total` | `INTEGER` | filas leídas del fichero. |
| `rows_ok` | `INTEGER` | transacciones efectivamente persistidas. |
| `rows_failed` | `INTEGER` | filas inválidas (validación). |
| `rows_skipped` | `INTEGER` | duplicados intra-batch + ya existentes en BD. |
| `column_mappings` | `JSONB` | mapping enviado en el upload. |
| `error_log` | `JSONB` | `[{ row, error }]`, capado a 100. |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

### `receipts` (`PHASE-5.1`)

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → `users.id` `ON DELETE CASCADE` | índice. |
| `status` | `ENUM('pending','confirmed','rejected')` | tipo `receiptstatus`. |
| `blob_key` | `VARCHAR(512)` | path en MinIO bucket `receipts`. |
| `content_type` | `VARCHAR(100)` | MIME type del original. |
| `extraction` | `JSON` | salida del modelo de visión (validada Pydantic antes de guardar). |
| `transaction_id` | `UUID` FK → `transactions.id` `ON DELETE SET NULL` | índice, nullable. Se rellena al confirmar. |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

No existe FK formal `transactions.receipt_id → receipts.id` (evita
ciclo bidireccional); la consistencia la garantiza
`receipts.service.confirm_receipt`.

### `exchange_rates` (`PHASE-8.1`)

| Columna | Tipo | Notas |
|---------|------|-------|
| `rate_date` | `DATE` | PK compuesta. |
| `base` | `CHAR(3)` | PK compuesta; siempre `'EUR'` por convención. |
| `quote` | `CHAR(3)` | PK compuesta. |
| `rate` | `NUMERIC(20, 8)` | precisión amplia; redondeo a 2 dec lo hace `currency.service.convert` con `ROUND_HALF_EVEN`. |
| `source` | `VARCHAR(32)` | `'frankfurter'` (default) / `'snapshot'` (seed inicial) / `'test'`. |
| `fetched_at` | `TIMESTAMPTZ` | `server_default=now()`. |

Sin `user_id`: las tasas son datos públicos globales (ECB), no
aplica aislamiento multi-tenant. Índice secundario
`ix_exchange_rates_quote_date(quote, rate_date)` para acelerar
"última tasa conocida para X en una ventana".

---

## Diagrama relacional

```
users ─┬─< refresh_tokens
       ├─< categories ──┐
       ├─< transactions ┘   (category_id ON DELETE SET NULL)
       ├─< import_jobs
       └─< receipts ──┐
                      │
                      └─→ transactions   (receipts.transaction_id ON DELETE SET NULL)

transactions.import_hash → unique partial index para deduplicar
                           imports sin afectar a manual/receipt.
transactions.receipt_id  → UUID sin FK formal (consistencia en service).
```

## Enums (PostgreSQL `CREATE TYPE`)

| Nombre | Valores |
|--------|---------|
| `categorykind` | `INCOME`, `EXPENSE` |
| `transactionsource` | `MANUAL`, `IMPORT`, `RECEIPT` |
| `importjobstatus` | `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED` |
| `receiptstatus` | `PENDING`, `CONFIRMED`, `REJECTED` |
