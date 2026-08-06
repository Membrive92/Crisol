import type { MetricDefinition, MetricResult, ThresholdSpec } from '@crisol/types';

/**
 * Índices de acceso a un `AnalysisRun` (PHASE-44.9).
 *
 * Antes se buscaba con `Array.find` por cada fila. Con 22 filas de un solo año
 * daba igual; con 52 métricas × N ejercicios × 6 pestañas, no. Se construyen una
 * vez por run y se pasan hacia abajo.
 */

/** Clave compuesta de una celda de la matriz. */
function cellKey(metricKey: string, fiscalYear: number): string {
  return `${metricKey}|${fiscalYear}`;
}

export interface MetricIndex {
  /** Un resultado concreto (métrica × ejercicio). */
  get(metricKey: string, fiscalYear: number): MetricResult | undefined;
  /** La serie completa de una métrica, en el orden de `years`. */
  series(metricKey: string): (MetricResult | undefined)[];
  /** Los ejercicios presentes, ascendente. */
  years: number[];
  /** Las claves de métrica presentes, en el orden en que llegaron. */
  keys: string[];
}

export function buildMetricIndex(metrics: MetricResult[], years: number[]): MetricIndex {
  const byCell = new Map<string, MetricResult>();
  const keys: string[] = [];
  const seen = new Set<string>();
  for (const metric of metrics) {
    byCell.set(cellKey(metric.key, metric.fiscal_year), metric);
    if (!seen.has(metric.key)) {
      seen.add(metric.key);
      keys.push(metric.key);
    }
  }
  return {
    get: (metricKey, fiscalYear) => byCell.get(cellKey(metricKey, fiscalYear)),
    series: (metricKey) => years.map((year) => byCell.get(cellKey(metricKey, year))),
    years,
    keys,
  };
}

export interface CatalogIndex {
  definition(metricKey: string): MetricDefinition | undefined;
  /** Las claves de una familia, en el orden del catálogo. */
  byFamily(family: string): MetricDefinition[];
  /** Todas las familias, en el orden en que aparecen. */
  families: string[];
  /** `true` si el catálogo se ha podido cargar. */
  ready: boolean;
}

export function buildCatalogIndex(definitions: MetricDefinition[] | undefined): CatalogIndex {
  const list = definitions ?? [];
  const byKey = new Map(list.map((d) => [d.key, d]));
  const families: string[] = [];
  for (const definition of list) {
    if (!families.includes(definition.family)) families.push(definition.family);
  }
  return {
    definition: (metricKey) => byKey.get(metricKey),
    byFamily: (family) => list.filter((d) => d.family === family),
    families,
    ready: list.length > 0,
  };
}

/**
 * El corte EFECTIVO de una métrica en un run concreto.
 *
 * Prioriza `thresholds_used` (lo que realmente se aplicó) sobre el corte por
 * defecto del catálogo: un `(sector × norma)` puede haberlo sobrescrito, y
 * pintar el del catálogo sería enseñar una vara distinta de la que se usó.
 * En los runs anteriores a PHASE-44.9 no hay nada guardado y se cae al catálogo,
 * cosa que la pantalla declara.
 */
export function effectiveThreshold(
  metricKey: string,
  thresholdsUsed: Record<string, ThresholdSpec> | undefined,
  definition: MetricDefinition | undefined,
): MetricDefinition | undefined {
  const used = thresholdsUsed?.[metricKey];
  if (!used || !definition) return definition;
  return {
    ...definition,
    direction: used.direction,
    low_alarm: used.low_alarm,
    low_ok: used.low_ok,
    high_ok: used.high_ok,
    high_alarm: used.high_alarm,
  };
}
