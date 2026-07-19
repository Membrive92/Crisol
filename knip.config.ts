import type { KnipConfig } from 'knip';

/**
 * Configuración de knip — detector de código muerto del monorepo.
 *
 * knip parte de los entrypoints reales y calcula alcanzabilidad de todo el
 * proyecto. Cubre el punto ciego de `tsc` y ESLint: ambos son de ámbito
 * FICHERO, así que un símbolo `export`ado se considera usado por definición
 * (el compilador no puede saber que ningún módulo lo importa).
 *
 * ────────────────────────────────────────────────────────────────────
 * IMPORTANTE — cada exclusión de aquí abajo existe porque knip NO puede
 * ver el mecanismo que hace vivo al fichero/dependencia. No las quites sin
 * leer el motivo: quitarlas hace que knip reporte código VIVO como muerto.
 * ────────────────────────────────────────────────────────────────────
 */
const config: KnipConfig = {
  workspaces: {
    'apps/web': {
      // Vitest se autodetecta; sin más ajustes.
    },

    'apps/mobile': {
      entry: [
        // Expo Router: las rutas son convención de fichero, nadie las importa.
        'app/**/*.{ts,tsx}',
        // El preset `jest-expo` recoge los tests vía `testMatch` de
        // jest.config.js, no por import → sin esto knip los da por muertos
        // y arrastra consigo @testing-library/react-native y react-test-renderer.
        '**/*.test.{ts,tsx}',
        'jest.config.js',
      ],
      ignoreDependencies: [
        // Target web de Expo (`expo start --web`, app.json → web.bundler=metro).
        // Metro los exige en runtime; no hay import explícito.
        'react-dom',
        'react-native-web',
        // Requerido por Metro/Babel para transformar el bundle.
        '@babel/core',
        // Heurística del plugin Expo de knip: los infiere desde app.json
        // (userInterfaceStyle/updates) aunque no estén ni usados ni instalados.
        'expo-updates',
        'expo-system-ui',
      ],
      ignoreUnresolved: [
        // babel.config.js lo referencia por nombre; llega como transitivo de
        // `expo` (convención de Expo, no se declara en package.json).
        'babel-preset-expo',
      ],
    },

    'packages/store': {
      ignore: [
        // ⚠️ TRAMPA: Metro resuelve `.native.ts` por extensión de plataforma.
        // `currency.ts` importa './storage' y Metro sustituye storage.native.ts
        // en iOS/Android. NADIE lo importa explícitamente → knip lo da por
        // muerto. Borrarlo rompe la persistencia de móvil en silencio.
        'src/*.native.ts',
      ],
      ignoreDependencies: [
        // Sólo lo usa storage.native.ts (ver arriba) → misma causa raíz.
        '@react-native-async-storage/async-storage',
      ],
    },

    'tooling/typescript': {
      // nextjs.json referencia el plugin de tipos de `next`, que vive en
      // apps/web, no aquí. Es un preset de tsconfig, no un paquete con deps.
      ignoreDependencies: ['next'],
    },
  },

  // NOTA: no añadas `ignoreBinaries: ['eslint']`. Si knip reporta eslint como
  // binario no listado, NO es un falso positivo: son los symlinks de
  // `packages/*/node_modules` apuntando a una ruta obsoleta del store `.pnpm`
  // (pasa cuando una dep nueva cambia el hash de resolución de un peer — p. ej.
  // instalar knip mete `jiti`, y eslint pasa de `eslint@9.39.4` a
  // `eslint@9.39.4_jiti@2.7.0`). Se arregla con `pnpm install`, no silenciándolo.
};

export default config;
