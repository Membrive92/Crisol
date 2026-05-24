# PHASE-25 — Drill-down de categoría desde el desglose

**Estado**: ✅ completada
**Rama**: `feat/phase-24-debt-from-source` (continúa la rama abierta)
**Fecha de merge**: 2026-05-20

## Objetivo

La card "Desglose de gastos" en `/personal-finance/analysis` (web) y
el donut equivalente en el dashboard mobile listaban las categorías
sin más, sin permitir profundizar. PHASE-25 convierte esos items en
acciones:

- **Click en una categoría** → nueva pantalla con KPIs + evolución
  mensual + top movimientos de esa categoría.
- **Click en "Otros (N)"** → el bucket agregado se expande en el
  propio gráfico, mostrando las N categorías individualmente; cada
  una ya clicable.

## Qué se implementó

### Backend

- **`dashboard/schemas.py`** — nuevos modelos:
  - `CategoryMonthlyBucket` (mes + total).
  - `CategoryDetailResponse` con `category_*`, `currency`, `total`,
    `count`, `average_amount`, `by_month`, `top_transactions`.
- **`dashboard/repository.py`** — tres queries nuevas:
  - `get_category_kpis` → total + count en rango.
  - `get_category_monthly_evolution` → serie temporal de la
    categoría (últimos N meses).
  - `get_category_top_transactions` → top 10 tx por importe.
  Las tres respetan exclusiones de cashflow (papelera +
  transferencias) y soportan ambos modos de moneda (legacy +
  cross-currency).
- **`dashboard/service.py::get_category_detail`** orquesta:
  resuelve modo moneda → garantiza rates si es cross-currency →
  ejecuta las tres queries → devuelve `CategoryDetailResponse`.
  404 si la categoría no es del usuario. El `total` se cuantiza a
  céntimos para que Pydantic serialice siempre `"0.00"` cuando no
  hay datos.
- **`dashboard/router.py`** — `GET /dashboard/category/{id}` con
  query params: `currency` / `target_currency`, `date_from`,
  `date_to`, `months_back` (1-36, default 12).

### Frontend shared

- `@crisol/types`:
  - `CategoryDetail`, `CategoryMonthlyBucket`.
  - `DashboardCategoryDetailQuery`.
- `@crisol/services`:
  - `dashboardApi.categoryDetail(id, query)`.
  - `useCategoryDetail(id, query)` (disabled si id es undefined).

### Frontend web

- **`components/analysis/stitch-expense-breakdown.tsx`**:
  - Cada `Slice` lleva `categoryId` + `groupedItems`.
  - `handleSliceClick`: si es "Otros" → expande (state local); si es
    categoría real → `router.push(/analysis/category/:id)`.
  - `<Pie onClick>` + LegendRow con `role="button"`, foco accesible
    via Tab + Enter/Space, cursor pointer, title tooltip.
  - Estado `otherExpanded` invierte el slicing (sin top N cap)
    cuando se ha desplegado.
- **`app/(app)/personal-finance/analysis/category/[id]/page.tsx`** (nuevo):
  - Header con icono + color de categoría + eyebrow "Categoría · Gasto/Ingreso".
  - Toggle de periodo (reutiliza `StitchPeriodToggle`) — mismo set
    que el padre `/analysis`.
  - Tres KPIs: total del periodo, número de movimientos, ticket
    medio.
  - BarChart de Recharts con la evolución mensual (color = color de
    la categoría).
  - Tabla "Top movimientos" con descripción enlazable al detalle de
    cada tx.

### Frontend mobile

- **`components/dashboard/category-donut.tsx`**: idéntica
  refactorización al web — `handlePress` que navega a la nueva
  pantalla, `otherExpanded` para expandir el bucket. El
  long-press preserva el comportamiento de "destacar slice" del
  PHASE-18.2.
- **`app/(modules)/personal-finance/analysis/category/[id].tsx`**
  (nuevo): KPIs + `BarChart` de gifted-charts + lista de top tx
  enlazables al detalle.

### Tests backend

`tests/test_dashboard.py` (+4 tests, módulo 23/23):

- `test_category_detail_returns_kpis_and_evolution`: total/count/
  ticket medio + evolución mensual + top tx ordenadas desc.
- `test_category_detail_404_when_not_owned`: aislamiento entre
  users.
- `test_category_detail_filters_by_date_range`: `date_from`/`date_to`
  filtran KPIs y top tx pero NO `by_month` (que mira últimos N meses
  con su propio horizonte).
- `test_category_detail_zero_count_when_no_tx`: categoría sin tx
  devuelve "0.00" cuantizado, listas vacías.

## Flujo técnico

```
Usuario en /personal-finance/analysis
    │ Card "Desglose de gastos" lista categorías + bucket "Otros (7)"
    │
    ├── Click "Tarjeta de crédito"
    │       │ stitch-expense-breakdown.handleSliceClick(slice)
    │       │ → router.push('/analysis/category/<id>')
    │       ▼
    │   /analysis/category/<id>
    │       │ useCategoryDetail(id, { currency, date_from, date_to })
    │       │ → GET /dashboard/category/<id>?currency=EUR&...
    │       │   ↳ backend: KPIs + by_month + top_transactions
    │       ▼
    │   UI muestra:
    │     - Header con icono + nombre + kind
    │     - Toggle periodo (mes/trim/año)
    │     - KPIs (total, count, ticket medio)
    │     - BarChart mensual (color = color de la categoría)
    │     - Tabla top 10 tx con enlaces al detalle
    │
    └── Click "Otros (7)"
            │ stitch-expense-breakdown.handleSliceClick(otherSlice)
            │ → setOtherExpanded(true)  // estado local
            │ → rerender SIN top N cap → muestra las 7 categorías
            ▼
        Cada una ya es clicable → drill-down individual
```

## Archivos clave

Backend:
- `backend/app/modules/personal_finance/dashboard/{schemas,repository,service,router}.py`

Frontend shared:
- `packages/types/src/models/dashboard.ts`
- `packages/types/src/dto/dashboard.dto.ts`
- `packages/services/src/api/endpoints/dashboard.ts`
- `packages/services/src/query/hooks/useDashboard.ts`
- `packages/services/src/query/keys.ts`

Frontend web:
- `apps/web/components/analysis/stitch-expense-breakdown.tsx`
- `apps/web/app/(app)/personal-finance/analysis/category/[id]/page.tsx` (nuevo)

Frontend mobile:
- `apps/mobile/components/dashboard/category-donut.tsx`
- `apps/mobile/app/(modules)/personal-finance/analysis/category/[id].tsx` (nuevo)

## Endpoints añadidos

- `GET /dashboard/category/{category_id}` — drill-down: KPIs +
  evolución mensual + top tx.

## Verificación

- [x] `pytest tests/test_dashboard.py` — 23/23 verde (+4 PHASE-25).
- [x] `pytest` completo (en background) — sin regresiones esperadas.
- [x] `pnpm typecheck` — 4/4 verde.
- [x] `pnpm lint` — 4/4 verde.
- [x] `pnpm test` — 46 web + 18 mobile verde.

## Decisiones tomadas

- **`by_month` no respeta el rango del periodo**: el toggle controla
  KPIs + top tx, pero la evolución mensual siempre mira los últimos
  N meses con su propio horizonte (default 12). Razón: tener una
  serie estable independientemente del filtro permite contexto
  histórico ("este mes fue el más bajo del año").
- **"Otros" expandible en lugar de "Otros" clicable**: una lista
  combinada de 7 categorías mezcladas sería menos útil que ver las 7
  individualmente — cada una con su peso visual y oferta a drill-down
  propio. El estado `otherExpanded` se resetea al re-montar la card
  (cambio de periodo, etc.).
- **Long-press para "destacar slice" en mobile**: el tap simple
  ahora navega; el long-press mantiene el comportamiento previo
  (PHASE-18.2) de aislar visualmente un slice sin salir del donut.
- **No reutilizamos `/dashboard/by-category` con filtro**: hubiera
  requerido fan-out de queries en el frontend (KPIs + monthly + top
  tx serían 3-4 llamadas). Un solo endpoint compone todo en backend
  → menos round-trips, response cacheable como unidad.

## Limitaciones conocidas

- La pantalla de detalle no permite **editar la categoría** desde
  ahí — para renombrarla / cambiar color, sigues yendo a Settings →
  Categorías.
- "Top movimientos" muestra 10 fijo, sin paginación. Para ver más
  hay que ir a la lista de transacciones (link en cada fila).
- La evolución mensual se basa en `Transaction.occurred_at` con
  `to_char(date, 'YYYY-MM')` → asume zona horaria UTC implícita en
  Postgres. Para usuarios en otra zona, el último día del mes puede
  caer al siguiente bucket. No es bloqueante.

## Próxima fase

PHASE-26 — Cross-currency transfers (pendiente desde PHASE-23.1).
