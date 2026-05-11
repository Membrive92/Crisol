import baseConfig from '@crisol/eslint-config/base.js';

/** @type {import('eslint').Linter.Config[]} */
export default [
  {
    ignores: ['dist/**', '.turbo/**'],
  },
  ...baseConfig,
];
