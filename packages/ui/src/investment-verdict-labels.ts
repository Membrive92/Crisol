import type {
  CanonicalItemDefinition,
  DividendVerdict,
  FinancialStatement,
  SafetyLabel,
  SafetyProfile,
} from '@crisol/types';

import { colors } from './tokens';

/**
 * Las etiquetas y las reglas del veredicto, en un solo sitio (PHASE-44.24.E).
 *
 * `SAFETY` estaba **duplicada** en `analysis-hero.tsx` y `tab-verdict.tsx`, y
 * las cinco reglas del perfil Conservador vivían escritas a mano en la segunda.
 * Copiarlas a móvil habría hecho cuatro copias de una lista que describe lo que
 * hace `_safety_profile` en el motor: en cuanto el motor añada una condición,
 * las cuatro mienten a la vez y ninguna avisa.
 */

export interface SafetyTone {
  label: string;
  fg: string;
  bg: string;
}

export const SAFETY: Record<SafetyLabel, SafetyTone> = {
  conservative: { label: 'Conservador', fg: colors.success, bg: colors.successSoft },
  watch: { label: 'Vigilar', fg: colors.warning, bg: colors.warningSoft },
  avoid: { label: 'Evitar', fg: colors.danger, bg: colors.dangerSoft },
};

export const DIVIDEND: Record<DividendVerdict, string> = {
  healthy: 'Dividendo sano',
  caution: 'Dividendo a vigilar',
  stressed: 'Dividendo en riesgo',
  not_applicable: 'Sin dividendo relevante',
};

/**
 * Las cinco condiciones que exige el perfil Conservador, tal y como las evalúa
 * `_safety_profile` en el motor. Se imprimen SIEMPRE, cumplidas o no: un sello
 * sin sus reglas no es auditable.
 */
export const CONSERVATIVE_RULES: readonly string[] = [
  'M-Score en verde',
  "Z''-Score en verde",
  'X-Score en verde',
  'F-Score ≥ 7',
  'Accruals en verde',
];

/** Las cuatro condiciones que fuerzan «Evitar». */
export const AVOID_RULES: readonly string[] = [
  'M-Score y accruals ambos en rojo (manipulación probable)',
  "Z''-Score en rojo (riesgo de insolvencia)",
  'X-Score en rojo (riesgo de quiebra)',
  'dividendo financiado con deuda o emisión',
];

export interface SafetyRule {
  text: string;
  /** Si la condición se cumple en ESTE análisis. */
  met: boolean;
}

export interface SafetyChecklist {
  /** Las cuatro que fuerzan «Evitar». Cumplirlas es la mala noticia. */
  avoid: { title: string; metIsBad: true; rules: SafetyRule[] };
  /** Las cinco que exige «Conservador». */
  conservative: { title: string; metIsBad: false; rules: SafetyRule[] };
  /** Lo que el motor da como motivo, tal cual. Vacío si no bloquea nada. */
  blocking: readonly string[];
  /** El rótulo del bloque de motivos, según el perfil. */
  blockingLabel: string;
}

/**
 * El perfil de seguridad convertido en dos listas auditables.
 *
 * @param profile el `safety_profile` del run.
 */
export function safetyRules(profile: SafetyProfile): SafetyChecklist {
  const blocking = profile.blocking_reasons ?? [];
  return {
    avoid: {
      title: 'Se evita si se cumple CUALQUIERA de estas',
      metIsBad: true,
      rules: AVOID_RULES.map((text) => ({ text, met: blocking.includes(text) })),
    },
    conservative: {
      title: 'Es conservador sólo si se cumplen LAS CINCO',
      metIsBad: false,
      rules: CONSERVATIVE_RULES.map((text) => ({
        text,
        // `blocking_reasons` de un perfil «watch» lista lo que NO se cumple,
        // con el texto en negativo («M-Score no está en verde»).
        met:
          profile.label === 'conservative'
            ? true
            : !blocking.some((reason) => isNegationOf(reason, text)),
      })),
    },
    blocking,
    blockingLabel: profile.label === 'avoid' ? 'Motivos: ' : 'Falta para Conservador: ',
  };
}

function isNegationOf(reason: string, rule: string): boolean {
  const head = rule.split(' ')[0] ?? '';
  return head.length > 0 && reason.startsWith(head);
}

/**
 * Las 10 partidas núcleo con las que el motor calcula la completitud.
 *
 * Compartida (PHASE-44.24.E) porque las dos apps enseñan qué falta, y una copia
 * por app haría que una dijera «9 de 10» y la otra «10 de 10» sobre el mismo
 * análisis.
 */
export const CORE_ITEMS = [
  'revenue',
  'ebit',
  'net_income',
  'cfo',
  'capex',
  'dividends_paid',
  'total_assets',
  'equity',
  'current_assets',
  'current_liabilities',
] as const;

export type CoreItemKey = (typeof CORE_ITEMS)[number];

export interface CoreCoverageRow {
  key: CoreItemKey;
  /** Etiqueta humana si el catálogo ha cargado; si no, la clave del motor. */
  label: string;
  /** Un `true` por ejercicio, en el orden de `years`. */
  present: boolean[];
}

export interface CoreCoverage {
  years: number[];
  rows: CoreCoverageRow[];
  /**
   * `true` si los ejercicios en pantalla no son los que el análisis juzgó.
   *
   * Pasa cuando se reingiere DESPUÉS de analizar: la tabla enseñaría una
   * cobertura que no es la que produjo el veredicto.
   */
  mismatch: boolean;
}

/**
 * Qué partidas núcleo publicó el filing en cada ejercicio.
 *
 * @param statements los estados ingeridos; vacío o ausente devuelve 0 filas.
 * @param items el catálogo de partidas, para las etiquetas.
 * @param yearsCovered los ejercicios que juzgó el análisis, para el descuadre.
 */
export function coreItemCoverage(
  statements: readonly FinancialStatement[] | undefined,
  items: readonly CanonicalItemDefinition[] | undefined,
  yearsCovered: readonly number[],
): CoreCoverage {
  const list = statements ?? [];
  const years = list.map((statement) => statement.fiscal_year);
  const labelOf = (key: string) => items?.find((item) => item.key === key)?.label ?? key;
  return {
    years,
    rows:
      list.length === 0
        ? []
        : CORE_ITEMS.map((key) => ({
            key,
            label: labelOf(key),
            // `null` es ausente en el filing. Un cero SÍ es un dato publicado
            // —una empresa que no reparte declara dividendo cero—, así que
            // comparar por verdad haría desaparecer partidas que sí están.
            present: list.map((statement) => statement[key] !== null),
          })),
    mismatch:
      years.length > 0 && years.join(',') !== [...yearsCovered].sort((a, b) => a - b).join(','),
  };
}
