# PHASE-12.2 — Frontend web de presupuestos

**Estado**: ✅ completada
**Rama**: `feat/phase-12.2-budgets-web`
**Fecha de merge**: 2026-05-05

## Objetivo

Consumir el backend de PHASE-12.1: ruta dedicada `/personal-finance/budgets`
con estado, formulario y lista, sección "Presupuestos" en la
navegación del módulo, y los hooks shared en `packages/services` para
que mobile (PHASE-12.3) los reutilice.

## Qué se implementó

### Capa shared

- **`packages/types/src/models/budget.ts`** (nuevo): `Budget`,
  `BudgetStatus`, `BudgetStatusItem`, `BudgetStatusResponse`. Importes
  como `string` (Decimal serializado) — frontend convierte con
  `Number()` cuando hace aritmética.
- **`packages/types/src/dto/budget.dto.ts`** (nuevo):
  `BudgetCreateRequest`, `BudgetUpdateRequest`.
- **`packages/services/src/api/endpoints/budgets.ts`** (nuevo):
  `budgetsApi.list/get/status/create/update/remove` mapeados a los
  endpoints de PHASE-12.1.
- **`packages/services/src/query/keys.ts`**:
  `queryKeys.budgets.{all,list,detail(id),status}`.
- **`packages/services/src/query/hooks/useBudgets.ts`** (nuevo):
  `useBudgets`, `useBudget`, `useBudgetStatus`, `useCreateBudget`,
  `useUpdateBudget`, `useDeleteBudget`. Mutations invalidan
  `budgets.all` para que list, detail y status se refresquen al
  unísono.
- Re-exports en ambos `index.ts`.

### Registro de módulo

`packages/types/src/registry/modules.ts`: `personal-finance.sections`
añade `{ key: 'budgets', label: 'Presupuestos', path: '/personal-finance/budgets' }`.
La sidebar/tabs del módulo lo recogen automáticamente — sin código nuevo
en `<ModuleSections>`.

### Componentes web

- **`apps/web/components/budgets/budget-status-card.tsx`** (nuevo):
  card con label de categoría (o "Global"), límite, badge "X% · status"
  con palette por kind (`ok` success, `warning`, `over` danger), barra
  de progreso cap a 100% (el `over` se distingue por color), spent y
  remaining (con el "Excedido" en rojo cuando es negativo).
- **`apps/web/components/budgets/budget-form.tsx`** (nuevo): form para
  crear con select de categoría (sólo `kind='expense'`), input amount,
  select currency hidratado de `useUserCurrencies`, input date
  `effective_from`. Validación local (positivo, fecha YYYY-MM-DD); el
  409 del backend lo gestiona el caller con toast.

### Página `/personal-finance/budgets`

`apps/web/app/(app)/personal-finance/budgets/page.tsx` (nuevo):

- Sección **Estado del mes** con grid de `BudgetStatusCard` (auto-fit
  280px). Empty state con dashed card cuando no hay budgets.
- Sección **Crear nuevo** con `BudgetForm`. `onSuccess` →
  `toast.success`; `onError` → `toast.error` (cubre el 409 con el
  mensaje del backend).
- Sección **Presupuestos activos** (sólo si hay) con lista compacta
  + botón "Cerrar" por fila con `confirm` nativo y toasts.

### Tests `apps/web/components/budgets/budget-status-card.test.tsx`

4 tests: nombre de categoría / "Global" / palette warning / texto
"Excedido" cuando remaining < 0.

Suite web pasa de 23 → **27 tests** (+4 nuevos en `budget-status-card`).

## Archivos clave

- `packages/types/src/models/budget.ts` (nuevo)
- `packages/types/src/dto/budget.dto.ts` (nuevo)
- `packages/types/src/index.ts` (re-exports)
- `packages/types/src/registry/modules.ts` (sección `budgets`)
- `packages/services/src/api/endpoints/budgets.ts` (nuevo)
- `packages/services/src/query/keys.ts` (`budgets.*`)
- `packages/services/src/query/hooks/useBudgets.ts` (nuevo)
- `packages/services/src/index.ts` (re-exports)
- `apps/web/components/budgets/budget-status-card.tsx` (nuevo)
- `apps/web/components/budgets/budget-form.tsx` (nuevo)
- `apps/web/components/budgets/budget-status-card.test.tsx` (nuevo, 4 tests)
- `apps/web/app/(app)/personal-finance/budgets/page.tsx` (nuevo)

## Verificación

- [x] `pnpm typecheck` verde.
- [x] `pnpm lint` verde.
- [x] `pnpm test` — 27 web + 5 mobile = 32 tests, sin regresiones.
- [ ] Smoke manual:
  - [ ] Navegar a `/personal-finance/budgets` desde la pestaña
        "Presupuestos" del módulo.
  - [ ] Crear presupuesto categoría EUR 300 → toast.success + status
        card aparece con 0% / ok.
  - [ ] Insertar tx de 250€ en esa categoría → status pasa a 83% /
        warning.
  - [ ] Insertar tx de 100€ adicional → 117% / over con badge rojo y
        "Excedido".
  - [ ] Crear segundo budget mismo cat → toast.error con mensaje 409.
  - [ ] Crear budget global → coexiste con el de categoría.
  - [ ] Cerrar un budget → confirm → toast.success → desaparece de
        Estado pero mantiene su row hasta mañana (effective_to=today
        sigue activo "hoy"); en próximo refresh ya no aparece.

## Decisiones tomadas

- **Sin widget en dashboard**. El roadmap propuesto sugería una
  tarjeta resumen en el dashboard, pero la página dedicada
  `/budgets` ya da el estado completo. Añadir un widget extra
  duplica datos; mejor enlazar desde el dashboard cuando sea
  necesario (sub-fase futura si se prioriza).
- **Sólo categorías `expense` en el dropdown**. Presupuestos miden
  gasto. Income categories no aplican; mostrarlas confunde.
- **`confirm` nativo para cerrar (no Alert / modal custom)**.
  Coherente con el patrón ya establecido en transactions/page.tsx
  y receipts. Cuando llegue un sistema de modales globales, migrar
  todos a la vez.
- **Cap visual de barra a 100%, badge muestra el % real**. La barra
  llena al 100% con color rojo + badge "117% · over" comunica más
  claro que una barra que se desborda visualmente (que requiere
  layout especial y confunde la métrica).
- **`useBudgetStatus` con `placeholderData: previous`**. Misma
  política que `useTransactions` — al refetch se mantiene el
  estado anterior visible para evitar flicker.
- **Mutations invalidan `budgets.all` (no detail individual)**.
  Crear/borrar afecta lista, status y futuras detail queries. El
  blast radius es pequeño (un solo grupo) y simplifica el
  razonamiento — `invalidateQueries({ queryKey: budgets.all })` es
  el patrón ya usado en transactions.
- **Sección "Presupuestos activos" sólo se renderiza si hay items**.
  Empty state ya está en "Estado del mes"; repetirlo abajo es
  ruido.
- **Form sin guardar en draft / sin auto-save**. Crear un
  presupuesto es acción puntual y rápida (3 campos). Auto-save
  añadiría complejidad (cuándo enviar, qué considerar "completo")
  sin beneficio claro.

## Limitaciones conocidas

- **Sin edición de amount/currency desde la página**. Los hooks
  `useUpdateBudget` están listos; falta UI inline (un "editar" que
  muestre input + botón guardar). Trivial de añadir cuando se
  priorice.
- **Sin filtros / sort en la lista activos**. Asumimos pocos
  budgets por usuario. Si crece, añadir search/filter.
- **Sin histórico de cerrados**. Backend no expone endpoint para
  ello (PHASE-12.1 limitation). Si llega la pantalla "ver mis
  budgets pasados", primero el endpoint backend, luego la UI.
- **Sin widget integrado en dashboard** (decidido) — la página
  dedicada es la home de presupuestos.
- **El status del mes NO usa `convertAll`** del store. Cada budget
  vive en una currency; spent se compara 1:1 (decisión de
  PHASE-12.1). Cross-currency en presupuestos es backlog.

## Próxima fase

PHASE-12.3 — Frontend mobile. Reusa los hooks shared introducidos
aquí. Pantalla `/budgets` en `apps/mobile/app/(modules)/personal-finance/`
accesible desde el header de Análisis o como link aparte; tarjetas
status con barras de progreso y form de crear con `Modal` nativo.
