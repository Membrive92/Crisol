# PHASE-14.1 — Edición inline de amount en presupuestos (web + mobile)

**Estado**: ✅ completada
**Rama**: `feat/phase-14.1-budget-amount-edit`
**Fecha de merge**: 2026-05-05

## Objetivo

Cubrir la limitación documentada en PHASE-12.2/12.3: los hooks
`useUpdateBudget` ya estaban listos en `packages/services` pero la
UI no tenía forma de editar el `amount` de un presupuesto activo.
Esta fase añade el modo lectura/edición en la fila de "Presupuestos
activos" (web) y la fila equivalente en mobile.

## Qué se implementó

### Capa shared

- **`useUpdateBudget` refactorizado** para tomar la mutation
  variables `{ id, data }` en lugar de cerrar `id` en el hook
  factory. Antes era `useUpdateBudget(id)` → fuerza un hook por
  fila (rompe rules of hooks si la lista cambia). Ahora es
  `useUpdateBudget()` → mutation única que recibe `{ id, data }`
  por llamada — patrón estándar y reutilizable. Sin callers
  previos, refactor sin riesgo.
- Nuevo type `UpdateBudgetVariables` exportado.

### Web

- **`apps/web/components/budgets/budget-row.tsx`** (nuevo): fila
  reusable con modo lectura (texto + botones Editar/Cerrar) y modo
  edición (input decimal-pad + Guardar/Cancelar). Validación local
  idéntica a `BudgetForm` (positivo, formato `0.00` con `,`
  permitida). Errores como texto inline rojo dentro del modo
  edición (no toast — contexto del input).
- **`apps/web/app/(app)/personal-finance/budgets/page.tsx`**:
  sustituye el `<li>` plano por `<BudgetRow>`. Nuevo
  `handleSaveAmount` envuelve `updateMutation.mutate` en una
  Promise para que el componente pueda hacer `await` y cerrar el
  modo edición sólo tras success/error. Toast `success: 'Importe
  actualizado'` o `error: ...`.
- 6 vitest tests (`budget-row.test.tsx`): lectura → edición,
  cancelar sin llamar onSave, guardar válido llama onSave con
  `(id, amount)`, guardar inválido bloquea con error inline,
  "Global" cuando `category_id=null`, render base.

### Mobile

- **`apps/mobile/components/budgets/budget-active-row.tsx`** (nuevo):
  equivalente RN. Mismo contrato que el `BudgetRow` web (`onSave`
  Promise-based, `onDelete`, `busy`). Modo edición usa `TextInput`
  decimal-pad con `autoFocus`. Botones `Editar/Cerrar` (lectura) y
  `Guardar/Cancelar` (edición) en columna vertical para no
  desbordar a la derecha en pantallas estrechas.
- **`apps/mobile/app/(modules)/personal-finance/budgets.tsx`**:
  sustituye el `<View style={styles.row}>` plano por
  `<BudgetActiveRow>`. Limpia los styles huérfanos (`row`,
  `rowTitle`, `rowMeta`, `closeButton`, `closeButtonText`).

## Archivos clave

- `packages/services/src/query/hooks/useBudgets.ts` (refactor a
  `{id, data}` + nuevo `UpdateBudgetVariables`)
- `apps/web/components/budgets/budget-row.tsx` (nuevo)
- `apps/web/components/budgets/budget-row.test.tsx` (nuevo, 6 tests)
- `apps/web/app/(app)/personal-finance/budgets/page.tsx` (consume
  `BudgetRow` + `handleSaveAmount`)
- `apps/mobile/components/budgets/budget-active-row.tsx` (nuevo)
- `apps/mobile/app/(modules)/personal-finance/budgets.tsx` (consume
  `BudgetActiveRow` + `handleSaveAmount` + cleanup styles)

## Verificación

- [x] `pnpm typecheck` verde.
- [x] `pnpm lint` verde.
- [x] `pnpm test` — 38 web + 5 mobile = 43 tests, sin regresiones
      (+6 en `budget-row.test.tsx`).
- [ ] Smoke manual:
  - [ ] Web: `/budgets` → fila → Editar → input visible con valor
        actual → cambiar a 450 → Guardar → toast.success +
        formatted "450,00 €" en la fila.
  - [ ] Web: Editar → cambiar a 0 / -5 → Guardar → error inline,
        no llama backend.
  - [ ] Web: Editar → Cancelar → vuelve al valor original sin
        tocar nada.
  - [ ] Mobile: idem en `/budgets`.

## Decisiones tomadas

- **Refactor de `useUpdateBudget` a `{id, data}` mutation
  variables**. La firma anterior (`useUpdateBudget(id)`) se ata a
  un id en tiempo de hook construction — válido para una página
  de detalle pero rompe en lista. La nueva firma es estándar
  TanStack y no obliga a un hook por row. Sin callers previos →
  refactor sin riesgo.
- **`onSave` Promise-based en `BudgetRow`**. El componente espera
  el await antes de cerrar el modo edición — si la mutation
  falla, el toast aparece y el modo edición queda abierto para que
  el usuario corrija o cancele explícitamente. Si éxito, cierra y
  vuelve a lectura.
- **Validación local antes de la mutation**. Mismas reglas que
  `BudgetForm`: positivo + parseable + comma normalizada a dot.
  El error se muestra inline en el modo edición, no como toast —
  es contexto inmediato del input.
- **No editar `currency` ni `effective_from`** desde aquí. El
  backend permite cambiar `currency` (PHASE-12.1) pero cambiar la
  moneda de un budget existente sin recalcular el spent es
  semánticamente confuso. Mejor cerrar el budget actual y crear
  uno nuevo en otra moneda. Si emerge necesidad real, añadir un
  flujo separado.
- **Estilos del row mobile en columna vertical**. Botones
  Editar/Cerrar y Guardar/Cancelar van en `flexDirection: column`
  para no desbordar en pantallas pequeñas (~360dp). Trade-off:
  más alto pero claro.
- **Limpiar styles huérfanos del mobile screen**. `row`,
  `rowTitle`, etc. ya no se usan; mantenerlos sería deuda técnica
  inmediata.

## Limitaciones conocidas

- **Sólo `amount` editable**. `currency`, `effective_from`,
  `category_id` siguen sin UI de edición (ver decisiones — diseño,
  no ausencia de implementación).
- **Sin optimistic update**. Tras Guardar el row muestra
  "Guardando…" hasta que el backend responde y la query
  refetchea. La latencia local es ~ms; trivial. Si se vuelve
  notable en un despliegue remoto, `useMutation` con `onMutate`
  para optimistic update.
- **Tests UI mobile pendientes** (heredado del backlog general).

## Próxima fase

PHASE-14.2 — Sección "Descartadas" en subscriptions UI. Backend
ya expone vía `?status=dismissed`; falta UI en web + mobile.
