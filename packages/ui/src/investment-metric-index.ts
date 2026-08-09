import type { MetricDefinition, MetricResult, ThresholdSpec } from '@crisol/types';

/**
 * Índices de acceso a un `AnalysisRun` (PHASE-44.9).
 *
 * Antes se buscaba con `Array.find` por cada fila. Con 22 filas de un solo año
 * daba igual; con 52 métricas × N ejercicios × 7 pestañas, no. Se construyen una
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

/**
 * Todas las métricas de un run, de sus cuatro bloques.
 *
 * Se comparte porque olvidar un bloque no falla: las filas de ese bloque salen
 * como huecos («—»), que es indistinguible de «el motor no lo pudo calcular».
 * Con una sola implementación, web y móvil indexan lo mismo o no indexa ninguno.
 */
export function collectRunMetrics(run: {
  scores_detail: { base_ratios: { metrics: MetricResult[] }; forensic: { metrics: MetricResult[] } };
  evolution: { metrics: MetricResult[] };
  dividend_analysis: { metrics: MetricResult[] };
}): MetricResult[] {
  return [
    ...run.scores_detail.base_ratios.metrics,
    ...run.scores_detail.forensic.metrics,
    ...run.evolution.metrics,
    ...run.dividend_analysis.metrics,
  ];
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
 * El corte de una métrica más lo que hace falta para leerlo con honestidad.
 *
 * `applies` no está en `MetricDefinition` a propósito: el catálogo del motor no
 * conoce el sector, así que la aplicabilidad sólo existe una vez resuelto el
 * `(sector × norma)` del run.
 */
export interface EffectiveThreshold extends MetricDefinition {
  /**
   * `false` = los cortes NO están calibrados para este tipo de empresa, así que
   * el número se enseña sin semáforo. No es «no se pudo calcular»: el valor es
   * bueno, la vara no sirve. Caso vivo: S7 (pasivo/patrimonio) en una
   * financiera, donde un 10× es normal y la banda 1-2 pintaría un rojo
   * permanente que no informa de nada.
   */
  applies: boolean;
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
): EffectiveThreshold | undefined {
  const used = thresholdsUsed?.[metricKey];
  if (!definition) return undefined;
  if (!used) return { ...definition, applies: true };
  return {
    ...definition,
    direction: used.direction,
    low_alarm: used.low_alarm,
    low_ok: used.low_ok,
    high_ok: used.high_ok,
    high_alarm: used.high_alarm,
    // Los DOS atributos por los que la tabla de umbrales se diferencia del
    // catálogo del motor. Se descartaban aquí (PHASE-44.18), así que la
    // diferenciación por (sector × norma) viajaba hasta el cliente y moría en
    // la última línea: la pantalla no podía distinguir «no se pudo colorear»
    // de «la vara no sirve para este sector», ni declarar que unos cortes
    // US-GAAP se están aplicando a cuentas IFRS.
    model_variant: used.model_variant,
    applies: used.applies,
  };
}
