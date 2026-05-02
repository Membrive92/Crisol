# PHASE-7.0 — Design primitives + layout shell

**Estado**: 🚧 en curso
**Rama**: `feat/phase-7.0-design-primitives`
**PR**: —
**Fecha de merge**: —

## Objetivo

Sentar la base visual de la fase 7. Cuatro primitives nuevos en
`apps/web/components/ui/` que las pantallas de 7.1–7.3 reutilizarán,
y compactar el header de la app a una sola fila.

## Qué se implementó

### Primitives nuevos (`apps/web/components/ui/`)

- `kpi-card.tsx` — `KpiCard` con `label`, `value`, `valueColor?`,
  `trailing?` (slot para badge/icono) y `footer?` (slot para delta /
  barra de presupuesto / sub-texto). Tipografía: `caption` muted para
  el label, `display` (32 px bold) tabular-nums para el valor.
- `fab.tsx` — `FabButton` y `FabLink`. Botón flotante circular 56×56,
  position fixed bottom-right, `primary` filled. Sombra propia más
  sutil que `elevation.overlay` porque vive sobre cualquier surface.
- `data-table.tsx` — `DataTable<T>` con `columns: DataTableColumn<T>[]`
  y `rows: T[]`. Cabecera `overline` sobre `surfaceMuted`, filas con
  hover `surfaceMuted`, divider `border` entre filas. Soporte opcional
  para `onRowClick` (filas focusables, `role="button"`, Enter/Space).
  Sin paginación ni filtros — eso lo aporta el caller.
- `category-chip.tsx` — `CategoryChip` con `label` y `kind`. Mapea
  `income → success-soft+success`, `expense → danger-soft+danger`,
  `null → primary-soft+primary`. Tipografía `overline`.

### Layout shell

- `apps/web/app/(app)/layout.tsx`: header colapsado a una sola fila —
  marca + module switcher + secciones del módulo + acciones de cuenta
  (Ajustes, theme toggle, Salir). El antiguo split en dos filas queda
  fuera. Las secciones viven dentro de un contenedor `flex: 1 1 auto`
  con `overflow-x: auto` para que en viewports estrechos las tabs
  scrolleen sin romper el header.
- `apps/web/components/modules/module-sections.tsx`: rediseñado para
  vivir inline en el header. Cambios:
  - Render como `<ul>` con `display: inline-flex` y `flex-wrap: nowrap`
    (el wrapping era apropiado para una fila propia, no para un header).
  - Cada item con `whiteSpace: nowrap` y `flex: 0 0 auto`.
  - Eliminado el subrayado de 2 px de la tab activa: ya no es
    necesario porque el `borderBottom` del header marca el límite y
    el bg `surfaceMuted` + texto fuerte ya distinguen el activo.
- "Cerrar sesión" pasa a `Salir` en color `textMuted` con borde
  hairline neutro — antes era `danger`, demasiado loud para una
  acción de cuenta de uso normal.

## Flujo técnico

Sin lógica de negocio nueva; sólo presentación. Los primitives son
puros, sin estado externo, sin data fetching. `KpiCard` y `Fab` son
composiciones de `Card` + tokens. `DataTable` mantiene su propio
estado de hover por fila inline (estilo simple). `CategoryChip` es
un span coloreado por tema vía tokens.

## Archivos clave

- `apps/web/components/ui/kpi-card.tsx`
- `apps/web/components/ui/fab.tsx`
- `apps/web/components/ui/data-table.tsx`
- `apps/web/components/ui/category-chip.tsx`
- `apps/web/app/(app)/layout.tsx`
- `apps/web/components/modules/module-sections.tsx`

## Endpoints añadidos

Ninguno.

## Migraciones

Ninguna.

## Verificación

- [x] `pnpm typecheck` verde
- [x] `pnpm lint` verde
- [x] `pnpm test` (8/8) verde
- [ ] Smoke manual: dashboard, transactions, imports, receipts,
      settings — header se ve consistente con la nueva fila única.
- [ ] Smoke manual: viewport estrecho (≤480 px) — tabs scrollean
      sin romper el header.

## Decisiones tomadas

- **Primitives en `apps/web/components/ui/`, no en `packages/ui`.**
  `packages/ui` es solo tokens (ADR-0001). Los componentes con JSX
  viven en cada app porque web y mobile no comparten runtime de
  rendering. Una versión equivalente para mobile vendrá en PHASE-7.4.
- **`DataTable` genérico desde el principio.** El primer caller será
  Transactions (PHASE-7.2), pero la API se diseña ya para que Imports
  y otras listas la consuman sin refactor. El generic `<T>` permite
  pasar columnas type-safe sin parsear filas a `unknown`.
- **`Fab` con dos componentes (`FabButton` + `FabLink`)** en lugar
  de uno polimórfico. La distinción entre acción (`onClick`) y
  navegación (`href`) es lo bastante frecuente para que un componente
  por caso quede más claro que un prop `as`.
- **Header en una fila + tabs inline scrollables**, no dos filas con
  tabs en su propia fila. Es la opción más densa, deja más espacio
  vertical al contenido y respeta mejor la mecánica del Stitch.

## Limitaciones conocidas

- `DataTable` no incluye paginación; cada caller la implementa
  encima. Si se ve patrón repetido en 2-3 sitios, se extraerá a un
  `DataTablePagination` en una sub-fase posterior.
- El hover de las filas se gestiona inline con `onMouseEnter`/`Leave`.
  Funciona pero es tosco — si añadimos CSS Modules o equivalente más
  adelante, mover a `:hover` puro.

## Próxima fase

PHASE-7.1 — Dashboard bento + delta vs periodo anterior.
