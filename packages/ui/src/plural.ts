/**
 * Seam de internacionalización para la pluralización (AUDIT-2026-05).
 *
 * El producto es monolingüe (es-ES) hoy, así que NO extraemos cada
 * string a catálogos; pero centralizamos la decisión singular/plural en
 * un único helper para no repetir el ternario `n === 1 ? 'x' : 'xs'` por
 * toda la UI. Cuando se añada un segundo idioma, este es el punto de
 * enganche (cambiar el locale + alimentar catálogos), no decenas de
 * ternarios dispersos.
 *
 * Usa `Intl.PluralRules` cuando está disponible (web + Hermes con la
 * variante Intl) y cae a la regla simple de español (uno → singular) si
 * el runtime no lo expone — así nunca rompe en React Native.
 */

let _rules: Intl.PluralRules | null = null;
try {
  // `Intl` o `Intl.PluralRules` pueden faltar en algunos runtimes RN.
  _rules = typeof Intl !== 'undefined' ? new Intl.PluralRules('es-ES') : null;
} catch {
  _rules = null;
}

function category(count: number): Intl.LDMLPluralRule {
  const n = Math.abs(count);
  if (_rules) return _rules.select(n);
  return n === 1 ? 'one' : 'other';
}

/**
 * Devuelve `singular` o `plural` según `count` (regla del locale).
 * No incluye el número — usa `withCount` si lo necesitas pegado.
 *
 * @example pluralize(1, 'par enlazado', 'pares enlazados') // 'par enlazado'
 */
export function pluralize(count: number, singular: string, plural: string): string {
  return category(count) === 'one' ? singular : plural;
}

/**
 * `pluralize` con el número prefijado: `withCount(2, 'gasto', 'gastos')`
 * → `'2 gastos'`.
 */
export function withCount(count: number, singular: string, plural: string): string {
  return `${count} ${pluralize(count, singular, plural)}`;
}
