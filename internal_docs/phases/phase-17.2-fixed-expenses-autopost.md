# PHASE-17.2 — Auto-post de gastos fijos confirmados

**Estado**: ✅ completada
**Rama**: `feat/phase-17.2-fixed-expenses-autopost`
**Fecha de merge**: 2026-05-07

## Objetivo

Heredado del backlog: que los gastos fijos confirmados puedan
auto-postear su transacción cuando llegue su `next_due`. Hipoteca,
gym, Netflix — el patrón es estable, el usuario no quiere
escribirlo cada mes. Quedan fuera por diseño los gastos de
cantidad variable (luz/gas) — no hay reconciliación todavía
(llega en 17.3) así que la cantidad fija evita el problema del
desfase con el banco.

**Opt-in por gasto fijo**: el flag está OFF por defecto al
confirmar. El usuario lo activa explícitamente para los gastos
seguros.

## Qué se implementó

### Backend

- **Migración `e8c34a9b1d52`**:
  - `fixed_expenses.auto_post BOOLEAN NOT NULL DEFAULT FALSE`
    (`server_default=sa.false()` para filas existentes).
  - `ALTER TYPE transactionsource ADD VALUE IF NOT EXISTS 'expected'`
    (Postgres native, idempotente). Downgrade documentado como
    no-op para el enum (mismo patrón que PHASE-15.2).
- **Modelo `FixedExpense`**: nuevo campo `auto_post: bool`.
- **`TransactionSource`** extendido con `EXPECTED`. Docstring
  describe la semántica: lo emite el cron de autoposteo, y la
  reconciliación con imports (PHASE-17.3) podrá asignarle
  `import_hash` sin tocar `source`.
- **Schemas**:
  - `FixedExpenseResponse.auto_post: bool` añadido.
  - `FixedExpenseUpdate { auto_post: bool | None }` — request
    body para el nuevo PUT.
  - `AutopostResponse { created, advanced }`.
- **Repository**: `list_due_for_autopost(user_id, today)` —
  filtra `auto_post=True AND status=CONFIRMED AND next_due <= today`.
- **Service `autopost_due_for_user`**:
  - Itera los gastos fijos due, crea `Transaction(source=EXPECTED,
    amount/category/currency` del fixed_expense, `occurred_at=next_due`
    en UTC midnight, `description=raw_description`).
  - Avanza `next_due += cadence_days` por cada tx creada.
  - Backfill cap en **12 ciclos** por seguridad (caso: usuario
    activó hace meses sin txs reales en medio).
  - Devuelve `(created, advanced)` separados por si en el futuro
    falla parcialmente.
- **Service `update_fixed_expense`**: setea `auto_post` con
  `FixedExpenseUpdate`. Por ahora sólo este campo es editable;
  el resto del lifecycle (confirm/pause/cancel) sigue por
  endpoints específicos.
- **Router**:
  - `PUT /fixed-expenses/{id}` — body `{ auto_post? }`.
  - `POST /fixed-expenses/autopost` — fuerza el cron manualmente.
- **Scheduler**: nuevo job `FIXED_EXPENSES_AUTOPOST_JOB_ID`,
  corre 30 min después del scan diario (asume scan refresca
  `next_due`, autopost ve la fecha nueva). Sólo activo si
  `enable_fixed_expenses_cron=True`.
- **Tests** (7 nuevos en `tests/test_fixed_expenses_autopost.py`):
  - default `auto_post=false` al crear vía detector.
  - PUT activa/desactiva el flag.
  - Autopost crea tx `expected` y avanza `next_due` (test
    determinista vía session directa porque el helper deja
    `next_due` en futuro).
  - Backfill multi-ciclo con cap a 12.
  - Skip cuando flag off.
  - Skip cuando paused/cancelled aunque flag on.
  - Aislamiento entre usuarios.

Suite backend: **232/232** (+7 nuevos sobre 225).

### Frontend

- **Tipos** (`packages/types`):
  - `FixedExpense.auto_post: boolean` añadido.
  - `TransactionSource` extendido a
    `'manual' | 'import' | 'receipt' | 'expected'`.
- **Services** (`packages/services`):
  - `fixedExpensesApi.update(id, { auto_post })` y
    `fixedExpensesApi.autopost()`.
  - Hooks `useUpdateFixedExpense`, `useAutopostFixedExpenses`
    invalidan `fixedExpenses.all` (y `transactions.all` el
    autopost porque crea txs).
- **Web** (`/personal-finance/fixed-expenses`):
  - Header con dos botones: **Auto-añadir vencidos** (manual
    trigger del cron) + **Re-escanear** (existente).
  - Cada `FixedExpenseCard` confirmado lleva un check inline
    "Auto-añadir" wired a `handleToggleAutoPost`. Toggle
    inmediato con toast info.
  - Nuevo prop `onToggleAutoPost?` + `autoPostBusy?` en el
    `FixedExpenseCard` — sólo se renderiza cuando se pasa el
    handler (no afecta a pending/dismissed).
- **Mobile** (`/personal-finance/fixed-expenses`):
  - Mismo flujo: actions row con dos pressables, toggle row
    custom en la card con check ASCII (no react-native-checkbox
    para no añadir dep). Estilos: `autoPostRow`, `checkbox`,
    `checkboxActive`, `checkmark`, `autoPostLabel`.
- **Origin badge**:
  - Web + mobile añaden `expected` con label "Esperada" y
    palette `colors.warning` para distinguir las txs
    auto-posteadas hasta que la reconciliación con bank import
    (PHASE-17.3) las marque conciliadas.

## Archivos clave

- `backend/alembic/versions/e8c34a9b1d52_fixed_expenses_autopost.py` (nuevo)
- `backend/app/modules/personal_finance/fixed_expenses/{models,schemas,repository,service,router}.py`
- `backend/app/modules/personal_finance/transactions/models.py` (`TransactionSource.EXPECTED`)
- `backend/app/core/scheduler.py` (job autopost + ID)
- `backend/tests/test_fixed_expenses_autopost.py` (7 tests)
- `packages/types/src/models/{fixed-expense,transaction}.ts`
- `packages/services/src/api/endpoints/fixed-expenses.ts` (`update`, `autopost`)
- `packages/services/src/query/hooks/useFixedExpenses.ts` (`useUpdateFixedExpense`, `useAutopostFixedExpenses`)
- `apps/web/app/(app)/personal-finance/fixed-expenses/page.tsx` (acciones + toggle)
- `apps/web/components/fixed-expenses/fixed-expense-card.tsx` (props nuevos)
- `apps/web/components/ui/origin-badge.tsx` (`expected` palette)
- `apps/mobile/app/(modules)/personal-finance/fixed-expenses.tsx`
- `apps/mobile/components/fixed-expenses/fixed-expense-card.tsx`
- `apps/mobile/components/ui/origin-badge.tsx`

## Verificación

- [x] `alembic upgrade head` aplica `e8c34a9b1d52` sin error.
- [x] `pytest tests/` — 232/232.
- [x] `pnpm typecheck` y `pnpm lint` verdes.
- [x] `pnpm test` — 40 web + 18 mobile sin regresiones.
- [ ] Smoke:
  - [ ] Activar "Auto-añadir" en una hipoteca confirmada.
  - [ ] Tap "Auto-añadir vencidos" → si `next_due ≤ hoy`,
        aparece la tx con badge "Esperada".
  - [ ] `next_due` avanza un ciclo.
  - [ ] Cron diario crea la tx automáticamente al día siguiente
        del `next_due`.

## Decisiones tomadas

- **Opt-in por fila, off por defecto**. Encender autopost
  globalmente al confirmar postearía cosas que el usuario no
  quiere (cargo único que pareció recurrente). El flag
  individual hace explícita la intención.
- **`source=EXPECTED` separado del flujo de import** (en lugar
  de marcar como `MANUAL` o `IMPORT`). Permite distinguir en la
  UI las txs que el usuario "no escribió" — útil para que el
  badge "Esperada" sea evidente y la reconciliación de 17.3
  pueda buscar específicamente este source.
- **`occurred_at = next_due` en UTC midnight**. Coherente con
  cómo el banco suele cargar (al inicio del día). No usamos
  `now()` porque rompe el calendario (autopost del día 1 a las
  4:30 UTC en huso +2 ya estaría en día 1 — perfecto).
- **Cap de 12 ciclos en backfill**. Evita avalanchas si los
  datos vienen mal (ej. `next_due` en 2020 por bug). Para
  cadence mensual = 1 año máximo de backfill. Si hace falta
  más, el usuario lo añade manual.
- **Cron 30 min después del scan**. El scan refresca `next_due`
  con la última observación del banco; si al día siguiente
  vuelve a tocar, autopost ve la fecha actualizada y no postea
  duplicados.
- **Lifecycle gana sobre flag**. Una hipoteca pausada con flag
  on NO se postea. El flag persiste — al reanudarla el autopost
  vuelve. Si el usuario cancela, el flag se queda on en BD pero
  el filtro de `status=CONFIRMED` lo excluye.

## Limitaciones conocidas

- **Sin reconciliación con imports todavía**. Si el banco trae
  la tx el día 5 después de que autopost la creó el día 1,
  ahora habrá dos transacciones para el mismo evento real.
  PHASE-17.3 lo arregla — esa fase mira `expected` activas que
  matcheen merchant + amount + ±3 días sobre `next_due` y las
  fusiona en lugar de crear duplicado.
- **Sin tests UI** del toggle web/mobile. El componente
  visual es incremental (mismo patrón mutation+toast); smoke en
  runtime cubre el flujo.
- **Sin paginación del backfill**. 12 ciclos en una sola
  llamada es OK para volúmenes esperados (< 50 fixed expenses
  por user). Si en el futuro emerge un usuario con cientos de
  gastos fijos backfilleados a la vez, mover a job en
  background.

## Próxima fase

PHASE-17.3 — reconciliación con imports: cuando un import trae
una tx que matchea (merchant + amount + ±3 días) una `expected`
existente, fusiona ambas asignando `import_hash` a la `expected`
en lugar de crear una segunda fila.
