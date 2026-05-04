# PHASE-9.2 — Pantalla "Análisis" en mobile

**Estado**: ✅ completada
**Rama**: `feat/phase-9.2-mobile-analysis-screen`
**PR**: —
**Fecha de merge**: 2026-05-04

## Objetivo

Cerrar la última disparidad estructural entre web y mobile dentro
del módulo Personal Finance: la web tiene la tab "Análisis"
(`/personal-finance/analysis`) con período toggleable, tasa de ahorro
y smart insights; la app móvil sólo tenía un "Dashboard" reducido
con filtro por año y los mismos KPIs/charts pero sin las features
de análisis. Esta fase reemplaza la tab `home` por `analysis` con
paridad funcional.

## Qué se implementó

### Componentes mobile nuevos

`apps/mobile/components/dashboard/`:

- **`period-toggle.tsx`** — segmented Mes/Trimestre/Año con
  `Pressable` nativo. Exporta `rangeForPeriod(period)` que devuelve
  el `dateFrom`/`dateTo` del período seleccionado. Equivalente
  funcional a `StitchPeriodToggle` (web).
- **`savings-rate-card.tsx`** — tarjeta single-KPI con tasa de
  ahorro (`balance / income`) y barra de progreso. Equivalente al
  sub-card "Saving rate" de `StitchKeyMetrics` (web). Si `income == 0`
  muestra `—`.
- **`smart-insights.tsx`** — heurísticas client-side idénticas a
  `StitchSmartInsights` (web): cash-flow vs periodo previo, top
  categoría con peso ≥30%, tasa de ahorro saludable. Sin datos
  suficientes, mensaje neutro. Mantiene la fila "Subscripciones
  recurrentes — próximamente" para dejar el hook visible.
- **`currency-picker.tsx`** — versión slim de `dashboard-filters.tsx`
  sin year picker (el período toggle lo reemplaza). Chip + sheet
  Modal nativo con la lista de monedas con datos del usuario.

### Pantalla `analysis.tsx`

`apps/mobile/app/(modules)/personal-finance/(tabs)/analysis.tsx`
(nuevo, sustituye `home.tsx`):

- Estado local: `currency`, `period: PeriodKey`, `donutKind`.
- `useDashboardSummary` / `useDashboardByCategory` /
  `useDashboardTopExpenses` consumen `dateFrom/dateTo` del período
  seleccionado.
- `useDashboardByMonth` sigue ligado al `currentYear` — la query
  sólo acepta `year`, no rango (igual que web).
- Render order: greeting+logout → CurrencyPicker → PeriodToggle →
  KpiCards → SavingsRateCard → MonthlyChart → CategoryDonut →
  TopExpensesList → SmartInsights.
- `RefreshControl` que dispara `refetch` de las cuatro queries.
- `FabLink` a "Añadir transacción" (sin cambios respecto a `home`).

### Cambios de routing

- `apps/mobile/app/(modules)/personal-finance/(tabs)/_layout.tsx`:
  `home` → `analysis` (`title: 'Análisis'`). Las otras tabs
  (`transactions`, `receipts`) sin tocar.
- `apps/mobile/app/_layout.tsx`: redirección post-login pasa de
  `/(modules)/personal-finance/(tabs)/home` →
  `/(modules)/personal-finance/(tabs)/analysis`.
- `apps/mobile/app/(modules)/personal-finance/(tabs)/home.tsx`
  eliminado.

## Flujo técnico

```
 Usuario abre Análisis
    ▼ Estado inicial: period='year', currency='EUR' (o primera del usuario)
 [PeriodToggle] [CurrencyPicker]
    │
    ▼ rangeForPeriod('year') → dateFrom=YYYY-01-01, dateTo=YYYY-12-31
 4 queries paralelas:
    summary        ({currency, dateFrom, dateTo})
    byMonth        ({currency, year: currentYear})
    byCategory     ({currency, dateFrom, dateTo, kind?})
    topExpenses    ({currency, dateFrom, dateTo, limit: 5})
    │
    ▼ Render scroll
 KpiCards (Saldo / Ingresos / Gastos / Movimientos con deltas)
 SavingsRateCard (balance / income %)
 MonthlyChart (todos los buckets del año)
 CategoryDonut (toggle income/expense/all)
 TopExpensesList (5 más altos)
 SmartInsights (insights computados client-side)

 Cambio de período → re-fetch de summary/byCategory/topExpenses
 (monthly no cambia — siempre año en curso)
```

## Archivos clave

- `apps/mobile/app/(modules)/personal-finance/(tabs)/analysis.tsx` (nuevo)
- `apps/mobile/app/(modules)/personal-finance/(tabs)/_layout.tsx`
  (rename home → analysis)
- `apps/mobile/app/_layout.tsx` (redirect)
- `apps/mobile/components/dashboard/period-toggle.tsx` (nuevo)
- `apps/mobile/components/dashboard/savings-rate-card.tsx` (nuevo)
- `apps/mobile/components/dashboard/smart-insights.tsx` (nuevo)
- `apps/mobile/components/dashboard/currency-picker.tsx` (nuevo)
- `apps/mobile/app/(modules)/personal-finance/(tabs)/home.tsx` (eliminado)

## Endpoints añadidos

Ninguno. Reusa `dashboard.*` y `currency.*`.

## Migraciones

Ninguna.

## Verificación

- [x] `pnpm --filter @finanzas/mobile typecheck` verde.
- [x] `pnpm --filter @finanzas/mobile lint` verde.
- [ ] Smoke manual en Expo:
  - [ ] Login redirige a `Análisis`.
  - [ ] Toggle Mes/Trimestre/Año recalcula KPIs y donut.
  - [ ] CurrencyPicker actualiza todas las queries.
  - [ ] SavingsRateCard muestra `—` cuando income=0.
  - [ ] SmartInsights muestra mensaje neutro sin datos, insights
        cuando hay (subir transacciones reales).
  - [ ] Pull-to-refresh refresca las 4 queries.
  - [ ] FAB → "Añadir transacción" navega correctamente.

## Decisiones tomadas

- **Reemplazar `home` por `analysis` (no añadir tab nueva)**. La
  tab `home` ya era el equivalente funcional de "dashboard": KPIs +
  charts + breakdowns. Mantener ambas crearía duplicación. La spec
  del módulo (`packages/types/src/registry/modules.ts`) sólo lista
  `analysis` y `transactions` como sections — alinear mobile a esa
  estructura era lo coherente.
- **`rangeForPeriod` duplicado entre web y mobile**, no compartido
  en `packages/ui`. La función es 15 líneas puras y exportable; meterla
  en `packages/ui` requiere actualizar exports y su test. Si crece o
  aparece un tercer caller, mover entonces. Está en backlog.
- **`useCurrencyStore` no se usa en mobile** — el store persiste en
  `localStorage` (web-only). Mobile mantiene `useState` local para
  currency, igual que la `home` previa. Migrar el store a
  `AsyncStorage` cross-platform es pre-requisito para compartirlo —
  follow-up fuera del scope de esta fase.
- **`MonthlyChart` no se ata al período**. La query
  `useDashboardByMonth` sólo acepta `year`. Cambiar el contrato del
  endpoint para soportar rangos arbitrarios es un cambio backend que
  no aporta a la paridad mobile inmediata. Web hace lo mismo.
- **SmartInsights mobile como `View` plano, no card-en-card**. El
  ancho mobile no soporta el bento de web (Smart Insights vivía en
  la columna derecha de un grid 7/5). La versión mobile muestra
  insights apilados con palette idéntico (success / info) y mantiene
  el "próximamente" final como hook.
- **`SavingsRateCard` separado de `KpiCards`**, no como 5° KPI. El
  grid 2×2 de `KpiCards` es ratio fijo y la barra de progreso
  necesita ancho completo. Single card debajo es más legible.

## Limitaciones conocidas

- **Sin `convertAll` (cross-currency global) en mobile**. Web tiene
  el toggle global en el header que activa `target_currency` en todas
  las queries; mobile no, porque `useCurrencyStore` es web-only.
  Cuando se haga `useCurrencyStore` cross-platform (AsyncStorage
  adapter) se podrá heredar el toggle aquí.
- **No hay tests de UI mobile** — `jest-expo` sigue sin configurar
  (heredado del backlog desde PHASE-2.2). La verificación de esta
  fase es manual (smoke en Expo).
- **`MonthlyChart` ligado a año en curso**. Cambiar a "últimos 12
  meses rolling" o rango libre requiere modificar
  `DashboardByMonthQuery` + endpoint backend. Follow-up si hace falta.
- **`rangeForPeriod` duplicado**. Trivial de mover a `packages/ui`
  cuando aparezca un tercer caller.
- **`dashboard-filters.tsx` ya no se usa** — el único caller era
  `home.tsx`. Se conserva el archivo en componentes por si vuelve a
  hacer falta una variante con year picker. Si en la próxima sesión
  se decide que no, eliminar.

## Próxima fase

Sin definir. Siguiente candidato del backlog top:

- **Soft-delete + papelera de transacciones** (mayor laguna funcional
  para el usuario — borrar es destructivo total).
- **Cron nocturno de tasas (APScheduler)** — para que las tasas no
  se queden atrás si la app pasa días sin abrirse.
