import type { MetricResult, MetricUnit } from '@crisol/types';

import { formatMetricValue } from './investment-metric-format';

/**
 * La serie de una métrica reducida a lo que una celda puede dibujar
 * (PHASE-44.24.D).
 *
 * El informe pinta el nivel de cada año y no la DIRECCIÓN: un Z''-Score de 2,6
 * en verde y un Z''-Score de 2,6 que viene de 3,1 → 2,9 → 2,8 cuentan historias
 * distintas, y la tabla las presenta igual.
 *
 * Capa PURA: devuelve puntos normalizados y una etiqueta de texto; quien dibuja
 * es cada app con sus primitivas. La etiqueta la genera esta misma función para
 * que el lector de pantalla oiga lo mismo en las dos.
 */

/** Mínimo de puntos con número para que una línea signifique algo. */
const MIN_POINTS = 3;

/**
 * Cuánto tiene que moverse la serie para llamarla creciente o decreciente.
 *
 * Por debajo de esto es ruido, y decir «descendente» de una serie plana es
 * afirmar una tendencia que no está. El corte es el mismo que usa la escala de
 * variaciones de PHASE-44.22 para su banda neutra.
 */
const FLAT_BAND = 0.02;

export type SparklineTrend = 'up' | 'down' | 'flat';

export interface SparklinePoint {
  /** Posición horizontal en [0,1], por índice en la serie COMPLETA. */
  x: number;
  /** Valor normalizado en [0,1]. Con serie constante, 0,5 — centrada. */
  y: number;
}

export interface Sparkline {
  points: SparklinePoint[];
  trend: SparklineTrend;
  /**
   * La serie leída en voz alta, con su unidad y su tendencia. Un dibujo sin
   * texto alternativo es un dato que sólo existe para quien puede verlo.
   */
  ariaLabel: string;
}

/**
 * La serie de una métrica lista para dibujar, o `null` si no da para una línea.
 *
 * `null` NO significa «no hay datos»: significa que con menos de tres puntos una
 * línea no dice nada. Quien pinta debe decirlo («serie corta») en vez de dejar
 * la celda en blanco, que se lee como «no calculable» — la regla 6 de honestidad.
 */
export function sparklineOf(
  series: readonly (MetricResult | undefined)[],
  unit: MetricUnit | undefined,
  years: readonly number[] = [],
): Sparkline | null {
  const usable: { index: number; value: number }[] = [];
  series.forEach((metric, index) => {
    // Sólo los ejercicios con NÚMERO. Un `not_computable` o un `not_applicable`
    // no se interpola: la línea saltaría ese año como si nada hubiera pasado.
    if (!metric || metric.value === null || metric.value === undefined) return;
    if (metric.status === 'not_computable' || metric.status === 'not_applicable') return;
    const parsed = Number(metric.value);
    if (Number.isFinite(parsed)) usable.push({ index, value: parsed });
  });
  if (usable.length < MIN_POINTS) return null;

  const values = usable.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min;
  const lastIndex = Math.max(series.length - 1, 1);

  const points = usable.map((point) => ({
    x: point.index / lastIndex,
    // Serie constante: la línea va por el medio en vez de dividir por cero.
    y: span === 0 ? 0.5 : (point.value - min) / span,
  }));

  const first = values[0] as number;
  const last = values[values.length - 1] as number;
  const reference = Math.abs(first) || Math.abs(last) || 1;
  const change = (last - first) / reference;
  const trend: SparklineTrend = Math.abs(change) < FLAT_BAND ? 'flat' : change > 0 ? 'up' : 'down';

  return { points, trend, ariaLabel: label(usable, unit, years, trend) };
}

const TREND_WORD: Record<SparklineTrend, string> = {
  up: 'ascendente',
  down: 'descendente',
  flat: 'estable',
};

function label(
  usable: { index: number; value: number }[],
  unit: MetricUnit | undefined,
  years: readonly number[],
  trend: SparklineTrend,
): string {
  const valores = usable.map((p) => formatMetricValue(String(p.value), unit)).join('; ');
  const etiquetados = usable
    .map((p) => years[p.index])
    .filter((year): year is number => year !== undefined);
  // Un rango («2020-2023») sólo es honesto si los ejercicios son CONSECUTIVOS.
  // Con un hueco en medio, nombrar los extremos sugiere una serie continua que
  // no existe — y la línea ya se salta ese año a propósito, así que la etiqueta
  // tiene que decir lo mismo. Con la ventana de 5 ejercicios del informe,
  // enumerarlos cabe de sobra.
  const contiguos =
    etiquetados.length === usable.length &&
    usable.every((p, i) => i === 0 || p.index === (usable[i - 1] as { index: number }).index + 1);
  const rango =
    etiquetados.length === 0
      ? `${usable.length} ejercicios`
      : contiguos
        ? `${etiquetados[0]}-${etiquetados[etiquetados.length - 1]}`
        : etiquetados.join(', ');
  return `serie ${rango}: ${valores} — ${TREND_WORD[trend]}`;
}
