# PHASE-10.2 — Frontend papelera (web) + capa shared

**Estado**: ✅ completada
**Rama**: `feat/phase-10.2-web-trash`
**PR**: —
**Fecha de merge**: 2026-05-05

## Objetivo

Hacer visible y usable el soft-delete de PHASE-10.1: el cambio de
comportamiento del DELETE no se notaba en la UI porque la página
seguía pintando "Borrar". Esta fase añade capa shared (api + hooks +
tipos) para los nuevos endpoints `/trash`, `/restore`, `/purge`, una
página `/personal-finance/trash` para gestionar la papelera, un
banner inline "Movido a papelera" + Deshacer tras el soft-delete, y
un link con badge desde Transacciones cuando hay items.

PHASE-10.3 cierra el frente con la versión mobile, reutilizando los
hooks creados aquí.

## Qué se implementó

### Capa shared

- **`packages/types/src/models/transaction.ts`**: `Transaction` añade
  `deleted_at: string | null`. NULL en activas, ISO timestamp en
  filas de `/trash`.
- **`packages/services/src/api/endpoints/transactions.ts`**:
  `transactionsApi.listTrash`, `restore`, `purge` mapeados a los
  endpoints de PHASE-10.1.
- **`packages/services/src/query/keys.ts`**:
  `queryKeys.transactions.trash(query)` — el cache key para la lista
  de papelera.
- **`packages/services/src/query/hooks/useTransactions.ts`**:
  - `useTrashedTransactions(query)` — query con `placeholderData`.
  - `useRestoreTransaction()` — mutation. Invalida
    `transactions.all` (cubre list + trash + detail) y
    `dashboard.all` (summary/top-expenses se actualizan al instante).
  - `usePurgeTransaction()` — mutation. Invalida `transactions.all`
    sólo (la tx ya estaba excluida del dashboard como soft-deleted).
  - `useDeleteTransaction()` actualizado: ahora también invalida
    `dashboard.all` para que el soft-delete se refleje sin esperar
    al staleTime.
- Re-exports en `packages/services/src/index.ts`.

### Página `/personal-finance/trash`

`apps/web/app/(app)/personal-finance/trash/page.tsx`:

- Header con back-link a Transacciones, título y subtítulo con
  contador (`X transacciones en papelera`).
- Tabla `TrashList` con paginación.
- `confirm()` nativo en purge ("Eliminar permanente esta
  transacción. Esta acción no se puede deshacer."). Restore directo,
  sin confirm — el riesgo de "no quería restaurar" es bajo y se
  puede deshacer borrando otra vez.
- Empty state cuando `total === 0`.
- Botón principal/secundarios bloqueados durante la mutation activa
  vía `busyId`.

### Componente `TrashList`

`apps/web/components/transactions/trash-list.tsx` — equivalente a
`TransactionList` pero:

- Drop columna "Origen" (irrelevante en papelera, ahorra ancho).
- Drop conversión cross-currency (si el usuario quiere ver convertido,
  va a la lista normal — la papelera es contexto de "qué borré").
- Nueva columna "Borrada" con tiempo relativo (`hace X min/h/días`).
- Acciones por fila: `Restaurar` (primario tinte) y `Eliminar`
  (tinte danger). Ambas se deshabilitan cuando `busyId === tx.id`.

### Banner "Movido a papelera" + Deshacer

`apps/web/components/transactions/trashed-banner.tsx`:

- Estado interno `visibleId` sincronizado con `lastDeletedId` prop.
  Cambiar la prop a un nuevo ID re-arma el banner; `null` lo oculta.
- Auto-dismiss tras `dismissAfterMs` (default 6s).
- `[Deshacer]` ejecuta `onUndo()` y oculta el banner. `[Ver papelera]`
  link a `/personal-finance/trash`.
- `role="status"` + `aria-live="polite"` para que screen readers lo
  anuncien sin interrumpir.
- Inline en lugar de toast global porque el codebase no tiene aún un
  sistema de toasts. Cuando llegue (Sonner/react-hot-toast/propio),
  reemplazar este banner por una toast call.

### Modificaciones en `/personal-finance/transactions`

`apps/web/app/(app)/personal-finance/transactions/page.tsx`:

- `confirm()` cambia de "¿Eliminar esta transacción?" a "¿Mover esta
  transacción a la papelera?".
- Tras `deleteMutation.mutate`, `onSuccess` setea `lastDeletedId`
  para activar el banner.
- `handleUndo()` resetea el banner y dispara `restoreMutation.mutate`.
- `<TrashedBanner>` renderizado encima de los KPIs.
- Nuevo link "Papelera" en el eyebrow bar (junto a Importar /
  Capturar / Nueva). Muestra badge azul con el contador cuando
  `useTrashedTransactions({limit:1}).total > 0`.

### Tests

`apps/web/components/transactions/trash-list.test.tsx` (5 tests):

- Empty state.
- Render de filas con descripción/categoría.
- Click Restaurar → `onRestore(id)`.
- Click Eliminar → `onPurge(id)`.
- `busyId` deshabilita ambos botones de la fila.

`apps/web/components/transactions/trashed-banner.test.tsx` (4 tests):

- No render con `lastDeletedId=null`.
- Render con mensaje + acciones cuando hay ID.
- Click Deshacer → `onUndo()` + banner oculto.
- Auto-dismiss tras `dismissAfterMs` con `vi.useFakeTimers()`.

Suite web: 20/20 (5 archivos, +9 nuevos vs PHASE-9.1).

## Flujo técnico

```
 Usuario clica "Borrar" en una fila
    │
    ▼
 confirm() — "¿Mover a papelera?"
    │
    ▼ acepta
 deleteMutation.mutate(id)
    │
    ▼ onSuccess
 setLastDeletedId(id)               invalida transactions.all + dashboard.all
    │                                  │
    ▼                                  ▼
 <TrashedBanner> aparece           lista se refresca sin la tx;
 ("Movido a papelera"               summary del header se ajusta;
  + [Deshacer] [Ver papelera])      badge "Papelera N" sube en 1.
    │
    ├── Click Deshacer (dentro de 6s)
    │       │
    │       ▼ restoreMutation.mutate(id)
    │       │   onSuccess → invalida transactions + dashboard
    │       └─→ tx vuelve a la lista; badge baja en 1
    │
    ├── Click Ver papelera → /personal-finance/trash
    │       │
    │       ├── Restaurar    → mismo flujo que [Deshacer]
    │       └── Eliminar     → confirm() → purgeMutation
    │                          → tx desaparece de papelera permanente
    │
    └── 6s sin interacción → banner se oculta automático
        (la tx sigue en papelera; recuperable desde /trash)
```

## Archivos clave

- `packages/types/src/models/transaction.ts` (deleted_at)
- `packages/services/src/api/endpoints/transactions.ts`
  (listTrash/restore/purge)
- `packages/services/src/query/keys.ts` (transactions.trash)
- `packages/services/src/query/hooks/useTransactions.ts`
  (3 hooks nuevos + invalidate dashboard en delete)
- `packages/services/src/index.ts` (re-exports)
- `apps/web/app/(app)/personal-finance/trash/page.tsx` (nuevo)
- `apps/web/components/transactions/trash-list.tsx` (nuevo)
- `apps/web/components/transactions/trashed-banner.tsx` (nuevo)
- `apps/web/app/(app)/personal-finance/transactions/page.tsx`
  (banner + link papelera + restore handler)
- `apps/web/components/transactions/trash-list.test.tsx` (nuevo)
- `apps/web/components/transactions/trashed-banner.test.tsx` (nuevo)

## Endpoints añadidos

Ninguno — consume los de PHASE-10.1.

## Migraciones

Ninguna.

## Verificación

- [x] `pnpm lint` verde.
- [x] `pnpm typecheck` verde.
- [x] `pnpm test` — 20/20 web (3 previos + 9 nuevos en 2 archivos).
- [ ] Smoke manual:
  - [ ] Borrar tx desde la lista → confirm "Mover a papelera" →
        banner aparece, badge "Papelera N" sube, tx desaparece de la
        lista, summary se actualiza.
  - [ ] Click Deshacer dentro de 6s → tx vuelve, badge baja.
  - [ ] Esperar 6s sin tocar → banner desaparece, tx sigue en /trash.
  - [ ] Ir a /trash → ver tx con tiempo relativo "hace X min".
  - [ ] Click Restaurar → tx vuelve, badge baja.
  - [ ] Borrar otra → ir a /trash → click Eliminar → confirm
        permanente → tx desaparece de papelera y no es recuperable.

## Decisiones tomadas

- **Banner inline en lugar de toast global**. El repo no tiene aún
  un sistema de toasts. Introducir uno (Sonner / react-hot-toast)
  para esta fase añadía dependencia y abstracción no justificadas
  por el caso de uso. Cuando un siguiente flujo necesite toasts
  (snackbars de éxito de import, confirmaciones de receipt, etc.),
  ese flujo introduce el sistema y este banner se convierte en una
  llamada `toast(...)` simple.
- **Restore sin confirm; purge con confirm**. Restore es reversible
  (vuelve a borrar es trivial); purge es destructivo permanente. El
  doble check sólo donde tiene valor.
- **Trash list sin conversión cross-currency**. La papelera es
  contexto de "qué borré recientemente" — el importe original es la
  información relevante para identificar la tx. Si el usuario
  necesita el converted amount, tiene la lista normal después de
  restaurar.
- **Badge de papelera vía `useTrashedTransactions({limit:1})`**.
  Una llamada extra por cargar la página de transacciones, pero el
  payload es minúsculo (1 item + total) y el cache key es
  independiente del resto de paginas (`offset:0,limit:1`). Compartir
  cache con la página `/trash` en próximas visitas es bonus.
- **`useDeleteTransaction` ahora invalida dashboard también**. Antes
  no porque DELETE destruía y el dashboard refetcheaba en
  re-navegación; con soft-delete el usuario sigue en la misma
  página y espera ver el cambio en el summary inmediatamente. La
  invalidación es barata (las queries de dashboard se cachean).
- **`busyId` para deshabilitar botones de la fila activa**. Mostrar
  "Restaurando…" en el botón presionado mientras los demás siguen
  clicables — coherente con el patrón de `deletingId` ya usado en
  `TransactionList`.

## Limitaciones conocidas

- **Sin toast global** — el banner inline es ad-hoc para esta
  pantalla. Otros flujos (import, receipt confirm, etc.) siguen sin
  feedback de éxito. Cuando se priorice un sistema de toasts será
  fase aparte.
- **Banner no sobrevive a navegación** — `lastDeletedId` vive en
  `useState` local. Si el usuario borra y navega antes de los 6s,
  pierde la opción de Deshacer (debe ir manualmente a /trash). Si
  molesta, promover a Zustand o a la URL como query param.
- **Sin drag-to-restore ni acciones bulk** — operaciones individuales
  por fila. Si la papelera crece y aparece patrón "borré 50 cosas y
  quiero recuperarlas todas", añadir acciones bulk.
- **Sin filtro/búsqueda en /trash** — vista plana ordenada por
  `deleted_at DESC`. Igual que el backend documentó. Si crece y
  hace falta, añadir filtros entonces.
- **Sin TTL** — heredado de PHASE-10.1: las trasheadas viven
  indefinidamente. Cuando se priorice auto-purge nocturno, el
  endpoint backend lo gestiona y la UI seguirá pintando lo que
  haya.

## Próxima fase

PHASE-10.3 — Frontend papelera mobile (Expo). Reusa los hooks
`useTrashedTransactions / useRestoreTransaction / usePurgeTransaction`
introducidos aquí. Pantalla `trash.tsx` accesible desde el header de
transactions; snackbar de "deshacer" tras delete; Alert nativo para
purge.
