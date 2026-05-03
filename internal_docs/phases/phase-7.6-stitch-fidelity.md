# PHASE-7.6 — Stitch fidelity rewrite

**Estado**: 🚧 en curso
**Rama**: `feat/phase-7.6-stitch-fidelity`
**PR**: —
**Fecha de merge**: —

## Objetivo

Reemplazar el shell + las tres pantallas principales (Dashboard,
Transacciones, Análisis) por versiones fieles al diseño Stitch
generado en PHASE-7. La fase 7.0–7.5 entregaba la *estructura* del
diseño pero no la *fidelidad visual*; aquí cerramos esa brecha.

Decisiones tomadas con el usuario antes de empezar:

- **Iconos**: SVGs inline propios en lugar de `lucide-react` (pnpm
  EPERM bloqueó la instalación en Windows; los SVGs inline son más
  controlables y eliminan la dependencia externa).
- **Iconos por categoría**: diccionario hardcoded (`apps/web/lib/category-icons.tsx`).
  Selector de icono al crear categoría queda como follow-up cuando se
  habilite la columna `categories.icon` (ya existe en BD pero está
  siempre `NULL`).
- **Sidebar persistente** que reemplaza las tabs del top header. Los
  items navegan a las secciones reales del módulo activo. Otros
  módulos del registro aparecen como deshabilitados con badge
  "Pronto".
- **Smart Insights con cómputos client-side reales** sobre los
  datos del usuario; nada de mocks. Subscripciones recurrentes y
  comparación con grupos quedan como `Próximamente`.

## Qué se implementó

### Iconos + helpers

- `apps/web/components/ui/icons.tsx` — 36 iconos SVG inline
  (24×24, `currentColor`, stroke 1.75). Todo lo que pinta la chrome
  + categorías + states + chart legends. ~6 KB total. Sin libs
  externas.
- `apps/web/lib/category-icons.tsx` — `iconForCategoryName(name)` y
  `iconForTransaction(description, categoryName)`. Match exacto +
  substring + fallback `FolderIcon`. Cubre claves comunes en
  español e inglés (hogar/housing, comida/food, transporte/car,
  trabajo/income, salud/health, ocio, viajes…).

### Shell

- `apps/web/components/modules/module-sidebar.tsx` — sidebar fija
  240 px. Cabecera con dot indicator + label del módulo activo +
  caption "Local-first". Lista de secciones del módulo (Dashboard,
  Análisis, Transacciones, Importar, Tickets) con icono lucide-style
  + active state (bg `surface-muted` + texto `primary` + border
  derecho). Sección "Otros módulos" deshabilitada. Footer fijo:
  link a Ajustes + CTA "+ Añadir transacción" filled primary.
- `apps/web/app/(app)/layout.tsx` — top header slim sticky con
  marca alineada al ancho de la sidebar + acciones (notificaciones,
  cartera, theme toggle, salir). Main content desplazado con
  `padding-left: 240px`. Las tabs flat del header anterior se han
  retirado — la navegación entera vive en la sidebar.
- Componentes obsoletos eliminados:
  `apps/web/components/modules/module-switcher.tsx` y
  `apps/web/components/modules/module-sections.tsx`.

### Dashboard

Nuevo bento al estilo Stitch:

- `stitch-kpi-row.tsx` — tres cards principales con headers que llevan
  trailing slot (icono `BanknoteIcon` para Saldo, badge "RECURRENTE"
  para Ingresos, botón `MoreHorizontal` para Gastos), valor en
  `display` con `tabular-nums`, footer con delta + caption en Saldo,
  conteo de transacciones en Ingresos, barra de progreso + caption
  "% de los ingresos" en Gastos.
- `stitch-balance-chart.tsx` — bar chart denso 6/12 meses con
  toggle 6M/1Y/ALL. Sin recharts: divs verticales con altura
  proporcional al balance, hover muestra tooltip con el importe.
  Mes actual destacado en `primary` sólido, resto en `primary-soft`.
- `stitch-secondary-metrics.tsx` — dos cards compactas: "Mayor gasto
  del periodo" (con icono warning circular) y "Ahorro proyectado"
  (con icono rocket circular). Proyección lineal naïve a fin de mes.
- `stitch-recent-activity.tsx` — listado de las 4 últimas
  transacciones con icono cuadrado leading (derivado por
  `iconForTransaction`), descripción, fecha relativa (Hoy/Ayer/X
  días/dd MMM), importe coloreado por kind. Footer: botón filled
  primary "+ Añadir Transacción" inline.
- `stitch-tip-card.tsx` — card `primary-soft` con eyebrow "Consejo
  financiero" + insight calculado client-side (delta vs periodo
  anterior, tasa de gasto, fallback informativo). Sparkles muy
  desaturadas como background visual.

Componentes obsoletos eliminados: `kpi-cards`, `kpi-delta`,
`recent-activity`, `tip-card`, `monthly-chart`, `category-donut`,
`top-expenses-list`.

### Transacciones

- `stitch-transactions-kpi-row.tsx` — fila de 4 KPIs sobre la tabla:
  Income / Expenses / Net Balance (con signo) / Tickets pendientes
  (count de receipts en `pending`). Reusa `useDashboardSummary` y
  `useReceipts({limit:100})`. Bg `surface-muted` (variante distinta a
  los del dashboard para diferenciarlos).
- `stitch-search-toolbar.tsx` — search bar con icono lupa interior +
  botones "Filtros" y "Este mes" como toggles. El panel de filtros
  se despliega al pulsar "Filtros" y contiene categoría + rango de
  fechas. "Este mes" rellena `date_from`/`date_to` al rango del mes
  actual con un click.
- `transactions/page.tsx` reescrito con eyebrow bar (dot indicator +
  título + contador), KPI row, toolbar nueva, `TransactionList`
  (DataTable existente, sin cambios) y `Pagination`.
- `transaction-filters.tsx` antiguo eliminado — sustituido por la
  toolbar.

### Análisis

- `stitch-period-toggle.tsx` — segmented control Mes/Trimestre/Año
  con `rangeForPeriod()` que devuelve el rango ISO correspondiente.
- `stitch-income-vs-expenses.tsx` — bar chart Income vs Expenses con
  buckets apilados (income encima, expense debajo) sin libs externas.
  Líneas de cuadrícula al 15% opacidad. Hover muestra tooltip con
  ambos importes.
- `stitch-key-metrics.tsx` — Net Cash Flow + Saving Rate apilados
  en columna a la derecha del chart. Net Cash Flow incluye delta
  vs periodo anterior (flecha + porcentaje). Saving Rate con barra
  de progreso fija al porcentaje.
- `stitch-expense-breakdown.tsx` — listado vertical con icono cuadrado
  leading por categoría (vía `iconForCategoryName`), barra de
  progreso y porcentaje. Top 5 + bucket "Otros (k)".
- `stitch-smart-insights.tsx` — sección de insights calculados
  client-side. Algoritmo: 1) saldo neto vs periodo anterior, 2)
  concentración en la categoría top de gasto, 3) tasa de ahorro ≥
  25%. Se pintan sólo los insights que aplican; si ninguno, se
  muestra un mensaje "todavía no hay datos suficientes". Una
  fila adicional con `ChevronRight` y caption "Próximamente"
  para las subscripciones recurrentes.
- `analysis/page.tsx` reescrito con eyebrow "ANALYTICS ENGINE",
  título grande + descripción, period toggle, dos filas de bento
  grids (chart + key metrics; breakdown + insights), y comparación
  peer group como card `surfaceMuted` con borde discontinuo y copy
  "Próximamente".

Componentes obsoletos eliminados: `coming-soon-card`,
`expense-breakdown`, `income-vs-expenses-chart`.

## Archivos clave

- `apps/web/components/ui/icons.tsx`
- `apps/web/lib/category-icons.tsx`
- `apps/web/components/modules/module-sidebar.tsx`
- `apps/web/app/(app)/layout.tsx`
- `apps/web/app/(app)/personal-finance/dashboard/page.tsx`
- `apps/web/app/(app)/personal-finance/transactions/page.tsx`
- `apps/web/app/(app)/personal-finance/analysis/page.tsx`
- `apps/web/components/dashboard/stitch-*` (5 archivos)
- `apps/web/components/transactions/stitch-*` (2 archivos)
- `apps/web/components/analysis/stitch-*` (5 archivos)

## Endpoints añadidos

Ninguno. Todo se monta sobre los endpoints existentes
(`/dashboard/summary` con `previous_period_*`, `/dashboard/by-month`,
`/dashboard/by-category`, `/dashboard/currencies`, `/transactions`,
`/receipts`).

## Migraciones

Ninguna.

## Verificación

- [x] `pnpm typecheck` verde
- [x] `pnpm lint` verde
- [x] `pnpm test` (8/8) verde
- [ ] Smoke manual: las tres pantallas con datos reales — sidebar
      activa la sección correcta al navegar; KPIs con delta cuando
      hay periodo previo; chart de balance con bars proporcionales;
      actividad reciente con iconos contextuales; toggle de periodo
      en Análisis cambia el rango.

## Decisiones tomadas

- **Iconos inline en lugar de `lucide-react`** — no por preferencia
  estética, sino porque el lock de Windows en `pnpm` bloqueaba la
  instalación en este entorno (`EPERM` al renombrar el tmp). Los
  SVGs inline son más controlables, no añaden dependencia y caben
  en ~6 KB. Si el bloqueo se resuelve en el futuro, migrar a la lib
  es un find-and-replace mecánico.
- **Sidebar reemplaza tabs del top**, no las complementa. Mantener
  ambas era ruidoso. El header queda con marca + acciones de cuenta
  + theme toggle. Si en el futuro se añade un módulo activo con
  muchas secciones se puede añadir una sub-nav, pero hoy no.
- **Insights reales, no mocks**. Los algoritmos son simples
  (delta de balance, share de la top categoría, tasa de ahorro) pero
  son honestos: si no hay datos suficientes, no se pinta el insight.
  Esto respeta el principio "la IA sugiere, el usuario confirma" del
  proyecto.
- **`Pending Clear` = count de receipts pendientes**, no un importe.
  El concepto Stitch ("Pending Clear") es ambiguo en nuestro modelo
  — los tickets son el equivalente más cercano a "pending". Mostrar
  el conteo es útil para que el usuario sepa cuántos tickets le
  quedan por confirmar.

## Limitaciones conocidas

- Sidebar no tiene drawer mobile. En viewports < 768 px la sidebar
  se sigue mostrando comprimiendo el contenido — no es ideal, pero
  funciona. Drawer queda como follow-up.
- Categoría coloreada por **kind** (income/expense/null), no por
  nombre. Stitch mostraba colores únicos por categoría. Cuando se
  habilite `categories.icon` y `categories.color` en BD podremos
  ofrecer paleta personalizada.
- El bar chart "Income vs Expenses" agrupa por mes pero no respeta
  el periodo del toggle (Mes/Trimestre/Año). Siempre pinta los 12
  meses del año actual. Esto es porque el endpoint `by-month` es
  anual. Para una visión Mes/Trimestre habría que añadir un
  endpoint con granularidad mensual en periodo arbitrario.
- Subscripciones recurrentes y comparación con grupos siguen siendo
  placeholders. Real backend pendiente (PHASE-8 candidata).
- El número de teléfono / "Pending Clear" estima sólo con los 100
  primeros receipts cargados. Si un usuario tiene >100 tickets
  pendientes, el contador queda corto. Aceptable hasta que se añada
  un filtro por status al endpoint `/receipts`.

## Próxima fase

Sin definir. Posibles candidatas para PHASE-8:

- Detección de subscripciones recurrentes (módulo `ai`).
- Modelo de presupuestos (vault de Stitch) con alertas.
- Selector de icono y color al crear categoría.
- Drawer mobile para la sidebar.
