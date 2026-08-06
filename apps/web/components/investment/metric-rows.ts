import type { MetricDefinition, MetricResult, ThresholdSpec } from '@crisol/types';

import { bandColors } from './band-chip';
import { formatMetricValue, formatThreshold } from './metric-format';
import { effectiveThreshold, type CatalogIndex, type MetricIndex } from './metric-index';
import type { MatrixCell, MatrixRow } from './year-matrix';

/**
 * Construcción de filas de matriz a partir de métricas del engine.
 *
 * Concentra las **seis reglas de honestidad** de la pantalla, para que las
 * cuatro pestañas que pintan métricas no puedan divergir:
 *
 * 1. Una métrica `not_computable` muestra su razón VISIBLE, no escondida en un
 *    `title=`.
 * 2. Una banda `null` sale gris con «sin banda», nunca verde.
 * 3. `approximation` se marca (input degradado, típicamente sin ejercicio t−1).
 * 4. Una procedencia distinta de `sourced` se marca con un punto.
 * 5. El corte aplicado se enseña al lado, tomado de `thresholds_used` cuando
 *    existe — la vara con la que se midió, no la del catálogo.
 * 6. Lo que no se calcula se lista en gris con motivo; nunca se omite.
 */

/** Marca de procedencia. Una partida `sourced` no lleva marca: es lo normal. */
const PROVENANCE_MARK: Record<string, string> = {
  derived: '†',
  imputed_zero: '·',
  estimated: '≈',
};

const PROVENANCE_TITLE: Record<string, string> = {
  derived: 'derivada de otras partidas con una identidad contable',
  imputed_zero: 'cero imputado: el filing no publica el concepto',
  estimated: 'proxy estimado, no un dato publicado',
};

export function metricCell(
  metric: MetricResult | undefined,
  definition: MetricDefinition | undefined,
): MatrixCell {
  if (!metric || metric.status === 'not_computable') {
    return {
      text: '—',
      color: undefined,
      title: metric?.reason ?? 'no se calculó en este ejercicio',
    };
  }
  const { fg, bg } = bandColors(metric.band);
  const marks: string[] = [];
  const titles: string[] = [];
  if (metric.status === 'approximation') {
    marks.push('*');
    titles.push(metric.reason ?? 'calculada con un input degradado');
  }
  const provenanceMark = PROVENANCE_MARK[metric.provenance];
  if (provenanceMark) {
    marks.push(provenanceMark);
    const title = PROVENANCE_TITLE[metric.provenance];
    if (title) titles.push(title);
  }
  return {
    text: formatMetricValue(metric.value, definition?.unit),
    // Sin banda no se colorea el texto: gris es «no hay vara», no «va bien».
    color: metric.band ? fg : undefined,
    background: metric.band ? bg : undefined,
    title: titles.join('; ') || undefined,
    mark: marks.join('') || undefined,
  };
}

export interface MetricRowOptions {
  index: MetricIndex;
  catalog: CatalogIndex;
  thresholdsUsed: Record<string, ThresholdSpec> | undefined;
}

/** Una fila de la matriz para una métrica, con su corte y su motivo. */
export function metricRow(metricKey: string, options: MetricRowOptions): MatrixRow {
  const { index, catalog, thresholdsUsed } = options;
  const base = catalog.definition(metricKey);
  const definition = effectiveThreshold(metricKey, thresholdsUsed, base);
  const series = index.series(metricKey);

  const threshold = formatThreshold(definition);
  const allMissing = series.every((m) => !m || m.status === 'not_computable');
  const firstReason = series.find((m) => m?.status === 'not_computable')?.reason ?? null;

  const hint = allMissing
    ? (firstReason ?? 'no calculable con los datos disponibles')
    : (threshold ?? 'sin banda absoluta: se juzga por deriva o por sector');

  return {
    key: metricKey,
    label: base?.label ?? metricKey,
    hint,
    cells: series.map((metric) => metricCell(metric, definition)),
  };
}

/** Cabecera de bloque dentro de la matriz. */
export function groupRow(key: string, label: string): MatrixRow {
  return { key, label, isGroup: true, cells: [] };
}

/**
 * Fila para una métrica que el cuaderno del usuario pide y el motor NO calcula.
 *
 * Se lista en gris con el motivo en vez de omitirse: un hueco silencioso se lee
 * como «no aplica», y lo que pasa es que no existe.
 */
export function missingRow(key: string, label: string, reason: string, years: number[]): MatrixRow {
  return {
    key,
    label,
    hint: reason,
    cells: years.map(() => ({ text: '—', title: reason })),
  };
}
