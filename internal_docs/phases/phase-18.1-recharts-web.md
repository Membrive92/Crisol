# PHASE-18.1 — Recharts en web

**Estado**: ✅ completada
**Rama**: `feat/phase-18.1-recharts-web`
**Fecha de merge**: 2026-05-07

## Objetivo

Las gráficas web (balance evolution, income vs expenses, desglose
de gastos) eran hand-rolled con divs/inline-styles: barras a baja
opacidad por defecto, sin eje Y, valores sólo visibles al hacer
hover. Migrar a [Recharts](https://recharts.org) para tener ejes,
ticks formateados, tooltips persistentes, animaciones y
accesibilidad por defecto. La app va a seguir creciendo y
añadiendo módulos (crypto, inversiones, inmuebles) — la inversión
en una lib de charts compensa.

## Qué se implementó

### Gráficas migradas

- **`StitchBalanceChart`** (dashboard) → `BarChart` con:
  - Eje X custom `<MonthTick>` que pinta el mes actual en
    `colors.primary` y semibold.
  - Eje Y con `formatCompact` (ticks `1,2k €`, `1,5M €`) — evita
    overflow del eje en pantallas estrechas.
  - `<CartesianGrid>` horizontal sutil + `<ReferenceLine y={0}>`
    para que se intuya el cero cuando hay balances negativos.
  - `<Cell>` por barra: mes actual en `primary`, resto en
    `primarySoft`, opacidad reducida si negativo.
  - Tooltip card-style con mes label + monto formateado;
    color rojo si balance negativo.
- **`StitchIncomeVsExpenses`** (Análisis) → `BarChart` con:
  - **Barras agrupadas** (income al lado de expenses) en lugar
    del stacked-confuso anterior. Mucho más legible.
  - Leyenda persistente con dots de color en lugar de inline
    rendering custom.
  - Tooltip multi-fila que muestra ambos valores con su color.
- **`StitchExpenseBreakdown`** (Análisis) — **convertido a donut**:
  - `PieChart` con `innerRadius=62 / outerRadius=92`,
    `paddingAngle=2` (separación entre slices), animación de
    entrada.
  - **Centro fijo** con "Total" + monto formateado.
  - **Leyenda lateral** lista con icono de categoría + nombre +
    amount + porcentaje. Hover sincronizado: hover en el slice
    resalta la fila de la leyenda y viceversa (los slices no
    activos bajan opacidad a 0.45).
  - Top N + "Otros (k)" (mismo agrupado que la versión anterior).

### Conversión vs anteriormente hand-rolled

- **Eje Y siempre visible** — antes no había, ahora con ticks
  formateados.
- **Barras con su color sólido por defecto** — antes a opacidad
  baja hasta hover.
- **Animación de entrada** — antes nada.
- **Tooltips uniformes** — antes cada chart tenía su tooltip
  hand-rolled con posicionamiento custom.

### Dependencia

- `recharts ^3.x` en `apps/web` (no en packages para no acoplar
  el monorepo). Bundle ~95kb gzipped — aceptable para una app
  personal con plan de crecer.

## Archivos clave

- `apps/web/components/dashboard/stitch-balance-chart.tsx` (reescrito)
- `apps/web/components/analysis/stitch-income-vs-expenses.tsx` (reescrito)
- `apps/web/components/analysis/stitch-expense-breakdown.tsx` (lista → donut)
- `apps/web/package.json` (`recharts` añadido)

## Verificación

- [x] `pnpm typecheck` y `pnpm lint` verdes.
- [x] `pnpm test` — 40 web + 18 mobile sin regresiones.
- [ ] Smoke:
  - [ ] Dashboard: eje Y con ticks `1,2k €`, mes actual
        resaltado, tooltip al hover sin que la barra cambie
        de opacidad.
  - [ ] Análisis: barras agrupadas Ingresos/Gastos, leyenda
        siempre visible, tooltip muestra ambos valores.
  - [ ] Análisis: donut con centro fijo `Total {monto}`,
        hover en slice resalta la leyenda.

## Decisiones tomadas

- **Recharts en lugar de Tremor / Visx**. Tremor es Tailwind-only
  (no encaja con el `colors`/`spacing` tokens del proyecto).
  Visx es más bajo nivel — ahorra ~30kb pero el coste de
  componer cada chart desde primitives no compensa para 3
  gráficas. Recharts da el equilibrio bueno: defaults pulidos
  + customización fácil con tokens de `@finanzas/ui`.
- **Bar agrupado en lugar de stacked en Income vs Expenses**.
  El stacked anterior era confuso (income encima, expenses
  debajo en la misma columna) — visualmente se interpreta
  como suma cuando son cantidades independientes.
- **Donut + leyenda lateral en lugar de pie completo**. El
  centro vacío permite mostrar el `Total` siempre. La leyenda
  lateral conserva la legibilidad de la versión lista anterior.
- **Tooltip render inline con narrowing manual**. Los tipos
  genéricos de Recharts (`TooltipProps<ValueType, NameType>`)
  chocan con `exactOptionalPropertyTypes: true` del proyecto
  al spreadear props. Solución: extraer datos en el callback
  `content={({ active, payload }) => ...}` y pasar tipos
  estrictos al componente helper. Más boilerplate por chart
  pero typesafe.
- **`useMemo` para el `currentMonthIso`**. La fecha actual se
  calcula una vez por render — no es caro, pero memo evita
  re-renders cuando el chart se re-renderiza por otros
  motivos (ej. cambio de range).
- **Sin `activeShape` en el donut**. La API de `activeShape`
  con `Sector` no encaja bien con `exactOptionalPropertyTypes`
  (props opcionales que pueden venir `undefined`). El efecto
  visual lo hago con `fillOpacity` por `<Cell>` — más simple
  y typesafe.

## Limitaciones conocidas

- **Sin tests UI** de los charts. Los hooks de TanStack que
  alimentan los datos siguen cubiertos por los tests
  existentes; el chart en sí es presentational.
- **Mobile sigue pendiente** (PHASE-18.2). Hasta que se cierre,
  hay incoherencia visual entre web (Recharts) y mobile
  (hand-rolled).
- **Bundle web sube ~95kb gzipped**. Para uso personal local
  es indiferente; en despliegue futuro con Internet considerar
  code-splitting de las páginas con charts (Next.js dynamic
  import).

## Próxima fase

PHASE-18.2 — equivalentes mobile. Candidatos: `victory-native`
(API similar a Recharts) o `react-native-gifted-charts` (API
distinta pero modern + sin Skia).
