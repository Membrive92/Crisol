# PHASE-7.4 — Mobile parity

**Estado**: 🚧 en curso
**Rama**: `feat/phase-7.4-mobile-parity`
**PR**: —
**Fecha de merge**: —

## Objetivo

Aplicar al app mobile el mismo lenguaje visual y comportamiento que se
añadió en PHASE-7.1–7.3 al web: primitives nuevos, KPI con delta vs
periodo anterior, smart currency default, opción "Total" en el donut,
y FAB contextual en el dashboard.

## Qué se implementó

### Mobile primitives nuevos (`apps/mobile/components/ui/`)

- `category-chip.tsx` — versión RN del CategoryChip web. `View` + `Text`
  con paleta tonal (`income → success-soft+success`, `expense →
  danger-soft+danger`, `null → primary-soft+primary`). Misma jerarquía
  visual que el web.
- `origin-badge.tsx` — versión RN del OriginBadge web. Tres variantes:
  `manual` (neutral), `import` (primary tinted), `receipt` (success
  tinted).
- `kpi-delta.tsx` — flecha + porcentaje + caption "vs anterior".
  Soporta `polarity` (`up=good` | `up=bad`) y los mismos casos límite
  que el web (sin previo → null, diff=0 → "Sin cambio", previo=0 →
  signo sin %).
- `fab.tsx` — `FabLink` con `Pressable` + `expo-router`. 56×56
  circular, primary filled, sombra fuerte. `accessibilityLabel`
  obligatorio.

### Dashboard mobile actualizado

- `apps/mobile/components/dashboard/kpi-cards.tsx`: cuatro KPIs (Saldo,
  Ingresos, Gastos, Movimientos) con `<KpiDelta>` en el footer cuando
  `summary.previous_period_*` está disponible. Polaridad por KPI: Saldo
  e Ingresos `up=good`, Gastos `up=bad`. Movimientos sin delta —
  mantiene el card compacto.
- `apps/mobile/components/dashboard/dashboard-filters.tsx`: acepta
  `currencies?: string[]`. Si está vacío usa `FALLBACK_CURRENCIES =
  ['EUR', 'USD']`. Si la moneda activa no está en la lista, se añade
  al final para no perder selección. Texto del option seleccionado
  usa `colors.onPrimary` en lugar de `surface` (consistencia con
  PHASE-7.1).
- `apps/mobile/components/dashboard/category-donut.tsx`: nuevo tipo
  `DonutKindFilter = 'all' | 'income' | 'expense'` y tres botones de
  toggle (Total / Gastos / Ingresos). Texto activo usa `onPrimary`.
- `apps/mobile/app/(modules)/personal-finance/(tabs)/home.tsx`:
  - Default currency `EUR` en lugar de `USD`.
  - Hook `useUserCurrencies()` para hidratar el filtro con la primera
    moneda real del usuario (idéntica lógica al web).
  - `donutKind` arranca en `'all'`.
  - Estructura cambia de `ScrollView` directo a `View` que envuelve
    `ScrollView` + `<FabLink>` para que el botón flotante quede sobre
    el scroll y no se desplace con él.

## Archivos clave

- `apps/mobile/components/ui/category-chip.tsx`
- `apps/mobile/components/ui/origin-badge.tsx`
- `apps/mobile/components/ui/kpi-delta.tsx`
- `apps/mobile/components/ui/fab.tsx`
- `apps/mobile/components/dashboard/kpi-cards.tsx`
- `apps/mobile/components/dashboard/dashboard-filters.tsx`
- `apps/mobile/components/dashboard/category-donut.tsx`
- `apps/mobile/app/(modules)/personal-finance/(tabs)/home.tsx`

## Endpoints añadidos

Ninguno. Se reusa `GET /dashboard/currencies` y los `previous_period_*`
de `GET /dashboard/summary` introducidos en PHASE-7.1.

## Migraciones

Ninguna.

## Verificación

- [x] `pnpm typecheck` verde
- [x] `pnpm lint` verde
- [ ] Smoke manual en simulador iOS / dispositivo Android — KPIs con
      delta, filtros respetan monedas reales, donut con tres tabs,
      FAB navega a `transaction/new`.

## Decisiones tomadas

- **Primitives mobile separados de los web** — `apps/mobile/components/ui/`
  vs `apps/web/components/ui/`. RN no comparte runtime con web (no hay
  `<button>`, no hay CSS), así que duplicar es la forma sensata. Los
  tokens de `@finanzas/ui` aseguran que los valores son los mismos.
  Confirma ADR-0001.
- **`FabLink` mobile sólo (no `FabButton`).** Mobile no tiene casos
  donde el FAB dispare lógica inline; siempre navega a una ruta. Si
  aparece la necesidad, se añade.
- **No se replica `DataTable` en mobile.** Las pantallas de lista en
  mobile (transactions, receipts) seguirán siendo cards apilados —
  apropiado para viewports estrechos. La tabla densa es un patrón
  desktop.
- **Listas mobile (transactions, receipts) sin cambios en este PR.**
  Su layout actual ya funciona en mobile y reescribirlo a tablas no
  aporta. Quedan como están.

## Limitaciones conocidas

- El FAB del dashboard mobile siempre apunta a `transaction/new`. Si
  la acción contextual cambia por sub-ruta (ej. desde Tickets debería
  ir a `receipt/new`), habrá que añadir un FAB por pantalla o pasar
  `href` desde el caller.
- No se ha añadido un FAB a `receipts.tsx` ni a `transactions.tsx`
  porque esas pantallas tienen ya su propio botón "+ ..." en el
  header. Se deja como follow-up si se quiere consistencia visual.
- Las pantallas de listado mobile (transactions, receipts) siguen
  usando los componentes anteriores. No se introducen los chips
  (`CategoryChip`, `OriginBadge`) ahí en este PR — quedaría para una
  pasada de polish concreta si se ve necesario tras testear.

## Próxima fase

PHASE-7.5 — Analysis sub-tab (opcional).
