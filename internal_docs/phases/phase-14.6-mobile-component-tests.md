# PHASE-14.6 — Cobertura UI mobile (componentes presentacionales)

**Estado**: ✅ completada
**Rama**: `feat/phase-14.6-mobile-component-tests`
**Fecha de merge**: 2026-05-06

## Objetivo

Heredado del backlog: PHASE-11.6 dejó `jest-expo` configurado con
sólo un test smoke (`Toaster`). Esta fase añade cobertura para los
componentes presentacionales mobile clave introducidos en
PHASE-12.x / 13.x / 14.x.

## Alcance

Cubre **componentes de presentación pura** (sin queries, sin
hooks, sólo props + render + interacción). Las pantallas
completas no se testean — requieren mockear todos los hooks
shared y se vuelven frágiles. La cobertura de estos componentes
da el 80% del valor con el 20% del esfuerzo.

## Qué se implementó

Tres archivos nuevos de tests:

- **`apps/mobile/components/budgets/budget-status-card.test.tsx`**
  (3 tests): pinta categoría + porcentaje + status, "Global"
  fallback con `category_id=null`, "Excedido" cuando
  `remaining < 0`.
- **`apps/mobile/components/budgets/budget-active-row.test.tsx`**
  (5 tests): modo lectura inicial, transición a edición,
  validación inline negativa, "Global" fallback, callback
  `onDelete` con `(id, label)`.
- **`apps/mobile/components/subscriptions/subscription-card.test.tsx`**
  (5 tests): render base + cadencia mensual/anual + "Sin
  categoría", `primaryAction.onPress` y `secondaryAction.onPress`.

Suite mobile: **18/18** (4 archivos, +13 nuevos sobre 5 previos).

## Archivos clave

- `apps/mobile/components/budgets/budget-status-card.test.tsx` (nuevo)
- `apps/mobile/components/budgets/budget-active-row.test.tsx` (nuevo)
- `apps/mobile/components/subscriptions/subscription-card.test.tsx` (nuevo)

## Verificación

- [x] `pnpm --filter @finanzas/mobile test` — 18/18.
- [x] `pnpm --filter @finanzas/mobile typecheck` verde.
- [x] `pnpm --filter @finanzas/mobile lint` verde.

## Decisiones tomadas

- **Solo componentes presentacionales**. Pantallas completas
  necesitan mock exhaustivo de hooks de `@finanzas/services` +
  `@finanzas/store`, lo que crea tests frágiles que se rompen
  al refactorizar. Los componentes presentacionales son
  contratos visuales claros: props in → render out.
- **No se testea `DateInput`**. Envuelve
  `@react-native-community/datetimepicker`, que es nativo y no
  se monta en el test renderer sin setup adicional. La lógica
  testeable (parse / format) es trivial; smoke en Expo es la
  verificación real.
- **Reusar `@types/jest` globals** (sin `import { describe } from
  '@jest/globals'`). Patrón ya establecido en PHASE-11.6 — el
  paquete `@jest/globals` da problemas con peer deps de React.
- **Espejos directos de los tests web** donde aplica
  (`BudgetStatusCard`, `SubscriptionCard`). Coherencia entre
  plataformas; cualquier regresión visual cross-platform se
  detecta en las dos suites a la vez.
- **No mocks de `@expo/vector-icons` ni cosas similares**. Los
  componentes cubiertos no los usan. Si en el futuro se prueba
  algo que sí, el setup de `jest-expo` los maneja
  automáticamente.

## Limitaciones conocidas

- **Sin tests de pantallas** (analysis, transactions, trash,
  budgets, subscriptions). Las pruebas E2E con `detox`/`maestro`
  serían el siguiente nivel; queda fuera del alcance ahora.
- **DateInput sin tests** (decidido, ver arriba).
- **Sin tests del `transaction-form` ni del `receipt-capture-form`**
  porque dependen de `useCategories`. Mockear el hook es
  factible pero suma deuda; cuando se priorice cobertura más
  amplia, primero introducir un patrón de wrap con
  `QueryClientProvider` mock y reusarlo.

## Próxima fase

PHASE-14.7 — Detector IA Ollama para subscripciones. Más
exploratorio: validar prompts con datos reales antes de meterlo
al pipeline.
