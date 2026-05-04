# PHASE-9.1 — Web sidebar como drawer en viewport mobile

**Estado**: ✅ completada
**Rama**: `feat/phase-9.1-mobile-sidebar-drawer`
**PR**: —
**Fecha de merge**: 2026-05-04

## Objetivo

Cerrar la limitación heredada de PHASE-7.6: la sidebar web no
colapsaba a drawer en viewport `<768px` — comprimía el contenido en
su lugar, dejando ~240px menos para el grid principal en pantallas
estrechas. Esta fase la convierte en drawer overlay con backdrop,
trigger hamburguesa en el header, y cierre por click-fuera, ESC o
navegación.

## Qué se implementó

### Iconos

`apps/web/components/ui/icons.tsx`: dos nuevos `MenuIcon` y `XIcon`
(estilo lucide, stroke-based, tamaño por prop). Reemplazan candidatos
parecidos pero distintos — `ListIcon` empezaba en x=8 (bullet list),
`MenuIcon` empieza en x=3 (full-width hamburguesa). `XIcon` se usa en
el botón "cerrar" interno de la sidebar.

### `app-sidebar.tsx`

- Nuevo prop `mobileOpen?: boolean` (default `false`). Se proyecta
  como `data-mobile-open="true"|"false"` en el `<aside>`.
- Nuevo prop `onCloseMobile?: () => void`. Llamado por el botón "X"
  en la cabecera de la sidebar (sólo visible en mobile vía
  `data-mobile-only`).
- `<aside>` gana `data-app-sidebar="true"` para que la media query
  global pueda dirigirse a él sin acoplarse a clases.
- `zIndex` sube de 40 → 60 para que el drawer pueda cubrir header
  (50) y backdrop (45). En desktop sidebar y header no se solapan,
  así que no afecta visualmente.
- Se exporta `MOBILE_BREAKPOINT_PX = 768` como single source of
  truth — el layout lo usa para componer la media query.

### `(app)/layout.tsx`

- Estado local `mobileNavOpen` (`useState`) — UI ephemeral, no entra
  en Zustand.
- `useEffect([pathname])`: al cambiar de ruta cierra el drawer
  automáticamente (el usuario navegó, no necesita volver a cerrar).
- `useEffect([mobileNavOpen])`: registra `keydown` global para que
  ESC cierre el drawer; cleanup al cerrar.
- Botón hamburguesa al inicio del header (`data-mobile-only`,
  `aria-label="Abrir menú"`). Visible sólo en `<768px`.
- Backdrop `<div data-mobile-backdrop>`: `position: fixed; inset: 0;`
  con tinte `rgba(0,0,0,0.45)` y `zIndex: 45`. Sólo se renderiza
  cuando el drawer está abierto; CSS lo oculta en desktop por si una
  transición de viewport lo deja vivo.
- `IconButton` ahora acepta `dataMobileOnly?: boolean` y `style?`.
  Cuando `dataMobileOnly`, el `display` por defecto es `none` y la
  media query lo eleva a `inline-flex` en mobile.
- Estilos globales inyectados vía `<style>` inline (constante
  `MOBILE_NAV_GLOBAL_STYLES`) con `!important` para batir a los
  inline styles del layout:

  ```css
  @media (max-width: 767px) {
    [data-app-main] { padding-left: 0 !important; }
    [data-app-header] { left: 0 !important; }
    [data-app-sidebar] {
      transform: translateX(-100%);
      transition: transform 200ms ease;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
    }
    [data-app-sidebar][data-mobile-open="true"] {
      transform: translateX(0);
    }
    [data-mobile-only] { display: inline-flex !important; }
  }
  @media (min-width: 768px) {
    [data-mobile-only] { display: none !important; }
    [data-mobile-backdrop] { display: none !important; }
  }
  ```

  El layout sigue usando `style={{}}` inline en el resto — los `!important`
  son necesarios sólo donde el inline gana sin ellos.

### Tests

`apps/web/components/modules/app-sidebar.test.tsx` (3 tests nuevos):

- `data-mobile-open=false` por defecto.
- `mobileOpen=true` → `data-mobile-open="true"`.
- Click en "Cerrar menú" → llama `onCloseMobile`.

`vitest.config.mts`: añadido alias `@` → root del paquete para que
los tests puedan importar `@/components/...` igual que la app.

## Flujo técnico

```
 Viewport <768px:
    ▼ Estado inicial
 [data-app-sidebar][data-mobile-open="false"]
 → CSS: transform: translateX(-100%)  → fuera de pantalla
 [data-app-main][padding-left: 0]    → main ocupa 100% del ancho
 [data-app-header][left: 0]          → header full-width
 [hamburguesa][data-mobile-only]      → visible (display: inline-flex)

    ▼ Click hamburguesa
 setMobileNavOpen(true)
 → backdrop renderizado (rgba 0.45, fixed, inset 0)
 → sidebar [data-mobile-open="true"] → transform: translateX(0) (200ms)

    ▼ Cierre por
   - Click backdrop  → setMobileNavOpen(false)
   - Tecla ESC       → setMobileNavOpen(false)
   - Click "X" en sidebar → onCloseMobile → setMobileNavOpen(false)
   - Navegación a otra ruta → useEffect([pathname]) → setMobileNavOpen(false)
 → backdrop unmount
 → sidebar slide-out a translateX(-100%) (200ms)

 Viewport >=768px:
 → media query no aplica las reglas mobile → sidebar visible siempre
 → hamburguesa display: none → backdrop display: none
```

## Archivos clave

- `apps/web/components/ui/icons.tsx` (nuevos `MenuIcon` y `XIcon`)
- `apps/web/components/modules/app-sidebar.tsx`
  (nuevos props `mobileOpen` / `onCloseMobile`, `data-app-sidebar`,
  `data-mobile-open`, `MOBILE_BREAKPOINT_PX` exportado)
- `apps/web/app/(app)/layout.tsx`
  (estado drawer + ESC + auto-close en navegación + estilos globales)
- `apps/web/components/modules/app-sidebar.test.tsx` (nuevo)
- `apps/web/vitest.config.mts` (alias `@`)

## Endpoints añadidos

Ninguno. Sólo frontend.

## Migraciones

Ninguna.

## Verificación

- [x] `pnpm lint` verde.
- [x] `pnpm typecheck` verde.
- [x] `pnpm test` — 11/11 (3 nuevos en `app-sidebar.test.tsx`).
- [ ] Smoke manual con DevTools responsive (<768px):
  - [ ] Hamburguesa visible en header.
  - [ ] Click abre drawer con backdrop.
  - [ ] Click backdrop / ESC / "X" cierra drawer.
  - [ ] Click en un módulo navega y cierra drawer.
  - [ ] En `>=768px` la sidebar es estática, hamburguesa oculta.

## Decisiones tomadas

- **Estilos globales vía `<style>` inline en el layout, no CSS module**.
  El layout y la sidebar ya usan `style={{}}` inline para todo el chrome
  (patrón establecido en PHASE-7.6 — ver
  `internal_docs/decisions/0001-ui-tokens-only.md`). Mantener la
  consistencia y no introducir un patrón nuevo (CSS module / Tailwind)
  pesa más que la pureza de "no inline `<style>`". El `!important` es
  necesario sólo en los selectores que baten a inline styles concretos.
- **Estado del drawer en `useState`, no en Zustand**. Es UI ephemeral
  con scope = layout. No hay otro consumidor que necesite leerlo. Si
  algún día Settings o un toast quisiera abrirlo programáticamente,
  promover a Zustand entonces.
- **Backdrop sólo se renderiza cuando `mobileNavOpen=true`**. Evita
  un `<div>` parásito en desktop. La media query `display: none !important`
  es un cinturón por si una transición de viewport lo deja vivo.
- **`zIndex` sidebar 40 → 60**. En desktop no afecta (no se solapan
  con header). En mobile cubre header (50) y backdrop (45) cuando el
  drawer está abierto, que es lo deseado.
- **Hamburguesa al inicio del header con `marginRight: auto`**. Mantiene
  el resto de iconos (notifs, currency, theme, user) alineados a la
  derecha como antes; sólo mete la hamburguesa a la izquierda en
  mobile.
- **`MOBILE_BREAKPOINT_PX` exportado desde la sidebar, no desde
  tokens**. Por ahora es un detalle del chrome web — si en el futuro
  hace falta en más sitios, promover a `packages/ui/src/tokens.ts` con
  un objeto `breakpoints`.

## Limitaciones conocidas

- **`setMobileNavOpen(false)` en cambio de pathname** es eager: si el
  usuario clica en "Añadir transacción" del footer (que sí está
  dentro del drawer) se cierra y luego navega — orden correcto. Si
  algún flujo futuro requiriera mantener el drawer abierto tras una
  navegación pasiva, hay que diferenciar.
- **No hay focus trap** dentro del drawer. ESC y click-fuera cierran,
  pero TAB puede salir al contenido detrás. Aceptable para MVP; meter
  `focus-trap-react` u algún equivalente cuando se haga el sweep de
  accesibilidad completo.
- **Botón "X" interno de la sidebar es algo redundante** con el
  backdrop. Se mantiene porque hay usuarios que esperan el control
  explícito (patrón de iOS/Material) y porque en pantallas muy
  estrechas el backdrop puede ser un sliver de pixels difícil de
  acertar.

## Próxima fase

PHASE-9.2 — Análisis screen en mobile (depende de este merge).
