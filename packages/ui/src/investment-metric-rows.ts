import type {
  DuPontDecomposition,
  MetricDefinition,
  MetricResult,
  ThresholdSpec,
} from '@crisol/types';

import { bandColors } from './investment-matrix';
import { colors } from './tokens';
import { formatMetricValue, formatThreshold } from './investment-metric-format';
import { effectiveThreshold, type CatalogIndex, type MetricIndex } from './investment-metric-index';
import type { MatrixCell, MatrixRow } from './investment-matrix';

/**
 * Construcción de filas de matriz a partir de métricas del engine.
 *
 * Concentra las **siete reglas de honestidad** de la pantalla, para que las
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
 * 7. Una métrica que **el motor de aquel día no emitía** dice eso, y no «no
 *    calculable»: la carencia es del análisis, no de las cuentas de la empresa.
 */

/** Marca de procedencia. Una partida `sourced` no lleva marca: es lo normal. */
const PROVENANCE_MARK: Record<string, string> = {
  derived: '†',
  imputed_zero: '·',
  estimated: '≈',
};

/** `model_variant` con el que el seed marca los cortes US-GAAP aplicados a otra norma. */
export const UNCALIBRATED = 'uncalibrated';

export const UNCALIBRATED_TITLE =
  'los cortes son US-GAAP y estas cuentas no lo son: se aplican sin recalibrar';

export const NOT_CALIBRATED_TITLE =
  'sin semáforo: los cortes no están calibrados para este tipo de empresa, ' +
  'así que el número se enseña pero no se juzga';

const PROVENANCE_TITLE: Record<string, string> = {
  derived: 'derivada de otras partidas con una identidad contable',
  imputed_zero: 'cero imputado: el filing no publica el concepto',
  estimated: 'proxy estimado, no un dato publicado',
};

export function metricCell(
  metric: MetricResult | undefined,
  definition: (MetricDefinition & { applies?: boolean }) | undefined,
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
  // Por qué este número sale SIN color. Sin esto, «la vara no sirve para este
  // sector» y «no se pudo colorear» se ven exactamente igual (PHASE-44.18).
  if (!metric.band && definition?.applies === false) {
    titles.push(NOT_CALIBRATED_TITLE);
  }
  if (definition?.model_variant === UNCALIBRATED) {
    marks.push('≠');
    titles.push(UNCALIBRATED_TITLE);
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

  // Regla 7: «el motor no la calculaba» ≠ «no se pudo calcular».
  //
  // Una métrica AUSENTE de todos los ejercicios no es un dato que faltase en el
  // filing: es una métrica que la versión del motor que produjo el análisis no
  // emitía (S7 y S8 llegaron en 1.2.0, las DUPONT_* en 1.1.0). Meterla en el
  // mismo saco que `not_computable` hacía que la pantalla dijera «no calculable
  // con los datos disponibles» — una afirmación FALSA sobre las cuentas de la
  // empresa, que además desvía el diagnóstico hacia el emisor.
  if (series.length > 0 && series.every((m) => !m)) {
    return missingRow(
      metricKey,
      base?.label ?? metricKey,
      'no existía en la versión del motor que produjo este análisis: vuelve a ejecutarlo',
      index.years,
    );
  }

  const threshold = formatThreshold(definition);
  const allMissing = series.every((m) => !m || m.status === 'not_computable');
  const firstReason = series.find((m) => m?.status === 'not_computable')?.reason ?? null;

  const hint = allMissing
    ? (firstReason ?? 'no calculable con los datos disponibles')
    : definition?.applies === false
      ? // Enseñar el corte de una vara que NO se ha aplicado sería peor que no
        // enseñar nada: el usuario compararía el número contra un umbral que el
        // motor descartó a propósito para este sector.
        NOT_CALIBRATED_TITLE
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

/**
 * La fila de comprobación del DuPont: el producto de los factores menos el ROE.
 * Debe ser 0.
 *
 * Vive aquí y no en un tab porque las dos apps la necesitan (PHASE-44.20).
 * Mientras estuvo escrita en `apps/web/.../tab-ratios.tsx`, móvil no tenía el
 * DuPont entero y nada avisaba.
 *
 * Tres estados, y confundir dos de ellos ya costó un bug:
 * - `undefined` — el cuadre llegó en PHASE-44.10, así que un run anterior no lo
 *   trae. Cuando se trataba igual que `null`, `Number(undefined)` daba `NaN`,
 *   `NaN === null` es falso, y la celda salía en ROJO acusando «la identidad NO
 *   cierra: hay un problema en los datos o en una fórmula» — la pantalla
 *   denunciando un descuadre contable inexistente en cuentas reales.
 * - `null` — **no verificable**: faltaba algún factor (a McDonald's le pasa, con
 *   patrimonio neto negativo). Un cuadre que no se ha podido comprobar nunca se
 *   presenta como superado.
 * - un número — cierra o no cierra.
 */
export function dupontCheckRow(
  key: string,
  dupont: readonly DuPontDecomposition[],
  pick: (point: DuPontDecomposition) => string | null | undefined,
): MatrixRow {
  return {
    key,
    label: 'Comprobación',
    hint: 'producto de los factores menos el ROE: debe ser cero',
    emphasis: true,
    cells: dupont.map((point) => {
      const raw = pick(point);
      if (raw === undefined) {
        return {
          text: '—',
          title:
            'este análisis lo produjo un motor anterior, que no emitía la comprobación; ' +
            'vuelve a ejecutarlo para verla',
        };
      }
      if (raw === null) {
        return {
          text: 'no verificable',
          title: 'falta algún factor, así que la identidad no se puede comprobar',
        };
      }
      const value = Number(raw);
      const closes = Math.abs(value) < 1e-12;
      return {
        text: closes ? '0' : value.toExponential(1),
        color: closes ? colors.success : colors.danger,
        title: closes
          ? 'la identidad cierra'
          : 'la identidad NO cierra: hay un problema en los datos o en una fórmula',
      };
    }),
  };
}
