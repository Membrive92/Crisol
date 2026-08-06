# PHASE-0.1 — Bootstrap monorepo

**Estado**: ✅ completada
**Rama**: `feat/phase-0.1-bootstrap-monorepo`
**PR**: (pendiente)
**Fecha de merge**: (pendiente)

## Objetivo

Dejar un monorepo pnpm + Turborepo funcional con dos apps vacías (Next.js y
Expo) arrancando un "hello world", tooling compartido (tsconfig + eslint +
prettier) y CI en GitHub Actions verde.

## Qué se implementó

- Monorepo `pnpm` + `turborepo` con workspaces `apps/*`, `packages/*`, `tooling/*`.
- **`apps/web`** — Next.js 15 (App Router) con una página de bienvenida.
- **`apps/mobile`** — Expo SDK 52 (Expo Router) con una pantalla de bienvenida.
- **`tooling/typescript`** — config compartida (`base.json`, `nextjs.json`,
  `expo.json`) con `strict`, `noUncheckedIndexedAccess`,
  `exactOptionalPropertyTypes`.
- **`tooling/eslint`** — flat config v9 con `typescript-eslint`,
  `eslint-config-prettier`, reglas que prohíben `any` y `require()`.
- `.prettierrc`, `.editorconfig`, `.nvmrc` (Node 20), `.npmrc`.
- **`.github/`** — CI (solo frontend por ahora), validador de título de PR,
  plantilla de PR, dependabot, CODEOWNERS, templates de issue.

## Scripts disponibles en la raíz

```bash
pnpm dev              # web + mobile en paralelo
pnpm dev:web          # solo web (localhost:3000)
pnpm dev:mobile       # solo mobile (Expo DevTools)
pnpm lint             # ESLint en ambas apps
pnpm typecheck        # tsc --noEmit en ambas apps
pnpm test             # stubs (PHASE-1.2 introduce tests reales)
pnpm build            # next build para web
pnpm format           # Prettier
```

## Archivos clave

- [pnpm-workspace.yaml](../../pnpm-workspace.yaml) — define los workspaces.
- [turbo.json](../../turbo.json) — pipeline de Turborepo.
- [tooling/typescript/base.json](../../tooling/typescript/base.json) — reglas TS estrictas.
- [tooling/eslint/base.js](../../tooling/eslint/base.js) — flat config compartido.
- [apps/web/app/page.tsx](../../apps/web/app/page.tsx), [apps/web/app/layout.tsx](../../apps/web/app/layout.tsx) — hello world web.
- `apps/mobile/app/index.tsx` (retirado después, al entrar el enrutado por
  grupos), [apps/mobile/app/_layout.tsx](../../apps/mobile/app/_layout.tsx) —
  hello world mobile.
- [.github/workflows/ci.yml](../../.github/workflows/ci.yml) — CI frontend.

## Verificación

- [x] `pnpm install` limpio (1034 paquetes).
- [x] `pnpm lint` verde.
- [x] `pnpm typecheck` verde.
- [x] `pnpm test` verde (stubs).
- [x] `pnpm --filter @finanzas/web build` verde (Next.js compila y genera páginas estáticas).
- [ ] `pnpm dev:web` manual — arranca en http://localhost:3000.
- [ ] `pnpm dev:mobile` manual — arranca Expo DevTools.
- [ ] CI en GitHub Actions verde tras el push.

## Decisiones tomadas

- **React 18.3** en ambas apps (no 19) para alineamiento con Expo SDK 52.
- **ESLint flat config v9** en lugar de legacy `.eslintrc`.
- **Sin Tailwind / NativeWind** todavía — se introducirá en PHASE-1.2 con la
  primera UI real.
- **Sin `packages/*`** todavía — se crean cuando haya código compartido real.
- **`eslint-config-next` eliminado** — no necesario con nuestro base flat config.
- `.github/` introducida en esta fase (no en 0.0) porque ya hay código que
  testear, evitando un CI fantasma.

## Limitaciones conocidas

- `pnpm test` son stubs (`echo "(no tests yet)"`). Los tests reales llegan
  en PHASE-1.2 junto con la primera UI compartida.
- CI solo ejecuta jobs de frontend. El job de backend (`pytest`, `mypy`) se
  añade en PHASE-0.2.
- Los archivos `babel.config.js` y `metro.config.js` de Expo usan CommonJS
  (requerido por Expo) y llevan un override en su eslint config.

## Próxima fase

PHASE-0.2 — Bootstrap backend (FastAPI + Postgres + Alembic + job de CI backend).
