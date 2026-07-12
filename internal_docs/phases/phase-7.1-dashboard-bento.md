# PHASE-7.1 — Dashboard bento + delta vs periodo anterior

**Estado**: ✅ completada
**Rama**: `feat/phase-7.1-dashboard-bento`
**PR**: —
**Fecha de merge**: —

## Objetivo

Reescribir el dashboard con un layout bento más denso, KPIs con delta
vs periodo anterior, sidebar de "Actividad reciente", FAB contextual y
arranque inteligente del filtro de moneda. Trabajo derivado del
ejercicio Stitch que se decidió en PHASE-7.

## Qué se implementó

### Backend (`backend/app/modules/personal_finance/dashboard/`)

- `schemas.SummaryResponse` añade tres campos:
  `previous_period_income`, `previous_period_expenses`,
  `previous_period_balance` (`Decimal | None`). Sólo se rellenan cuando
  el caller envía `date_from` y `date_to` — sin rango quedan `None` y
  el frontend no pinta delta.
- `service.get_summary` calcula el periodo previo de igual longitud
  terminando justo antes de `date_from`, vuelve a llamar a
  `repository.get_totals_by_kind` para ese rango y devuelve los
  importes en los nuevos campos.
- Nuevo endpoint `GET /dashboard/currencies` → `list[str]` con las
  monedas distintas en las transacciones del usuario, ordenadas
  alfabéticamente. Implementado en `repository.list_user_currencies`
  (`select(Transaction.currency).distinct().order_by(...)`).
- 6 tests nuevos en `test_dashboard.py`:
  - `test_summary_previous_period_null_without_date_range`
  - `test_summary_previous_period_computed_with_date_range`
  - `test_summary_previous_period_zero_when_no_prior_data`
  - `test_currencies_returns_distinct_user_currencies`
  - `test_currencies_empty_for_new_user`
  - `test_currencies_isolated_per_user`

  Más el ya existente `test_dashboard_requires_auth` ampliado para
  incluir `/dashboard/currencies`.

### Tipos compartidos (`packages/types`)

- `DashboardSummary` añade los tres `previous_period_*: string | null`.
  Los importes viajan como string desde el backend (Pydantic Decimal
  serializado), idéntico al resto.

### Services (`packages/services`)

- `dashboardApi.currencies()` → `Promise<string[]>`.
- Hook `useUserCurrencies()` con `staleTime: 5 min` (cambia poco — se
  invalida sólo si el usuario crea/borra transacciones en otra moneda).
- `queryKeys.dashboard.currencies()`.

### Frontend (`apps/web/components/dashboard/`)

- `kpi-cards.tsx` reescrito: usa el `<KpiCard>` de PHASE-7.0 con tres
  KPIs (Saldo, Ingresos, Gastos). El cuarto card "Movimientos" se
  retira para no duplicar el conteo (ya está en el sidebar de
  actividad).
- Cada KPI tiene un `<KpiDelta>` en el slot `footer` con la flecha,
  porcentaje y "vs periodo anterior". Polaridad por KPI:
  `Saldo` y `Ingresos` usan `up=good`; `Gastos` usa `up=bad` (subir
  gastos es negativo).
- `kpi-delta.tsx` nuevo: oculta el delta cuando no hay periodo previo
  o el cambio es exactamente 0 (texto "Sin cambio"). Si el periodo
  previo es 0, muestra sólo el signo sin porcentaje.
- `recent-activity.tsx` nuevo: card con las últimas 5 transacciones
  (`useTransactions({ limit: 5 })`). Cada fila enlaza al detalle.
- `tip-card.tsx` nuevo: tarjeta tonal `primary-soft` con copy
  estático. Follow-up PHASE-7.1.1 para cablear al módulo `ai`.
- `dashboard-filters.tsx`: pasa a aceptar `currencies?: string[]`. Si
  está vacío, usa `FALLBACK_CURRENCIES = ['EUR', 'USD']`. Si la moneda
  activa no está en la lista, se añade al final (no se pierde la
  selección al borrar la última transacción de esa moneda).
- `apps/web/app/(app)/personal-finance/dashboard/page.tsx`: layout
  bento responsive:
  - Header con título + filtros alineados a la derecha.
  - Fila 1: 3 KPIs (Saldo, Ingresos, Gastos).
  - Fila 2: gráfica mensual (2/3) + actividad reciente (1/3).
  - Fila 3: donut por categoría + top expenses + tip card.
  - FAB `<FabLink>` "+" abajo a la derecha apuntando a
    `/personal-finance/transactions/new`.
- Smart currency hydration: tras el primer fetch de
  `useUserCurrencies()`, si la moneda actual del filtro no está entre
  las del usuario, se cambia a la primera real. Sólo se hace una vez
  (flag `currencyHydrated`) para no pisar la elección manual.

## Flujo técnico

```
DashboardPage
  ├─ useUserCurrencies()         → hidrata filters.currency (1ª vez)
  ├─ useDashboardSummary()       → KpiCards + KpiDelta (clientside)
  ├─ useDashboardByMonth()       → MonthlyChart
  ├─ useDashboardByCategory()    → CategoryDonut (kind=all|income|expense)
  ├─ useDashboardTopExpenses()   → TopExpensesList
  └─ <RecentActivity />
       └─ useTransactions({ limit: 5 })
```

## Archivos clave

- `backend/app/modules/personal_finance/dashboard/schemas.py`
- `backend/app/modules/personal_finance/dashboard/service.py`
- `backend/app/modules/personal_finance/dashboard/repository.py`
- `backend/app/modules/personal_finance/dashboard/router.py`
- `backend/tests/test_dashboard.py`
- `packages/types/src/models/dashboard.ts`
- `packages/services/src/api/endpoints/dashboard.ts`
- `packages/services/src/query/hooks/useDashboard.ts`
- `packages/services/src/query/keys.ts`
- `apps/web/components/dashboard/kpi-cards.tsx`
- `apps/web/components/dashboard/kpi-delta.tsx`
- `apps/web/components/dashboard/recent-activity.tsx`
- `apps/web/components/dashboard/tip-card.tsx`
- `apps/web/components/dashboard/dashboard-filters.tsx`
- `apps/web/app/(app)/personal-finance/dashboard/page.tsx`

## Endpoints añadidos

- `GET /dashboard/currencies` — monedas distintas del usuario.

`GET /dashboard/summary` extiende su payload con
`previous_period_income/expenses/balance`. Sin breaking changes — los
clientes anteriores ignoran los campos nuevos.

## Migraciones

Ninguna.

## Verificación

- [x] `pytest tests/test_dashboard.py -v` (19/19)
- [x] `pnpm typecheck` verde
- [x] `pnpm lint` verde
- [x] `pnpm test` (8/8)
- [ ] Smoke manual: `/personal-finance/dashboard` con datos reales —
      KPIs con delta, sidebar con últimas 5, FAB navega a "Nueva
      transacción".
- [ ] Smoke manual: cambiar año en filtro → KPIs y delta recalculan.

## Decisiones tomadas

- **`previous_period_*` opcional, no separado en otra ruta.** Pasamos
  los datos con la summary existente para evitar dos round-trips.
  Quien no necesite delta ignora los campos.
- **El delta lo calcula el frontend.** El backend devuelve absolutos;
  el frontend hace `(curr - prev) / |prev|`. Mantiene el backend como
  pure aggregator y el frontend libre de cambiar la presentación
  (porcentaje vs absoluto vs gráfica) sin tocar API.
- **Sidebar "Actividad reciente" reusa `/transactions`.** No se crea
  un endpoint dedicado: `GET /transactions?limit=5` ya devuelve lo
  necesario y la cache se comparte con la página de Transactions.
- **Tip card como placeholder.** El consejo IA-driven es trabajo
  significativo (módulo ai → análisis del usuario → prompt → guardar /
  invalidar). Lo dejo como follow-up explícito en lugar de mockearlo
  con generación on-demand.

## Limitaciones conocidas

- El KpiDelta no rinde con `previous=0` y `current!=0` con porcentaje
  (no se puede dividir por 0). Muestra sólo el signo sin %. Suficiente
  pero podríamos pintar "Nuevo" como caption en una iteración.
- El FAB siempre apunta a "Nueva transacción". Si en el futuro la
  acción contextual cambia por sub-ruta (ej. `/imports/new` desde la
  sección de imports), habrá que aceptar `href` desde el caller en
  lugar de hardcodearlo en la página.
- `RecentActivity` no diferencia visualmente income vs expense porque
  el `amount` se guarda siempre positivo y la dirección la determina
  el `category.kind`, que en esta vista compacta no consultamos. La
  página de Transactions sí lo hará en PHASE-7.2.

## Próxima fase

PHASE-7.2 — Transactions tabla.
