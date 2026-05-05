# PHASE-11.3 — Sistema de toasts global (web + mobile)

**Estado**: ✅ completada
**Rama**: `feat/phase-11.3-toasts-global`
**PR**: —
**Fecha de merge**: 2026-05-05

## Objetivo

PHASE-10.2 / 10.3 introdujeron dos notificaciones ad-hoc para el
flujo "Movido a papelera": `TrashedBanner` (web inline) y
`TrashedSnackbar` (mobile sticky bottom). Otros flujos (imports,
receipts confirm, errores de mutation) seguían sin feedback.
Reinventar la rueda en cada feature no escala.

Esta fase introduce un **store de toasts cross-platform** + dos
componentes `<Toaster />` (web/mobile) que lo renderizan, y migra
los dos sitios ad-hoc a la nueva API. El flujo de papelera ahora
usa el toast genérico; futuras features llaman a `toast.show(...)`
sin pensar en UI.

## Qué se implementó

### Tipos shared (`@finanzas/types`)

`packages/types/src/models/toast.ts`:

- **`ToastKind`**: `'info' | 'success' | 'warning' | 'error'`.
- **`ToastAction`**: `{ label, onPress }`. No `href` — navegación
  y mutation se mezclan mal en un solo primitive; si hace falta
  navegar, el caller hace `router.push` desde su `onPress`.
- **`Toast`**: forma persistida en el store (`id` generado, `kind`,
  `message`, `action?`, `dismissAfterMs`).
- **`ToastInput`**: forma pública del `show(...)` — el store rellena
  `id` y `dismissAfterMs` por defecto.

Re-export en `packages/types/src/index.ts`.

### Store (`@finanzas/store`)

`packages/store/src/toast.ts`:

- **`useToastStore`** (Zustand sin persist): queue `toasts: Toast[]`,
  acciones `show(input) → id`, `dismiss(id)`, `clear()`.
- **Defaults de auto-dismiss por kind**: info 5s, success 5s,
  warning 6s, **error 0** (manual). Si el toast lleva acción, sube
  a 8s para dar tiempo a leerla y pulsarla.
- **`generateId()`**: `crypto.randomUUID()` con fallback
  `Date.now()+random` por si algún runtime exótico no la tiene.
- **`toast` helper procedural**: `toast.show()`, `toast.info()`,
  `toast.success()`, `toast.warning()`, `toast.error()`,
  `toast.dismiss(id)`, `toast.clear()`. Para callers que no quieren
  llamar a `useToastStore.getState()`.

Re-exports en `packages/store/src/index.ts` (`useToastStore`,
`toast`, `ToastState`).

### Componente web (`apps/web/components/ui/toaster.tsx`)

- Stack `position: fixed; top; right` con z-index alto (1000) para
  flotar sobre header/sidebar.
- Cada `<ToastCard>`: `border-left` 3px del color del `kind`,
  `aria-live="polite"` (assertive para errors), botón Cerrar (X) y
  botón Acción opcional.
- Auto-dismiss vía `useEffect` con `setTimeout`/`clearTimeout`.
- `pointer-events: none` en el container, `auto` en cada toast —
  no bloquea clicks en la app cuando hay toasts vivos en zonas
  vacías del stack.
- Paleta por kind reutiliza tokens (`primarySoft`, `successSoft`,
  `warningSoft`, `dangerSoft`).

Montado **una vez** en `apps/web/app/(app)/layout.tsx` al final del
`<div>` raíz.

### Componente mobile (`apps/mobile/components/ui/toaster.tsx`)

- Stack `position: absolute; bottom` para no chocar con el header
  Stack de Expo Router.
- Toasts con fondo oscuro (`colors.text`) + texto claro
  (`colors.surface`) + acento `borderLeftColor` por kind. Patrón
  material/iOS de snackbar.
- `accessibilityLiveRegion` mismo criterio que web.
- `pointerEvents="box-none"` en el stack — clicks en zonas vacías
  pasan a la lista debajo.
- Cierre (×) sólo cuando el usuario quiere — equivalente al web.

Montado **una vez** en `apps/mobile/app/_layout.tsx` dentro de
`<QueryProvider>`, después del `<Stack>`.

### Migraciones de los sitios ad-hoc

- **Web `transactions/page.tsx`**: borrado el state
  `lastDeletedId` y el `<TrashedBanner>`. El `onSuccess` del
  `deleteMutation` ahora llama a `toast.show({ kind: 'info',
  message: 'Transacción movida a papelera.', action: { label:
  'Deshacer', onPress: () => restoreMutation.mutate(id) } })`.
- **Mobile `transactions.tsx`**: idéntico — borrado state +
  componente `<TrashedSnackbar>`. El `onSuccess` del delete usa
  `toast.show(...)` con la misma forma.
- **Borrados**:
  - `apps/web/components/transactions/trashed-banner.tsx`
  - `apps/web/components/transactions/trashed-banner.test.tsx`
  - `apps/mobile/components/transactions/trashed-snackbar.tsx`

### Tests

`apps/web/components/ui/toaster.test.tsx` (7 tests, todos pasan):

- Empty state.
- Render del toast tras `toast.success('...')`.
- Acción dispara `onPress` y cierra el toast.
- Botón Cerrar cierra el toast.
- Auto-dismiss tras `dismissAfterMs` con `vi.useFakeTimers`.
- `dismissAfterMs=0` (error default) NO auto-dismiss.
- `toast con action` usa default `8000` ms.

Suite web: **23/23** (+9 nuevos, −2 borrados con `TrashedBanner`).

## Flujo técnico

```
 Cualquier código:
    toast.show({ kind, message, action? })
        │
        ▼
    useToastStore.getState().show(input)
        ├── id = crypto.randomUUID()
        ├── dismissAfterMs = input.dismissAfterMs
        │     ?? (input.action ? 8000 : DEFAULT_BY_KIND[kind])
        └── set((s) => ({ toasts: [...s.toasts, toast] }))

 <Toaster /> (montado en root layout)
    useToastStore((s) => s.toasts)
        │
        ▼ por cada toast:
    <ToastCard toast={t} />
        ├── useEffect: setTimeout(dismiss(id), t.dismissAfterMs)
        │   (no-op si dismissAfterMs <= 0)
        ├── render mensaje
        ├── render action button (opcional)
        │     onClick → action.onPress() + dismiss(id)
        └── render close button
              onClick → dismiss(id)

 dismiss(id) → set((s) => ({ toasts: s.toasts.filter(t => t.id !== id) }))
```

## Archivos clave

- `packages/types/src/models/toast.ts` (nuevo)
- `packages/types/src/index.ts` (re-exports)
- `packages/store/src/toast.ts` (nuevo, store + `toast` helper)
- `packages/store/src/index.ts` (re-exports)
- `apps/web/components/ui/toaster.tsx` (nuevo)
- `apps/web/components/ui/toaster.test.tsx` (nuevo, 7 tests)
- `apps/web/app/(app)/layout.tsx` (monta `<Toaster />`)
- `apps/web/app/(app)/personal-finance/transactions/page.tsx`
  (toast en lugar de banner)
- `apps/mobile/components/ui/toaster.tsx` (nuevo)
- `apps/mobile/app/_layout.tsx` (monta `<Toaster />`)
- `apps/mobile/app/(modules)/personal-finance/(tabs)/transactions.tsx`
  (toast en lugar de snackbar)
- **Borrados**: `trashed-banner.{tsx,test.tsx}` web,
  `trashed-snackbar.tsx` mobile.

## Endpoints

Ninguno.

## Migraciones

Ninguna.

## Verificación

- [x] `pnpm typecheck` verde (web + mobile + packages).
- [x] `pnpm lint` verde.
- [x] `pnpm test` — 23/23 web (+9 nuevos en `toaster.test.tsx`,
      −4 borrados con `trashed-banner.test.tsx`).
- [ ] Smoke manual:
  - [ ] Web: borrar tx → toast top-right "Movida a papelera" +
        Deshacer + cerrar (X). Click Deshacer → tx vuelve, toast
        cierra. Esperar 8s sin tocar → cierra solo.
  - [ ] Mobile: long-press tx → Alert → Mover → toast bottom dark
        con misma forma. Tap Deshacer → idem.

## Decisiones tomadas

- **Store en `@finanzas/store` en lugar de prop drilling / Context**.
  Cualquier código (incluso fuera de React, p. ej. interceptors de
  axios o callbacks de queries) puede llamar
  `useToastStore.getState().show(...)` o el helper procedural
  `toast.show(...)`. Sin pasar refs ni montar Providers extra.
- **Helper procedural `toast.{info,success,warning,error,show}`**.
  Lecturas rápidas en sitios donde no quieres importar dos cosas.
  `toast.show(...)` cubre el caso completo (kind + action +
  override de tiempo).
- **`ToastAction` sin `href`**. Mezclar navegación con acciones
  custom en el mismo primitive obliga a discriminar en el render
  ("¿es link? ¿es botón?"). El caller que quiere navegar hace
  `router.push` desde su `onPress`. Trade-off mínimo, contrato más
  limpio.
- **Errores con auto-dismiss `0` por default**. Tragar un error
  silenciosamente frustra al usuario. El caller que quiera un
  error que se cierre solo pasa `dismissAfterMs` explícito.
- **Posición fija top-right (web) vs bottom (mobile)**. Convención
  de cada plataforma — top-right en desktop deja libre el contenido
  primario; bottom en mobile evita interferir con el contenido
  scrollable y queda al alcance del pulgar.
- **Sin animación de entrada/salida**. Mount/unmount directo —
  funciona, accesible. Si en el futuro se quiere transición CSS /
  Reanimated, el `<ToastCard>` es el único punto a tocar.
- **Sin queue cap / prioridades**. Un usuario que dispara 10 toasts
  los ve apilados. Si se vuelve un problema (ej. tras un import con
  N errores por fila), el caller agrupa antes de llamar (`toast.show`
  con un mensaje compuesto).
- **`crypto.randomUUID` con fallback**. Disponible en todos los
  navegadores modernos y RN ≥0.74. El fallback (Date+random)
  garantiza que el módulo no peta en runtimes exóticos.
- **Borrar `TrashedBanner` / `TrashedSnackbar` ahora**. Mantenerlos
  como código muerto sería deuda técnica inmediata. Cualquier feature
  futuro que necesite "deshacer" usa el toast genérico.

## Limitaciones conocidas

- **No persiste entre rutas mobile que reinicialicen el QueryProvider**.
  El store vive en memoria — si una ruta hace teardown del proveedor
  raíz, los toasts en cola se pierden. Hoy no aplica (root provider
  estable), pero conviene saberlo.
- **Sin swipe-to-dismiss en mobile**. Sólo el botón ×. Si UX lo
  pide, integrar `react-native-gesture-handler` en `<ToastCard>`.
- **Sin `toast.promise(p, { loading, success, error })`** estilo
  Sonner. Casi siempre hace falta cuando se conecta a un fetch
  async — añadir si llega un caso real (probablemente PHASE-11.4
  con la captura de tickets).
- **Posición top-right web es absoluta**. Si una página
  tiene su propio overlay con z-index >1000 (modales, drawers
  futuros), el toast quedaría debajo. Si pasa: subir el z-index del
  toaster.
- **Sin tests UI mobile** (heredado de PHASE-2.2: `jest-expo`
  pendiente). El componente RN se prueba vía smoke en Expo. La
  lógica testeable (store push/dismiss/auto) está cubierta por los
  tests web del Toaster (mismo store).

## Próxima fase

PHASE-11.4 — Captura de tickets por cámara mobile. `expo-image-picker`
ya está instalado; la pantalla de receipt capture mobile sigue en
modo "subir desde galería" — falta integrar la cámara, conectarla al
endpoint `/receipts/extract`, y dar feedback con el nuevo sistema de
toasts (`toast.success("Ticket añadido")` /
`toast.error("Ollama no responde")`).
