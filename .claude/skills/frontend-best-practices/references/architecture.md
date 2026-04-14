# Arquitectura y estructura del monorepo

## Tabla de contenidos
1. [Configuración del monorepo](#configuración-del-monorepo)
2. [Reglas por directorio](#reglas-por-directorio)
3. [Gestión de dependencias](#gestión-de-dependencias)
4. [Feature modules](#feature-modules)
5. [Barrel exports](#barrel-exports)
6. [Alias de importación](#alias-de-importación)

---

## Configuración del monorepo

### pnpm-workspace.yaml

```yaml
packages:
  - 'apps/*'
  - 'packages/*'
  - 'tooling/*'
```

### turbo.json

```jsonc
{
  "$schema": "https://turborepo.com/schema.json",
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": ["dist/**", ".next/**", ".expo/**"]
    },
    "dev": {
      "persistent": true,
      "cache": false
    },
    "lint": {
      "dependsOn": ["^lint"]
    },
    "typecheck": {
      "dependsOn": ["^typecheck"]
    },
    "test": {
      "dependsOn": ["^build"]
    }
  }
}
```

### Scripts raíz (package.json)

```jsonc
{
  "scripts": {
    "dev": "turbo dev",
    "dev:web": "turbo dev --filter=web",
    "dev:mobile": "turbo dev --filter=mobile",
    "build": "turbo build",
    "lint": "turbo lint",
    "typecheck": "turbo typecheck",
    "test": "turbo test",
    "format": "prettier --write .",
    "prepare": "husky"
  }
}
```

---

## Reglas por directorio

### `apps/web/` — Next.js

- Usa App Router exclusivamente (no Pages Router).
- Cada ruta es un directorio con `page.tsx`, `layout.tsx`, `loading.tsx`, `error.tsx`.
- Los componentes específicos de una ruta van en una carpeta `_components/` dentro de la ruta.
- `components/` raíz solo para componentes web-only reutilizables (ej: `<Head>`, wrappers de Next.js).
- NUNCA poner lógica de negocio aquí — va en `packages/`.

```
apps/web/app/
├── (auth)/
│   ├── login/
│   │   ├── page.tsx
│   │   └── _components/
│   │       └── LoginForm.tsx    # Compone UI compartida + lógica web
│   └── register/
│       └── page.tsx
├── (dashboard)/
│   ├── layout.tsx               # Layout compartido del dashboard
│   └── home/
│       └── page.tsx
├── layout.tsx                   # Root layout
└── globals.css
```

### `apps/mobile/` — Expo

- Usa Expo Router (file-based routing).
- Misma convención de `_components/` por pantalla para componentes locales.
- `components/` raíz solo para wrappers nativos (ej: `<SafeAreaWrapper>`).
- NUNCA poner lógica de negocio aquí — va en `packages/`.

```
apps/mobile/app/
├── (auth)/
│   ├── login.tsx
│   └── register.tsx
├── (tabs)/
│   ├── _layout.tsx              # Tab navigator
│   ├── home.tsx
│   └── profile.tsx
├── _layout.tsx                  # Root layout
└── +not-found.tsx
```

### `packages/ui/` — Componentes compartidos

Organización atómica simplificada (no Atomic Design completo):

```
packages/ui/src/
├── components/
│   ├── Button/
│   │   ├── Button.tsx           # Implementación
│   │   ├── Button.test.tsx      # Tests
│   │   ├── types.ts             # Props interface
│   │   └── index.ts             # Re-export
│   ├── Input/
│   ├── Card/
│   └── Avatar/
├── layouts/
│   ├── ScreenContainer/
│   └── Section/
├── primitives/
│   ├── Text/                    # Wrapper tipográfico cross-platform
│   ├── Box/                     # View/div abstracto
│   └── Pressable/               # TouchableOpacity/button abstracto
└── index.ts                     # Barrel export público
```

Reglas de `packages/ui/`:
- Cada componente en su propia carpeta con index.ts, types.ts y test.
- Los componentes SOLO reciben datos por props — no acceden a stores ni servicios.
- Si necesitan datos, reciben callbacks: `onPress`, `onSubmit`, `onChange`.
- Documentar TODAS las props con JSDoc.

### `packages/hooks/` — Hooks compartidos

```
packages/hooks/src/
├── useDebounce.ts
├── useMediaQuery.ts
├── useToggle.ts
├── useLocalStorage.ts
└── index.ts
```

Reglas:
- Hooks genéricos y reutilizables. Sin lógica de negocio específica.
- Hooks de dominio/negocio van en `packages/services/` o `packages/store/`.

### `packages/services/` — API y servicios

```
packages/services/src/
├── api/
│   ├── client.ts                # Instancia base (fetch/axios configurado)
│   ├── interceptors.ts          # Auth headers, refresh token, error handling
│   └── endpoints/
│       ├── auth.ts              # login(), register(), logout()
│       ├── users.ts             # getUser(), updateProfile()
│       └── index.ts
├── queries/                     # TanStack Query hooks
│   ├── useUserQuery.ts
│   ├── useAuthMutation.ts
│   └── queryKeys.ts             # Centralización de query keys
└── index.ts
```

### `packages/types/` — Tipos del dominio

```
packages/types/src/
├── models/
│   ├── user.ts                  # User, UserProfile, UserRole
│   ├── auth.ts                  # AuthSession, LoginCredentials
│   └── common.ts                # Pagination, ApiResponse<T>, ApiError
├── dto/                         # Data Transfer Objects (request/response shapes)
│   ├── auth.dto.ts
│   └── user.dto.ts
└── index.ts
```

Reglas:
- Separar modelos de dominio de DTOs de API.
- NUNCA acoplar tipos del frontend a la estructura exacta de la API.
- Usar funciones mapper en `packages/services/` para transformar DTO → Model.

---

## Gestión de dependencias

### Regla de dependencias internas

Las dependencias entre packages siguen una jerarquía estricta:

```
types  →  (sin dependencias internas)
utils  →  types
hooks  →  types, utils
store  →  types, utils, services
services → types, utils
ui     →  types, utils, hooks (NUNCA services ni store)
apps/* →  puede importar cualquier package
```

- NUNCA crear dependencias circulares entre packages.
- `packages/ui/` es "tonto" — no sabe de dónde vienen los datos.

### Dependencias externas

- Las dependencias compartidas (react, react-native, typescript) se declaran 
  en el `package.json` raíz.
- Las dependencias específicas de un package se declaran en su propio `package.json`.
- Usar `pnpm add -w` para dependencias raíz.
- Usar `pnpm add --filter=<package>` para dependencias específicas.
- SIEMPRE fijar versiones exactas en packages compartidos para evitar duplicados.

---

## Feature modules

Para features complejas que agrupen múltiples concerns, usar feature modules:

```
packages/features/
├── auth/
│   ├── components/              # Componentes del feature (LoginForm, etc.)
│   ├── hooks/                   # useLogin, useRegister
│   ├── services/                # API calls específicas
│   ├── store/                   # Estado específico del feature
│   ├── types.ts
│   └── index.ts                 # API pública del feature
└── checkout/
    ├── components/
    ├── hooks/
    ├── services/
    ├── store/
    ├── types.ts
    └── index.ts
```

Reglas de feature modules:
- Un feature module SOLO exporta lo que necesitan otros módulos a través de `index.ts`.
- Los imports internos del feature usan rutas relativas.
- Otros features NUNCA importan archivos internos — solo el barrel export.

---

## Barrel exports

Cada package expone una API pública limpia:

```typescript
// packages/ui/src/index.ts — BIEN
export { Button } from './components/Button';
export { Input } from './components/Input';
export type { ButtonProps } from './components/Button/types';
export type { InputProps } from './components/Input/types';

// NUNCA exportar todo con wildcard
// export * from './components'; ← PROHIBIDO
```

Reglas:
- Barrel exports explícitos — listar cada export.
- No re-exportar internals (helpers privados, constantes internas).
- Exportar tipos con `export type` para tree-shaking.

---

## Alias de importación

Configurar path aliases en el `tsconfig.json` base:

```jsonc
{
  "compilerOptions": {
    "paths": {
      "@app/ui": ["../../packages/ui/src"],
      "@app/utils": ["../../packages/utils/src"],
      "@app/hooks": ["../../packages/hooks/src"],
      "@app/services": ["../../packages/services/src"],
      "@app/store": ["../../packages/store/src"],
      "@app/types": ["../../packages/types/src"]
    }
  }
}
```

En la práctica con pnpm workspaces, los packages se referencian por nombre 
en `package.json` y TypeScript resuelve via `exports` field o `main`/`types`:

```jsonc
// packages/ui/package.json
{
  "name": "@app/ui",
  "main": "./src/index.ts",
  "types": "./src/index.ts",
  "exports": {
    ".": "./src/index.ts"
  }
}
```
