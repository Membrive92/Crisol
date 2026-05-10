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
| `e4f7c91a8b3d` | 10.1 | `transactions.deleted_at` + partial index `ix_transactions_user_id_active` + recreado `uq_transactions_user_import_hash` con `AND deleted_at IS NULL`. |
| `f8b3c91d4e22` | 12.1 | `budgets` (presupuestos mensuales por categoría) + índices por `user_id` y `category_id`. |
| `c54e9b3a7d18` | 16   | `budgets.convert_other_currencies` (BOOLEAN, default FALSE) — opt-in para sumar gasto en otras monedas convertido. |
| `d72f1a5e8b29` | 17.1 | rename `subscriptions` → `fixed_expenses` (tabla, índices, enum `subscriptionstatus` → `fixedexpensestatus`). |
| `e8c34a9b1d52` | 17.2 | `fixed_expenses.auto_post` (BOOLEAN, default FALSE) + `transactionsource.expected`. |
| `f3a78b5c19d0` | 20   | `import_jobs.preview_payload` (JSONB nullable) — payload del wizard preview. |
| `g4b89c612e07` | 20   | Normalize enum casing — alinea `transactionsource` y `fixedexpensestatus` a UPPER (SA emite `name` del StrEnum). |
| `h5c92d703f18` | 19   | `bank_category_mappings` (`user_id, bank_concept_normalized, category_id` con UNIQUE). |
| `i6d83e4f29a5` | 20   | `category_rules` + enums `rulematchtype` y `rulefield`. |
| `j7e95d1b3f4c` | 21.2 | `accounts` + enums `accounttype`/`accountnature` + WIPE de transactions/import_jobs/receipts + `account_id` (NOT NULL en transactions, opcional en import_jobs y fixed_expenses). |
| `k8a92c4e7d5a1` | 21.3 | `transactions.transfer_pair_id` (FK auto-referente, NULLABLE, ON DELETE SET NULL) + index parcial `WHERE transfer_pair_id IS NOT NULL AND deleted_at IS NULL`. |

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

### `transactions` (`PHASE-2.1` + `PHASE-4.1` + `PHASE-10.1`)

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
| `deleted_at` | `TIMESTAMPTZ` NULLABLE | PHASE-10.1. NULL = activa, timestamp = en papelera. |

**Índices**:
- `ix_transactions_user_id`.
- `ix_transactions_category_id`.
- `ix_transactions_user_id_active` PARTIAL `(user_id) WHERE deleted_at IS NULL` (PHASE-10.1).
- `uq_transactions_user_import_hash` UNIQUE PARTIAL `(user_id, import_hash) WHERE import_hash IS NOT NULL AND deleted_at IS NULL` — el `AND deleted_at IS NULL` (PHASE-10.1) permite re-importar una fila cuya versión previa fue trasheada.

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

### `budgets` (`PHASE-12.1`)

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → `users.id` `ON DELETE CASCADE` | índice. |
| `category_id` | `UUID` FK → `categories.id` `ON DELETE SET NULL` | índice, nullable. NULL = budget global del mes. |
| `amount` | `NUMERIC(14,2)` | límite mensual. |
| `currency` | `CHAR(3)` | ISO 4217. Default `EUR`. |
| `effective_from` | `DATE` | cuándo empieza a aplicar. |
| `effective_to` | `DATE` NULLABLE | NULL = vigente. |
| `convert_other_currencies` | `BOOLEAN` | default `FALSE`. PHASE-16. Si `TRUE`, el SUM de status convierte txs en otras monedas a `currency` con `converted_amount_expr` (tasa del día de la tx); las txs sin tasa se cuentan en `unconvertible_count` de la respuesta. |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

**Índices**:
- `ix_budgets_user_id`.
- `ix_budgets_category_id`.

Política "uno activo por (user, category)" se valida en service
(409 en POST si hay otro con `effective_to IS NULL OR >= today`).
Sin unique constraint en BD por flexibilidad futura (overlapping
budgets parciales / temporales).

### `fixed_expenses` (`PHASE-13.1`, renombrado en `PHASE-17.1`)

Antes `subscriptions`. Renombrado para reflejar que el área cubre
cualquier gasto recurrente con cantidad estable (suscripciones,
hipotecas, préstamos, gym, seguros…).

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → `users.id` `ON DELETE CASCADE` | índice. |
| `merchant` | `VARCHAR(60)` | normalizado (lowercase + alfanumérico, 30 chars). Parte de la huella. |
| `raw_description` | `TEXT` | sample legible para mostrar al usuario. |
| `amount` | `NUMERIC(14,2)` | parte de la huella. |
| `currency` | `CHAR(3)` | parte de la huella. |
| `cadence_days` | `INTEGER` | 7 / 14 / 30 / 90 / 180 / 365 (canónico). Parte de la huella. |
| `next_due` | `DATE` | `last_seen_at + cadence_days`. |
| `status` | `ENUM('pending','confirmed','paused','cancelled','dismissed')` | tipo `fixedexpensestatus`. Default `pending`. |
| `category_id` | `UUID` FK → `categories.id` `ON DELETE SET NULL` | sugerida (la más común entre los matches). |
| `first_seen_at` / `last_seen_at` | `DATE` | rango observado del patrón. |
| `occurrence_count` | `INTEGER` | nº de transacciones que matchean. |
| `confidence` | `FLOAT` | `1 - std/mean` clamped [0,1]. |
| `auto_post` | `BOOLEAN` | default `FALSE`. PHASE-17.2. Si `TRUE` y `status=confirmed`, el cron diario crea una tx `source=expected` cuando `next_due ≤ today` y avanza `next_due += cadence_days`. |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

**Índices**:
- `ix_fixed_expenses_user_id`.
- `ix_fixed_expenses_merchant`.
- `ix_fixed_expenses_status`.

Política de re-detección: el service busca por huella (merchant +
amount + currency + cadence). Match → refresca datos derivados sin
tocar `status`/`category_id`. No match → crea como `pending`. Una
`dismissed` con misma huella sólo se refresca → no se vuelve a
sugerir al usuario.

### `bank_category_mappings` (`PHASE-19`)

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK `users(id) ON DELETE CASCADE` | índice. |
| `bank_concept_normalized` | `VARCHAR(255)` | `casefold()` + trim aplicado por el service. |
| `category_id` | `UUID` FK `categories(id) ON DELETE CASCADE` | |
| `created_at`/`updated_at` | `TIMESTAMPTZ` | `now()`. |

UNIQUE `(user_id, bank_concept_normalized)` — un concepto sólo
mapea a una categoría por usuario. UPSERT silencioso: si el
usuario reasigna el concepto en un import posterior, el mapping
se actualiza sin conflicto.

### `category_rules` (`PHASE-20`)

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK `users(id) ON DELETE CASCADE` | índice. |
| `pattern` | `VARCHAR(255)` | el "qué" matchear. |
| `match_type` | `rulematchtype` | `EXACT`, `CONTAINS`, `STARTS_WITH`, `REGEX`. |
| `field` | `rulefield` | `CONCEPT`, `DESCRIPTION`, `BOTH`. |
| `category_id` | `UUID` FK `categories(id) ON DELETE CASCADE` | |
| `priority` | `INTEGER` | `default 100`. Las reglas del seed van 10-79; las custom 100. Menor número = más prioridad. |
| `enabled` | `BOOLEAN` | `default TRUE`. |
| `created_at`/`updated_at` | `TIMESTAMPTZ` | `now()`. |

UNIQUE `(user_id, pattern, match_type, field, category_id)` — el
mismo patrón puede mapear a categorías distintas si difiere algún
otro campo, pero no se duplica la combinación exacta.

### `accounts` (`PHASE-21.2`)

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK `users(id) ON DELETE CASCADE` | índice. |
| `name` | `VARCHAR(100)` | único case-insensible por usuario (validado en service). |
| `type` | `accounttype` | `BANK`, `SAVINGS`, `BROKERAGE`, `CRYPTO`, `CASH` (PHASE-21.2) + `CREDIT_CARD`, `LOAN`, `MORTGAGE` reservados para PHASE-22. |
| `nature` | `accountnature` | `ASSET` (default) o `LIABILITY` (reservado). |
| `currency` | `VARCHAR(3)` | ISO 4217. Default `'EUR'`. |
| `color` | `VARCHAR(7)` | hex `#RRGGBB`, opcional. |
| `icon` | `VARCHAR(50)` | emoji, opcional. |
| `opening_balance` | `NUMERIC(14, 2)` | default `0`. Saldo inicial declarado. |
| `opening_balance_date` | `DATE` | opcional. |
| `display_order` | `INTEGER` | default `0`. Orden en UI. |
| `is_archived` | `BOOLEAN` | default `FALSE`. Si TRUE, oculta del selector pero conserva histórico. |
| `created_at`/`updated_at` | `TIMESTAMPTZ` | `now()`. |

`transactions.account_id` (NOT NULL, FK CASCADE),
`import_jobs.account_id` (nullable, FK SET NULL) y
`fixed_expenses.account_id` (nullable, FK SET NULL) referencian
esta tabla.

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
       ├─< categories ──┬───────────────┐
       ├─< accounts ─┐  │               │
       ├─< transactions ┴── (account_id NOT NULL CASCADE)
       │              └── (category_id ON DELETE SET NULL)
       │              └── (transfer_pair_id → transactions.id ON DELETE SET NULL)
       ├─< import_jobs ── (account_id ON DELETE SET NULL)
       ├─< receipts ──┐
       │              └─→ transactions (receipts.transaction_id ON DELETE SET NULL)
       ├─< budgets ── (category_id ON DELETE SET NULL)
       ├─< fixed_expenses ── (account_id, category_id ON DELETE SET NULL)
       ├─< bank_category_mappings ── (category_id ON DELETE CASCADE)
       └─< category_rules ── (category_id ON DELETE CASCADE)

transactions.import_hash       → unique partial index para deduplicar
                                  imports sin afectar a manual/receipt.
transactions.receipt_id        → UUID sin FK formal (consistencia en service).
transactions.transfer_pair_id  → FK auto-referente bidireccional;
                                  partial index WHERE NOT NULL AND deleted_at NULL.
                                  Las txs con valor se EXCLUYEN de cashflow,
                                  donut, top-expenses y budgets.
```

## Enums (PostgreSQL `CREATE TYPE`)

| Nombre | Valores |
|--------|---------|
| `categorykind` | `INCOME`, `EXPENSE` |
| `transactionsource` | `MANUAL`, `IMPORT`, `RECEIPT`, `EXPECTED` |
| `importjobstatus` | `PENDING`, `PROCESSING`, `PREVIEW`, `COMPLETED`, `FAILED` |
| `receiptstatus` | `PENDING`, `CONFIRMED`, `REJECTED` |
| `accounttype` | `BANK`, `SAVINGS`, `BROKERAGE`, `CRYPTO`, `CASH`, `CREDIT_CARD`, `LOAN`, `MORTGAGE` (los 3 últimos reservados para PHASE-22). |
| `accountnature` | `ASSET`, `LIABILITY` (la última reservada). |
| `rulematchtype` | `EXACT`, `CONTAINS`, `STARTS_WITH`, `REGEX` |
| `rulefield` | `CONCEPT`, `DESCRIPTION`, `BOTH` |
