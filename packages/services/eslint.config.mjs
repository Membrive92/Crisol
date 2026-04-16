import baseConfig from '@finanzas/eslint-config/base.js';

/** @type {import('eslint').Linter.Config[]} */
export default [
  {
    ignores: ['dist/**', '.turbo/**'],
  },
  ...baseConfig,
];
