# PHASE-13.2 — Frontend web de subscripciones

**Estado**: ✅ completada
**Rama**: `feat/phase-13.2-subscriptions-web`
**Fecha de merge**: 2026-05-05

## Objetivo

Consumir el backend de PHASE-13.1: capa shared en `packages/*` +
ruta `/personal-finance/subscriptions` con secciones "Sugeridas
(pendientes)" y "Confirmadas", botón Re-escanear, y la sección
"Subscripciones" en la navegación del módulo.

## Qué se implementó

### Capa shared

- **`packages/types/src/models/subscription.ts`** (nuevo):
  `Subscription`, `SubscriptionStatus`, `SubscriptionScanResponse`.
- **`packages/services/src/api/endpoints/subscriptions.ts`** (nuevo):
  `subscriptionsApi.list/get/scan/confirm/dismiss/remove` +
  `SubscriptionListQuery`.
- **`packages/services/src/query/keys.ts`**:
  `queryKeys.subscriptions.{all,list(status?),detail(id)}`.
- **`packages/services/src/query/hooks/useSubscriptions.ts`** (nuevo):
  `useSubscriptions(query)`, `useSubscription(id)`,
  `useScanSubscriptions`, `useConfirmSubscription`,
  `useDismissSubscription`, `useDeleteSubscription`. Mutations
  invalidan `subscriptions.all` para refrescar pending + confirmed
  + detail al unísono.
- Re-exports en ambos `index.ts`.

### Registro de módulo

`personal-finance.sections` añade
`{ key: 'subscriptions', label: 'Subscripciones', path: '/personal-finance/subscriptions' }`.
Sidebar/tabs lo recogen automáticamente.

### Componente `SubscriptionCard`

`apps/web/components/subscriptions/subscription-card.tsx`:

- Reusable entre secciones — los callers controlan qué acciones
  ofrecer vía `primaryAction` y `secondaryAction` props.
- Header con `raw_description` (sample legible), amount, cadencia
  legible (`Mensual` / `Anual` / etc.), categoría sugerida y
  confianza %.
- Footer con `next_due` formateado + `occurrence_count` + botones
  de acción.

### Página `/personal-finance/subscriptions`

`apps/web/app/(app)/personal-finance/subscriptions/page.tsx`:

- Header con título, descripción del flujo (incl. "heurística
  local, sin enviar datos fuera del equipo") y botón **Re-escanear**
  → toast con `created`/`updated`.
- Sección **Sugeridas (pendientes)** con cards [Confirmar /
  Descartar]. Empty state dashed cuando no hay.
- Sección **Confirmadas** (sólo si hay) con cards y botón Eliminar
  (confirm nativo + toast).
- Toasts cubren todos los success/error vía `formatApiError` +
  PHASE-11.3 toaster.

### Tests `subscription-card.test.tsx` (5)

- Render con description/amount/cadencia/categoría/confianza.
- `primaryAction.onClick` llamado al pulsar.
- `secondaryAction.onClick` llamado al pulsar.
- "Sin categoría" cuando `category_id=null`.
- Cadencia 365 → "Anual".

Suite web: **32 tests** (+5 nuevos).

## Archivos clave

- `packages/types/src/models/subscription.ts` (nuevo)
- `packages/types/src/index.ts` (re-exports)
- `packages/types/src/registry/modules.ts` (sección `subscriptions`)
- `packages/services/src/api/endpoints/subscriptions.ts` (nuevo)
- `packages/services/src/query/keys.ts` (`subscriptions.*`)
- `packages/services/src/query/hooks/useSubscriptions.ts` (nuevo)
- `packages/services/src/index.ts` (re-exports)
- `apps/web/components/subscriptions/subscription-card.tsx` (nuevo)
- `apps/web/components/subscriptions/subscription-card.test.tsx` (nuevo, 5 tests)
- `apps/web/app/(app)/personal-finance/subscriptions/page.tsx` (nuevo)

## Verificación

- [x] `pnpm typecheck` verde.
- [x] `pnpm lint` verde.
- [x] `pnpm test` — 32 web + 5 mobile = 37 tests, sin regresiones.
- [ ] Smoke manual:
  - [ ] Navegar a `/personal-finance/subscriptions` desde la pestaña.
  - [ ] Sin sugerencias → empty state. Insertar 4 cargos mensuales
        de "NETFLIX.COM 12.99 EUR" (vía Transacciones), pulsar
        "Re-escanear" → toast con `created: 1` + card aparece en
        "Sugeridas".
  - [ ] Confirmar → toast.success + pasa a "Confirmadas".
  - [ ] Descartar otra → toast.info + desaparece.
  - [ ] Eliminar una confirmada → confirm + toast + desaparece.

## Decisiones tomadas

- **Dos queries separadas para pending y confirmed**. Permite empty
  states por sección y caches independientes (la confirmed-list es
  más estable, la pending-list cambia con cada scan). Trade-off:
  dos network calls; acceptable.
- **No exponer las dismissed en la UI por defecto**. Son
  "rechazadas", el usuario no quiere verlas. Si llega un caso "ver
  qué he descartado para reactivarlo", añadir un toggle o sección
  colapsable (los hooks ya soportan `status: 'dismissed'`).
- **`SubscriptionCard` con `primary/secondaryAction` props
  flexibles**. Mismo componente sirve a pending (Confirmar +
  Descartar) y confirmed (Eliminar). Si llegan más estados, se
  añaden actions sin tocar el componente.
- **`Re-escanear` como botón secondary en el header**. Sugiere
  que el flujo principal es esperar al cron diario; el botón es la
  vía rápida cuando el usuario importó muchas transacciones.
- **Confirm nativo (window.confirm) para eliminar confirmadas**.
  Patrón ya establecido en transactions/budgets web. Cuando se
  introduzca un sistema de modales, migrar todos a la vez.
- **Categoría sugerida sólo se muestra (no editable)**. Si el
  detector se equivoca con la categoría, el usuario edita la
  categoría de las transacciones individuales — la subscripción no
  rige las txs futuras (es sólo metadata). UI de edición pendiente
  como follow-up.

## Limitaciones conocidas

- **Sin sección "Descartadas"** — los datos están, falta UI.
- **Sin edición** — amount, currency, category_id de una
  subscripción no se pueden cambiar desde la UI. Backend tampoco
  expone PUT (decisión de PHASE-13.1: la huella es la subscripción;
  cambios significan dismiss + nueva).
- **Sin "pause" entre confirmed y dismissed** — heredado de
  PHASE-13.1 backlog.
- **Sin gráfica de gasto en subscripciones**. Sumar el coste
  mensual/anual de las confirmed sería un widget natural en
  dashboard. Sub-fase futura.

## Próxima fase

PHASE-13.3 — Frontend mobile. Reusa los hooks shared. Pantalla
`/subscriptions` accesible desde el header de Análisis (igual que
budgets); cards con acciones mobile.
