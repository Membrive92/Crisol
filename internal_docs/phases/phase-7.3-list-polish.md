# PHASE-7.3 — Imports + Receipts polish

**Estado**: ✅ completada
**Rama**: `feat/phase-7.3-list-polish`
**PR**: —
**Fecha de merge**: —

## Objetivo

Aplicar el mismo lenguaje visual de Transactions (PHASE-7.2) a los
otros dos listados del módulo: Imports y Receipts. Mismo `<DataTable>`,
mismo `<Pagination>`, misma cabecera con CTA secundario y subtítulo
con estado de fetching. Trabajo cosmético, sin backend.

## Qué se implementó

### Imports (`apps/web/components/imports/import-list.tsx` + `personal-finance/imports/page.tsx`)

- Lista pasa de `<ul>` con cards a `<DataTable>` con cuatro columnas:
  | Fecha | Archivo | Resultado | Estado |
- `Resultado` sintetiza los contadores en una línea: `N ok · N dup ·
  N err` con cada número en su color semántico (success / warning /
  danger). Tabular-nums para alineación.
- `Estado`: `StatusBadge` (ya existente, ya migrado a tokens tonales en
  PHASE-6.1) alineada a la derecha.
- Click en la fila → `/personal-finance/imports/{id}`. Reemplaza el
  link "Ver detalle →" inline.
- Página: `maxWidth` sube a 1100 px, header alineado al patrón de
  Transactions (CTA secondary + subtítulo con estado de fetching),
  footer reemplazada por `<Pagination>` numérica.

### Receipts (`apps/web/components/receipts/receipt-list.tsx` + `personal-finance/receipts/page.tsx`)

- Lista pasa a `<DataTable>` con cuatro columnas:
  | Fecha | Comercio | Total | Estado |
- `Comercio`: nombre extraído por la IA, fallback "(sin comercio)" en
  `text-subtle` cuando no se pudo leer.
- `Total`: importe + moneda alineado a la derecha, tabular-nums.
  Fallback "—" cuando no hay total extraído.
- `Estado`: `ReceiptStatusBadge` (CONFIRMADO / PENDIENTE / RECHAZADO).
- Click en la fila → `/personal-finance/receipts/{id}`.
- Página: mismo tratamiento que Imports/Transactions. CTA "+ Subir
  ticket" en secondary, paginación numérica.

## Archivos clave

- `apps/web/components/imports/import-list.tsx`
- `apps/web/components/receipts/receipt-list.tsx`
- `apps/web/app/(app)/personal-finance/imports/page.tsx`
- `apps/web/app/(app)/personal-finance/receipts/page.tsx`

## Endpoints añadidos

Ninguno.

## Migraciones

Ninguna.

## Verificación

- [x] `pnpm typecheck` verde
- [x] `pnpm lint` verde
- [x] `pnpm test` (8/8) verde
- [ ] Smoke manual: `/personal-finance/imports` y
      `/personal-finance/receipts` con datos reales — fila clickable,
      badges tonales, paginación numérica funciona.

## Decisiones tomadas

- **Mismo `<DataTable>` para los tres listados**, no abstracciones
  específicas por módulo. La estructura datatable+filters+pagination
  cubre los tres casos sin esfuerzo adicional. Si Receipts o Imports
  añaden secciones específicas (ej. quick-actions inline) las
  resolveremos a medida.
- **Tres páginas con `maxWidth: 1100 px`**. Antes Imports y Receipts
  iban a 960; ahora alineadas. Da aire a las columnas y la lectura es
  consistente entre las tres pantallas hermanas.
- **Sin filtros para Imports/Receipts en este PR.** No los tienen
  ahora y no son urgentes (son listados cortos por uso). Se añadirán
  cuando el volumen del usuario lo justifique.
- **Sin acciones inline.** Imports y Receipts no tenían botón de
  borrar inline antes (la columna de acciones se introdujo en
  Transactions porque ya existía). Mantengo la asimetría: borrar un
  ticket o una importación no debería ser one-click — viven en su
  propio detalle.

## Limitaciones conocidas

- La tabla en mobile (viewport <600 px) no scrollea horizontal. Mismo
  caveat que en PHASE-7.2; se resuelve en PHASE-7.4 (mobile parity) o
  parcheamos el primitive si hace falta antes.
- `pickMerchant`/`pickTotal` siguen castando `extraction` a
  `Record<string, unknown>` y leyendo manualmente. Funcional, pero el
  schema TS (`ReceiptExtraction` con `total: string | null`) ya
  permitiría una versión typesafe — refactor menor pendiente.

## Próxima fase

PHASE-7.4 — Mobile parity (replicar primitives + dashboard simplificado
en `apps/mobile`).
