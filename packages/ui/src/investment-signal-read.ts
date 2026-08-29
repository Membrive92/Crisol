import type { MetricUnit, ReportSignal, SignalDistance, ThresholdOrigin } from '@crisol/types';

import { formatMetricValue } from './investment-metric-format';

/**
 * Cómo se LEE una señal enriquecida: la distancia dicha en su unidad y la
 * procedencia de la vara (PHASE-44.24.C).
 *
 * Capa PURA y compartida. El servidor manda los números —distancia absoluta,
 * relativa, corte, orden— y aquí se convierten en las frases que se pintan. Se
 * comparte porque **la misma señal tiene que leerse igual en las dos apps**: si
 * web dijera «a 3 pp del verde» y móvil «0,03 del corte», serían dos productos.
 */

const BAND_NAME: Record<'caution' | 'stressed', string> = {
  caution: 'ámbar',
  stressed: 'rojo',
};

/**
 * Unidades en las que una distancia se lee en PUNTOS y no en múltiplos.
 *
 * Un margen que está a 0,03 del corte está a «3 puntos», no «a 0,08× del
 * verde»: la fracción es aritméticamente correcta y no se parece a nada que
 * nadie diga en voz alta.
 */
const POINT_UNITS = new Set<MetricUnit>(['percent', 'pp']);

/**
 * La distancia de una señal a su corte, en una frase.
 *
 * Devuelve `null` cuando no hay distancia que decir — y entonces la fila no
 * pinta nada, en vez de un hueco con forma de dato.
 */
export function distanceSentence(
  distance: SignalDistance | null | undefined,
  unit: MetricUnit | undefined,
): string | null {
  if (!distance) return null;
  if (distance.cut === null || distance.absolute === null) {
    // S7 por debajo de su banda: no hay corte de alarma hacia donde medir, y el
    // motivo explica que la métrica no puede empeorar más por ese lado.
    return distance.missing_reason ?? null;
  }
  const band = BAND_NAME[distance.next_band];
  const magnitude = absoluteSentence(distance, unit);
  if (magnitude === null) return null;
  return distance.side === 'inside'
    ? `a ${magnitude} del ${band}`
    : `${magnitude} dentro del ${band}`;
}

/** La magnitud sola, ya en la escala en que se lee esa unidad. */
function absoluteSentence(distance: SignalDistance, unit: MetricUnit | undefined): string | null {
  const absolute = Number(distance.absolute);
  if (!Number.isFinite(absolute)) return null;
  if (unit && POINT_UNITS.has(unit)) {
    // `formatMetricValue` de un `percent` multiplica por cien y añade el signo
    // de porcentaje; para una DIFERENCIA lo correcto son puntos.
    const points = unit === 'percent' ? absolute * 100 : absolute;
    return `${points.toLocaleString('es-ES', { maximumFractionDigits: 1 })} pp`;
  }
  const relative = distance.relative === null ? null : Number(distance.relative);
  if (relative !== null && Number.isFinite(relative)) {
    return `${relative.toLocaleString('es-ES', { maximumFractionDigits: 1 })}×`;
  }
  // Sin relativa —corte cero, o una puntuación— se dice la absoluta tal cual.
  return formatMetricValue(distance.absolute, unit);
}

/**
 * De dónde salió la vara, en las palabras del usuario.
 *
 * `perfil` es el perfil efectivo de HOY, que el servidor emite aparte: se pasa
 * para poder nombrarlo («banda de utilities») en vez de decir «sectorial» a
 * secas, y NO se compone aquí con `security.sector` porque para una entidad
 * financiera clasificada en otro sector eso sería falso.
 */
export function originSentence(
  origin: ThresholdOrigin,
  profile: string | undefined,
): string | null {
  switch (origin) {
    case 'generic':
      return 'banda genérica';
    case 'sector':
      return profile ? `banda de ${profile}` : 'banda sectorial';
    case 'financial':
      return 'banda de entidades financieras';
    case 'table':
      return 'banda recalibrada a mano';
    case 'earlier_calibration':
      // El valor que evita el falso «esto parece un bug»: dos empresas con
      // cortes distintos porque una se analizó antes de recalibrar.
      return 'cortes de una calibración anterior: vuelve a ejecutar el análisis';
    case 'uncalibrated':
      return 'cortes US-GAAP sin recalibrar para esta norma contable';
    case 'not_applicable':
      return null; // La fila ya explica por qué la vara no aplica.
    case 'not_recorded':
      return 'este análisis no registró el corte: se muestra el del catálogo de hoy';
  }
}

/** Las señales de una pregunta en el orden que manda el servidor. */
export function orderedSignals<T extends { key: string }>(
  signals: readonly T[],
  report: readonly ReportSignal[] | undefined,
): T[] {
  if (!report || report.length === 0) return [...signals];
  const rank = new Map(report.map((s) => [s.key, s.severity_rank]));
  // Lo que el servidor no clasifique va al final, en su orden original: nunca
  // se cuela por delante de una señal cuyo lugar sí se ha decidido.
  return [...signals].sort(
    (a, b) =>
      (rank.get(a.key) ?? Number.MAX_SAFE_INTEGER) - (rank.get(b.key) ?? Number.MAX_SAFE_INTEGER),
  );
}

/** El índice de la capa de lectura de una pregunta, por clave de señal. */
export function reportSignalsOf(
  report: { questions: { key: string; signals: ReportSignal[] }[] } | undefined,
  questionKey: string,
): Map<string, ReportSignal> {
  const question = report?.questions.find((q) => q.key === questionKey);
  return new Map((question?.signals ?? []).map((s) => [s.key, s]));
}
