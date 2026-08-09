import type { MetricBand } from '@crisol/types';

import { colors } from './tokens';

/**
 * Modelo de la matriz concepto × ejercicio del informe de Inversión, y el
 * semáforo que la colorea. **Puro**: no hay JSX aquí, sólo el view-model que
 * web y móvil pintan cada uno con sus primitivas (ADR-0001).
 *
 * Vive en un paquete compartido y no en `apps/web` porque el informe tiene que
 * decir lo MISMO en los dos sitios. Duplicar esta capa es cómo se llega a que
 * una pantalla enseñe un margen del 42 % y la otra `0,42` — que es exactamente
 * el defecto que PHASE-44.9 arregló en web mientras el móvil seguía pintando las
 * señales del veredicto en crudo.
 */

export interface MatrixCell {
  /** Texto ya formateado. `—` para hueco. */
  text: string;
  /** Color del texto (el semáforo lo decide quien construye la fila). */
  color?: string | undefined;
  /** Fondo suave de banda. */
  background?: string | undefined;
  /** Explicación (razón de un no-calculable, el corte aplicado…). */
  title?: string | undefined;
  /** Marca de aproximación / procedencia degradada. */
  mark?: string | undefined;
}

export interface MatrixRow {
  key: string;
  label: string;
  /** Nota bajo la etiqueta: el corte aplicado, o por qué no se pudo calcular. */
  hint?: string | undefined;
  /** Sub-cabecera de bloque (Activo corriente, Solvencia…). No lleva celdas. */
  isGroup?: boolean | undefined;
  /** Fila de total: se resalta. */
  emphasis?: boolean | undefined;
  cells: MatrixCell[];
}

/**
 * El semáforo del módulo. Una banda `null` es GRIS y dice «sin banda» — nunca
 * verde: `ThresholdSpec.band_for` del engine documenta que `None` no significa
 * «sana», sino «no hay banda que aplicar».
 */
export function bandColors(band: MetricBand | null): { fg: string; bg: string } {
  if (band === 'healthy') return { fg: colors.success, bg: colors.successSoft };
  if (band === 'caution') return { fg: colors.warning, bg: colors.warningSoft };
  if (band === 'stressed') return { fg: colors.danger, bg: colors.dangerSoft };
  return { fg: colors.textMuted, bg: colors.surfaceMuted };
}

const BAND_LABEL: Record<MetricBand, string> = {
  healthy: 'Sano',
  caution: 'Vigilar',
  stressed: 'Riesgo',
};

export function bandLabel(band: MetricBand | null): string {
  return band ? BAND_LABEL[band] : 'Sin banda';
}
