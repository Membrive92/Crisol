/**
 * Design tokens compartidos entre web y mobile.
 *
 * Son valores primitivos (colores, espaciados, tipografía). Los componentes
 * reales viven en cada app (`apps/*\/components/`) porque el repo aún no
 * tiene NativeWind/Tailwind — ver `internal_docs/decisions/0001-ui-tokens-only.md`.
 */

export const colors = {
  primary: '#1976d2',
  primaryDark: '#115293',
  danger: '#d32f2f',
  success: '#2e7d32',
  warning: '#ed6c02',
  text: '#1f1f1f',
  textMuted: '#666666',
  textSubtle: '#8a8a8a',
  border: '#e0e0e0',
  borderStrong: '#bdbdbd',
  surface: '#ffffff',
  surfaceMuted: '#f5f5f5',
  background: '#fafafa',
  income: '#2e7d32',
  expense: '#d32f2f',
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const;

export const radius = {
  sm: 4,
  md: 8,
  lg: 12,
} as const;

export const fontSize = {
  xs: 12,
  sm: 14,
  md: 16,
  lg: 18,
  xl: 24,
  xxl: 32,
} as const;

export const fontWeight = {
  regular: '400',
  medium: '500',
  semibold: '600',
  bold: '700',
} as const;

export type ColorToken = keyof typeof colors;
export type SpacingToken = keyof typeof spacing;
