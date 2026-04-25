# PHASE-3.2 — Dashboard frontend

**Estado**: ✅ completada
**Rama**: `feat/phase-3.2-dashboard-frontend`
**PR**: — (push directo a `main` por decisión del usuario)
**Fecha de merge**: 2026-04-24

## Objetivo

Consumir los 4 endpoints de agregación de PHASE-3.1 desde web (Next.js) y
móvil (Expo) con KPIs, gráfica de evolución mensual, donut por categoría y
top 5 de gastos. Pantalla principal post-login en ambas plataformas.

## Qué se implementó

- **Tipos compartidos** en `packages/types`:
  - `DashboardSummary`, `CategoryBreakdownItem`, `MonthlyBucket`, `TopExpenseItem`.
  - Query DTOs `DashboardSummaryQuery`, `DashboardByCategoryQuery`,
    `DashboardByMonthQuery`, `DashboardTopExpensesQuery`.
- **Cliente HTTP** en `packages/services`:
  - `dashboardApi` con `summary` / `byCategory` / `byMonth` / `topExpenses`.
- **Query keys** ampliados:
  - `queryKeys.dashboard.{ all, summary, byCategory, byMonth, topExpenses }`.
  - `normalizeQuery` se hizo genérico (`<T extends object>`) para reutilizarlo
    entre transactions y dashboard.
- **Hooks** TanStack Query: `useDashboardSummary`, `useDashboardByCategory`,
  `useDashboardByMonth`, `useDashboardTopExpenses`. `staleTime` de 60s y
  `placeholderData: previous` para evitar parpadeos al cambiar filtros.
- **`formatMonthLabel`** en `packages/ui` — `"YYYY-MM" → "Abr 2026"`.
- **Web (`apps/web`)**:
  - `app/(dashboard)/dashboard/page.tsx` — vista principal.
  - `components/dashboard/` con `dashboard-filters` (selector año + moneda),
    `kpi-cards`, `monthly-chart` (Recharts BarChart), `category-donut`
    (Recharts PieChart con toggle income/expense, leyenda interactiva) y
    `top-expenses-list`.
  - `app/(dashboard)/layout.tsx`: link "Dashboard" añadido al nav y botón
    "Cerrar sesión" desplazado al extremo derecho.
  - Redirecciones (`/`, `/login`, `/register`) ahora apuntan a `/dashboard`.
  - `app/(dashboard)/home/page.tsx` queda como redirect → `/dashboard` para
    no romper bookmarks viejos.
- **Mobile (`apps/mobile`)**:
  - `app/(tabs)/home.tsx` reescrito como dashboard con `ScrollView` +
    `RefreshControl` (pull-to-refresh refresca las 4 queries).
  - `components/dashboard/` con los mismos 5 componentes adaptados a RN
    (`react-native-gifted-charts` para gráficas, `Modal` para el selector
    de filtros).
  - Tab home renombrado de "Inicio" → "Dashboard".
  - Botón "Salir" en el header de la pantalla.

## Endpoints consumidos

- `GET /dashboard/summary?currency&date_from&date_to`
- `GET /dashboard/by-category?currency&date_from&date_to&kind`
- `GET /dashboard/by-month?year&currency`
- `GET /dashboard/top-expenses?currency&date_from&date_to&limit=5`

## Decisiones tomadas

- **Recharts (web) + react-native-gifted-charts (mobile)**: librerías
  distintas en cada plataforma — el coste de mantener un wrapper
  unificado (Victory Universal, etc.) no compensa para el set de
  gráficas del MVP. Cada plataforma usa lo que mejor encaja.
- **`/home` → redirect a `/dashboard`**: en lugar de borrar la ruta y
  arriesgar 404 si alguien tiene un bookmark, queda como redirect.
- **Currency selector sin persistencia**: el componente vive en el state
  local del dashboard. Cuando aparezca el módulo de "settings/preferences"
  se moverá al store. Default `USD` (consistente con el backend).
- **Año en `by-month` con selector de últimos 5 años**: rango fijo,
  suficiente para el MVP. No filtramos por mes/rango porque
  `by-month` ya devuelve los 12 buckets del año pedido.
- **`date_from` / `date_to` derivados del año seleccionado**: el filtro
  único "año" se usa como rango global para summary/by-category/
  top-expenses. Si en el futuro hace falta granularidad mensual, se
  añadirán los selectores correspondientes.
- **Donut: leyenda click para ocultar (web)**: solo en web, mobile no
  tiene event de click sobre legend de gifted-charts. Aceptable para 3.2.
- **Logout en el dashboard mobile**: como el home ahora es el dashboard,
  el botón "Salir" se mantiene visible en la cabecera de la pantalla.
  Cuando aparezca un menú de perfil se moverá allí.

## Archivos clave

**Tipos**:
- `packages/types/src/models/dashboard.ts`
- `packages/types/src/dto/dashboard.dto.ts`

**Services / Query**:
- `packages/services/src/api/endpoints/dashboard.ts`
- `packages/services/src/query/keys.ts` (ampliado)
- `packages/services/src/query/hooks/useDashboard.ts`

**UI compartida**:
- `packages/ui/src/format.ts` — `formatMonthLabel`

**Web**:
- `apps/web/app/(dashboard)/dashboard/page.tsx`
- `apps/web/components/dashboard/{dashboard-filters,kpi-cards,monthly-chart,category-donut,top-expenses-list}.tsx`
- `apps/web/app/(dashboard)/layout.tsx` (nav + logout)

**Mobile**:
- `apps/mobile/app/(tabs)/home.tsx` (dashboard completo)
- `apps/mobile/components/dashboard/{dashboard-filters,kpi-cards,monthly-chart,category-donut,top-expenses-list}.tsx`

## Tests

- `packages/services/src/api/endpoints/dashboard.test.ts` — 4 tests (cada GET).
- `packages/services/src/query/keys.test.ts` — +3 tests para `dashboard.*`.
- `packages/ui/src/format.test.ts` — +3 tests para `formatMonthLabel`.

Total proyecto: 31 tests verde.

## Verificación

- [x] `pnpm lint` verde.
- [x] `pnpm typecheck` verde.
- [x] `pnpm test` verde (31 tests).
- [x] Flujo manual web: login → `/dashboard`, cambiar año/moneda,
      toggle gastos/ingresos, ver tooltips, navegar a transacciones.
- [x] Flujo manual mobile: login → tab Dashboard, pull-to-refresh,
      cambiar filtros vía modal, ver gráfica y donut, logout.

## Limitaciones conocidas

- Sin agregación multi-moneda: el backend filtra por `currency`, así que
  un usuario que opera en EUR no ve sus datos hasta cambiar el selector.
- `category-donut` mobile no tiene leyenda interactiva (gifted-charts no
  expone evento click en `PieChart`).
- `monthly-chart` mobile usa labels de 3 letras de mes; con 12 meses
  puede quedar apretado en pantallas estrechas — RN gestiona overflow
  pero no es ideal.
- Sin tests UI (web/mobile) — la cobertura sigue centrada en lógica
  pura (formatters, keys, endpoints).

## Próxima fase

PHASE-4.1 — Imports backend (parser CSV/Excel + dedup + estado del job).
