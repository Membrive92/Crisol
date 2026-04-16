---
name: frontend-best-practices
description: >
  Buenas prácticas de desarrollo frontend para aplicaciones híbridas (web + móvil) 
  basadas en React, React Native, Expo y Next.js en arquitectura monorepo. 
  Usa esta skill SIEMPRE que el usuario pida crear componentes, pantallas, hooks, 
  servicios, módulos o cualquier código frontend para este stack. También cuando 
  pregunte sobre arquitectura de proyecto, estructura de carpetas, patrones de 
  componentes compartidos entre web y móvil, gestión de estado, data fetching, 
  testing, convenciones de código, o configuración de herramientas de calidad 
  (ESLint, Prettier, TypeScript, Husky). Activa esta skill incluso si el usuario 
  no menciona explícitamente "buenas prácticas" — cualquier tarea de código frontend 
  en este stack debe seguir estas guías.
---

# Frontend Best Practices — React / React Native / Expo Monorepo

Esta skill define las reglas, patrones y convenciones para desarrollar el frontend 
de una aplicación híbrida web + móvil con el siguiente stack:

| Capa             | Tecnología                        |
|------------------|-----------------------------------|
| Web              | Next.js (App Router)              |
| Móvil            | Expo (React Native)               |
| Monorepo         | Turborepo + pnpm workspaces       |
| Estilos          | NativeWind / Tailwind CSS         |
| Lenguaje         | TypeScript (modo estricto)        |
| Calidad          | ESLint + Prettier + Husky         |
| Estado           | Zustand + TanStack Query          |
| Navegación       | Expo Router (móvil) + Next.js App Router (web) |

---

## Guía rápida de decisión

Antes de escribir código, consulta esta tabla para saber qué referencia leer:

| Tarea | Referencia |
|-------|------------|
| Crear estructura de proyecto, carpetas, módulos | `references/architecture.md` |
| Crear un componente compartido web/móvil | `references/components.md` |
| Añadir estado global, cache de servidor, fetching | `references/state-and-data.md` |
| Escribir tests, configurar linting, pre-commits | `references/testing-and-quality.md` |

Lee SIEMPRE la referencia relevante antes de generar código.

---

## Principios fundamentales

Estos principios aplican a TODO el código generado, sin excepción:

### 1. TypeScript estricto — sin atajos

```jsonc
// tsconfig.json base
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "forceConsistentCasingInFileNames": true,
    "exactOptionalPropertyTypes": true
  }
}
```

- NUNCA usar `any`. Usar `unknown` y hacer narrowing explícito.
- NUNCA usar `as` para castear tipos salvo en boundaries (ej: respuesta de API externa).
- SIEMPRE tipar props con `interface` para componentes, `type` para uniones/utilidades.
- SIEMPRE exportar los tipos de props junto al componente.

### 2. Convenciones de naming

| Elemento | Convención | Ejemplo |
|----------|------------|---------|
| Componentes | PascalCase | `UserProfileCard.tsx` |
| Hooks | camelCase con prefijo `use` | `useAuthSession.ts` |
| Utilidades/helpers | camelCase | `formatCurrency.ts` |
| Constantes | UPPER_SNAKE_CASE | `API_BASE_URL` |
| Tipos/Interfaces | PascalCase con sufijo descriptivo | `UserProfileProps`, `AuthState` |
| Archivos de test | mismo nombre + `.test.ts(x)` | `UserProfileCard.test.tsx` |
| Directorios | kebab-case | `user-profile/` |
| Feature modules | kebab-case en plural | `packages/features/auth/` |

### 3. Imports — orden obligatorio

Todos los archivos deben seguir este orden de imports, separados por línea en blanco:

```typescript
// 1. Dependencias externas (react, expo, next, librerías)
import { useState } from 'react';
import { View, Text } from 'react-native';

// 2. Packages internos del monorepo (@app/ui, @app/utils, etc.)
import { Button } from '@app/ui';
import { formatDate } from '@app/utils';

// 3. Imports relativos del mismo módulo/feature
import { useUserData } from '../hooks/useUserData';
import { UserAvatar } from './UserAvatar';

// 4. Tipos (con import type cuando sea solo tipo)
import type { UserProfileProps } from './types';
```

### 4. No magic — explícito sobre implícito

- NUNCA hardcodear strings, números o URLs en el código. Usar constantes o config.
- SIEMPRE nombrar las funciones (no arrow functions anónimas) en callbacks complejos.
- SIEMPRE documentar con JSDoc las funciones públicas de los packages compartidos.
- Preferir composición sobre herencia. Preferir hooks sobre HOCs.

### 5. Regla de la barrera de plataforma

El código compartido (`packages/`) NUNCA debe importar directamente de:
- `next/router`, `next/image`, o cualquier API exclusiva de Next.js
- `expo-camera`, `expo-location`, o APIs nativas específicas

Para acceder a funcionalidad específica de plataforma desde código compartido, 
usar el patrón de **inyección por props** o **Platform-specific extensions** 
(`.web.tsx` / `.native.tsx`). Ver `references/components.md` para detalles.

---

## Estructura del monorepo

```
proyecto/
├── apps/
│   ├── web/                    # Next.js App Router
│   │   ├── app/                # Rutas (App Router)
│   │   ├── components/         # Componentes solo-web
│   │   └── lib/                # Utilidades solo-web
│   └── mobile/                 # Expo
│       ├── app/                # Rutas (Expo Router)
│       ├── components/         # Componentes solo-móvil
│       └── lib/                # Utilidades solo-móvil
├── packages/
│   ├── ui/                     # Componentes compartidos
│   │   ├── src/
│   │   │   ├── components/     # Componentes atómicos y moleculares
│   │   │   ├── layouts/        # Layouts reutilizables
│   │   │   └── index.ts        # Barrel export
│   │   └── package.json
│   ├── utils/                  # Helpers, formatters, validators
│   ├── hooks/                  # Hooks compartidos
│   ├── services/               # API clients, servicios externos
│   ├── store/                  # Estado global (Zustand stores)
│   ├── types/                  # Tipos compartidos del dominio
│   └── config/                 # Configuraciones compartidas
│       ├── eslint/
│       ├── typescript/
│       └── tailwind/
├── tooling/
│   ├── eslint/                 # Preset ESLint compartido
│   └── typescript/             # tsconfig base
├── turbo.json
├── pnpm-workspace.yaml
├── .husky/
│   └── pre-commit
└── .prettierrc
```

Para detalles sobre cada directorio y sus reglas, lee `references/architecture.md`.

---

## Checklist antes de entregar código

Antes de dar por terminado cualquier código, verificar:

- [ ] TypeScript compila sin errores con `strict: true`
- [ ] No hay `any`, `as` innecesarios, ni `@ts-ignore`
- [ ] Los imports siguen el orden establecido
- [ ] Los componentes compartidos no importan APIs de plataforma
- [ ] Props tipadas con interface y exportadas
- [ ] Funciones públicas documentadas con JSDoc
- [ ] Nombres siguen las convenciones de naming
- [ ] No hay magic numbers/strings — todo en constantes
- [ ] Componentes siguen el patrón de composición (ver references/components.md)
- [ ] Si hay estado servidor → TanStack Query. Si hay estado cliente → Zustand
