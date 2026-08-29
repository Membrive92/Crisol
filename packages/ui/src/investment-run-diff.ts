import type { MetricBand, RunDiff } from '@crisol/types';

import { bandLabel } from './investment-matrix';
import { EVIDENCE_LABEL, type QuestionEvidence } from './investment-run-version';
import { DIVIDEND, SAFETY } from './investment-verdict-labels';

/**
 * La comparación de dos análisis, lista para pintar (PHASE-44.24.F).
 *
 * Capa PURA y compartida: las dos apps enseñan las mismas filas y en el mismo
 * orden. Lo que ordena no es la severidad de la métrica sino la DIRECCIÓN del
 * cambio — lo que ha empeorado va primero, porque es lo que hace mirar esta
 * pantalla.
 */

/** Cómo se ha movido una fila. `flat` es un cambio sin dirección clara. */
export type DiffDirection = 'better' | 'worse' | 'flat';

export interface DiffRow {
  key: string;
  /** Qué cambió, en lenguaje del informe. */
  label: string;
  /** Cómo estaba. `null` cuando no existía antes. */
  before: string | null;
  /** Cómo está. `null` cuando ha desaparecido. */
  after: string | null;
  direction: DiffDirection;
  /** Para agrupar en pantalla. */
  group: 'verdict' | 'question' | 'score' | 'band' | 'flag';
}

export interface DiffView {
  /**
   * `false` cuando cambió el motor o la calibración.
   *
   * No es una etiqueta decorativa: con `false`, `rows` está VACÍO porque el
   * servidor no emite cambios de empresa. Leer un cambio de banda como una
   * degradación del negocio cuando lo que se movió fue el corte es la
   * conclusión contraria a la verdadera.
   */
  comparable: boolean;
  rows: DiffRow[];
  /** Los cambios de método, tal como los redacta el servidor. */
  methodChanges: string[];
  /** El aviso único cuando la comparación no puede aislar la causa. */
  caveat: string | null;
  /** Reexpresiones entre las dos fechas, en una frase por ejercicio. */
  restatements: string[];
  /** `true` si no hay ni un cambio que enseñar y sí se podía comparar. */
  unchanged: boolean;
}

const BAND_RANK: Record<string, number> = { healthy: 0, caution: 1, stressed: 2 };
const SAFETY_RANK: Record<string, number> = { conservative: 0, watch: 1, avoid: 2 };
const DIVIDEND_RANK: Record<string, number> = {
  healthy: 0,
  caution: 1,
  stressed: 2,
  not_applicable: 1,
};
/** Perder respaldo es empeorar aunque el color no se mueva. */
const EVIDENCE_RANK: Record<string, number> = {
  evaluated: 0,
  'not-audited': 1,
  'no-evidence': 2,
  'not-recorded': 3,
};

export function diffRows(diff: RunDiff | undefined): DiffView {
  if (!diff) {
    return {
      comparable: true,
      rows: [],
      methodChanges: [],
      caveat: null,
      restatements: [],
      unchanged: false,
    };
  }

  const rows: DiffRow[] = [];

  if (diff.safety_before !== diff.safety_after) {
    rows.push({
      key: 'safety',
      label: 'Perfil de seguridad',
      before: diff.safety_before ? SAFETY[diff.safety_before].label : null,
      after: diff.safety_after ? SAFETY[diff.safety_after].label : null,
      direction: compare(SAFETY_RANK, diff.safety_before, diff.safety_after),
      group: 'verdict',
    });
  }

  if (diff.dividend_before !== diff.dividend_after) {
    rows.push({
      key: 'dividend',
      label: 'Veredicto del dividendo',
      before: diff.dividend_before ? DIVIDEND[diff.dividend_before] : null,
      after: diff.dividend_after ? DIVIDEND[diff.dividend_after] : null,
      direction: compare(DIVIDEND_RANK, diff.dividend_before, diff.dividend_after),
      group: 'verdict',
    });
  }

  for (const question of diff.questions) {
    const colorCambio = question.verdict_before !== question.verdict_after;
    rows.push({
      key: `q:${question.key}`,
      label: colorCambio
        ? `Pregunta «${question.key}»`
        : `Pregunta «${question.key}»: cambió la evidencia, no el color`,
      before: describeQuestion(question.verdict_before, question.evidence_before),
      after: describeQuestion(question.verdict_after, question.evidence_after),
      direction: colorCambio
        ? compare(BAND_RANK, question.verdict_before, question.verdict_after)
        : compare(EVIDENCE_RANK, question.evidence_before, question.evidence_after),
      group: 'question',
    });
  }

  for (const score of diff.scores) {
    rows.push({
      key: `s:${score.key}`,
      label: score.key,
      before: describeValue(score.before, score.band_before),
      after: describeValue(score.after, score.band_after),
      direction: compare(BAND_RANK, score.band_before, score.band_after),
      group: 'score',
    });
  }

  for (const band of diff.bands) {
    rows.push({
      key: `b:${band.key}`,
      label: band.key,
      before: describeValue(band.value_before, band.band_before),
      after: describeValue(band.value_after, band.band_after),
      direction: compare(BAND_RANK, band.band_before, band.band_after),
      group: 'band',
    });
  }

  for (const flag of diff.flags) {
    rows.push({
      key: `f:${flag.key}`,
      label: flag.label ?? flag.key,
      before: flag.appeared ? 'no estaba' : 'encendida',
      after: flag.appeared ? 'encendida' : 'se ha apagado',
      // Encenderse es empeorar; apagarse, mejorar. Sin esto, las dos saldrían
      // juntas y la lista dejaría de responder «¿va peor?».
      direction: flag.appeared ? 'worse' : 'better',
      group: 'flag',
    });
  }

  // Lo que ha empeorado primero: es lo que hace mirar esta pantalla. Dentro de
  // cada dirección, el orden es el de los grupos, que va de lo general
  // (veredicto) a lo particular (una métrica).
  const DIRECTION_RANK: Record<DiffDirection, number> = { worse: 0, flat: 1, better: 2 };
  const GROUP_RANK: Record<DiffRow['group'], number> = {
    verdict: 0,
    question: 1,
    score: 2,
    flag: 3,
    band: 4,
  };
  rows.sort(
    (a, b) =>
      DIRECTION_RANK[a.direction] - DIRECTION_RANK[b.direction] ||
      GROUP_RANK[a.group] - GROUP_RANK[b.group] ||
      a.key.localeCompare(b.key),
  );

  return {
    comparable: diff.comparable,
    rows: diff.comparable ? rows : [],
    methodChanges: diff.method_changes,
    caveat: diff.caveat,
    restatements: diff.restatements.map(
      (note) =>
        `Ejercicio ${note.fiscal_year}: ${note.item_count} partidas cambiaron entre ` +
        `${note.filing_a} y ${note.filing_b}.`,
    ),
    unchanged: diff.comparable && rows.length === 0,
  };
}

/**
 * Cómo se ha movido un valor dentro de una escala ordinal.
 *
 * Un extremo ausente devuelve `flat`: sin uno de los dos lados no se puede
 * decir si mejoró o empeoró, y adivinarlo pondría una flecha roja sobre una
 * comparación que no se ha hecho.
 */
function compare(
  rank: Record<string, number>,
  before: string | null | undefined,
  after: string | null | undefined,
): DiffDirection {
  // UNA sola guarda a propósito. Había dos solapadas —`!before || !after` y
  // el `undefined` del rango— y con dos, romper cualquiera de ellas la tapaba
  // la otra: el test no podía distinguir cuál protegía, que es la forma exacta
  // de tener un guardarraíl sin saber si funciona.
  const a = before == null ? undefined : rank[before];
  const b = after == null ? undefined : rank[after];
  if (a === undefined || b === undefined || a === b) return 'flat';
  return b > a ? 'worse' : 'better';
}

function describeQuestion(verdict: MetricBand | null, evidence: string): string {
  const color = verdict ? bandLabel(verdict) : 'sin veredicto';
  const label = EVIDENCE_LABEL[evidence as QuestionEvidence];
  return label ? `${color} (${label.toLowerCase()})` : color;
}

function describeValue(value: string | null, band: MetricBand | null): string | null {
  if (value === null && band === null) return null;
  const numero = value ?? '—';
  return band ? `${numero} · ${bandLabel(band)}` : numero;
}
