# PHASE-21.2 — Cuentas declaradas + onboarding bloqueante + account_id obligatorio

**Estado**: ✅ completada
**Rama**: directo a `main`
**Commit**: `b585ec1`
**Fecha de merge**: 2026-05-10

## Objetivo

Modelar las cuentas reales del usuario (corriente, ahorro, broker,
cripto, efectivo) como entidad de primera clase y exigir que cada
transacción se impute a una cuenta. Esto desbloquea PHASE-21.3
(transferencias internas y saldo por cuenta) y prepara el terreno
para PHASE-22 (cuentas tipo `liability`: deuda).

Acordado con el usuario: migración **dura** con wipe de
`transactions`/`import_jobs`/`receipts` para que `account_id` pueda
ser `NOT NULL` desde el día uno.

## Qué se implementó

### Backend — módulo `accounts`

`backend/app/modules/personal_finance/accounts/`:

- **`models.py`** — tabla `accounts` con `(id, user_id, name, type,
  nature, currency, color, icon, opening_balance,
  opening_balance_date, display_order, is_archived)`. Enums:
  - `AccountType`: `bank | savings | brokerage | crypto | cash`
    (PHASE-21.2) + `credit_card | loan | mortgage` reservados para
    PHASE-22.
  - `AccountNature`: `asset | liability` (todos `asset` por ahora).
- **`repository.py`** — CRUD + `count_transactions_for_account` +
  `get_balance_for_account` + `get_balances_for_user` (estos dos
  últimos los usa PHASE-21.3 pero viven en este módulo).
- **`service.py`** — CRUD con validaciones: nombre único
  case-insensible (`409`), `type` no puede ser `liability` aún
  (`400`), borrado bloqueado si hay transacciones (`409` —
  obliga a archivar para conservar histórico). `ensure_account_exists`
  como alias semántico para callers (transactions, imports, receipts,
  fixed_expenses).
- **`schemas.py`** + **`router.py`** — endpoints CRUD bajo `/accounts`
  con `?include_archived=` opcional.

### Backend — `account_id` obligatorio en cascada

- **`Transaction.account_id`** `NOT NULL` con FK
  `ON DELETE CASCADE` (la cuenta no puede borrarse con histórico,
  pero si lo hace, arrastra). Schemas `TransactionCreate` y
  `TransactionUpdate` lo aceptan; el create lo exige; el service
  valida ownership con `ensure_account_exists`.
- **`ImportJob.account_id`** opcional (auditar a qué cuenta se
  importó cada lote). El form-data del wizard lo exige; el service
  valida y lo guarda en el job + lo propaga a cada `Transaction`
  generada.
- **`ReceiptConfirmRequest.account_id`** obligatorio en el body —
  el receipt confirm crea la `Transaction` con esa cuenta.
- **`FixedExpense.account_id`** opcional. El cron de autopost
  salta silenciosamente los gastos fijos sin cuenta (no puede
  imputar la tx). La reconciliación con imports
  (`reconcile_with_expected`) restringe el match a la misma cuenta
  — un gasto esperado en cuenta A no concilia con un import en
  cuenta B aunque el importe coincida.

### Frontend — pantalla de cuentas + onboarding

- **Web** — `apps/web/app/(app)/settings/accounts/page.tsx`:
  CRUD con swatch + emoji picker (reusa `CategoryAppearanceFields`
  de PHASE-21.1), archivado (oculta del selector pero mantiene
  histórico), borrado bloqueado si hay tx (toast con mensaje del
  backend).
- **Mobile** — `apps/mobile/app/(modules)/personal-finance/accounts.tsx`
  + `apps/mobile/components/accounts/account-form-modal.tsx`:
  espejo del web con FAB y modal nativo.
- **Onboarding bloqueante** —
  `apps/web/app/onboarding/accounts/page.tsx` y
  `apps/mobile/app/onboarding/accounts.tsx`. Si `useAccounts()`
  devuelve lista vacía, el guard del root layout redirige al
  onboarding. Form mínimo (name + type + currency); al crear la
  primera cuenta, redirige al dashboard.

### Frontend — selectores en formularios

Selector de cuenta obligatorio (preselecciona la primera no
archivada) en:

- `apps/web/components/transactions/transaction-form.tsx` +
  `apps/mobile/components/transaction-form.tsx`
- `apps/web/components/imports/upload-step.tsx` +
  page `apps/web/app/(app)/personal-finance/imports/new/page.tsx`
  (forwarding del `accountId` a la mutación)
- `apps/web/components/receipts/confirm-form.tsx` +
  `apps/mobile/components/receipt-capture-form.tsx`
- `apps/web/components/fixed-expenses/fixed-expense-card.tsx` +
  `apps/mobile/components/fixed-expenses/fixed-expense-card.tsx`
  (selector inline + warning si está sin cuenta + checkbox de
  autopost deshabilitado en ese caso)

### Frontend — types/services/hooks

- `packages/types/src/models/account.ts` + `dto/account.dto.ts` —
  modelos y DTOs.
- `packages/services/src/api/endpoints/accounts.ts` — `accountsApi`.
- `packages/services/src/query/hooks/useAccounts.ts` —
  `useAccounts`, `useAccount`, `useCreateAccount`,
  `useUpdateAccount`, `useDeleteAccount`.

## Flujo técnico

```
 Usuario nuevo (post-migración) entra a la app
    ▼
 RootLayout: AccountsGuard
    │ useAccounts() → []
    │ → router.replace('/onboarding/accounts')
    ▼
 Onboarding form: nombre + type + currency
    │ POST /accounts
    ▼
 Redirect a /personal-finance
    ▼
 Crear transacción / importar / confirmar receipt:
    │ Selector de cuenta obligatorio (preselecciona la primera)
    │ POST /transactions (account_id required)
    │ POST /imports (form account_id field required)
    │ POST /receipts/{id}/confirm (account_id required en body)
```

## Archivos clave

### Backend
- `backend/app/modules/personal_finance/accounts/` (módulo nuevo)
- `backend/alembic/versions/j7e95d1b3f4c_accounts_module.py`
  (crea tabla + WIPE de transactions/import_jobs/receipts +
  añade `account_id NOT NULL` a transactions + columnas opcionales
  en import_jobs y fixed_expenses)
- `backend/app/modules/personal_finance/transactions/{models,schemas,service,router,repository}.py`
  (account_id required + filtro)
- `backend/app/modules/personal_finance/imports/{models,schemas,service,router}.py`
  (account_id en form + ImportJob + cada Transaction creada)
- `backend/app/modules/personal_finance/receipts/{schemas,service}.py`
  (account_id en confirm)
- `backend/app/modules/personal_finance/fixed_expenses/{models,schemas,service,reconciliation}.py`
  (account_id opcional, autopost skip, reconcile mismo account)
- `backend/tests/test_accounts.py` (módulo nuevo)
- `backend/tests/conftest.py` + tests existentes (account_id en
  helpers — ~17 archivos de test)

### Frontend
- `packages/types/src/models/account.ts`,
  `packages/types/src/dto/account.dto.ts`
- `packages/services/src/api/endpoints/accounts.ts`,
  `packages/services/src/query/hooks/useAccounts.ts`
- `apps/web/app/(app)/settings/accounts/page.tsx` (nuevo)
- `apps/web/app/onboarding/` (nuevo, layout sin sidebar)
- `apps/web/components/accounts/{account-form-fields,account-swatch}.tsx`
- `apps/mobile/app/(modules)/personal-finance/accounts.tsx` (nuevo)
- `apps/mobile/app/onboarding/` (nuevo)
- `apps/mobile/components/accounts/{account-appearance-fields,
  account-form-modal,account-swatch}.tsx`
- `apps/web/app/(app)/layout.tsx` (AccountsGuard sub-component)
- `apps/mobile/app/_layout.tsx` (guard equivalente)

## Endpoints añadidos

- `GET /accounts` — lista (`?include_archived=`).
- `GET /accounts/{id}` — detalle.
- `POST /accounts` — crea (409 si nombre duplicado, 400 si
  `type=liability`).
- `PUT /accounts/{id}` — update parcial.
- `DELETE /accounts/{id}` — borra (409 si tiene transacciones).

## Migraciones

- `j7e95d1b3f4c_accounts_module.py`:
  1. Crea tabla `accounts` + enums `accounttype`/`accountnature` +
     index `ix_accounts_user_id`.
  2. **DELETE** de `receipts`, `import_jobs`, `transactions` (en
     ese orden por FKs). Categorías, presupuestos, gastos fijos y
     reglas se conservan.
  3. ADD COLUMN `account_id UUID NOT NULL` en `transactions` con
     FK `ON DELETE CASCADE` + index.
  4. ADD COLUMN `account_id UUID NULL` en `import_jobs` y
     `fixed_expenses` (FK `ON DELETE SET NULL`) + index parcial.

## Verificación

- [x] `pytest backend/tests/` verde (333 tests, +12 nuevos).
- [x] `pnpm typecheck`, `pnpm lint`, `pnpm test` verdes.
- [x] Migración aplicada en BD local sin errores.
- [x] Login post-wipe redirige a onboarding bloqueante.
- [x] POST `/transactions` sin `account_id` → 422 Pydantic.
- [x] POST `/transactions` con `account_id` ajeno → 404.
- [x] DELETE `/accounts/{id}` con tx asociadas → 409 con mensaje
      indicando archivar.
- [x] Reimport de un extracto a la misma cuenta funciona; tx
      duplicadas se deduplican por `import_hash`.

## Decisiones tomadas

- **Migración dura con wipe** (acordada con el usuario). Alternativa
  suave (auto-crear "Cuenta principal" y asignar histórico) era
  retrocompatible pero menos sólida. El usuario tenía datos fáciles
  de reimportar; preferimos modelo limpio desde el inicio.
- **Enums `liability` reservados desde día uno**. El enum incluye
  `credit_card | loan | mortgage` aunque la UI no los expone
  todavía — así PHASE-22 (deuda) no necesita una nueva migración
  Alembic.
- **`AccountNature` separado de `AccountType`**. La nature (asset
  vs liability) determina el signo en el saldo agregado. Que sea
  campo independiente del type permite tipos futuros con nature
  custom (e.g. cuenta tipo `escrow` que es asset pero "no líquido").
- **Borrado bloqueado si hay transacciones**. CASCADE en BD por
  si se fuerza desde otro flujo, pero el endpoint REST exige
  archivar primero. Evita borrados accidentales del histórico.
- **`account_id` opcional en `fixed_expenses`** en lugar de
  obligatorio. Permite mantener gastos fijos detectados sin
  cuenta (heredados del wipe); el usuario decide cuándo
  asignarles cuenta. Sin asignar, el autopost se desactiva.
- **Reconciliación restringida a misma cuenta**. Una transferencia
  esperada de cuenta A no concilia con un import a cuenta B aunque
  importe y fecha coincidan — eso sería confundir un gasto fijo
  con una transferencia interna. Trade-off: si el usuario asigna
  mal la cuenta al fixed_expense, no concilia.

## Limitaciones conocidas

- **Sin saldo por cuenta visible** — esa parte llega en PHASE-21.3
  con `/accounts/balances` y `BalancesCard`.
- **Sin filtro por cuenta en transactions** — también PHASE-21.3.
- **El emoji/color de cuenta no se muestra en chips ni donut**.
  Sólo en la pantalla de cuentas y en selectores; los agregados
  de transacciones siguen pintando por categoría. Aceptable —
  añadir "color de cuenta" a chips de tx requeriría rediseño.
- **No hay `account_id` en `Receipt`** (sólo en la `Transaction`
  que se crea al confirmar). Si una imagen sin confirmar pertenece
  conceptualmente a una cuenta concreta, esa intención se pierde
  hasta el confirm. Aceptable.
- **El onboarding bloqueante puede confundir** a usuarios que
  abren la app por primera vez sin contexto. Falta un copy
  más amable en `/onboarding/accounts` explicando por qué se
  exige declarar cuentas.

## Próxima fase

PHASE-21.3 — Transferencias internas (matcher) + saldos por cuenta
+ patrimonio neto + filtro por cuenta en transactions.
