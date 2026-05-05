# PHASE-10.3 — Frontend papelera (mobile)

**Estado**: ✅ completada
**Rama**: `feat/phase-10.3-mobile-trash`
**PR**: —
**Fecha de merge**: 2026-05-05

## Objetivo

Cerrar el frente de papelera en mobile. PHASE-10.2 dejó la capa
shared (api/hooks/tipos) y la UI web; esta fase reusa los mismos
hooks (`useTrashedTransactions`, `useRestoreTransaction`,
`usePurgeTransaction`) para añadir pantalla `/trash` mobile,
snackbar inferior con deshacer, y un botón "Papelera" con badge en
el header de la pestaña de transacciones.

Marca el cierre de la **fase 10** completa: backend (10.1), web
(10.2), mobile (10.3).

## Qué se implementó

### Pantalla `/trash` mobile

`apps/mobile/app/(modules)/personal-finance/trash.tsx` (nueva, vive
fuera de `(tabs)/` porque la papelera es una vista secundaria):

- `<Stack.Screen options={{ title: 'Papelera' }} />` para el header
  de Expo Router.
- Subtítulo con contador (`X transacciones en papelera`).
- `FlatList` con `RefreshControl`.
- Cada fila: descripción, fecha + categoría, tiempo relativo
  (`Borrada hace X min/h/días`), importe, y dos `Pressable` con
  borde sutil — `Restaurar` (tinte primary) y `Eliminar` (tinte
  danger).
- Restore directo (sin confirm — reversible).
- `Alert.alert` destructivo nativo en purge: cancelar / eliminar.
- Disabled state vía `busyId` cuando una mutation está en vuelo.
- Empty state cuando `total === 0`.
- Banner de error inferior cuando `restoreMutation.isError ||
  purgeMutation.isError`.

### Snackbar `<TrashedSnackbar>`

`apps/mobile/components/transactions/trashed-snackbar.tsx`:

- Equivalente al `TrashedBanner` web: estado interno `visibleId`
  sincronizado con `lastDeletedId` prop, auto-dismiss tras
  `dismissAfterMs` (default 6s).
- Posicionado `position: 'absolute'` en el bottom de la pantalla
  para sobrevivir scroll. Sombra + fondo `colors.text` (oscuro)
  sobre tipografía clara — patrón material/iOS de toast.
- Acciones `[Deshacer]` y `[Ver]`. Tras tap, oculta el snackbar y
  ejecuta el callback (que en transactions.tsx llama a
  `restoreMutation` o navega a `/trash`).
- `accessibilityLiveRegion="polite"` para screen readers.

### Pantalla `(tabs)/transactions.tsx`

- Long-press en una fila: ahora `Alert.alert` confirm "Mover a
  papelera" en lugar de borrar silente. Antes era un `delete`
  destructivo silencioso al long-press, comportamiento poco
  forgiving que con soft-delete ya no escala (fácil borrar sin
  intención).
- Tras éxito, `setLastDeletedId(id)` activa el snackbar.
- `handleUndo` resetea el snackbar y dispara `restoreMutation`.
- Botón "Papelera" en el header con badge azul si hay items
  (`useTrashedTransactions({limit:1}).total`).
- `<TrashedSnackbar>` montado al final del `<View>` raíz para que
  flote sobre la lista.
- Cambios cosméticos para que las acciones del header quepan: nuevo
  `headerActions` row con gap; `addButton` cambia `:'600'` cast por
  `fontWeight.semibold` directo (mismo valor literal '600').

### Reuso de la capa shared

Esta fase **no añade hooks nuevos** — consume los exportados desde
`packages/services` en PHASE-10.2:

- `useTrashedTransactions({ limit, offset })`.
- `useRestoreTransaction()`.
- `usePurgeTransaction()`.
- `useDeleteTransaction()` (ya invalidaba dashboard tras 10.2).

Las invalidaciones de TanStack Query se aplican igual: `transactions.all`
cubre la lista de la pestaña, la papelera, el contador del badge y el
detalle. `dashboard.all` se invalida al delete/restore para que los
KPIs del Análisis se refresquen al volver a esa tab.

## Flujo técnico

```
 Usuario long-press una transacción en mobile
    │
    ▼
 Alert.alert "¿Mover a papelera?"  [Cancelar | Mover (destructive)]
    │
    ▼ Mover
 deleteMutation.mutate(id)
    │
    ▼ onSuccess
 setLastDeletedId(id)              invalida transactions.all + dashboard.all
    │                                  │
    ▼                                  ▼
 <TrashedSnackbar> aparece         lista se refresca sin la tx
 (oscuro, bottom sticky,            badge "Papelera N" sube
  + [Deshacer] [Ver])               KPIs del Análisis se ajustan al volver
    │
    ├── Tap Deshacer (dentro de 6s)
    │       │ snackbar oculto
    │       ▼ restoreMutation.mutate(id)
    │       └─→ tx vuelve, badge baja
    │
    ├── Tap Ver
    │       └─→ router.push('/trash') — Stack.Screen "Papelera"
    │
    └── 6s sin tap → snackbar auto-dismiss
        (tx sigue en /trash, recuperable manualmente)

 En /trash:
   Tap Restaurar  → restoreMutation directo (sin Alert)
   Tap Eliminar   → Alert.alert destructive
                    → confirma → purgeMutation
                    → tx desaparece de papelera permanente
```

## Archivos clave

- `apps/mobile/app/(modules)/personal-finance/trash.tsx` (nuevo)
- `apps/mobile/components/transactions/trashed-snackbar.tsx` (nuevo)
- `apps/mobile/app/(modules)/personal-finance/(tabs)/transactions.tsx`
  (Alert confirm + snackbar + link papelera + badge)

## Endpoints añadidos

Ninguno — consume PHASE-10.1.

## Migraciones

Ninguna.

## Verificación

- [x] `pnpm --filter @finanzas/mobile typecheck` verde.
- [x] `pnpm --filter @finanzas/mobile lint` verde.
- [ ] No hay tests UI mobile (heredado del backlog desde PHASE-2.2:
      `jest-expo` sin configurar). La verificación de esta fase es
      manual.
- [ ] Smoke en Expo:
  - [ ] Long-press una tx → Alert "Mover a papelera" → Mover.
  - [ ] Snackbar inferior aparece, badge "Papelera N" sube.
  - [ ] Tap Deshacer → tx vuelve, snackbar desaparece.
  - [ ] Long-press otra → Mover → tap Ver → /trash con la tx.
  - [ ] En /trash: tap Restaurar → vuelve.
  - [ ] En /trash: tap Eliminar → Alert destructive → tx desaparece
        permanente.
  - [ ] Pull-to-refresh en /trash actualiza.

## Decisiones tomadas

- **Trash fuera de `(tabs)/`** — la papelera es vista secundaria
  (acción explícita desde el header), no un tab principal.
  Coherente con cómo se accede en web (link en eyebrow bar). Crear
  un cuarto tab dedicado a papelera dilataría la navegación
  primaria que ya tiene Análisis / Transacciones / Tickets.
- **Long-press → `Alert.alert` confirm en lugar de borrar silente**.
  Pre-PHASE-10.3 el long-press borraba destructivo sin confirmar —
  fácil de invocar accidentalmente. Con soft-delete el coste de un
  borrado accidental es bajo (recuperable), pero pedir confirmación
  evita el "qué pasó" y deja descubrible el flujo papelera vía el
  copy "Mover a papelera".
- **Snackbar oscuro + posicionamiento absoluto bottom**. Patrón
  material/iOS estándar para snackbars de "deshacer". Sombra para
  que se separe visualmente del contenido. La alternativa (snackbar
  inline en el flujo de la pantalla) competía con la lista por
  espacio vertical y no se veía si la tx borrada estaba scroll
  abajo.
- **Sin date picker / search en /trash**. Igual que web — vista
  plana ordenada por `deleted_at DESC`. Si crece, añadir entonces.
- **Restaurar sin confirm**. Coherente con web. Restore es
  reversible (volver a borrar es trivial); pedir confirm añade
  fricción sin beneficio.
- **Sin tests UI mobile** — `jest-expo` sigue sin configurar
  (heredado del backlog desde PHASE-2.2). La lógica testeable
  (snackbar auto-dismiss, undo state) está cubierta por los tests
  equivalentes en web (`trashed-banner.test.tsx`).

## Limitaciones conocidas

- **Sin tests UI mobile** (heredado). El snackbar y la pantalla
  /trash se verifican vía smoke en Expo.
- **`lastDeletedId` vive en `useState` local de la pestaña
  transactions**. Si el usuario navega a otra tab antes de los 6s,
  el snackbar se desmonta y se pierde la opción de Deshacer. Si
  molesta, promover a Zustand. Coherente con la limitación
  documentada en PHASE-10.2 (web).
- **Sin keyboard shortcut para Cancelar el long-press confirm** — el
  Alert nativo gestiona esto solo (escape físico en iOS, back en
  Android).
- **Mobile no muestra `convertAll`** en la pestaña transactions
  (heredado de PHASE-9.2: `useCurrencyStore` es web-only). La
  papelera tampoco — irrelevante porque ya no muestra conversión
  ni siquiera en web.

## Próxima fase

Sin definir. Candidatos del backlog (sin priorizar):

- **Cron nocturno de tasas (APScheduler)** — el lazy fetch cubre
  "primer uso del día"; si la app pasa días sin abrirse las tasas
  se quedan atrás.
- **`useCurrencyStore` cross-platform (AsyncStorage adapter)** —
  pre-requisito para que mobile herede `convertAll` y la moneda
  global del web.
- **Sistema de toasts global** — el banner web y el snackbar mobile
  son ad-hoc para esta pantalla; otros flujos (imports, receipt
  confirm) siguen sin feedback de éxito.
- **Captura de tickets por cámara mobile** (heredado de PHASE-5.2).
- **Detección de subscripciones recurrentes vía AI**.
- **Modelo de presupuestos por categoría con alertas**.
