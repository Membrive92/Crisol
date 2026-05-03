# PHASE-7.2 — Transactions tabla

**Estado**: 🚧 en curso
**Rama**: `feat/phase-7.2-transactions-table`
**PR**: —
**Fecha de merge**: —

## Objetivo

Reescribir el listado de Transactions como tabla densa usando los
primitives de PHASE-7.0. La vista de cards apilada era válida con 5
filas pero deja de escalar a partir de 20+: la tabla es lo que el
producto necesita para que el usuario filtre, escanee y compare.

## Qué se implementó

### Frontend nuevo

- `apps/web/components/ui/origin-badge.tsx` — `OriginBadge` con tres
  variantes: `manual` (neutral, `surface-muted` + `text-muted`),
  `import` (`primary-soft` + `primary`), `receipt` (`success-soft` +
  `success`). Tipografía `overline`.
- `apps/web/components/ui/pagination.tsx` — `Pagination` numérica con
  elipsis. Anterior/Siguiente como botones `ghost`, páginas como pills
  compactas (32×32 px), activa con `primary` filled. Algoritmo
  `computePageWindow` para mostrar `1 … (n-1) [n] (n+1) … last` con
  reajuste cuando se está cerca de los bordes.

### Refactor `transaction-list.tsx`

- Render como `<DataTable>` con seis columnas:
  | Fecha | Categoría | Descripción | Origen | Importe | (Acciones) |
- `Categoría`: `<CategoryChip>` (de PHASE-7.0) tinted por kind
  (income/expense/null).
- `Origen`: `<OriginBadge>`.
- `Importe`: alineado a la derecha, mono (`tabular-nums`), color por
  kind (income → success, expense → danger, sin categoría → text), con
  signo `+`/`-` derivado del kind. El importe en BD es siempre
  positivo; el signo es presentación.
- `Acciones`: una sola columna con botón `Borrar` ghost (rojo). El
  click no propaga al row.
- Click en cualquier otra parte de la fila → navega a
  `/personal-finance/transactions/{id}` (página de edición). Esto
  reemplaza al botón "Editar" inline anterior.

### Refactor `transactions/page.tsx`

- `maxWidth` sube de 960 a 1100 px (la tabla con 6 columnas necesita
  más anchura).
- Header con título a la izquierda y CTA "+ Nueva" (secondary
  outlined) a la derecha. Subtítulo combina contador con estado de
  fetching ("128 registros · actualizando…").
- Filtros (`<TransactionFilters>`) sin cambios — ya estaban en grid.
- Footer pasa al `<Pagination>` numérico nuevo. Texto izquierdo
  "Mostrando 1–20 de 128", botones Anterior/Siguiente y páginas
  numéricas con elipsis.

## Archivos clave

- `apps/web/components/ui/origin-badge.tsx`
- `apps/web/components/ui/pagination.tsx`
- `apps/web/components/transactions/transaction-list.tsx`
- `apps/web/app/(app)/personal-finance/transactions/page.tsx`

## Endpoints añadidos

Ninguno. El endpoint `GET /transactions` ya devuelve todos los datos
necesarios.

## Migraciones

Ninguna.

## Verificación

- [x] `pnpm typecheck` verde
- [x] `pnpm lint` verde
- [x] `pnpm test` (8/8) verde
- [ ] Smoke manual: `/personal-finance/transactions` con datos reales
      — fila clickable, badges tinted, paginación numérica funciona,
      filtros recargan tabla.

## Decisiones tomadas

- **Row click → detalle** en lugar de un botón "Editar" inline. Es la
  convención en data-tables modernas (Linear, Notion, Stripe). Si el
  usuario quiere abrir en pestaña nueva, Cmd/Ctrl+click sigue
  funcionando porque la fila usa `router.push` síncrono.
- **Una sola acción explícita en la columna de acciones** (`Borrar`).
  Editar es la acción principal, va al hacer click en la fila. Borrar
  es destructiva, va aislada con `e.stopPropagation()` para evitar
  borrados accidentales al fallar el click.
- **`Pagination` como primitive en `components/ui/`**. Ya se intuye
  que Imports y Receipts la van a reusar en PHASE-7.3, así que se
  diseña genérica desde el principio (acepta `total`, `offset`,
  `limit`, `pageItemCount`, `onChange`).
- **Color del importe por kind**, no por signo: el signo (income/
  expense) lo da la categoría, no el importe en BD (que es siempre
  positivo). Para transacciones sin categoría usamos `text` neutral
  porque no podemos afirmar la dirección.
- **`Origen` con paleta diferenciada**: manual neutral, import primary,
  receipt success. La diferenciación añade información visual y se
  alinea con el resto del sistema tonal.

## Limitaciones conocidas

- `description` se trunca con ellipsis a 280 px. Para descripciones
  largas el usuario tiene que entrar al detalle. Aceptable para una
  vista de listado.
- La tabla en mobile (viewport <600 px) no scrollea horizontalmente:
  el `<DataTable>` original no tiene `overflow-x: auto`. Esto se
  resolverá en PHASE-7.4 (mobile parity) o se podría parchear ya en
  el primitive si genera fricción antes.
- `Pagination.computePageWindow` con `maxButtons=5` en escenarios
  exóticos (current cerca de los bordes con muchas páginas) podría
  mostrar 6 botones por el reajuste. Suficiente — no rompe layout.

## Próxima fase

PHASE-7.3 — Imports + Receipts polish.
