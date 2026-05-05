# PHASE-14.2 — Sección "Descartadas" en subscriptions UI

**Estado**: ✅ completada
**Rama**: `feat/phase-14.2-subscriptions-dismissed-ui`
**Fecha de merge**: 2026-05-05

## Objetivo

Cubrir la limitación documentada en PHASE-13.2/13.3: el endpoint
`GET /subscriptions?status=dismissed` ya existía (PHASE-13.1) pero
ninguna UI lo consumía. Ahora hay sección colapsable "Descartadas
(N)" en web y mobile con acción de reactivar.

## Qué se implementó

### Web

`apps/web/app/(app)/personal-finance/subscriptions/page.tsx`:

- Nueva `dismissedQuery = useSubscriptions({ status: 'dismissed' })`.
- Sección colapsable al final con toggle "▸/▾ Descartadas (N)" —
  oculta por defecto para no invadir la página cuando el usuario
  acumule muchos descartes.
- Cards con `primaryAction: Reactivar` (reusa `confirmMutation`
  que ya tenía la lógica "una dismissed confirmada se reactiva" de
  PHASE-13.1) y `secondaryAction: Eliminar`.

### Mobile

`apps/mobile/app/(modules)/personal-finance/subscriptions.tsx`:

- Misma estructura: query `dismissed`, toggle Pressable, sección
  oculta por defecto.
- `handleReactivate` usa `confirmMutation` igual que web. `Alert`
  destructivo se mantiene en `handleDelete`.

### Sin cambios shared

Reusa hooks y tipos existentes (`useSubscriptions`,
`useConfirmSubscription`, `useDeleteSubscription`). No hay nuevos
endpoints, types ni queries.

## Archivos clave

- `apps/web/app/(app)/personal-finance/subscriptions/page.tsx`
- `apps/mobile/app/(modules)/personal-finance/subscriptions.tsx`

## Verificación

- [x] `pnpm typecheck` verde.
- [x] `pnpm lint` verde.
- [x] `pnpm test` — 38 web + 5 mobile sin regresiones.
- [ ] Smoke: descartar una suggestion → aparece en sección
      colapsable; abrir → tap Reactivar → vuelve a "Confirmadas"
      con toast.success.

## Decisiones tomadas

- **Sección colapsable, oculta por defecto**. Las dismissed son
  ruido para el flujo principal. Mostrarlas siempre habría
  inflado la página visualmente cuando el usuario acumule muchas.
  Header con counter "(N)" hace visible que existen sin abrirlas.
- **Reactivar = confirm** (reuso del hook existente). PHASE-13.1
  ya implementó la lógica server-side: confirmar una dismissed la
  reactiva como confirmed. No necesitamos un endpoint nuevo.
- **Eliminar permanente disponible también en dismissed**. Una
  dismissed seguirá ocupando espacio en BD y bloqueando re-suggestion
  hasta que se elimine. Útil cuando el usuario quiere "olvidar
  completamente" una decisión vieja.

## Limitaciones conocidas

- **Sin filtro/búsqueda dentro de dismissed**. Asumimos volúmenes
  modestos. Si crece a 50+, añadir.
- **Sin tests UI mobile** (heredado).

## Próxima fase

PHASE-14.3 — Date picker nativo mobile (heredado desde PHASE-2.2).
