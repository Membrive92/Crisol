/**
 * Comparar la versión del motor que produjo un análisis con la del motor de hoy
 * (PHASE-44.16).
 *
 * **Por qué hace falta.** Un `AnalysisRun` es JSONB persistido: se guarda con el
 * motor de su día y se lee tal cual meses después. La tabla contiene, a la vez,
 * runs de todas las versiones que han existido. Hasta ahora la UI leía cualquiera
 * como si lo hubiera producido el motor actual, y eso reventó con el único valor
 * analizado antes de PHASE-44.9: `signals.length` sobre una clave que no existe.
 *
 * El arreglo defensivo (tolerar el hueco en cada consumidor) es necesario pero no
 * suficiente: deja al usuario delante de un informe con huecos y sin saber por
 * qué. Esto es la otra mitad — poder DECIR «esto lo calculó un motor viejo» en
 * vez de pintar la ausencia como si fuera un dato.
 */

import type { QuestionVerdict } from '@crisol/types';

/**
 * Qué se puede afirmar del veredicto de una pregunta, en tres estados que NO se
 * pueden colapsar a dos:
 *
 * - `evaluated` — se evaluaron señales y el veredicto se sostiene en ellas.
 * - `no-evidence` — había señales candidatas y NINGUNA puntuó, así que un verde
 *   es ausencia de prueba, no buena salud (PHASE-44.9).
 * - `not-recorded` — el motor que produjo el análisis no registraba el desglose
 *   (< 1.1.0). No se sabe cuál de los dos anteriores es, y fingir que se sabe
 *   es justo el fallo: `undefined === 0` da `false`, así que la comprobación
 *   vieja fallaba EN ABIERTO y pintaba estos casos como verde verificado.
 *
 * Vive aquí, y no en cada pantalla, porque la web lo tenía escrito en DOS
 * sitios (el hero y la pestaña Veredicto) con la misma expresión copiada — dos
 * copias de una regla es una divergencia esperando el momento.
 */
export type QuestionEvidence = 'evaluated' | 'no-evidence' | 'not-recorded' | 'not-audited';

export function questionEvidence(question: QuestionVerdict): QuestionEvidence {
  const { signals, evaluated_count: evaluated, audited } = question;
  if (signals === undefined || evaluated === undefined) return 'not-recorded';
  // El cuarto estado (motor ≥ 1.6.0): falta un PORTANTE, así que el veredicto no
  // está auditado dijeran lo que dijeran las demás señales. `undefined` no es
  // `false`: en los runs anteriores la distinción no se registraba.
  if (audited === false) return 'not-audited';
  return evaluated === 0 && signals.length > 0 ? 'no-evidence' : 'evaluated';
}

/** Etiqueta corta de cada estado, compartida por las dos apps. */
export const EVIDENCE_LABEL: Record<QuestionEvidence, string> = {
  evaluated: '',
  'no-evidence': 'Sin evidencia',
  'not-recorded': 'No auditable',
  'not-audited': 'No auditada',
};

/**
 * El desglose de evidencia de una pregunta, en una frase.
 *
 * Vive aquí porque tiene que decir la verdad sobre TRES formatos de run a la
 * vez: los que no registran nada (< 1.1.0), los que sólo tienen «evaluadas / no
 * disponibles» (1.1.0-1.4.0), y los que separan «comprobadas y limpias» de «sin
 * poder comprobar» (≥ 1.5.0).
 *
 * La distinción importa porque el cubo antiguo mezclaba cuatro cosas: en
 * McDonald's, «7 sin poder evaluar» eran 2 huecos reales y 5 banderas
 * comprobadas y limpias. La pantalla subestimaba la evidencia mientras el
 * veredicto verde la sobreestimaba — los dos errores a la vez y en direcciones
 * opuestas.
 */
export function evidenceBreakdown(question: QuestionVerdict): string {
  const {
    evaluated_count: evaluated,
    unavailable_count: unavailable,
    clear_count: clear,
    unchecked_count: unchecked,
  } = question;
  if (evaluated === undefined) return '';
  const parts = [`${evaluated} señales evaluadas`];
  if (clear === undefined || unchecked === undefined) {
    // Run anterior a 1.5.0: el desglose no existe, así que se dice lo que hay.
    parts.push(`${unavailable ?? 0} sin poder evaluar`);
    return parts.join(' · ');
  }
  if (clear > 0) parts.push(`${clear} comprobadas y limpias`);
  parts.push(`${unchecked} sin poder comprobar`);
  return parts.join(' · ');
}

/** Un `x.y.z` partido en números. Lo que no sea numérico cuenta como 0. */
function parts(version: string): [number, number, number] {
  const chunks = version.trim().split('.');
  const at = (i: number) => {
    const n = Number.parseInt(chunks[i] ?? '', 10);
    return Number.isFinite(n) ? n : 0;
  };
  return [at(0), at(1), at(2)];
}

/**
 * `< 0` si `a` es anterior a `b`, `0` si son la misma, `> 0` si es posterior.
 *
 * Comparación numérica por componente, no lexicográfica: `1.10.0` es POSTERIOR a
 * `1.9.0`, aunque como cadena sea menor. El motor ya ha pasado por `1.2.0` y
 * `1.3.0`, así que llegar a `1.10.0` es cuestión de tiempo.
 */
export function compareEngineVersions(a: string, b: string): number {
  const [aMajor, aMinor, aPatch] = parts(a);
  const [bMajor, bMinor, bPatch] = parts(b);
  return aMajor - bMajor || aMinor - bMinor || aPatch - bPatch;
}

/**
 * Si el análisis lo produjo un motor ANTERIOR al que corre ahora.
 *
 * Devuelve `false` cuando falta cualquiera de las dos versiones: sin saber
 * contra qué comparar, afirmar que un run está caducado sería inventárselo. Y
 * también cuando el run es POSTERIOR al catálogo (un frontend servido desde una
 * caché vieja): eso no es un run caducado, es un frontend caducado, y el aviso
 * mandaría a reejecutar un análisis que no tiene nada de malo.
 */
export function isRunOutdated(runVersion?: string | null, engineVersion?: string | null): boolean {
  if (!runVersion || !engineVersion) return false;
  return compareEngineVersions(runVersion, engineVersion) < 0;
}
