# PHASE-17.1 — Rename `subscriptions` → `fixed_expenses`

**Estado**: ✅ completada
**Rama**: `feat/phase-17.1-rename-fixed-expenses`
**Fecha de merge**: 2026-05-07

## Objetivo

Renombrar todo lo relacionado con "subscriptions" a "fixed_expenses"
para reflejar que el área cubre cualquier gasto recurrente con
cantidad estable, no sólo suscripciones (Netflix). El detector ya
detectaba hipotecas, préstamos, gym, seguros — el nombre del área
quedaba estrecho.

**Sin cambios de comportamiento.** Esta fase es 100% rename: tabla,
enum, módulo backend, endpoints, tipos frontend, query keys,
componentes, rutas, copy de UI. La fase 17.2 añadirá `auto_post` y
17.3 la reconciliación con imports.

## Qué se renombró

### Backend

- **Migración `d72f1a5e8b29`**: `RENAME TABLE subscriptions TO fixed_expenses`
  + `ALTER TYPE subscriptionstatus RENAME TO fixedexpensestatus` +
  `ALTER INDEX ix_subscriptions_* RENAME TO ix_fixed_expenses_*`.
  Idempotente; downgrade simétrico.
- **Módulo `app/modules/personal_finance/subscriptions/`** →
  `fixed_expenses/`. Renombrado vía `git mv` para preservar historia.
- **Clases**:
  - `Subscription` → `FixedExpense` (modelo)
  - `SubscriptionStatus` → `FixedExpenseStatus` (enum)
  - `SubscriptionResponse` → `FixedExpenseResponse` (Pydantic)
- **Funciones del service / repository**: `*_subscription` → `*_fixed_expense`,
  `list_subscriptions` → `list_fixed_expenses`, etc.
- **Endpoints**: `/subscriptions/*` → `/fixed-expenses/*` (kebab-case
  en URL, snake_case en módulo Python — convención FastAPI).
- **Config / scheduler**: `enable_subscriptions_cron` →
  `enable_fixed_expenses_cron`, `subscriptions_cron_hour/minute` →
  `fixed_expenses_cron_*`, `SUBSCRIPTIONS_SCAN_JOB_ID` →
  `FIXED_EXPENSES_SCAN_JOB_ID`, `scan_subscriptions_job` →
  `scan_fixed_expenses_job`.
- **Tests**: `test_subscriptions*.py` → `test_fixed_expenses*.py`
  con `git mv`. Contenido actualizado a las nuevas rutas y nombres.

### Frontend

- **Tipos** (`packages/types`): `models/subscription.ts` →
  `models/fixed-expense.ts`. `Subscription` → `FixedExpense`,
  `SubscriptionStatus` → `FixedExpenseStatus`,
  `SubscriptionScanResponse` → `FixedExpenseScanResponse`.
- **Services** (`packages/services`):
  - `api/endpoints/subscriptions.ts` → `fixed-expenses.ts`.
    `subscriptionsApi` → `fixedExpensesApi`. Path
    `/subscriptions` → `/fixed-expenses`.
  - `query/hooks/useSubscriptions.ts` → `useFixedExpenses.ts`.
    `useSubscriptions/useScanSubscriptions/useConfirmSubscription/...`
    → `useFixedExpenses/useScanFixedExpenses/useConfirmFixedExpense/...`.
  - Query key `subscriptions` → `fixedExpenses` en `queryKeys`.
- **Web** (`apps/web`):
  - `app/(app)/personal-finance/subscriptions/` → `fixed-expenses/`
  - `components/subscriptions/subscription-card.tsx` →
    `components/fixed-expenses/fixed-expense-card.tsx`
  - Componente `SubscriptionCard` → `FixedExpenseCard`.
  - Copy: "Subscripciones" → "Gastos fijos", "Confirmadas" →
    "Confirmados", "Pausadas" → "Pausados", etc.
- **Mobile** (`apps/mobile`):
  - `app/(modules)/personal-finance/subscriptions.tsx` →
    `fixed-expenses.tsx`
  - `components/subscriptions/subscription-card.tsx` →
    `components/fixed-expenses/fixed-expense-card.tsx`
  - Mismo trabajo de rename de componente y copy.
- **Module registry** (`packages/types/src/registry/modules.ts`):
  section `subscriptions` → `fixed-expenses` con label "Gastos fijos".
- **Dashboard placeholders** (smart insights coming-soon row):
  "Subscripciones recurrentes" → "Gastos fijos recurrentes".

### Tests

- Backend: 4 archivos renombrados sin tocar la lógica de los tests.
  Suite `pytest tests/` — 225/225 verde.
- Frontend: tests de cards renombrados; suite `pnpm test` —
  40 web + 18 mobile sin regresiones.

## Archivos clave

- `backend/alembic/versions/d72f1a5e8b29_rename_subscriptions_to_fixed_expenses.py` (nuevo)
- `backend/app/modules/personal_finance/fixed_expenses/*` (renombrado, contenido reescrito)
- `backend/app/main.py`, `app/core/scheduler.py`, `app/core/config.py`, `tests/conftest.py`
- `packages/types/src/models/fixed-expense.ts`, `index.ts`, `registry/modules.ts`
- `packages/services/src/api/endpoints/fixed-expenses.ts`, `query/hooks/useFixedExpenses.ts`, `query/keys.ts`, `index.ts`
- `apps/web/app/(app)/personal-finance/fixed-expenses/page.tsx`
- `apps/web/components/fixed-expenses/fixed-expense-card.{tsx,test.tsx}`
- `apps/mobile/app/(modules)/personal-finance/fixed-expenses.tsx`
- `apps/mobile/components/fixed-expenses/fixed-expense-card.{tsx,test.tsx}`

## Verificación

- [x] `alembic upgrade head` aplica `d72f1a5e8b29` sin error.
- [x] `pytest tests/` — 225/225.
- [x] `pnpm typecheck` y `pnpm lint` verdes.
- [x] `pnpm test` — 40 web + 18 mobile sin regresiones.
- [ ] Smoke: `/personal-finance/fixed-expenses` carga, lista actual
      sigue ahí, scan funciona, confirm/pause/cancel funcionan.

## Decisiones tomadas

- **Rename completo, no sólo cosmético**. Mantener el código
  diciendo `subscription` mientras la UI dice "Gastos fijos"
  habría dejado deriva semántica. Es trabajo de una sesión y vale
  la pena hacerlo bien antes de añadir autopost en 17.2.
- **Migración `RENAME` en lugar de `CREATE`/`DROP`**. Mantiene los
  datos del usuario. Postgres soporta `ALTER TABLE/TYPE/INDEX RENAME TO`
  como DDL transaccional. Más seguro que re-crear y migrar.
- **`git mv` para preservar historia**. Tanto los archivos del
  módulo backend como los componentes frontend y los tests se
  movieron con `git mv` para que `git log --follow` siga
  funcionando.
- **Path en URL kebab-case (`/fixed-expenses`)**. Coherente con
  cómo Next.js / FastAPI prefieren paths multi-palabra. El módulo
  Python sigue snake_case (`fixed_expenses`). Convención
  consolidada del proyecto.
- **`subscription-like` en docstrings del detector se queda**. Es
  un término técnico — describe el patrón "merchant + amount
  estables con cadence regular", no la noción de UI. Cambiarlo a
  "fixed-expense-like" sería pérdida de información sin ganancia.
- **No tocar migraciones antiguas** (`a92f5b1c8d34_subscriptions_module.py`,
  `b32c8a4d5f17_subscriptions_paused_cancelled.py`). Son
  histórico — el rename es una migración nueva encima.

## Limitaciones conocidas

- **Comentarios "Antes 'subscriptions'"** en algunos archivos
  para audit trail. Se pueden limpiar tras 17.2 + 17.3 cuando el
  rename ya esté asentado.
- **Sin redirect** desde `/personal-finance/subscriptions` viejo.
  Para personal app de un solo usuario es OK; si se añadieran
  bookmarks externos en el futuro, añadir un redirect en
  `next.config.mjs`.
- **`expo-router`**: la ruta vieja `subscriptions.tsx` desaparece;
  Expo no preserva navegación profunda al rename. Acceptable —
  el usuario navega vía drawer.

## Próxima fase

PHASE-17.2 — campo `auto_post: bool` por gasto fijo + cron de
autoposteo + nuevo `source='expected'` en el enum
`transactionsource`.
