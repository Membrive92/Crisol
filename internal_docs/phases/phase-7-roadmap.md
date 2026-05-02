# PHASE-7 — Rediseño dashboard + layout shell

> Roadmap. Este documento se va vaciando a medida que cada sub-fase se entrega
> y crea su propio `phase-7.X-*.md`.

## Origen

Tras PHASE-6.1 quedó claro que el chrome del módulo (header, switcher,
secciones, badges, botones) y el layout del dashboard no transmitían bien
la "tónica" del producto. Generamos un `DESIGN.md` siguiendo la spec de
Stitch y exploramos variantes con esa herramienta. El export de Stitch
respeta los tokens 1:1 y aporta una serie de mejoras de layout que se
pueden aplicar sin tocar la paleta — sólo redistribuyendo y añadiendo
metadatos de KPI.

Esta fase 7 implementa esos cambios de forma incremental.

## Dependencias y orden

```
7.0  primitives + layout shell
  ├─ 7.1  dashboard bento
  ├─ 7.2  transactions tabla
  └─ 7.3  imports + receipts polish
       └─ 7.4  mobile parity
              └─ 7.5  analysis sub-tab (opcional)
```

7.0 desbloquea todo. 7.1, 7.2 y 7.3 son independientes y pueden ir en
paralelo.

---

## PHASE-7.0 — Design primitives + layout shell

**Branch**: `feat/phase-7.0-design-primitives`
**Sin backend, sin migraciones.**

### Frontend nuevo (`apps/web/components/ui/`)

- `kpi-card.tsx` — Props: `label`, `value`, `valueColor?`, `trailing?`,
  `footer?`. Tipografía `display` para el valor, `caption` muted para
  label. Slots para badge/icono y para "vs periodo anterior" o barra
  de presupuesto.
- `fab.tsx` — botón flotante circular, posición fixed bottom-right,
  variant `primary` filled.
- `data-table.tsx` — tabla genérica con cabecera `overline` y filas
  con hover `surface-muted`. No incluye paginación (la pone el caller).
- `category-chip.tsx` — chip tonal: bg derivado de `kind` (income →
  `success-soft`, expense → `danger-soft`, sin kind → `primary-soft`).
  Tipografía `overline`.

### Layout shell

- Colapsar las dos filas del header en una. Layout final:
  `[Marca] [ModuleSwitcher] [─ tabs ─] ······· [Ajustes] [🌓] [Logout]`
- `ModuleSections` se monta inline con el header en la misma fila.
- Padding más comprimido en las secciones (xs vertical) para que la
  fila densa no resulte alta.

### Verificación

- `pnpm verify` verde.
- Manual: header consistente en dashboard, transactions, imports,
  receipts y settings. Las secciones se ven inline. Los primitives
  nuevos se renderizan en una página de prueba o en el storybook
  manual de la propia 7.1.

### Riesgo

Header en una fila puede quedar apretado en viewports estrechos.
Mitigación: `overflow-x: auto` en las tabs y un breakpoint que oculta
los textos de los iconos de acción.

**Estimación**: 1 día.

---

## PHASE-7.1 — Dashboard bento + delta vs periodo anterior

**Branch**: `feat/phase-7.1-dashboard-bento`

### Backend

- `DashboardSummary` añade `previous_period_income`,
  `previous_period_expenses`, `previous_period_balance` (todos
  `Decimal | None`).
- `service.compute_summary` calcula el periodo previo de igual
  longitud (terminando justo antes de `date_from`) y consulta los
  totales también para ese rango.
- Test nuevo: `test_summary_includes_previous_period`.
- Endpoint sigue siendo `GET /dashboard/summary?date_from=&date_to=`.

### Tipos compartidos

`packages/types` añade los tres campos al schema TS de `DashboardSummary`.

### Frontend

Layout bento responsive (web):

```
┌─ Saldo Total ─┬─ Ingresos ─┬─ Gastos ─┐
├───────────────┴────────────┼──────────┤
│  Evolución (8/12)          │ Recientes│
│                            │  (4/12)  │
├──────────┬──────────┬──────┴──────────┤
│ Top gasto│ Donut    │ Tip financiero  │
└──────────┴──────────┴─────────────────┘
```

- `KpiCard` (de 7.0) renderiza los 3 KPIs con delta calculado en cliente
  a partir de `previous_period_*`. Flecha verde/roja + porcentaje +
  caption "vs periodo anterior".
- Sidebar "Actividad reciente": consume `useTransactions({ limit: 5 })`,
  renderiza con icono de categoría a la izquierda.
- "Consejo financiero": placeholder estático en este PR. Follow-up
  PHASE-7.1.1 cablea al módulo `ai` para consejos basados en datos.
- FAB "+ Añadir transacción" abajo a la derecha.

### Smart currency default

- Endpoint nuevo `GET /dashboard/currencies` → `string[]` distintas en
  las transacciones del usuario.
- Hook `useUserCurrencies()`.
- `<DashboardFilters>` arranca con la primera moneda del usuario, no
  con `EUR` hardcodeado.

### Verificación

- `pytest tests/test_dashboard.py -v`
- `pnpm verify`
- Manual: KPIs con delta correcto, sidebar de actividad, FAB navega.

**Estimación**: 2-3 días.

---

## PHASE-7.2 — Transactions tabla

**Branch**: `feat/phase-7.2-transactions-table`
**Sin backend.**

### Frontend

- `transactions/page.tsx` y `transaction-list.tsx`: render como
  `<DataTable>` con columnas:
  | Fecha | Categoría | Descripción | Origen | Importe |
  con `<CategoryChip>` (de 7.0) tinted by kind, badge de origen
  (MANUAL / IMPORT / RECEIPT) y amount mono right-aligned coloreado
  por kind.
- Filtros (`<TransactionFilters>`) en una fila encima de la tabla.
- Footer de paginación: "Showing X of Y" + numérica con elipsis.

### Verificación

- `pnpm verify`
- Manual: filtrar, paginar, click en una fila → detalle.

**Estimación**: 2 días.

---

## PHASE-7.3 — Imports + Receipts polish

**Branch**: `feat/phase-7.3-list-polish`
**Sin backend.**

### Frontend

- `import-list.tsx` y `receipt-list.tsx`: alinear ritmo visual con
  Transactions (cabecera, hover `surface-muted`, status badges, paginación
  consistente). Tabla NO obligatoria — la estructura de datos es distinta —
  pero sí la misma jerarquía visual.

### Verificación

`pnpm verify` + manual.

**Estimación**: 1 día.

---

## PHASE-7.4 — Mobile parity

**Branch**: `feat/phase-7.4-mobile-parity`

### Frontend mobile

- Replicar `KpiCard`, `Fab`, `CategoryChip` en `apps/mobile/components/ui/`
  (no se comparten desde `packages/ui` por ADR-0001).
- Mobile dashboard simplificado: KPIs en grid 2×2.
- Tab bar `(modules)/personal-finance/(tabs)/_layout.tsx`: iconos y
  colores activos vía tokens.
- Header del módulo (`module-header.tsx`): tipografía y dot-indicator
  iguales a web.

### Verificación

`pnpm verify` (lint + typecheck) + manual en simulador.

**Estimación**: 2-3 días.

---

## PHASE-7.5 — Analysis sub-tab (opcional, candidata a posponer)

**Branch**: `feat/phase-7.5-analysis`

### Decisión arquitectónica previa

- (a) Nueva sección del módulo `personal-finance` en el registro
  `MODULES` → tab "Análisis" junto a Dashboard. Reusa endpoints
  actuales.
- (b) Sub-ruta dentro de Dashboard: `/personal-finance/dashboard/analysis`.
  Más cerca del Stitch (sidebar lateral) pero rompe el patrón actual
  de tabs flat.
- (c) Posponer hasta tener features detrás (Smart Insights, Budgets,
  Vault). Entonces sería PHASE-8 con backend nuevo.

**Recomendación: (c)**. Lo que aporta visualmente Analysis (Smart Insights,
Peer Group, Budgets) son features reales, no estilo. Construir la chrome
ahora con placeholders es deuda visible.

Si se decide (a):

- Endpoints adicionales para "expense breakdown", "saving rate", etc.
- Página nueva con el layout de Stitch.
- Estimación: 3-4 días.

---

## Definition of Done de la fase 7 completa

- [ ] PHASE-7.0 mergeada
- [ ] PHASE-7.1 mergeada con extensión backend de `DashboardSummary`
- [ ] PHASE-7.2 mergeada
- [ ] PHASE-7.3 mergeada
- [ ] PHASE-7.4 mergeada
- [ ] `internal_docs/phases/phase-7.X-*.md` creado por cada PR
- [ ] `internal_docs/architecture.md`: actualización de la shell
  (header en una fila) y mención de los primitives nuevos.
- [ ] `internal_docs/api/endpoints.md`: documentar
  `previous_period_*` en `GET /dashboard/summary` y el nuevo
  `GET /dashboard/currencies`.
- [ ] ADR `internal_docs/decisions/0002-data-table-primitive.md` —
  por qué `DataTable` vive en `apps/web/components/ui/` y no en
  `packages/ui` (mismo razonamiento que ADR-0001).
- [ ] Capturas comparativas antes/después en cada doc de fase.
- [ ] Tag `v0.7.0` al cerrar la fase mayor.

---

## Estimaciones agregadas

- Camino crítico (sin Analysis ni mobile): ~6-7 días.
- Camino completo hasta 7.4: ~10 días.
- Con Analysis (a): +3-4 días.
