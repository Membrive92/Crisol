# PHASE-42 — Rango de fechas personalizado (fuera trimestral)

**Estado**: ✅ completada
**Rama**: `main` (push directo, sin PR)
**Fecha de merge**: 2026-07-16
**Commits**: `209b31a` (backend) · `c22fc94` (web) · `693fad0` (móvil) · `docs`

## Objetivo

Eliminar el período **trimestral** (no aporta a un particular — "no somos
empresas") y añadir un **rango personalizado** que define el usuario con dos
fechas `desde`/`hasta` (p. ej. cobrar el día 15 y ver el balance de 15 a 15).
Alcance elegido por el usuario: **todo, incluida Deuda** (Análisis + Dashboard +
Deuda, web y móvil).

Durante la implementación surgieron —y se cerraron— varias incoherencias de la
vista con un rango arbitrario, más un episodio de depuración que resultó ser un
**backend obsoleto**, no un bug de código (ver §Depuración).

## Qué se implementó

1. **`quarter` fuera; `custom` dentro.** El tipo compartido `DebtTimeRange`
   pasa de `month|quarter|year` a **`month|year|custom`**. Nuevo
   `NavigableRange = month|year` (subconjunto navegable con flechas; el
   compilador garantiza que `custom` nunca llega a los helpers de navegación).
2. **Rango libre end-to-end.**
   - Backend: `dashboard/by-month` y `debt/category-summary` aceptan
     `date_from`/`date_to`; ventana **day-exact** con meses de borde
     **parciales**. `get_summary` deriva el "período anterior" como mes/año
     natural exacto o, en custom, una **ventana de igual longitud**
     inmediatamente anterior.
   - Web: `DatePicker` propio (marca cobre), `StitchPeriodToggle` con opción
     "Personalizado", `PeriodNavigator` de deuda con dos date-pickers, y las
     páginas de Análisis/Dashboard/Deuda siembran y gobiernan el rango. Fix del
     icono del calendario invisible en modo oscuro (`globals.css`).
   - Móvil: `PeriodToggle` + `PeriodNavigator` de deuda con opción "Rango" y
     `DateInput` nativo from/to; pantallas de Análisis y Deuda cableadas.
     `boundsForCustomRange` se **elevó a `@crisol/services`** (compartido
     web+móvil, dedup del web).
3. **Consistencia de la vista con un rango arbitrario** (raíz: una serie mensual
   es la visualización equivocada para una ventana libre).
   - **Ingresos vs Gastos** en custom muestra los **totales reales del periodo**
     (ingresos vs gastos + neto), no barras de meses parciales confusas. El neto
     es un bloque-resultado destacado y el contenido se centra en el alto de la
     card.
   - **Patrimonio a fecha**: nuevo `GET /accounts/position-as-of` → patrimonio
     neto **a fecha de fin del rango** + Δ **durante** el rango. Las tiles
     "Patrimonio neto" y "Δ Patrimonio" reflejan el período, no una foto de hoy.
   - **Chart "Evolución del patrimonio" respeta el toggle "incluir deuda"**:
     ON → línea = neto (activos − pasivos); OFF → línea = solo activos (oculta la
     línea "Activos" redundante, conserva "Pasivos" como contexto). Antes pintaba
     siempre el neto y contaba una historia distinta a la tile.

## Endpoints

- `GET /accounts/position-as-of?date_from&date_to` — patrimonio a fecha + Δ del
  rango (mono-divisa de referencia).
- `GET /dashboard/by-month` — nuevos `date_from`/`date_to` (opcionales): buckets
  del rango con bordes parciales, en vez de los 12 meses del año.
- `GET /debt/category-summary` — `range=custom` + `date_from`/`date_to`
  (obligatorios en custom; 422 si faltan o están cruzados).

## Archivos clave

- `backend/.../accounts/position_history.py` — `compute_position_as_of`.
- `backend/.../dashboard/{service,repository,router}.py` — rama de rango en
  `get_monthly_breakdown` + `get_totals_by_month_in_range` + `_previous_period`.
- `backend/.../debt/{service,router,schemas}.py` — `range=custom` day-exact.
- `packages/services/src/period/debt-period.ts` — `NavigableRange`,
  `boundsForCustomRange` (compartido).
- `apps/web/components/ui/date-picker.tsx` — DatePicker cobre.
- `apps/web/components/analysis/stitch-income-vs-expenses.tsx` — totales de
  periodo en custom.
- `apps/web/components/analysis/networth-evolution-card.tsx` — respeta el toggle.

## Depuración: un dato "sin sentido" que era un backend obsoleto

Al probar el rango, la card mostraba cifras del **año entero** (YTD). El
diagnóstico (workflow + prueba en vivo del endpoint) descartó todo el código y
localizó la causa: el **proceso backend estaba arrancado sin `--reload`** y
llevaba días sin recoger los cambios de esta fase (ignoraba `date_from`/`date_to`
→ FastAPI descarta query params desconocidos → devolvía el año). Reiniciado el
backend con `--reload`, el rango devuelve los buckets correctos. Encaja con la
lección de "zombie listener en Windows": **ante cambios de BE que no aparecen en
FE, revisar primero el proceso/puerto**, no el código.

## Validación (contra `transactions`, usuario real, ventana 15-may…15-jun)

Todas las cards/KPIs del periodo se cruzaron con la tabla `transactions` y
cuadran **al céntimo**: Ingresos 3.070,38 (6 tx `IN`) · Gastos 2.782,52 (65 tx
`OUT`) · Neto +287,86 · Desglose 18/18 categorías exactas · Δ Patrimonio +292,45
(Σ mov. firmados de activos; toggle deuda OFF) · Patrimonio 11.370,42 (activos a
fecha, brokerage excluido) · puntos del chart Evolución as-of month-end exactos ·
tasa de ahorro/esfuerzo/estructural = endpoints.

## Verificación

- BE: **673 tests** · mypy · ruff.
- FE: typecheck · lint · **web 106** · **móvil 18**.

## Decisiones y limitaciones conocidas

- **Deuda con custom**: los KPIs son day-exact, pero las barras del chart mensual
  de los meses frontera salen a **mes completo** (limitación de la serie mensual;
  gráfico secundario).
- **Patrimonio a fecha** es **mono-divisa** (divisa de referencia), misma
  limitación que la serie de patrimonio existente.
- **Drill-down de categoría** (web y móvil) se mantiene mes/año: el web usa ahí
  su propio `TimeSelector` (PHASE-27), no el toggle de período.
- **Móvil — Ingresos vs Gastos**: sigue con el `MonthlyChart` (no adoptó los
  totales de periodo del web). Follow-up de paridad.

## Lecciones

- [`lessons.md`](../lessons.md) — reutilizar una expresión SQL compartida
  (`signed_amount_expr`) exige replicar SUS joins: faltaba el join a `categories`
  en `compute_position_as_of` y un producto cartesiano inflaba el patrimonio.

## Próxima fase

Paridad móvil de "Ingresos vs Gastos" (totales de periodo) + evaluación de
elevar la exclusión brokerage/crypto a opción visible.
