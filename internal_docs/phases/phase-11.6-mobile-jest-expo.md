# PHASE-11.6 — Test setup mobile (`jest-expo`)

**Estado**: ✅ completada
**Rama**: `feat/phase-11.6-mobile-jest-expo`
**Fecha de merge**: 2026-05-05

## Objetivo

Heredado del backlog desde PHASE-2.2. Las cuatro fases mobile
recientes (`9.2` análisis, `10.3` papelera, `11.2` currency store
en analysis, `11.3-11.4` toasts en transactions y captura) carecían
de tests UI. Esta fase configura `jest-expo` + Testing Library RN
y añade el primer test smoke (`<Toaster />` mobile) que demuestra
que el setup funciona end-to-end.

No es una fase de cobertura — es la **infra** para cobertura.
Tests para las pantallas existentes son follow-up.

## Qué se implementó

### Dependencias dev nuevas (`apps/mobile/package.json`)

- **`jest-expo@~52.0.6`** — preset oficial de Expo SDK 52. Crítico
  fijar versión que coincida con el SDK; instalar `^55` daba error
  `Object.defineProperty called on non-object` porque la versión
  asume RN ≥0.78 (Expo 55) y la app va con RN 0.76.5 (Expo 52).
- **`@testing-library/react-native@^13.3.3`** — equivalente a
  `@testing-library/react`: `render`, `fireEvent`, `act`,
  queries `getByText` / `getByLabelText`.
- **`react-test-renderer@^18.3.1`** — peer dep necesaria, fijada a
  React 18 (la default `^19` requiere React 19).
- **`@types/jest@^30.0.0`** — globals (`describe`, `it`, `expect`,
  `jest`) sin necesidad de `import { ... } from '@jest/globals'`.

### Config (`apps/mobile/jest.config.js`)

- `preset: 'jest-expo'` — gestiona transform TS/JSX, mocks de
  módulos nativos Expo, setup RN.
- `transformIgnorePatterns` extendido para soportar **rutas
  pnpm**. El patrón estándar de Expo (`node_modules/(?!(jest-)?react-native|...)`)
  no matchea las rutas reales de pnpm
  (`node_modules/.pnpm/<pkg>@<ver>/node_modules/<pkg>/...`). Añadido
  `(\\.pnpm/)?` opcional al lookahead negativo y whitelisteados los
  packages workspace `@finanzas/*`.
- `testMatch: ['**/*.test.ts', '**/*.test.tsx']`.

### Script de tests

`apps/mobile/package.json`: `"test": "jest"` (antes era un dummy
`echo "(no tests yet)"`). Turbo lo coge automáticamente desde
`pnpm test` global.

### ESLint (`apps/mobile/eslint.config.mjs`)

`jest.config.js` añadido al bloque `files: ['babel.config.js',
'metro.config.js']` — usa CommonJS (`module.exports = {...}`) y
necesita el flag `sourceType: 'commonjs'` + globals Node + override
de `no-require-imports`.

### Primer test smoke (`apps/mobile/components/ui/toaster.test.tsx`)

5 tests con Testing Library RN:

- Empty queue → no renderiza nada.
- `toast.success(...)` → mensaje aparece.
- Tap acción → `onPress` se llama y toast se oculta.
- Tap × → toast se oculta.
- `dismissAfterMs` con `jest.useFakeTimers()` → auto-dismiss tras el
  tick configurado.

Mismos casos que el equivalente web (`apps/web/components/ui/toaster.test.tsx`)
— el store es shared, el componente RN merecía smoke local porque
se renderiza con `Pressable` y `View` en lugar de `<button>`/`<div>`.

## Flujo técnico

```
 pnpm test (root)
    │
    ▼ turbo run test
    ├── @finanzas/web    → vitest run    → 23 tests
    └── @finanzas/mobile → jest          → 5 tests (nuevo)
            │
            ▼ jest --config jest.config.js
            ├── preset 'jest-expo' aplica:
            │     babel transform (TS/JSX)
            │     mock RN nativo (BatchedBridge, NativeModules…)
            │     mock módulos Expo (expo-image-picker, etc.)
            ├── transformIgnorePatterns con '(\.pnpm/)?' permite
            │   transformar @react-native/, expo*, @finanzas/*
            └── testMatch = '**/*.test.ts(x)'
```

## Archivos clave

- `apps/mobile/package.json` (4 devDeps + script `test: jest`)
- `apps/mobile/jest.config.js` (nuevo, preset + transform pnpm-aware)
- `apps/mobile/eslint.config.mjs` (jest.config.js → bloque CommonJS)
- `apps/mobile/components/ui/toaster.test.tsx` (nuevo, 5 tests smoke)

## Endpoints

Ninguno.

## Migraciones

Ninguna.

## Verificación

- [x] `pnpm --filter @finanzas/mobile typecheck` verde.
- [x] `pnpm --filter @finanzas/mobile lint` verde.
- [x] `pnpm --filter @finanzas/mobile test` — 5/5 nuevos.
- [x] `pnpm test` global — 5 mobile + 23 web = 28 tests, sin
      regresiones.

## Decisiones tomadas

- **`jest-expo@~52.0.6` (no `^55`)**. Versión que coincide con
  Expo SDK 52 y RN 0.76. Las versiones más nuevas asumen RN ≥0.78
  y rompen con `Object.defineProperty called on non-object` al
  cargar el setup mock.
- **`react-test-renderer@^18.3.1` fijado**. La default `^19`
  requiere React 19; la app está en React 18.3.1.
- **Transform pattern con `(\\.pnpm/)?` opcional**. Sin esto, jest
  ignora todos los packages porque pnpm intercala `.pnpm/...` en
  las rutas y el lookahead negativo no whitelistea nada. Añadirlo
  como segmento opcional cubre tanto pnpm como npm/yarn flat
  layouts (por compatibilidad si alguien clona el repo y usa otro
  package manager).
- **No usar `@jest/globals` import explícito**. `@types/jest`
  expone globals (`describe`, `it`, `expect`, `jest`) — el import
  añade un re-export y el módulo no resolvía por la peer dep no
  cuadrada con React 18. Usar globals es el patrón estándar Jest.
- **Sólo el Toaster como primer test**. Mismo razonamiento que
  PHASE-11.3 web: cubre el flujo UI del componente RN específico
  (Pressable, accessibilityLabel, native styling); el store ya
  está cubierto en el equivalente web. No saturamos esta fase con
  cobertura — la infra es lo que habilita la cobertura futura.
- **`act` envuelve los `toast.show` en tests**. Las
  actualizaciones del store provocan re-render del Toaster y
  Testing Library RN avisa si no van dentro de `act`. Patrón
  idéntico al web.

## Limitaciones conocidas

- **Cobertura UI mobile sigue siendo mínima** (1 componente). Las
  pantallas (`analysis`, `transactions`, `trash`, `receipt/new`)
  no están testeadas todavía. Con el setup en marcha cada feature
  futuro puede añadir su test sin re-pelear con la config.
- **Sin tests de hooks shared en mobile**. Ya están cubiertos en
  web (vitest) — la duplicación tendría coste alto y aporte bajo.
  Si en el futuro un hook tiene comportamiento RN-específico,
  testearlo aquí.
- **`jest-expo` preset version pinned al SDK actual**. Cuando se
  actualice Expo (53/54/55) hay que bumpar `jest-expo` y
  `react-native` en el mismo PR; saltar uno solo rompe.
- **Patrón `transformIgnorePatterns` es frágil**. Si llega un
  package RN/Expo nuevo que no esté en el whitelist, el test que
  lo importe fallará con "SyntaxError: Unexpected identifier".
  Diagnóstico simple y arreglo trivial (añadir al regex).

## Próxima fase

PHASE-12 — Modelo de presupuestos por categoría con alertas.
Primera feature analítica además del dashboard read-only:
backend (modelo + endpoints + agregaciones), web + mobile
(pantallas y componentes), tests (con la infra mobile ya en su
sitio).
