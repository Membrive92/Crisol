# PHASE-18.2 — Mobile charts polish

**Estado**: ✅ completada
**Rama**: `feat/phase-18.2-mobile-charts`
**Fecha de merge**: 2026-05-07

## Objetivo

Cerrar PHASE-18 elevando los charts mobile a la misma calidad que
los nuevos charts web (Recharts) introducidos en PHASE-18.1.
Mobile ya usaba `react-native-gifted-charts` desde PHASE-3.2 — la
lib es buena pero el uso era básico: sin formato compacto en el
eje Y, sin tooltip al tap, donut sin agrupación, leyenda sin
amounts.

**Decisión de lib**: nos quedamos con `react-native-gifted-charts`
en lugar de migrar a `victory-native`. Razones:
- Ya está instalada y testeada en runtime.
- API más sencilla y RN-friendly.
- Sin dependencia de `react-native-skia` (Victory Native v40+).

## Qué se implementó

### `MonthlyChart` (income vs expenses, dashboard/análisis)

- **Hero card siempre visible**: encima del chart, el último mes
  (o el seleccionado) muestra Ingresos y Gastos formateados con
  dot de color y etiqueta. Resuelve el "datos sólo en hover" que
  el usuario reportó.
- **Tap en barra → bucket seleccionado**: la barra cambia a
  opacidad sólida y el hero card refleja el mes elegido. Tap en
  el badge del mes (esquina) resetea al último mes.
- **Eje Y compacto**: `formatYLabel` con la misma función que el
  web (`1,2k €`, `1,5M €`).
- **Reglas dashed**: `rulesType="dashed"` con `colors.border`,
  más sutiles que el sólido anterior.
- **Animación**: `isAnimated + animationDuration={400}`.
- **Leyenda con hint**: "Toca una barra para ver el detalle"
  alineado a la derecha del legend row.

### `CategoryDonut` (por categoría, análisis)

- **Top N + "Otros (k)"** agrupado (mismo patrón que el web). El
  donut con 12 slices ilegible se acabó.
- **Leyenda con amount + porcentaje** por categoría. La versión
  pre-18.2 sólo mostraba el nombre.
- **Tap en fila de leyenda → resaltado bidireccional**: el slice
  correspondiente queda a opacidad llena, el resto al 33%.
  Segundo tap deselecciona.
- **Centro en dos líneas**: "Total" (label) + monto formateado
  (semibold tabular). Antes sólo el monto sin contexto.
- **Paleta de tokens**: usa `colors.primary/warning/success/danger/text/borderStrong`
  en lugar de los hex hardcoded del componente original — coherente
  con el resto de la app.

## Archivos clave

- `apps/mobile/components/dashboard/monthly-chart.tsx` (reescrito con hero card + selección)
- `apps/mobile/components/dashboard/category-donut.tsx` (reescrito con top-N + leyenda mejorada)
- `apps/mobile/app/(modules)/personal-finance/(tabs)/analysis.tsx` (`MonthlyChart` recibe `currency` ahora)

## Verificación

- [x] `pnpm typecheck` y `pnpm lint` verdes.
- [x] `pnpm test` — 40 web + 18 mobile sin regresiones.
- [ ] Smoke en dispositivo:
  - [ ] Análisis: hero card encima del chart con el mes actual,
        tap en otro mes lo cambia.
  - [ ] Eje Y muestra `1,2k €` en lugar de `1234.56`.
  - [ ] Donut: top 5 + "Otros (k)" cuando hay >5 categorías.
  - [ ] Tap en leyenda baja la opacidad de los demás slices.

## Decisiones tomadas

- **Mantener gifted-charts en lugar de migrar a victory-native**.
  La lib actual cumple, no añade valor cambiarla. Victory Native
  v40+ exige `react-native-skia`, dep nativo pesado. Si en el
  futuro hace falta más sofisticación (line charts con tooltips
  cross-hair, area charts apilados), reconsiderar.
- **Hero card en lugar de tooltip al tap**. En mobile la
  superficie es chica; un tooltip flotante sobre la barra suele
  quedar tapado por el dedo. Hero arriba siempre visible es
  más usable y resuelve el feedback "los datos sólo se ven en
  hover".
- **Tap-to-select sincronizado en donut**. El slice no se
  "extrae" físicamente (gifted-charts no lo soporta de forma
  trivial); el efecto visual lo conseguimos atenuando los
  demás. Es menos efecto que la `activeShape` de Recharts pero
  funciona y es typesafe.
- **`fontVariant: ['tabular-nums']` en lugar de `fontVariantNumeric`**.
  La segunda es CSS-only; RN sólo soporta la primera con array
  de strings. Misma intención (números monoespaciados) en
  sintaxis nativa.

## Limitaciones conocidas

- **Sin selector de rango (6M/1Y/ALL) en mobile**. El web tiene
  el toggle; mobile siempre muestra todo el dataset que viene de
  `useDashboardByMonth`. Para añadirlo haría falta un picker
  nativo + filtrado client-side. Fuera de scope para 18.2.
- **Sin balance chart aparte en mobile**. Web tiene `Evolución
  del balance` (sólo balance) en `/dashboard`; mobile no tiene
  esa pantalla — Análisis combina KPIs + ingresos vs gastos +
  donut. Si en el futuro se añade un dashboard mobile separado,
  portar el balance chart.
- **Sin tests UI** de los charts. Convención del proyecto —
  charts son presentacionales, los hooks que alimentan datos
  ya están testeados.

## Cierre PHASE-18

PHASE-18 cerrada (2 sub-fases ✅). El stack de visualización es
ahora coherente:

- Web: Recharts (BarChart, PieChart) con eje Y formateado,
  tooltips persistentes, donut con leyenda lateral.
- Mobile: gifted-charts con hero card always-on + donut con top-N.

Siguientes mejoras de visualización (cuando lleguen) ya tienen
infraestructura: line charts para forecast, area charts para
running balance, sparklines en KPIs, etc.
