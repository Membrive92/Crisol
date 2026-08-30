import type { MetricUnit, ScoreBreakdown } from '@crisol/types';

import type { ScoreHelpIndex } from './investment-score-help';
import { sparklineOf, type Sparkline } from './investment-sparkline';
import type { MetricIndex } from './investment-metric-index';

/**
 * El desglose de un score forense, listo para pintar (PHASE-44.24.D).
 *
 * Hasta ahora la tarjeta hacía `Object.entries(breakdown.components)` en línea y
 * pintaba el NIVEL de cada variable en el último ejercicio. Un DSRI de 1,08 no
 * dice nada por sí solo; que venga de 0,98 sí — es justo el movimiento que el
 * modelo de Beneish existe para detectar.
 *
 * Capa PURA y COMPARTIDA: la delta y el orden se deciden aquí para que la
 * tarjeta de web y la de móvil no puedan discrepar en qué variable ha empeorado.
 * Las etiquetas llegan **por argumento** (`@crisol/ui` no hace fetching).
 */

/** Cuánto tiene que moverse una variable para no llamarla estable. */
const FLAT_DELTA = 0.005;

export interface ScoreComponentRow {
  key: string;
  /** El nombre humano si el motor lo publica; si no, la clave cruda. */
  label: string;
  /** Qué mide esta variable, de la ficha del engine. */
  help: string | undefined;
  kind: 'component' | 'check';
  /** El valor del ejercicio del veredicto, ya formateado. `—` si falta. */
  value: string;
  /** Sólo en los checks: si el test se cumple. */
  passed: boolean | undefined;
  /**
   * La variación frente al ejercicio anterior, con signo y ya formateada.
   *
   * `null` significa que NO se puede comparar (no hay ejercicio anterior, o su
   * desglose no llegó). No es «no ha cambiado»: eso es `'flat'`.
   */
  delta: string | null;
  direction: 'up' | 'down' | 'flat' | null;
}

export interface ScoreBreakdownView {
  /**
   * La serie del SCORE — no la de sus variables.
   *
   * `null` con menos de tres ejercicios con número: una línea de dos puntos es
   * una recta, y una recta afirma una tendencia que nadie ha medido.
   */
  spark: Sparkline | null;
  rows: ScoreComponentRow[];
}

/**
 * El desglose de un score en el ejercicio del veredicto, con su variación.
 *
 * @param metricKey clave del score (`m_score`, `z_score`, `f_score`, `c_score`).
 * @param breakdowns TODOS los desgloses del run; se filtran aquí por clave.
 * @param year ejercicio del veredicto.
 * @param index el índice de métricas, para la serie del score.
 * @param unit unidad del score, del catálogo — no escrita a mano: si un día un
 *   score se publica en otra unidad, la etiqueta de la serie la seguiría.
 * @param help fichas del engine; sin ellas se pinta la clave cruda.
 */
/**
 * Los scores que NO tienen desglose de variables, por diseño.
 *
 * Son un ratio único o una lectura de otro score, no un agregado: pedirles
 * componentes no tiene sentido. La distinción importa porque la pantalla dice
 * cosas distintas — «no tiene desglose por diseño» frente a «sin desglose para
 * este ejercicio», que suena a dato que falta.
 *
 * Vive aquí y no en cada app porque estaba escrita a mano en las DOS, y las dos
 * se habían quedado sin `FZ_P` a la vez (PHASE-44.25).
 */
export const NO_BREAKDOWN_BY_DESIGN: ReadonlySet<string> = new Set([
  'accruals',
  'F5',
  'F6',
  'FZ',
  'FZ_P',
]);

export function scoreBreakdownRows(
  metricKey: string,
  breakdowns: readonly ScoreBreakdown[] | undefined,
  year: number | undefined,
  index: MetricIndex,
  unit: MetricUnit | undefined,
  help?: ScoreHelpIndex | undefined,
): ScoreBreakdownView {
  const spark = sparklineOf(index.series(metricKey), unit, index.years);
  const mine = (breakdowns ?? []).filter((b) => b.key === metricKey);
  const current = year === undefined ? undefined : mine.find((b) => b.fiscal_year === year);
  if (!current) return { spark, rows: [] };

  // El ejercicio anterior es el mayor de los ANTERIORES presentes, no
  // `year - 1`: una serie con un hueco compararía contra un año que no está.
  const previous = mine
    .filter((b) => b.fiscal_year < current.fiscal_year)
    .sort((a, b) => b.fiscal_year - a.fiscal_year)[0];

  const rows: ScoreComponentRow[] = [];

  for (const [key, raw] of Object.entries(current.components)) {
    const value = Number(raw);
    const before = previous ? Number(previous.components[key]) : Number.NaN;
    const comparable = Number.isFinite(value) && Number.isFinite(before);
    const change = comparable ? value - before : 0;
    rows.push({
      key,
      label: help?.componentLabel(metricKey, key) ?? key,
      help: help?.componentHelp(metricKey, key)?.what,
      kind: 'component',
      value: Number.isFinite(value) ? decimal(value) : '—',
      passed: undefined,
      delta: comparable ? signed(change) : null,
      direction: comparable ? directionOf(change) : null,
    });
  }

  for (const [key, passed] of Object.entries(current.checks)) {
    const before = previous?.checks[key];
    rows.push({
      key,
      label: help?.componentLabel(metricKey, key) ?? key,
      help: help?.componentHelp(metricKey, key)?.what,
      kind: 'check',
      value: passed ? 'sí' : 'no',
      passed,
      // Un check no tiene magnitud: lo que se puede decir es si CAMBIÓ.
      delta: before === undefined ? null : before === passed ? null : passed ? 'nuevo' : 'perdido',
      direction: before === undefined || before === passed ? null : passed ? 'up' : 'down',
    });
  }

  return { spark, rows };
}

function decimal(value: number): string {
  return value.toLocaleString('es-ES', { maximumFractionDigits: 3 });
}

function signed(change: number): string {
  if (Math.abs(change) < FLAT_DELTA) return '=';
  return `${change > 0 ? '+' : '−'}${decimal(Math.abs(change))}`;
}

function directionOf(change: number): 'up' | 'down' | 'flat' {
  if (Math.abs(change) < FLAT_DELTA) return 'flat';
  return change > 0 ? 'up' : 'down';
}
