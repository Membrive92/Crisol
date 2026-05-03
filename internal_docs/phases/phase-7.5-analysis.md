# PHASE-7.5 — Analysis sub-tab

**Estado**: 🚧 en curso
**Rama**: `feat/phase-7.5-analysis`
**PR**: —
**Fecha de merge**: —

## Objetivo

Añadir una sección "Análisis" al módulo `personal-finance` con un
enfoque más analítico que el dashboard estándar: bar chart de
ingresos vs gastos, KPIs de flujo de caja neto y tasa de ahorro,
desglose horizontal de gastos por categoría con barra de progreso, y
placeholders explícitos para las features que aún no están construidas
(Smart Insights, Subscripciones recurrentes, Vault de presupuestos,
Comparación con grupos).

## Contexto

El roadmap de PHASE-7 marcaba esta fase como opcional con tres opciones
(a/b/c) y mi recomendación era diferirla (c) hasta tener las features
detrás. El usuario pidió cerrar todas las fases, así que se entrega
con la opción (a): nueva sección del módulo, reutilizando endpoints
existentes, con placeholders honestos para lo no construido.

## Qué se implementó

### Registry (`packages/types/src/registry/modules.ts`)

- Nueva sección `analysis` en `personal-finance.sections` entre
  `dashboard` y `transactions`.
- Path: `/personal-finance/analysis`.
- Las tabs del header del módulo la pintan automáticamente; no hay
  cambios en el shell.

### Página (`apps/web/app/(app)/personal-finance/analysis/page.tsx`)

Layout responsive en tres bloques:

1. **Header** — eyebrow "Análisis financiero", título "Patrones e
   insights", filtros (moneda + año) idénticos a los del dashboard.
2. **Métricas principales** — bar chart `IncomeVsExpensesChart` (2/3
   del ancho) + dos `KpiCard` (Flujo de caja neto, Tasa de ahorro)
   en columna a la derecha (1/3).
3. **Desglose** — `ExpenseBreakdown` (1/2) con top categorías de
   gasto y barra de progreso por porcentaje del total. A la derecha
   dos `ComingSoonCard` (Smart Insights, Comparación con grupos).
4. **Placeholders inferiores** — dos `ComingSoonCard` adicionales
   (Subscripciones recurrentes, Vault de presupuestos).

Smart currency hydration igual que en el dashboard: `useUserCurrencies`
arranca el filtro con la primera moneda real del usuario.

### Componentes (`apps/web/components/analysis/`)

- `coming-soon-card.tsx` — `Card` con bg `surface-muted`, borde
  punteado, eyebrow "Próximamente" en `text-subtle`. Deliberadamente
  discreto para no competir con las secciones que sí tienen datos.
- `income-vs-expenses-chart.tsx` — `BarChart` de recharts con dos
  series por mes (income en `success`, expenses en `expense`),
  `XAxis` con etiquetas mensuales abreviadas (Ene…Dic), tooltip
  formateado con `formatAmount`.
- `expense-breakdown.tsx` — listado horizontal con barra de progreso
  por categoría. Top N (default 6) + bucket "Otros (k)" agrupando el
  resto. Cada fila: nombre + importe + barra + porcentaje. Color de
  barra `expense` para top, `border-strong` muted para "Otros".

### Métricas computadas client-side

- **Flujo de caja neto**: `summary.balance` (income − expenses). Color
  semántico por signo. Footer muestra el balance del periodo previo
  cuando `summary.previous_period_balance` está disponible.
- **Tasa de ahorro**: `(balance / income) * 100`. Si `income === 0`,
  se muestra `—`. Color por signo. Caption fija: "Saldo / ingresos
  del periodo".

## Archivos clave

- `packages/types/src/registry/modules.ts`
- `apps/web/app/(app)/personal-finance/analysis/page.tsx`
- `apps/web/components/analysis/coming-soon-card.tsx`
- `apps/web/components/analysis/income-vs-expenses-chart.tsx`
- `apps/web/components/analysis/expense-breakdown.tsx`

## Endpoints añadidos

Ninguno. Se reusan:

- `GET /dashboard/summary` (con `previous_period_*` para el footer
  del KPI de flujo de caja neto).
- `GET /dashboard/by-month` (12 buckets para el bar chart).
- `GET /dashboard/by-category?kind=expense` (desglose por categoría).
- `GET /dashboard/currencies` (smart currency).

## Migraciones

Ninguna.

## Verificación

- [x] `pnpm typecheck` verde
- [x] `pnpm lint` verde
- [x] `pnpm test` (8/8) verde
- [ ] Smoke manual: `/personal-finance/analysis` con datos reales —
      bar chart pinta los 12 meses, KPI Flujo de caja neto coincide
      con el balance del dashboard, desglose suma 100%.

## Decisiones tomadas

- **Opción (a) del roadmap.** Sección como tab del módulo, no
  sidebar lateral (que rompería el patrón de tabs flat) ni
  sub-ruta del dashboard (que escondería la página). El usuario que
  busque "análisis" lo verá en la barra de secciones.
- **Placeholders honestos.** En lugar de mockear datos para Smart
  Insights / Vault / Peer Group, se entregan tarjetas explícitas
  "Próximamente" con la descripción de la feature. El usuario sabe
  qué viene; el equipo no acumula deuda visual.
- **Sin endpoint nuevo de `saving_rate`.** Se calcula en cliente
  desde `summary.balance / summary.income` para no añadir un endpoint
  que sólo es una división. Si hace falta exponerlo en mobile más
  adelante, se moverá al backend.
- **`ExpenseBreakdown` no es un donut**. Diferenciarse del donut del
  dashboard tiene valor: lista horizontal con barra de progreso
  comunica mejor "qué porcentaje del total se va en X" que un pie
  chart, sobre todo cuando hay muchas categorías pequeñas.

## Limitaciones conocidas

- Smart Insights / Subscripciones recurrentes / Vault / Peer Group son
  placeholders. Cada uno requiere backend nuevo (modelo de datos para
  presupuestos, detección de recurrencia, llamada a IA local…) que
  está fuera del alcance de PHASE-7. Quedan como candidatas a
  PHASE-8.
- No hay versión mobile de la página de Análisis. El roadmap original
  no la pedía y el bar chart de recharts no es trivial de portar a
  RN (se usaría `react-native-gifted-charts` con otro layout). Si se
  pide, sería una sub-fase 7.5-mobile.
- El delta del Flujo de caja neto se muestra como texto estático
  "Periodo previo: X €" en el footer del KPI, no como porcentaje con
  flecha como en el dashboard. Decisión consciente: en Análisis los
  números son protagonistas y el dato bruto del periodo previo se
  lee mejor que un delta relativo.

## Próxima fase

PHASE-7 completa. Próximas candidatas:

- PHASE-8 — Smart Insights / Subscripciones recurrentes (módulo `ai`).
- PHASE-9 — Vault de presupuestos (modelo nuevo + alertas).
- PHASE-7.4-mobile-followup — replicar la página de Análisis en mobile
  si los usuarios lo piden.
