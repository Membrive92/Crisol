/**
 * Design tokens compartidos entre web y mobile.
 *
 * Son valores primitivos (colores, espaciados, tipografía). Los componentes
 * reales viven en cada app (`apps/*\/components/`) porque el repo aún no
 * tiene NativeWind/Tailwind — ver `internal_docs/decisions/0001-ui-tokens-only.md`.
 *
 * En web los colores se emiten como `var(--color-…, fallback)` para que un
 * tema claro/oscuro pueda redefinirlos vía CSS sin tocar componentes. En
 * React Native (Hermes/JSC) no se interpreta `var()`, así que se devuelven
 * los literales y mobile sigue con tema único hasta que se añada su propio
 * mecanismo. Detección por `navigator.product === 'ReactNative'`, que es
 * `false` también durante el SSR de Next (no hay `navigator`), así que
 * cliente y servidor emiten lo mismo y no hay mismatch de hidratación.
 */

const isReactNative =
  typeof navigator !== 'undefined' &&
  (navigator as { product?: string }).product === 'ReactNative';

function color(varName: string, fallback: string): string {
  return isReactNative ? fallback : `var(--color-${varName}, ${fallback})`;
}

export const colors = {
  // PHASE-29: copper brand. Fallbacks usados por RN (que no parsea var()).
  primary: color('primary', '#c4671f'),
  primaryDark: color('primary-dark', '#8b461a'),
  // Color de texto/icono sobre fondo `primary`. Blanco cálido para AA
  // sobre copper (era #f7f9fc — frío y restaba contraste sobre naranja).
  onPrimary: color('on-primary', '#fff8f0'),
  // Versión "soft" del primario para fondos tonales (badges, hovers, chips
  // suaves) — ya tintada por tema, no se aplica vía rgba en runtime.
  primarySoft: color('primary-soft', '#fdf0e6'),
  danger: color('danger', '#d32f2f'),
  // `dangerSoft` / `successSoft` / `warningSoft` son los fondos tonales
  // semánticos. Cada tema define su propio valor para que los badges no
  // queden pastel claros sobre fondo oscuro (mismo principio que primarySoft).
  dangerSoft: color('danger-soft', '#fdecea'),
  success: color('success', '#2e7d32'),
  successSoft: color('success-soft', '#e8f5e9'),
  warning: color('warning', '#ed6c02'),
  warningSoft: color('warning-soft', '#fff4e5'),
  text: color('text', '#1f1f1f'),
  textMuted: color('text-muted', '#666666'),
  // #767676 sobre blanco da 4.54:1 (AA para texto normal). El #8a8a8a
  // anterior fallaba AA (2.97:1) — AUDIT-2026-05.
  textSubtle: color('text-subtle', '#767676'),
  border: color('border', '#e0e0e0'),
  borderStrong: color('border-strong', '#bdbdbd'),
  surface: color('surface', '#ffffff'),
  surfaceMuted: color('surface-muted', '#f5f5f5'),
  background: color('background', '#fafafa'),
  income: color('income', '#2e7d32'),
  expense: color('expense', '#d32f2f'),
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
