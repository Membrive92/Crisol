# PHASE-2.2 — Transactions frontend

**Estado**: ✅ completada
**Rama**: `feat/phase-2.2-transactions-frontend`
**PR**: —
**Fecha de merge**: 2026-04-16

## Objetivo

Consumir el CRUD de transacciones (PHASE-2.1) desde web (Next.js) y móvil
(Expo), con cache de servidor mediante TanStack Query y query keys
centralizados.

## Qué se implementó

- **Tipos compartidos** en `packages/types`:
  - `Category`, `CategoryKind`, `Transaction`, `TransactionSource`.
  - DTOs `CategoryCreateRequest`, `CategoryUpdateRequest`,
    `TransactionCreateRequest`, `TransactionUpdateRequest`,
    `TransactionListQuery`, `TransactionListResponse`.
- **Clientes HTTP** en `packages/services`:
  - `categoriesApi` con `list` / `get` / `create` / `update` / `remove`.
  - `transactionsApi` con `list` (filtros + paginación) / `get` / `create`
    / `update` / `remove`.
- **Setup TanStack Query**:
  - `QueryClientProvider` en `apps/web/lib/query-provider.tsx` y
    `apps/mobile/lib/query-provider.tsx`.
  - Montado en `layout.tsx` (web) y `_layout.tsx` (mobile) por encima
    de `AuthProvider`.
- **Query keys centralizados** en `packages/services/src/query/keys.ts`:
  - `queryKeys.categories.all | list() | detail(id)`
  - `queryKeys.transactions.all | list(query) | detail(id)`
  - Normaliza los filtros del listado (orden de keys y valores vacíos)
    para evitar duplicados de cache.
- **Hooks de React Query** (reutilizados en web y mobile):
  - `useCategories`, `useCategory`, `useCreateCategory`,
    `useUpdateCategory`, `useDeleteCategory`.
  - `useTransactions`, `useTransaction`, `useCreateTransaction`,
    `useUpdateTransaction`, `useDeleteTransaction`.
- **`packages/ui`** (nuevo paquete) con design tokens (colores,
  espaciado, tipografía) y formatters (`formatAmount`, `formatDate`,
  `toDateInputValue`, `fromDateInputValue`). Ver
  `internal_docs/decisions/0001-ui-tokens-only.md`.
- **Web (`apps/web`)**:
  - `app/(dashboard)/transactions/page.tsx` — listado con filtros
    (búsqueda, categoría, fecha desde/hasta) y paginación.
  - `app/(dashboard)/transactions/new/page.tsx` — crear.
  - `app/(dashboard)/transactions/[id]/page.tsx` — editar.
  - `components/ui/` — `Button`, `Field`/`TextInput`/`TextArea`/`Select`,
    `Card`.
  - `components/transactions/` — `TransactionForm`, `TransactionList`,
    `TransactionFilters`.
  - Nav añadida en `(dashboard)/layout.tsx` con links a Inicio y
    Transacciones.
- **Mobile (`apps/mobile`)**:
  - Root `_layout.tsx` pasa de `<Slot />` a `<Stack>` con screens
    registradas para `(auth)`, `(tabs)`, `transaction/new`, `transaction/[id]`.
  - `app/(tabs)/_layout.tsx` añade pestaña "Transacciones".
  - `app/(tabs)/transactions.tsx` — listado con `FlatList`,
    pull-to-refresh, borrado con long-press.
  - `app/transaction/new.tsx` y `app/transaction/[id].tsx` —
    pantallas pushed fuera de tabs.
  - `components/transaction-form.tsx` — formulario con chips de
    categoría.
- **Tests**:
  - `packages/ui/src/format.test.ts` — 9 tests (formatters).
  - `packages/services/src/query/keys.test.ts` — 4 tests
    (estabilidad y normalización).
  - `packages/services/src/api/endpoints/transactions.test.ts` — 5
    tests (cada verbo HTTP).
  - `apps/web/components/ui/button.test.tsx` — 3 tests.
  - Vitest como test runner. `apps/mobile` tests pospuestos (requieren
    `jest-expo` setup).

## Endpoints consumidos

- `GET /categories` (listado, cache 5 min).
- `GET /transactions` con `{category_id, date_from, date_to, search, limit, offset}`.
- `GET /transactions/{id}`.
- `POST /transactions`.
- `PUT /transactions/{id}`.
- `DELETE /transactions/{id}`.

## Archivos clave

**Types**:
- `packages/types/src/models/{category,transaction}.ts`
- `packages/types/src/dto/{category,transaction}.dto.ts`

**Services / Query**:
- `packages/services/src/api/endpoints/{categories,transactions}.ts`
- `packages/services/src/query/keys.ts`
- `packages/services/src/query/hooks/{useCategories,useTransactions}.ts`

**UI compartida**:
- `packages/ui/src/tokens.ts`
- `packages/ui/src/format.ts`

**Web**:
- `apps/web/lib/query-provider.tsx`
- `apps/web/app/(dashboard)/transactions/{page,new/page,[id]/page}.tsx`
- `apps/web/components/ui/{button,field,card}.tsx`
- `apps/web/components/transactions/{transaction-form,transaction-list,transaction-filters}.tsx`

**Mobile**:
- `apps/mobile/lib/query-provider.tsx`
- `apps/mobile/app/_layout.tsx` (ahora con `<Stack>`)
- `apps/mobile/app/(tabs)/{_layout,transactions}.tsx`
- `apps/mobile/app/transaction/{new,[id]}.tsx`
- `apps/mobile/components/transaction-form.tsx`

## Decisiones tomadas

- **`packages/ui` solo tokens** (no componentes) → ADR 0001.
- **Hooks de React Query en `packages/services`**: se exponen como
  dependencias peer (`react`, `@tanstack/react-query`) y se instalan en
  las apps. Mantiene un único punto donde se definen.
- **`amount` viaja como `string`** entre backend y frontend para
  preservar la precisión decimal (el backend usa `Decimal(14,2)`). El
  form lo valida antes de enviar y los formatters convierten a `number`
  solo para mostrar.
- **Signo visual lo decide `category.kind`**: los importes en la BD son
  siempre positivos; el frontend muestra `+` si la categoría asociada
  es `income`.
- **Categorías sin CRUD de UI todavía**: el listado las consume
  read-only, el form las expone como selector. El CRUD completo de
  categorías queda para una sub-fase si aparece la necesidad.
- **Tests de mobile aplazados**: añadir `jest-expo` (o Vitest con
  react-native preset) es fricción desproporcionada con lo que se
  entrega.

## Limitaciones conocidas

- Sin input de fecha nativo en mobile — se usa un `TextInput` con
  formato `YYYY-MM-DD`. Se revisará cuando se añada `@react-native-community/datetimepicker`.
- Pull-to-refresh funciona en mobile; web no tiene equivalente
  (el cache revalida por `staleTime`).
- El borrado web usa `window.confirm`. Aceptable por ahora.
- Sin virtualización en mobile; `FlatList` es suficiente hasta unos
  cientos de transacciones.

## Verificación

- [x] `pnpm lint` verde.
- [x] `pnpm typecheck` verde.
- [x] `pnpm test` verde (21 tests en 4 archivos).
- [x] Prueba manual web: listar, filtrar, paginar, crear, editar, borrar.
- [x] Prueba manual mobile: listar, tirar para refrescar, crear,
      editar, borrar.

## Próxima fase

PHASE-3.1 — Dashboard backend.
