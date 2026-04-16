# Testing y calidad de código

## Tabla de contenidos
1. [Estrategia de testing](#estrategia-de-testing)
2. [Tests unitarios con Vitest](#tests-unitarios)
3. [Tests de componentes con Testing Library](#tests-de-componentes)
4. [ESLint — configuración compartida](#eslint)
5. [Prettier](#prettier)
6. [Husky + lint-staged](#husky)
7. [TypeScript estricto](#typescript-estricto)

---

## Estrategia de testing

### Qué testear y dónde

| Capa | Qué testear | Herramienta | Prioridad |
|------|------------|-------------|-----------|
| `packages/utils/` | Funciones puras, formatters, validators | Vitest | Alta |
| `packages/hooks/` | Hooks compartidos | Vitest + renderHook | Alta |
| `packages/ui/` | Render, props, interacciones básicas | Vitest + Testing Library | Media |
| `packages/services/` | Mappers, lógica de queries | Vitest + MSW para mocks | Media |
| `packages/store/` | Acciones de store, estado derivado | Vitest | Media |
| `apps/*/` | Flujos de usuario, integración de pantallas | Testing Library / Maestro | Baja (selectiva) |

### Regla del ROI

No buscar 100% de cobertura. Testear donde el fallo tiene mayor impacto:

1. **Siempre testear:** lógica de negocio, transformaciones de datos, validaciones, hooks compartidos.
2. **Testear selectivamente:** componentes con lógica condicional compleja, flujos críticos (auth, checkout).
3. **No testear:** componentes puramente presentacionales sin lógica, re-exports, configuración estática.

---

## Tests unitarios

### Setup con Vitest

```typescript
// packages/utils/vitest.config.ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
});
```

### Patrón de test para utilidades

```typescript
// packages/utils/src/format-currency.test.ts

import { describe, it, expect } from 'vitest';
import { formatCurrency } from './format-currency';

describe('formatCurrency', () => {
  it('formatea euros con dos decimales', () => {
    expect(formatCurrency(1234.5, 'EUR')).toBe('1.234,50 €');
  });

  it('maneja cero correctamente', () => {
    expect(formatCurrency(0, 'EUR')).toBe('0,00 €');
  });

  it('maneja números negativos', () => {
    expect(formatCurrency(-50.3, 'EUR')).toBe('-50,30 €');
  });

  it('lanza error con moneda no soportada', () => {
    expect(() => formatCurrency(100, 'XYZ' as never)).toThrow();
  });
});
```

### Patrón: Arrange-Act-Assert

```typescript
it('debe calcular el total del carrito con descuento', () => {
  // Arrange
  const items: CartItem[] = [
    { id: '1', name: 'Camiseta', price: 25, quantity: 2 },
    { id: '2', name: 'Pantalón', price: 40, quantity: 1 },
  ];
  const discount = 0.1; // 10%

  // Act
  const total = calculateCartTotal(items, discount);

  // Assert
  expect(total).toBe(81); // (25*2 + 40) * 0.9
});
```

---

## Tests de componentes

### Setup con Testing Library

```typescript
// packages/ui/vitest.config.ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    include: ['src/**/*.test.tsx'],
  },
});
```

```typescript
// packages/ui/src/test-setup.ts
import '@testing-library/jest-dom/vitest';
```

### Patrón de test para componentes

```tsx
// packages/ui/src/components/Button/Button.test.tsx

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react-native';
import { Button } from './Button';

describe('Button', () => {
  it('renderiza el texto children', () => {
    render(<Button onPress={vi.fn()}>Guardar</Button>);
    expect(screen.getByText('Guardar')).toBeTruthy();
  });

  it('ejecuta onPress al presionar', () => {
    const onPress = vi.fn();
    render(<Button onPress={onPress}>Click</Button>);

    fireEvent.press(screen.getByText('Click'));

    expect(onPress).toHaveBeenCalledOnce();
  });

  it('NO ejecuta onPress cuando está disabled', () => {
    const onPress = vi.fn();
    render(<Button onPress={onPress} disabled>Click</Button>);

    fireEvent.press(screen.getByText('Click'));

    expect(onPress).not.toHaveBeenCalled();
  });

  it('muestra spinner cuando loading es true', () => {
    render(<Button onPress={vi.fn()} loading>Guardar</Button>);

    expect(screen.queryByText('Guardar')).toBeNull();
    // ActivityIndicator se renderiza en su lugar
  });

  it('aplica testID para testing automatizado', () => {
    render(<Button onPress={vi.fn()} testID="submit-btn">OK</Button>);
    expect(screen.getByTestId('submit-btn')).toBeTruthy();
  });
});
```

### Reglas de testing de componentes

1. **Testear comportamiento, no implementación.** No testear state interno, refs, o detalles de render.
2. **Usar `testID`** para selectores estables — no depender de texto que cambia con i18n.
3. **No testear estilos** — eso es responsabilidad de QA visual (Storybook, screenshots).
4. **Mockear lo mínimo** — preferir test con datos reales (fixtures) sobre mocks excesivos.

---

## ESLint

### Configuración compartida

```javascript
// tooling/eslint/base.js

/** @type {import('eslint').Linter.Config} */
module.exports = {
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    project: true,
  },
  plugins: ['@typescript-eslint', 'import'],
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/strict-type-checked',
    'plugin:@typescript-eslint/stylistic-type-checked',
    'plugin:import/recommended',
    'plugin:import/typescript',
  ],
  rules: {
    // --- TypeScript estricto ---
    '@typescript-eslint/no-explicit-any': 'error',
    '@typescript-eslint/no-non-null-assertion': 'error',
    '@typescript-eslint/prefer-nullish-coalescing': 'error',
    '@typescript-eslint/no-unnecessary-condition': 'error',
    '@typescript-eslint/strict-boolean-expressions': 'warn',
    '@typescript-eslint/consistent-type-imports': [
      'error',
      { prefer: 'type-imports', fixStyle: 'separate-type-imports' },
    ],

    // --- Imports ---
    'import/order': [
      'error',
      {
        groups: [
          'builtin',
          'external',
          'internal',
          'parent',
          'sibling',
          'index',
          'type',
        ],
        'newlines-between': 'always',
        alphabetize: { order: 'asc', caseInsensitive: true },
      },
    ],
    'import/no-default-export': 'warn',
    'import/no-duplicates': 'error',

    // --- Calidad general ---
    'no-console': ['warn', { allow: ['warn', 'error'] }],
    'prefer-const': 'error',
    'no-var': 'error',
    eqeqeq: ['error', 'always'],
    curly: ['error', 'all'],
  },
  settings: {
    'import/resolver': {
      typescript: {
        project: true,
      },
    },
  },
};
```

### Extensión para React/React Native

```javascript
// tooling/eslint/react.js

/** @type {import('eslint').Linter.Config} */
module.exports = {
  extends: [
    './base.js',
    'plugin:react/recommended',
    'plugin:react/jsx-runtime',
    'plugin:react-hooks/recommended',
  ],
  plugins: ['react', 'react-hooks'],
  rules: {
    'react/prop-types': 'off', // Usamos TypeScript
    'react-hooks/rules-of-hooks': 'error',
    'react-hooks/exhaustive-deps': 'warn',
    'react/self-closing-comp': 'error',
    'react/jsx-no-leaked-render': 'error',
    'react/jsx-curly-brace-presence': ['error', 'never'],

    // Permitir default exports en páginas/layouts (Next.js y Expo Router lo requieren)
    'import/no-default-export': 'off',
  },
  overrides: [
    {
      // Re-activar no-default-export para todo EXCEPTO pages/layouts
      files: ['packages/**/*.{ts,tsx}'],
      rules: {
        'import/no-default-export': 'warn',
      },
    },
  ],
};
```

### Uso por package

```javascript
// packages/ui/.eslintrc.js
module.exports = {
  root: true,
  extends: ['../../tooling/eslint/react.js'],
};
```

---

## Prettier

```jsonc
// .prettierrc (raíz del monorepo)
{
  "semi": true,
  "singleQuote": true,
  "trailingComma": "all",
  "printWidth": 100,
  "tabWidth": 2,
  "bracketSpacing": true,
  "arrowParens": "always",
  "endOfLine": "lf",
  "plugins": ["prettier-plugin-tailwindcss"]
}
```

```
// .prettierignore
node_modules
.next
.expo
dist
build
coverage
*.generated.*
pnpm-lock.yaml
```

---

## Husky + lint-staged

### Instalación y setup

```bash
pnpm add -wD husky lint-staged
pnpm exec husky init
```

### Pre-commit hook

```bash
# .husky/pre-commit
pnpm exec lint-staged
```

### Configuración de lint-staged

```jsonc
// package.json (raíz) — sección lint-staged
{
  "lint-staged": {
    "*.{ts,tsx}": [
      "eslint --fix --max-warnings=0",
      "prettier --write"
    ],
    "*.{json,md,yaml,yml}": [
      "prettier --write"
    ]
  }
}
```

**Regla `--max-warnings=0`**: No permitir warnings acumulados. 
Si el linter avisa, hay que arreglarlo antes de commitear.

---

## TypeScript estricto

### tsconfig base compartido

```jsonc
// tooling/typescript/base.json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "noImplicitOverride": true,
    "forceConsistentCasingInFileNames": true,
    "exactOptionalPropertyTypes": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "module": "ESNext",
    "target": "ES2022",
    "lib": ["ES2022"],
    "jsx": "react-jsx",
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "resolveJsonModule": true
  }
}
```

### Extensión por app

```jsonc
// apps/web/tsconfig.json
{
  "extends": "../../tooling/typescript/base.json",
  "compilerOptions": {
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "plugins": [{ "name": "next" }],
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
```

### Reglas no negociables de TypeScript

1. **`any` es un error de lint**, no un warning. Usar `unknown` + narrowing.
2. **`@ts-ignore` está prohibido.** Si es necesario suprimir, usar `@ts-expect-error` con comentario explicativo.
3. **`as` casting solo en boundaries:** respuestas de APIs externas, deserialización, FFI.
4. **Return types explícitos** en funciones exportadas de packages. No en componentes React (inferencia está bien).

```typescript
// ✅ BIEN — Return type explícito en utilidad pública
export function parseApiDate(raw: string): Date {
  const parsed = new Date(raw);
  if (isNaN(parsed.getTime())) {
    throw new Error(`Invalid date string: ${raw}`);
  }
  return parsed;
}

// ✅ BIEN — Sin return type en componente (inferido como JSX.Element)
export function Avatar({ url, size = 'md' }: AvatarProps) {
  return <Image source={{ uri: url }} className={SIZE_MAP[size]} />;
}
```

5. **Discriminated unions** sobre tipos opcionales para estados mutuamente excluyentes:

```typescript
// ❌ MAL
interface QueryState {
  data?: User;
  error?: Error;
  isLoading: boolean;
}

// ✅ BIEN
type QueryState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: User }
  | { status: 'error'; error: Error };
```
