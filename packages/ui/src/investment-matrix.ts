import type { MetricBand } from '@crisol/types';

import type { Sparkline } from './investment-sparkline';

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
  /**
   * PHASE-44.23 — qué ES este concepto, para la «i» de la fila.
   *
   * Distinto de `hint`, y por eso son dos campos: `hint` dice algo de ESTE
   * análisis (qué corte se aplicó, por qué faltó un año) y cambia con los
   * datos; `help` dice qué significa la fila y es el mismo siempre. Meterlos
   * juntos obligaría a elegir cuál se pierde.
   */
  help?: string | undefined;
  /**
   * PHASE-44.24 — por qué importa y cómo se lee, los otros dos tercios de la
   * ficha. Van en campos propios y no concatenados a `help` porque se pintan
   * en líneas separadas: «qué mide» se lee siempre, «por qué importa» una vez,
   * y «cómo se lee» es lo que se vuelve a consultar. Las partidas canónicas no
   * los tienen —su glosario es de un solo campo—, así que son opcionales.
   */
  helpWhy?: string | undefined;
  helpReading?: string | undefined;
  /**
   * La serie de la fila, para la columna de tendencia (PHASE-44.24.D).
   *
   * TRI-ESTADO, y los tres significan cosas distintas:
   * - clave AUSENTE: esta fila no tiene columna de tendencia (las 49 partidas
   *   de Estados, la fila de comprobación del DuPont). La tabla decide si pinta
   *   la columna mirando si ALGUNA fila trae la clave, así que ausente es lo
   *   que la deja fuera.
   * - `null`: la fila la tiene, pero con menos de tres ejercicios con número
   *   una línea no dice nada. Se pinta «serie corta», no un hueco en blanco,
   *   que se leería como «no calculable» (regla 6).
   * - un objeto: se dibuja.
   */
  spark?: Sparkline | null | undefined;
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

/** Un tramo de la ficha de una fila: el rótulo que lo encabeza y su texto. */
export interface HelpParagraph {
  /** `undefined` en el primero: «qué mide» no necesita presentarse. */
  label?: string | undefined;
  text: string;
}

/**
 * La ficha de una fila partida en sus tramos, en orden de lectura
 * (PHASE-44.24.A.1).
 *
 * Vive aquí y no en cada app porque el ORDEN y los RÓTULOS son contenido, no
 * presentación: si web dijera «Por qué importa» y móvil «Importancia», serían
 * dos productos. Lo único que cambia entre plataformas es si cada tramo se
 * pinta como párrafo o se une con saltos de línea.
 *
 * Devuelve `[]` cuando la fila no tiene ficha, y un solo tramo cuando sólo
 * tiene el «qué mide» — que es el caso de las 49 partidas canónicas, cuyo
 * glosario es de un campo. Así ningún rótulo queda huérfano.
 */
export function helpParagraphs(row: {
  help?: string | undefined;
  helpWhy?: string | undefined;
  helpReading?: string | undefined;
}): HelpParagraph[] {
  const parts: HelpParagraph[] = [];
  if (row.help) parts.push({ text: row.help });
  if (row.helpWhy) parts.push({ label: 'Por qué importa', text: row.helpWhy });
  if (row.helpReading) parts.push({ label: 'Cómo se lee', text: row.helpReading });
  return parts;
}
