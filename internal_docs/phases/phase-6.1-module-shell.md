# PHASE-6.1 — Module shell + personal_finance grouping

**Estado**: ✅ completada
**Rama**: `feat/phase-6.1-module-shell`
**PR**: —
**Fecha de merge**: 2026-04-30

## Objetivo

Alinear el frontend al modelo de dominio del backend: agrupar las features
de finanzas personales (`dashboard`, `transactions`, `imports`, `receipts`)
bajo un módulo `personal-finance/` y dejar la navegación preparada para
añadir nuevos módulos (crypto, inversiones, inmuebles) sin refactor.

## Qué se implementó

### Tipos compartidos (`@finanzas/types`)

- `models/module.ts` — tipos `AppModule`, `ModuleId`, `ModuleSection`.
- `registry/modules.ts` — registro `MODULES` con los cuatro slots
  (`personal-finance` activo; el resto deshabilitados con `enabled: false`).
- Helpers `getModule`, `findModuleByPath` y la constante
  `PERSONAL_FINANCE_BASE` para evitar paths hardcodeados en las apps.

### Web (`apps/web`)

- Renombrado del route group `(dashboard)` → `(app)`.
- Movidos `dashboard/`, `transactions/`, `imports/`, `receipts/` bajo
  `(app)/personal-finance/`. `settings/` y `home/` se quedan a nivel
  superior (cross-cutting).
- `components/modules/module-switcher.tsx` — dropdown accesible
  (`role="listbox"`) que pinta el módulo activo y la lista completa con
  los deshabilitados marcados como "Próximamente". Cierra con Escape o
  click fuera.
- `components/modules/module-sections.tsx` — sub-nav que pinta las
  secciones del módulo activo. Marca la activa con `borderBottom` y
  `usePathname` para resaltarla.
- Layout `(app)/layout.tsx` reescrito: fila superior con marca, switcher
  y acciones (Ajustes / tema / logout); fila inferior con las secciones
  del módulo activo.
- `next.config.mjs` añade redirects 308 desde las rutas planas previas
  (`/dashboard`, `/transactions`, `/imports`, `/receipts` y sus subpaths)
  a `/personal-finance/*`. Mantiene vivos bookmarks externos.
- Login, register y root page redirigen ahora a
  `/personal-finance/dashboard`.

### Mobile (`apps/mobile`)

- Movidos `(tabs)/`, `transaction/` y `receipt/` bajo
  `(modules)/personal-finance/`.
- Nuevos layouts:
  - `(modules)/_layout.tsx` — Stack mudo, prepara espacio para futuros
    módulos hermanos.
  - `(modules)/personal-finance/_layout.tsx` — declara las pantallas
    `transaction/*` y `receipt/*` con su título de Stack.
  - `(modules)/personal-finance/(tabs)/_layout.tsx` — `headerTitle`
    usa el nuevo `ModuleHeader`.
- `components/modules/module-header.tsx` — título-botón en el header de
  tabs. Tap abre un `Modal` con bottom sheet listando los módulos. La
  animación es la nativa de `Modal`, sin nuevas dependencias.
- Root `app/_layout.tsx` registra ahora `(modules)` en lugar de `(tabs)`
  + `transaction/*` + `receipt/*` (esos pasan a estar bajo el módulo).

## Flujo técnico — switch de módulo

```
ModuleSwitcher (web) / ModuleHeader (mobile)
   │
   │ click / tap
   ▼
selectModule(target)
   │
   │ if disabled or same → no-op
   │ else target.sections[0]?.path ?? target.basePath
   ▼
router.push(target_path)
```

El registro `MODULES` es la única fuente de paths del módulo. Añadir un
módulo nuevo es:

1. Cambiar `enabled: false` a `true` en `MODULES`.
2. Crear `apps/web/app/(app)/<basePath>/...` y
   `apps/mobile/app/(modules)/<basePath>/...`.
3. Rellenar `sections` con sus rutas internas.

No hace falta tocar el switcher ni la sub-nav.

## Archivos clave

- `packages/types/src/models/module.ts` — contrato.
- `packages/types/src/registry/modules.ts` — registro único.
- `apps/web/app/(app)/layout.tsx` — header con switcher + sub-nav.
- `apps/web/components/modules/module-switcher.tsx` — dropdown.
- `apps/web/components/modules/module-sections.tsx` — sub-nav.
- `apps/web/next.config.mjs` — redirects 308 legacy.
- `apps/mobile/app/(modules)/_layout.tsx` — Stack del grupo.
- `apps/mobile/app/(modules)/personal-finance/_layout.tsx` — Stack del módulo.
- `apps/mobile/components/modules/module-header.tsx` — header con bottom sheet.

## Endpoints añadidos

Ninguno. Cambio puramente frontend.

## Migraciones

Ninguna.

## Verificación

- [x] `pnpm typecheck` verde.
- [x] `pnpm lint` verde.
- [x] `pnpm test` verde (UI, services, web).
- [ ] Prueba manual web: navegar a `/dashboard` → 308 → `/personal-finance/dashboard`;
      cambiar de sección desde la sub-nav; abrir el dropdown y comprobar
      que los módulos deshabilitados están correctamente bloqueados.
- [ ] Prueba manual mobile: tap en el header de tabs → bottom sheet con
      los cuatro módulos; los deshabilitados no responden; el activo
      muestra el chip "Activo" implícito (semibold + color primary).

## Decisiones tomadas

- **URLs en inglés** (`/personal-finance/...`) para alinear con el módulo
  backend `personal_finance/` y con la convención del registro.
- **Settings cross-cutting**, no bajo el módulo. Los passkeys y el perfil
  de cuenta no son específicos de finanzas domésticas.
- **Switcher como dropdown** (web) y **bottom sheet** (mobile) en lugar
  de segmented control: con un solo módulo activo el segmented se ve
  raro, y el dropdown deja claro que vendrán más.
- **El registro `MODULES` vive en `@finanzas/types`** porque ya es el
  paquete sin dependencias internas y ambas apps lo consumen. No se
  añadió un paquete `@finanzas/modules` para no inflar la estructura.
- **Redirects 308 (permanent)**: las rutas planas estaban "públicas"
  durante toda la fase 1-5, así que asumimos bookmarks externos. 308
  preserva el método HTTP.

## Limitaciones conocidas

- El root `app/page.tsx` y `app/(app)/home/page.tsx` siguen redirigiendo
  a `/personal-finance/dashboard`. Cuando se añada un selector inicial
  de módulo (ej: el último usado, persistido), tendrán que leer ese
  estado en lugar de hardcodear personal-finance.
- El `ModuleHeader` mobile no informa al lector de pantalla de que es un
  selector — sólo dice "Cambiar módulo". Mejorable con
  `accessibilityState={{ expanded: open }}` cuando se añada un segundo
  módulo activo.
- Los módulos deshabilitados están hardcodeados en el registro. Cuando
  se implemente el primer módulo extra (PHASE-6.X) deberá moverse a
  feature flags si se quiere ramping por usuario.

## Próxima fase

Sin definir aún. Posibles candidatas:

- PHASE-6.2 — settings: avatar dropdown unificado (settings + logout +
  tema).
- PHASE-7.1 — primer módulo nuevo (a decidir: crypto / inversiones).
