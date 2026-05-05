# PHASE-12.3 — Frontend mobile de presupuestos

**Estado**: ✅ completada
**Rama**: `feat/phase-12.3-budgets-mobile`
**Fecha de merge**: 2026-05-05

## Objetivo

Cierre de PHASE-12 (presupuestos): pantalla mobile equivalente a la
web (PHASE-12.2) reutilizando los hooks shared. Acceso desde el
header de la pestaña Análisis.

## Qué se implementó

### Componentes mobile nuevos

`apps/mobile/components/budgets/`:

- **`budget-status-card.tsx`** — equivalente RN del web. Card con
  título de categoría (o "Global"), badge `X% · status` con color
  por kind (`ok` success, `warning`, `over` danger), barra de
  progreso cap a 100% (el `over` se distingue por color), spent +
  remaining (este último en rojo cuando es negativo + copy
  "Excedido").
- **`budget-form-modal.tsx`** — `Modal` nativo bottom-sheet (no
  inline form). Chips para selección de categoría (sólo
  `kind='expense'` + opción "Global") y currency, `TextInput`
  decimal-pad para amount, `TextInput` text para fecha
  (heredamos la deuda del backlog: sin date picker nativo).
  Validación local; el 409 del backend lo gestiona el caller con
  toast.

### Pantalla `/personal-finance/budgets`

`apps/mobile/app/(modules)/personal-finance/budgets.tsx` (nuevo,
fuera de `(tabs)/` porque es vista secundaria, mismo patrón que
`/trash`):

- `<Stack.Screen options={{ title: 'Presupuestos' }} />`.
- ScrollView con tres bloques: "Estado del mes" (cards apiladas o
  empty state), "Presupuestos activos" (sólo si hay items, lista
  compacta con botón Cerrar por fila usando `Alert.alert`
  destructivo), `BudgetFormModal` controlado.
- FAB `+` flotante en bottom-right que abre el modal.
- `useBudgets`, `useBudgetStatus`, `useCategories`,
  `useUserCurrencies`, `useCreateBudget`, `useDeleteBudget` — los
  mismos hooks shared de PHASE-12.2.
- Toasts para success/error vía `@finanzas/store` (PHASE-11.3).

### Entry point en Análisis

`apps/mobile/app/(modules)/personal-finance/(tabs)/analysis.tsx`:

- Header gana un `<Link href="/(modules)/personal-finance/budgets">`
  con botón "Presupuestos" antes del botón "Salir". Mismo styling
  de "headerButton" que se reusará en futuras secciones secundarias.

## Archivos clave

- `apps/mobile/components/budgets/budget-status-card.tsx` (nuevo)
- `apps/mobile/components/budgets/budget-form-modal.tsx` (nuevo)
- `apps/mobile/app/(modules)/personal-finance/budgets.tsx` (nuevo)
- `apps/mobile/app/(modules)/personal-finance/(tabs)/analysis.tsx`
  (botón Presupuestos en header)

## Verificación

- [x] `pnpm typecheck` verde.
- [x] `pnpm lint` verde.
- [x] `pnpm test` — sin regresiones (5 mobile + 27 web).
- [ ] Smoke en Expo:
  - [ ] Análisis → tap "Presupuestos" → pantalla con empty state.
  - [ ] FAB → modal → seleccionar categoría chip → input amount →
        Crear → toast.success + card de estado aparece con 0% / ok.
  - [ ] Insertar tx en categoría → pull-to-refresh estado refleja
        spent.
  - [ ] Tap "Cerrar" en active → Alert destructivo → confirmar →
        toast.success + budget desaparece de Estado.
  - [ ] Crear duplicado para misma categoría → toast.error con 409.

## Decisiones tomadas

- **Pantalla fuera de `(tabs)/`**. Coherente con `trash.tsx` —
  presupuestos es secundaria, accesible vía link explícito desde
  Análisis. No merece slot principal (mobile ya tiene 3 tabs:
  Análisis / Transacciones / Tickets).
- **Form como Modal bottom-sheet**. Patrón nativo iOS/Material;
  evita navegar a otra pantalla para algo puntual y permite ver el
  contexto de la lista al cerrar.
- **Chips para selección de categoría/currency en lugar de Picker
  nativo**. Pickers nativos son inconsistentes entre iOS y Android;
  los chips son visibles, claros, y con < 10 opciones (categorías
  típicas + monedas del usuario) caben sin scroll extra.
- **TextInput de fecha (sin date picker)**. Heredado del backlog
  (PHASE-2.2: `@react-native-community/datetimepicker` pendiente).
  Cuando se priorice el picker, sustituir aquí + en
  `transaction-form.tsx`.
- **FAB `+` en lugar de botón en header**. La acción "crear" es la
  primaria de esta pantalla; el FAB la pone al alcance del pulgar
  y es patrón estándar en mobile.
- **Botón "Cerrar" con `Alert.alert` destructivo**. Coherente con
  patrón de papelera (PHASE-10.3) y captura de tickets
  (PHASE-11.4). Confirms destructivos son bloqueantes; toasts son
  pasivos.
- **Sin tests UI mobile** para esta fase. El infra (`jest-expo`)
  está listo (PHASE-11.6); añadir tests para `BudgetStatusCard` y
  `BudgetFormModal` es follow-up — la prioridad fue cerrar la
  feature visible.

## Limitaciones conocidas

- **Sin date picker nativo** (heredado).
- **Sin edición inline de amount** (igual que web — los hooks
  están listos).
- **No se enlaza desde la pestaña Transacciones** — sólo desde
  Análisis. Si emerge UX hint de "ver budget de esta categoría
  desde la lista", añadir enlace.
- **Sin tests UI** del componente status mobile (mismo razonamiento
  que PHASE-11.6 limit).
- **Flujo currency picker chip vertical** funciona bien con 1-3
  monedas; si crece a 10+ se siente apretado. Si emerge, sustituir
  por `Modal` action sheet propio.

## Cierre de PHASE-12

PHASE-12 entera (backend + web + mobile) cerrada:
- **12.1** — modelo budgets, CRUD, status calc; 10 tests backend.
- **12.2** — capa shared (tipos + api + hooks), página web,
  integración en sidebar; 4 tests web.
- **12.3** — pantalla mobile, modal de creación, link desde Análisis.

Backlog ahora apunta a PHASE-13 — Detección de subscripciones
recurrentes vía IA local (pipeline AI sobre transacciones
existentes; el módulo `ai/` tiene cliente Ollama listo).
