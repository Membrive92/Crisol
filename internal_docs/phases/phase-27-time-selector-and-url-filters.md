# PHASE-27 — TimeSelector reutilizable + filtros sincronizados con URL

**Estado**: ✅ completada
**Rama**: `feat/phase-24-debt-from-source` (continúa la rama acumulada)
**Fecha de merge**: 2026-05-24

## Objetivo

Dos quejas concretas del usuario después de meses de uso:

1. **Filtrar por fecha era incómodo y poco visual**. Tenía que entrar
   en "Filtros" → escribir `Desde`/`Hasta` a mano. Los 12 meses
   típicos no eran clicables. No había forma rápida de saltar a
   "abril 2026".
2. **Al editar una transacción y volver, los filtros (y la página)
   se perdían**. El usuario que estaba en la página 3 filtrando por
   "Tarjeta de crédito" volvía a la página 1 sin filtros y tenía que
   re-aplicarlos. Lo mismo al refrescar.

## Qué se implementó

### Backend — endpoints de periodos disponibles

- **`GET /transactions/available-periods`** — devuelve
  `{periods: [{year, months: [1..12]}, …]}` con sólo los años y meses
  que tienen al menos una transacción activa del usuario (excluye
  papelera). Años descendentes; meses ascendentes.
- **`GET /dashboard/category/{category_id}/available-periods`** — lo
  mismo pero filtrado a la categoría dada (para el drill-down). 404
  si la categoría no es del usuario.
- Ambos endpoints viven ANTES de las rutas con `{id}` para que FastAPI
  no los confunda con UUIDs (lección PHASE-4.1 reaplicada).

### Frontend — componente `TimeSelector` reutilizable

`apps/web/components/ui/time-selector.tsx` — self-contained:

- Props: `availablePeriods` (array `{year, months[]}`),
  `value: {dateFrom, dateTo}`, `onChange: (range) => void`.
- Renderiza:
  - **Barra de meses** del año contextual (sólo los meses con datos),
    cada chip con la abreviatura (`Ene`/`Feb`/…) y el año debajo en
    pequeño.
  - **Chips de años** a la derecha (sólo los presentes en BD).
  - **Display del rango** efectivo: *"Abril 2026 · mes seleccionado"*,
    *"2026 · año seleccionado"*, *"01 Abr – 30 Abr · rango
    personalizado"* o *"Todo el histórico · sin filtro de fecha"*.
- Toggle: click sobre el chip activo limpia el rango (vuelve a "todo
  el histórico").
- "Año contextual": el activo si lo hay, si no el más reciente con
  datos, si no el actual. La barra de meses cambia con el año
  seleccionado.

### Frontend — uso en transacciones

- **`stitch-search-toolbar.tsx`** consume `useTransactionAvailable
  Periods()` + `TimeSelector`. Eliminado el botón "Este mes"
  (redundante con la barra). Los dropdowns `Desde`/`Hasta` siguen
  dentro de "Filtros" para rangos custom.
- **`transactions/page.tsx`** ahora sincroniza **todos** los filtros
  (`offset`, `account_id`, `category_id`, `date_from`, `date_to`,
  `search`) con la URL (`router.replace`, no `push`, para no inflar
  el historial). Al montar lee de `useSearchParams` y rehidrata el
  estado.
- **`transactions/[id]/page.tsx`** usa `router.back()` en submit y
  cancel — preserva la URL completa con todos los filtros. Resultado:
  editar una tx y volver → exacto mismo estado que tenías.

### Frontend — uso en drill-down de categoría

- **`analysis/category/[id]/page.tsx`** sustituye el toggle
  `Mes/Trimestre/Año` por el mismo `TimeSelector`. Default = año
  actual entero. El componente sólo ofrece años/meses con datos para
  ESTA categoría (vía el endpoint específico por categoría).
- También en esta fase: la gráfica "Evolución mensual" pasó de
  `BarChart` a `LineChart` (curva tipo deuda), porque con un solo
  mes el bar chart no comunica nada.

### Servicios + tipos

- `packages/services/src/api/endpoints/transactions.ts`: `availablePeriods()`
- `packages/services/src/api/endpoints/dashboard.ts`:
  `categoryAvailablePeriods(categoryId)`
- `packages/services/src/query/hooks/useTransactions.ts`:
  `useTransactionAvailablePeriods()`
- `packages/services/src/query/hooks/useDashboard.ts`:
  `useCategoryAvailablePeriods(categoryId)`
- `packages/services/src/query/keys.ts`:
  `transactions.availablePeriods()`,
  `dashboard.categoryAvailablePeriods(id)`
- Reexports en `packages/services/src/index.ts`.

## Flujo técnico (filtros viajan con la URL)

```
Usuario aterriza en /transactions
   │  searchParams: ""
   ▼
filtersFromSearchParams(searchParams) → {limit: 20, offset: 0}
   │
   ▼
Usuario filtra: "Tarjeta de crédito" + página 3
   │  setFilters → router.replace("?category_id=...&offset=40")
   ▼
Usuario hace click en una tx → /transactions/abc-id
   │  navegación normal; el estado vive en la URL
   ▼
Usuario edita y dale a Guardar/Cancelar
   │  router.back() → restaura "?category_id=...&offset=40"
   ▼
filtersFromSearchParams(searchParams) → rehidrata el filtro + página
```

## Archivos clave

- `backend/app/modules/personal_finance/transactions/service.py` —
  `list_available_periods`
- `backend/app/modules/personal_finance/transactions/router.py` —
  endpoint + schema `AvailablePeriodsResponse`
- `backend/app/modules/personal_finance/dashboard/service.py` —
  `get_category_available_periods`
- `backend/app/modules/personal_finance/dashboard/router.py` —
  endpoint + schema `CategoryAvailablePeriodsResponse`
- `apps/web/components/ui/time-selector.tsx` — componente nuevo
- `apps/web/components/transactions/stitch-search-toolbar.tsx` —
  reemplazo del bloque inline por `<TimeSelector />`
- `apps/web/app/(app)/personal-finance/transactions/page.tsx` —
  `filtersFromSearchParams` / `filtersToSearchParams` + `setFilters`
  con sync de URL
- `apps/web/app/(app)/personal-finance/transactions/[id]/page.tsx` —
  `router.back()` en submit y cancel
- `apps/web/app/(app)/personal-finance/analysis/category/[id]/page.tsx`
  — `TimeSelector` + `LineChart` para evolución mensual

## Verificación

- [x] `pytest tests/test_transactions.py` (16/16) y suite completa
      (386/386)
- [x] Web typecheck + 46/46 tests
- [x] Manual: filtrar "Tarjeta de crédito" + click en chip "Abr 2026"
      → URL pasa a `?category_id=...&date_from=...&date_to=...&offset=0`
- [x] Manual: editar tx → guardar → vuelves a la misma página y
      mismos filtros
- [x] Manual: refrescar la URL completa → restaura estado idéntico

## Limitaciones conocidas

- `limit` y `target_currency` NO viajan en la URL — fixed/derivados.
- La barra de meses no tiene flechas de scroll; con 12 meses cabe en
  pantallas estándar y hace `flex-wrap` en muy estrechas.

## Próxima fase

PHASE-28 — transferencias con cuenta ordenante / beneficiaria explícita.
