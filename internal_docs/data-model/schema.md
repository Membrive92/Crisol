# Schema de base de datos

> Estado actual del modelo de datos. Se actualiza cuando una fase
> introduce migraciones. Última actualización: PHASE-37.3 (head Alembic
> `c6s92u4rp6t5s1`).

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
| `a92f5b1c8d34` | 13.1 | `subscriptions` (detección de recurrentes) + enum `subscriptionstatus`. |
| `b32c8a4d5f17` | 15.2 | `subscriptionstatus` += `paused`, `cancelled`. |
| `c54e9b3a7d18` | 16   | `budgets.convert_other_currencies` (BOOLEAN, default FALSE) — opt-in para sumar gasto en otras monedas convertido. |
| `d72f1a5e8b29` | 17.1 | rename `subscriptions` → `fixed_expenses` (tabla, índices, enum `subscriptionstatus` → `fixedexpensestatus`). |
| `e8c34a9b1d52` | 17.2 | `fixed_expenses.auto_post` (BOOLEAN, default FALSE) + `transactionsource.expected`. |
| `f3a78b5c19d0` | 20   | `import_jobs.preview_payload` (JSONB nullable) — payload del wizard preview. |
| `g4b89c612e07` | 20   | Normalize enum casing — alinea `transactionsource` y `fixedexpensestatus` a UPPER (SA emite `name` del StrEnum). |
| `h5c92d703f18` | 19   | `bank_category_mappings` (`user_id, bank_concept_normalized, category_id` con UNIQUE). |
| `i6d83e4f29a5` | 20   | `category_rules` + enums `rulematchtype` y `rulefield`. |
| `j7e95d1b3f4c` | 21.2 | `accounts` + enums `accounttype`/`accountnature` + WIPE de transactions/import_jobs/receipts + `account_id` (NOT NULL en transactions, opcional en import_jobs y fixed_expenses). |
| `k8a92c4e7d5a1` | 21.3 | `transactions.transfer_pair_id` (FK auto-referente, NULLABLE, ON DELETE SET NULL) + index parcial `WHERE transfer_pair_id IS NOT NULL AND deleted_at IS NULL`. |
| `l9b03d5f8e6b2` | 22   | `accounts.apr` (NUMERIC(6,4) NULL) + `accounts.term_months` (INTEGER NULL) + `accounts.start_date` (DATE NULL) — campos opcionales del cuadro de amortización francés para loans/mortgages. |
| `m0c14e6a9f7c3` | 23   | `categorykind` += `TRANSFER` (value legacy, luego en desuso) + seed por nombre. |
| `n1d25f7ba0e8d4` | 23.1 | `categories.is_transfer` (BOOLEAN) + restaura `kind` original de las categorías `TRANSFER`. |
| `o2e36g8cb1f9d5` | 24.1 | `liability_installments` (cuotas persistidas) + backfill con `build_schedule`. |
| `p3f47h9dc2g0e6` | 24.2 | `accounts.tae` (NUMERIC(6,4) NULL). |
| `q4g58i0ed3h1f7` | 24.3 | `accounts.total_to_pay` + `accounts.interest_only_first_payment` (NUMERIC(14,2) NULL). |
| `r5h69j1fe4i2g8` | 31.1 | Seed `Transferencia a favor` (INCOME, is_transfer) + recategoriza tx entrantes mal clasificadas. |
| `s6i70k2gf5j3h9` | 30.1 | `categories.role` + enum `categoryrole` + índice parcial `ix_categories_role_debt`. |
| `t7j81l3hg6k4i0` | 30.4 | `accounts.category_id` (FK SET NULL) + índice parcial `ix_accounts_category_id`. |
| `u8k92m4ih7l5j1` | AUDIT-2026-05 | refresh tokens auto-identificables: `refresh_tokens.token_id` (UNIQUE) + `family_id` (índice). Invalida sesiones previas (DELETE). |
| `v9l14n6kj8m7l3` | AUDIT-2026-05 | `ix_transactions_user_occurred_active` PARTIAL `(user_id, occurred_at) WHERE deleted_at IS NULL`. |
| `w0m25o7lk9n8m4` | 32   | `accounts.is_default` (BOOLEAN NOT NULL DEFAULT FALSE) — cuenta principal. |
| `x1n36p8ml0o9n5` | AUDIT-2026-05 | `CHECK (rate > 0)` en `exchange_rates` (`ck_exchange_rates_rate_positive`, NOT VALID + VALIDATE). |
| `y2o47q9nm1p0o6` | 32   | Índice único parcial `uq_accounts_one_default_per_user` `(user_id) WHERE is_default`. |
| `z3p58r0on2q1p7` | 34.1 | `transactions.flow` + enum `transactionflow` + índice parcial `ix_transactions_user_flow_active` (backfill por categoría, equivalencia). |
| `a4q70s2pn4r3q9` | 35   | `accounts.parent_account_id` (FK auto-ref CASCADE) + índice parcial `ix_accounts_parent_account_id`. |
| `b5r81t3qo5s4r0` | AUDIT-2026-07 | `transactions.absorbed_as_mirror` (BOOLEAN NOT NULL DEFAULT FALSE) — cargo espejo absorbido. |
| `c6s92u4rp6t5s1` | 37.3 | `transactions.is_exceptional` (BOOLEAN NULL) — override estructural/puntual. |
| `d7t03v5sq7u6t2` | 39   | `transactions.statement_balance` (NUMERIC(14,2) NULL) + `accounts.anchored_statement_balance` (NUMERIC(14,2) NULL) — saldo del extracto por movimiento + ancla persistida del saldo real. |
| `d4e15f9a3b7c62` | 44.9 | `analysis_runs.thresholds_used` (JSONB NOT NULL DEFAULT `'{}'`) — los cortes EFECTIVOS del run. Aditiva y reversible. |
| `f2b84a6c1d9e73` | 44.14 | `listing_directory` (GLOBAL, PK `(isin, mic)`) + extensión `pg_trgm` + índice GIN sobre `name` — el directorio oficial UE/UK de FIRDS. Aditiva y reversible (el downgrade tira la tabla; la extensión se queda, porque desinstalarla en un downgrade parcial rompería a quien la use). |

> **Deuda documental**: las 14 tablas del módulo Inversión (13 de PHASE-44.1 más
> `listing_directory` de 44.14) y las migraciones intermedias entre
> `d7t03v5sq7u6t2` y `cc3d69e1f4a8b2` no están recogidas en esta tabla. Su modelo
> vive en las phase docs
> ([44.1](../phases/phase-44.1-investment-foundations.md),
> [44.14](../phases/phase-44.14-eu-uk-listing-directory.md)) y en los ADR
> [`0007`](../decisions/0007-investment-global-tables.md) y
> [`0010`](../decisions/0010-identity-official-registers.md). El head real se
> consulta SIEMPRE con `alembic heads`, nunca por el nombre del fichero
> (lección PHASE-44.1).

### `analysis_runs.thresholds_used` (PHASE-44.9)

Por qué una columna y no una referencia a `scoring_thresholds`: esa tabla tiene
la unique `(sector, accounting_std, metric_key)` **sin versión ni vigencia** y el
seed **muta la fila existente in situ**, así que la calibración con la que se
juzgó un run pasado desaparece al resembrar. `thresholds_version` es un SHA-256:
sirve para DETECTAR que dos runs se midieron distinto, nunca para reconstruir
cómo. Sin esta columna, la pantalla no puede decir «6,8× frente a un mínimo de
6». Va en columna propia y no dentro de `verdict` porque son dos cosas
ortogonales — el dictamen y la vara de medir (lección PHASE-23.1).

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

### `refresh_tokens` (`PHASE-1.1`, ampliada en AUDIT-2026-05)

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → `users.id` `ON DELETE CASCADE` | índice. |
| `token_hash` | `VARCHAR(512)` UNIQUE | SHA-256 del refresh token. |
| `token_id` | `VARCHAR(64)` UNIQUE | AUDIT-2026-05 (migración `u8k92m4ih7l5j1`), indexado. Identificador público (parte izquierda de `<token_id>.<secret>`); localiza la fila con una query + un solo argon2 verify. |
| `family_id` | `UUID` | AUDIT-2026-05 (migración `u8k92m4ih7l5j1`), indexado. Linaje de rotación: reutilizar un token revocado revoca toda la familia. |
| `expires_at` | `TIMESTAMPTZ` | 7 días. |
| `revoked` | `BOOLEAN` | rotación marca el viejo. |
| `created_at` | `TIMESTAMPTZ` | |

### `webauthn_credentials` (`PHASE-1.1`)

Passkeys registradas (Touch ID / Windows Hello / llaves físicas). Sólo se
guarda la clave pública; la privada nunca sale del dispositivo. Migración
`d18a4c75b2e9`.

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → `users.id` `ON DELETE CASCADE` | índice. |
| `credential_id` | `BYTEA` UNIQUE | identificador que envía el navegador al autenticar. |
| `public_key` | `BYTEA` | clave pública de la credencial. |
| `sign_count` | `INTEGER` | default `0`. Detección de clones (si baja, alerta). |
| `transports` | `VARCHAR(100)` NULLABLE | CSV de transports (usb, nfc, ble, internal, hybrid). |
| `label` | `VARCHAR(100)` NULLABLE | etiqueta opcional del dispositivo. |
| `created_at` | `TIMESTAMPTZ` | `now()`. |
| `last_used_at` | `TIMESTAMPTZ` NULLABLE | |

### `webauthn_challenges` (`PHASE-1.1`)

Challenge efímero de un flujo de registro/autenticación. Migraciones
`d18a4c75b2e9` + `b27e391fa4c8` (`user_id` nullable para Conditional UI).

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → `users.id` `ON DELETE CASCADE` | NULLABLE (Conditional UI sin email), índice. |
| `challenge` | `BYTEA` | reto emitido. |
| `purpose` | `VARCHAR(20)` | `register` o `authenticate`. |
| `expires_at` | `TIMESTAMPTZ` | expiración. |
| `created_at` | `TIMESTAMPTZ` | `now()`. |

### `categories` (`PHASE-2.1`)

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → `users.id` `ON DELETE CASCADE` | índice. |
| `name` | `VARCHAR(100)` | |
| `icon` | `VARCHAR(50)` NULLABLE | identificador de icono (frontend lo resuelve). |
| `color` | `VARCHAR(7)` NULLABLE | hex `#RRGGBB`. |
| `kind` | `ENUM('income','expense')` | tipo `categorykind`. |
| `is_transfer` | `BOOLEAN` | NOT NULL, default `FALSE` (PHASE-23.1, migración `n1d25f7ba0e8d4`). TRUE = transferencia interna: fuera del cashflow pero conserva el signo del `kind` en el saldo (separa exclusión y signo — lección PHASE-23.1). |
| `role` | `ENUM('GENERIC','TRANSFER','DEBT_PAYMENT','DEBT_INTEREST')` | tipo `categoryrole`, NOT NULL, default `GENERIC` (PHASE-30.1, migración `s6i70k2gf5j3h9`). Rol semántico; los callers de deuda filtran por `role IN (DEBT_PAYMENT, DEBT_INTEREST)`. Índice parcial `ix_categories_role_debt`. Backfill deriva de `is_transfer` + nombres del seed. |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

### `transactions` (`PHASE-2.1` + `PHASE-4.1` + `PHASE-10.1` + `PHASE-21.3` + `PHASE-34` + `PHASE-37.3` + `PHASE-39`)

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → `users.id` `ON DELETE CASCADE` | índice. |
| `category_id` | `UUID` FK → `categories.id` `ON DELETE SET NULL` | índice, nullable. |
| `amount` | `NUMERIC(14,2)` | siempre positivo. El signo lo deciden `flow` + `account.nature` (PHASE-34 / ADR-0004), ya no `category.kind`. |
| `currency` | `CHAR(3)` | ISO 4217. Default `EUR`. |
| `occurred_at` | `TIMESTAMPTZ` | fecha de la transacción. |
| `description` | `TEXT` NULLABLE | |
| `source` | `ENUM('manual','import','receipt','expected')` | tipo `transactionsource`. `expected` (PHASE-17.2) lo emite el autoposteo de gastos fijos. |
| `receipt_id` | `UUID` NULLABLE | (PHASE-5.1, FK aún no creada). |
| `import_hash` | `VARCHAR(64)` NULLABLE | SHA-256 — solo presente si `source='import'`. |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |
| `deleted_at` | `TIMESTAMPTZ` NULLABLE | PHASE-10.1. NULL = activa, timestamp = en papelera. |
| `transfer_pair_id` | `UUID` FK → `transactions.id` `ON DELETE SET NULL` | NULLABLE (PHASE-21.3, migración `k8a92c4e7d5a1`). Enlace a la otra pata de una transferencia interna entre cuentas; NULL = movimiento normal. Índice parcial `ix_transactions_transfer_pair_id`. |
| `flow` | `ENUM('IN','OUT','TRANSFER_IN','TRANSFER_OUT')` NULLABLE | tipo `transactionflow` (PHASE-34.1, migración `z3p58r0on2q1p7`, ADR-0004). Fuente de verdad del dinero: saldo y cashflow derivan de `flow` + `account.nature`, no de la categoría. NULL = sin clasificar (contribuye 0). Índice parcial `ix_transactions_user_flow_active`. |
| `absorbed_as_mirror` | `BOOLEAN` | NOT NULL, default `FALSE` (AUDIT-2026-07 H-04, migración `b5r81t3qo5s4r0`). TRUE = "cargo espejo" (ADEUDO/liquidación de tarjeta) que el sistema soft-borró al convertir una compra en deuda; el dedup de imports lo trata como existente para no resucitarlo. |
| `is_exceptional` | `BOOLEAN` NULLABLE | PHASE-37.3, migración `c6s92u4rp6t5s1`. Override manual estructural/puntual del gasto: NULL = heurística, TRUE = puntual (one-off), FALSE = estructural. |
| `statement_balance` | `NUMERIC(14,2)` NULLABLE | PHASE-39, migración `d7t03v5sq7u6t2`. Saldo de la cuenta según el EXTRACTO tras este movimiento (columna "Saldo" del fichero). Firmado (puede ser 0 o negativo). NULL para tx manuales o imports sin esa columna. Informativo/auditable: NO participa en el cálculo del saldo; alimenta el auto-anclaje del `opening_balance` y NO entra en el `import_hash` (re-imports idempotentes que backfillean el saldo en filas duplicadas). |

**Índices**:
- `ix_transactions_user_id`.
- `ix_transactions_category_id`.
- `ix_transactions_user_id_active` PARTIAL `(user_id) WHERE deleted_at IS NULL` (PHASE-10.1).
- `ix_transactions_user_occurred_active` PARTIAL `(user_id, occurred_at) WHERE deleted_at IS NULL` (AUDIT-2026-05) — cubre listados ordenados por fecha + rangos `occurred_at <= X` de dashboard/drill-down/debt-history (el btree ascendente sirve el `ORDER BY … DESC` con scan hacia atrás).
- `uq_transactions_user_import_hash` UNIQUE PARTIAL `(user_id, import_hash) WHERE import_hash IS NOT NULL AND deleted_at IS NULL` — el `AND deleted_at IS NULL` (PHASE-10.1) permite re-importar una fila cuya versión previa fue trasheada.

### `import_jobs` (`PHASE-4.1`)

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → `users.id` `ON DELETE CASCADE` | índice. |
| `filename` | `VARCHAR(255)` | nombre original del fichero subido. |
| `status` | `ENUM('pending','processing','preview','completed','failed')` | tipo `importjobstatus`. `preview` = flujo en dos pasos (POST /imports/preview → commit). |
| `rows_total` | `INTEGER` | filas leídas del fichero. |
| `rows_ok` | `INTEGER` | transacciones efectivamente persistidas. |
| `rows_failed` | `INTEGER` | filas inválidas (validación). |
| `rows_skipped` | `INTEGER` | duplicados intra-batch + ya existentes en BD. |
| `column_mappings` | `JSONB` | mapping enviado en el upload. |
| `error_log` | `JSONB` | `[{ row, error }]`, capado a 100. |
| `preview_payload` | `JSONB` NULLABLE | PHASE-20 (migración `f3a78b5c19d0`). Filas parseadas + metadata del wizard preview para el commit posterior; NULL en jobs directos/antiguos. |
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

### `accounts` (`PHASE-21.2`, ampliada en `PHASE-22`, `PHASE-24.2/24.3`, `PHASE-30.4`, `PHASE-32`, `PHASE-35`)

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK `users(id) ON DELETE CASCADE` | índice. |
| `name` | `VARCHAR(100)` | único case-insensible por usuario (validado en service). |
| `type` | `accounttype` | `BANK`, `SAVINGS`, `BROKERAGE`, `CRYPTO`, `CASH` (assets) + `CREDIT_CARD`, `LOAN`, `MORTGAGE` (liabilities, PHASE-22). |
| `nature` | `accountnature` | `ASSET` o `LIABILITY`. Se asigna automáticamente según `type` en el service (PHASE-22). |
| `currency` | `VARCHAR(3)` | ISO 4217. Default `'EUR'`. |
| `color` | `VARCHAR(7)` | hex `#RRGGBB`, opcional. |
| `icon` | `VARCHAR(50)` | emoji, opcional. |
| `opening_balance` | `NUMERIC(14, 2)` | default `0`. Saldo inicial declarado. Para liabilities representa la deuda inicial (positivo = se debe). |
| `opening_balance_date` | `DATE` | opcional. Desde PHASE-39 es la FECHA DEL ANCLA de saldo (la sella "Cuadrar saldo" manual con hoy, o el auto-anclaje de imports con la fecha del extracto). |
| `anchored_statement_balance` | `NUMERIC(14, 2)` NULLABLE | PHASE-39, migración `d7t03v5sq7u6t2`. Saldo REAL declarado en el último anclaje, a fecha `opening_balance_date`. Permite re-derivar `opening_balance` cuando se importa historia anterior al ancla, preservando `saldo(fecha_ancla) == anchored_statement_balance`. |
| `apr` | `NUMERIC(6, 4)` | opcional (PHASE-22). Tasa **anual** como decimal (`0.035` = 3.5%). Sólo relevante en loans/mortgages/credit_cards. |
| `term_months` | `INTEGER` | opcional (PHASE-22). Plazo del cuadro francés. Sólo relevante en loans/mortgages. |
| `start_date` | `DATE` | opcional (PHASE-22). Fecha de inicio del cuadro francés. Sólo relevante en loans/mortgages. |
| `tae` | `NUMERIC(6, 4)` NULLABLE | opcional (PHASE-24.2, migración `p3f47h9dc2g0e6`). TAE informativa (regulación ES); no afecta al cálculo, que usa `apr` como TIN. |
| `total_to_pay` | `NUMERIC(14, 2)` NULLABLE | opcional (PHASE-24.3, migración `q4g58i0ed3h1f7`). "Total a pagar" del contrato; la diferencia con `Σ(cuotas) + interest_only_first_payment` aflora como cargos extra. |
| `interest_only_first_payment` | `NUMERIC(14, 2)` NULLABLE | opcional (PHASE-24.3, migración `q4g58i0ed3h1f7`). Primera cuota especial sólo de intereses cuando el contrato no arranca en fecha de cuota. |
| `category_id` | `UUID` FK → `categories.id` `ON DELETE SET NULL` | opcional (PHASE-30.4, migración `t7j81l3hg6k4i0`). Categoría de pagos vinculada; sólo en liabilities cuya categoría tenga `role IN (DEBT_PAYMENT, DEBT_INTEREST)`. Índice parcial `ix_accounts_category_id`. |
| `parent_account_id` | `UUID` FK → `accounts.id` `ON DELETE CASCADE` | opcional (PHASE-35, migración `a4q70s2pn4r3q9`). Tarjeta padre cuando la cuenta es una compra a plazos; NULL = cuenta normal. Índice parcial `ix_accounts_parent_account_id`. |
| `display_order` | `INTEGER` | default `0`. Orden en UI. |
| `is_archived` | `BOOLEAN` | default `FALSE`. Si TRUE, oculta del selector pero conserva histórico. |
| `is_default` | `BOOLEAN` | default `FALSE` (PHASE-32, migración `w0m25o7lk9n8m4`). Cuenta principal del usuario, pre-seleccionada en formularios. Única por usuario (la fuerza el service, sin constraint en BD). Su saldo refleja ahorro neto (ver excepción abajo). |
| `created_at`/`updated_at` | `TIMESTAMPTZ` | `now()`. |

`transactions.account_id` (NOT NULL, FK CASCADE),
`import_jobs.account_id` (nullable, FK SET NULL) y
`fixed_expenses.account_id` (nullable, FK SET NULL) referencian
esta tabla.

**Inversión de signo en saldos (PHASE-22)**: la query
`get_balances_for_user` calcula el `signed_amount` con un CASE que
tiene en cuenta `nature` y `Category.kind`:

- `is_default` + `is_transfer` → `0` (PHASE-32: la cuenta principal
  refleja ahorro neto; las transferencias internas no la mueven). Se
  evalúa ANTES que los casos de abajo.
- `LIABILITY` + `EXPENSE` → `+amount` (la compra sube la deuda)
- `LIABILITY` + `INCOME` → `-amount` (un pago la baja)
- `ASSET` + `EXPENSE` → `-amount`
- `ASSET` + `INCOME` → `+amount`

Esto permite tratar tarjetas de crédito como cuenta con saldo
arrastrado (cada compra suma deuda, cada pago la resta) sin invertir
las transacciones en sí. El resto de cuentas (no `is_default`) sí
suma las transferencias internas a su saldo individual (modo cash,
PHASE-23.1).

### `liability_installments` (`PHASE-24.1`)

Cuotas persistidas y editables del cuadro de amortización francés de una
liability (`loan`/`mortgage`, y `credit_card` financiada). Antes calculado
en vivo; desde PHASE-24.1 se materializa para permitir overrides puntuales
y marcar cuotas como pagadas.

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → `users.id` `ON DELETE CASCADE` | índice. |
| `account_id` | `UUID` FK → `accounts.id` `ON DELETE CASCADE` | índice. |
| `installment_index` | `INTEGER` | 1..term_months. Orden en la UI. |
| `due_date` | `DATE` | vencimiento de la cuota. |
| `payment` | `NUMERIC(14,2)` | importe total de la cuota. |
| `interest` | `NUMERIC(14,2)` | parte de intereses. |
| `principal` | `NUMERIC(14,2)` | parte de capital. |
| `remaining_balance` | `NUMERIC(14,2)` | capital vivo tras la cuota. |
| `paid_at` | `TIMESTAMPTZ` NULLABLE | NULL = pendiente, timestamp = pagada. |
| `paid_transaction_id` | `UUID` FK → `transactions.id` `ON DELETE SET NULL` | tx del extracto que liquidó la cuota (informativo). |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

UNIQUE `(account_id, installment_index)` (`uq_liability_installments_account_index`)
— una cuota N por cuenta; permite UPSERT al regenerar el cuadro. Migración
`o2e36g8cb1f9d5` (backfill con `build_schedule` para liabilities con
apr+term_months+start_date+opening_balance>0). Las ediciones son overrides
puntuales — no recomputan las cuotas siguientes.

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
       ├─< category_rules ── (category_id ON DELETE CASCADE)
       └─< liability_installments ─┬ (account_id ON DELETE CASCADE)
                                   └ (paid_transaction_id → transactions.id ON DELETE SET NULL)

accounts.parent_account_id     → FK auto-referente ON DELETE CASCADE
                                  (compras a plazos agrupadas bajo su tarjeta, PHASE-35).
accounts.category_id           → FK → categories.id ON DELETE SET NULL
                                  (liability ↔ categoría de pagos, PHASE-30.4).
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
| `accounttype` | `BANK`, `SAVINGS`, `BROKERAGE`, `CRYPTO`, `CASH`, `CREDIT_CARD`, `LOAN`, `MORTGAGE` (los 3 últimos = liabilities, activos desde PHASE-22). |
| `accountnature` | `ASSET`, `LIABILITY` (activa desde PHASE-22). |
| `rulematchtype` | `EXACT`, `CONTAINS`, `STARTS_WITH`, `REGEX` |
| `rulefield` | `CONCEPT`, `DESCRIPTION`, `BOTH` |
| `transactionflow` | `IN`, `OUT`, `TRANSFER_IN`, `TRANSFER_OUT` (PHASE-34.1, migración `z3p58r0on2q1p7`) |
| `categoryrole` | `GENERIC`, `TRANSFER`, `DEBT_PAYMENT`, `DEBT_INTEREST` (PHASE-30.1, migración `s6i70k2gf5j3h9`) |
| `fixedexpensestatus` | `PENDING`, `CONFIRMED`, `PAUSED`, `CANCELLED`, `DISMISSED` (rename desde `subscriptionstatus`, migración `d72f1a5e8b29`) |

---

## Módulo Inversión — las 14 tablas (PHASE-44.1 … 44.14)

Llevaban desde 44.1 fuera de este documento. La partición GLOBAL / SCOPED es la
decisión del [ADR-0007](../decisions/0007-investment-global-tables.md): la
identidad de un valor de mercado y sus cuentas publicadas son **objetivas**, así
que duplicarlas por usuario no tiene sentido; lo que es del usuario es su
cartera y sus análisis.

| Tabla | Ámbito | PK | FK | Qué guarda |
|---|---|---|---|---|
| `securities` | GLOBAL | `id` | — | Identidad del valor: ticker, plaza, CIK, ISIN, sector, norma contable, divisa, `is_financial`/`is_reit` y `analysis_status`. Unique `(ticker, exchange)`. |
| `listing_directory` | GLOBAL | `(isin, mic)` | — | Directorio oficial UE/UK de FIRDS (ESMA + FCA). Índice GIN trigram sobre `name`. [ADR-0010](../decisions/0010-identity-official-registers.md). |
| `financial_statements` | GLOBAL | `id` | `securities` | Las 49 partidas canónicas por ejercicio, más `raw_source_ref` (trazas de mapeo, procedencia y banderas de calidad). |
| `restatement_flags` | GLOBAL | `id` | `securities` | Reexpresiones detectadas entre filings del mismo ejercicio. |
| `scoring_thresholds` | GLOBAL | `id` | — | Cortes por `(sector, accounting_std, metric_key)`. `model_variant='uncalibrated'` para IFRS/PGC. |
| `price_quotes` | GLOBAL | `id` | `securities` | Última cotización con su divisa **del proveedor** (no la del catálogo) y su `as_of`. |
| `ingestion_jobs` | SCOPED | `id` | `securities`, `users` | Job de descarga EDGAR, con estado y error legible. |
| `analysis_runs` | SCOPED | `id` | `securities`, `users` | Un run del motor: scores, veredicto, banderas, `engine_version`, `thresholds_version` y `thresholds_used`. Inmutable. |
| `inv_lots` | SCOPED | `id` | `securities`, `accounts`, `users` | Compras: cantidad, precio, comisiones y `fx_rate_at_trade`. |
| `inv_sales` | SCOPED | `id` | `securities`, `users` | Ventas, que consumen lotes por FIFO. |
| `inv_sale_allocations` | GLOBAL* | `id` | `inv_lots`, `inv_sales` | Qué lote pagó qué venta. *Sin `user_id` propio: cuelga de filas que ya lo tienen. |
| `inv_dividends_received` | SCOPED | `id` | `securities`, `users` | Dividendos cobrados, brutos y netos de retención. |
| `inv_corporate_actions` | SCOPED | `id` | `securities`, `users` | Splits, stock dividends (y `spinoff`/`return_of_capital`, registrables pero aún no aplicables). |
| `inv_lot_adjustments` | GLOBAL* | `id` | `inv_lots`, `inv_corporate_actions` | Rastro auditable y reversible de cómo una acción corporativa modificó un lote. |

### Enums del módulo

| Nombre | Valores |
|--------|---------|
| `accountingstd` | `GAAP`, `IFRS`, `PGC` |
| `securitytype` | `STOCK`, `ADR`, `ETF` |
| `sectorinternal` | `technology`, `healthcare`, `financials`, `consumer_staples`, `consumer_discretionary`, `industrials`, `energy`, `materials`, `utilities`, `real_estate`, `communication`, `unknown` |
| `periodtype` | `ANNUAL`, `QUARTERLY` |
| `statementsource` | `EDGAR_XBRL`, `MANUAL` |
| `thresholddirection` | `lower_better`, `higher_better`, `band` |
| `corpactiontype` | `split`, `spinoff`, `stock_dividend`, `return_of_capital` |
| `jobstatus` | `pending`, `running`, `done`, `failed` |

`securities.analysis_status` **no** es un enum nativo sino `String(16)`
(`ok` · `no_annual` · `non_gaap` · `not_supported` · NULL): el conjunto va a
crecer y un `ALTER TYPE ADD VALUE` no es reversible en un `downgrade` limpio.
Su traducción vive en `catalog/capabilities.py`, fuente única de la regla.
