/**
 * Jest config para la app mobile (PHASE-11.6).
 *
 * Usa el preset oficial `jest-expo`. `transformIgnorePatterns` se
 * extiende para que las rutas reales de pnpm (`node_modules/.pnpm/...`)
 * permitan transformación de los packages RN/Expo y de los workspace
 * `@finanzas/*`. La opción positiva del lookahead es necesaria porque
 * el patrón por defecto sólo permite `node_modules/<pkg>` y pnpm
 * intercala `.pnpm/<pkg>@<ver>/node_modules/<pkg>`.
 */
module.exports = {
  preset: 'jest-expo',
  transformIgnorePatterns: [
    'node_modules/(?!(\\.pnpm/)?(((jest-)?react-native|@react-native(-community)?)|expo(nent)?|@expo(nent)?(-google-fonts)?|react-navigation|@react-navigation|@unimodules|unimodules|sentry-expo|native-base|react-native-svg|@finanzas))',
  ],
  testMatch: ['**/*.test.ts', '**/*.test.tsx'],
};
