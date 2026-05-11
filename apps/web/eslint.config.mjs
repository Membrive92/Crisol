import baseConfig from '@crisol/eslint-config/base.js';

/** @type {import('eslint').Linter.Config[]} */
export default [
  {
    ignores: ['next-env.d.ts', '.next/**'],
  },
  ...baseConfig,
  {
    languageOptions: {
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
  },
];
