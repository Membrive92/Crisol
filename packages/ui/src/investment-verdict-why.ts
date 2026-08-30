import type {
  AnalysisRun,
  ReportWhy,
  SafetyCondition,
  SafetyProfile,
  ThresholdSpec,
} from '@crisol/types';

import { effectiveThreshold, type CatalogIndex } from './investment-metric-index';
import { formatMetricValue, formatThreshold } from './investment-metric-format';
import { bandLabel } from './investment-matrix';
import { AVOID_RULES, CONSERVATIVE_RULES } from './investment-verdict-labels';

/**
 * Por qué este veredicto, en filas listas para pintar (PHASE-44.25).
 *
 * El informe demuestra todo y no argumentaba nada: el titular nombraba una
 * señal («X-Score en rojo»), la checklist la marcaba con un glifo invertido, la
 * frase de la pregunta la citaba con otro nombre y la fila con el número vivía
 * tras un desplegable cerrado. Cuatro representaciones del mismo hecho y ningún
 * pixel que dijera que son la misma cosa.
 *
 * Vive en la capa compartida porque lo pintan TRES superficies desde el día uno
 * —web, móvil y el dictamen imprimible—, y porque las tres tienen que decir lo
 * mismo sobre el mismo run.
 *
 * Lo que esta capa NO hace: redactar. Las frases del veredicto se componen en
 * el servidor con plantillas versionadas y goldens de texto exacto; aquí sólo
 * se añade el NÚMERO, que es lo que se formatea por unidad y tiene que salir
 * igual en las dos apps.
 */

/** Cómo se lee el estado de una condición. */
export type ConditionState = 'holds' | 'clear' | 'unknown' | 'unrecorded';

export interface WhySignalRow {
  key: string;
  label: string;
  /** «0,87 · Riesgo», ya formateado. Vacío si la señal no trae número. */
  reading: string;
  /** «el rojo empieza en −0,25», si el run registró el corte. */
  cut: string | null;
  /** `true` para una bandera: no tiene número ni corte que enseñar. */
  isFlag: boolean;
}

export interface WhyRow {
  key: string;
  /** La afirmación, tal y como la escribió el motor que produjo el run. */
  text: string;
  state: ConditionState;
  /**
   * El rótulo del estado, en PALABRAS.
   *
   * El diseño anterior usaba ✓/✕ con el significado invertido entre las dos
   * listas: en «Evitar», cumplir una condición pintaba ✕, que junto a una
   * proposición se lee como «no es verdad» — la única línea que respondía a la
   * pregunta salía negada.
   */
  stateLabel: string;
  /** Si este estado es la mala noticia (para el color). */
  isBad: boolean;
  /** Por qué no se pudo comprobar. Sólo con `state === 'unknown'`. */
  reason: string | null;
  /** Si esta condición es la que disparó el sello. */
  decided: boolean;
  signals: WhySignalRow[];
}

export interface WhySection {
  key: 'avoid' | 'conservative';
  title: string;
  rows: WhyRow[];
}

export interface VerdictWhy {
  sections: WhySection[];
  /** Qué tendría que cambiar para salir del sello. Vacío si no se sabe. */
  exitSentence: string;
  /** Los dos modelos de insolvencia en extremos opuestos. */
  modelsDisagree: string | null;
  /**
   * `true` cuando el run no registró la matriz evaluada.
   *
   * La pantalla lo DICE en vez de rellenarlo: la versión anterior infería el
   * estado de las condiciones de «Conservador» desde `blocking_reasons`, que en
   * un perfil «Evitar» contiene otra cosa — y acababa pintando «F-Score ≥ 7 ✓»
   * sobre una condición que el motor no había llegado a evaluar.
   */
  legacy: boolean;
}

const STATE_LABEL: Record<ConditionState, string> = {
  holds: 'se cumple',
  clear: 'no se cumple',
  unknown: 'sin poder comprobar',
  unrecorded: 'sin registro en este análisis',
};

const SECTION_TITLE: Record<'avoid' | 'conservative', string> = {
  avoid: 'Se evita si se cumple CUALQUIERA de estas',
  // Sin cardinal: el motor comprueba seis condiciones y la lista decía cinco.
  conservative: 'Es conservador sólo si se cumplen TODAS',
};

/** El estado de una condición del run, con su tri-estado intacto. */
function stateOf(condition: SafetyCondition): ConditionState {
  if (condition.met === null || condition.met === undefined) return 'unknown';
  return condition.met ? 'holds' : 'clear';
}

function signalRows(
  condition: SafetyCondition,
  thresholds: Record<string, ThresholdSpec> | undefined,
  catalog: CatalogIndex | undefined,
): WhySignalRow[] {
  return (condition.signals ?? []).map((signal) => {
    // El MISMO camino que la tabla de señales: el corte del run fusionado sobre
    // el catálogo. Dos formas de resolverlo serían dos números para la misma
    // raya, y el corte se calibra por sector — escribirlo aquí caducaría.
    const definition = effectiveThreshold(
      signal.key,
      thresholds,
      catalog?.definition(signal.key),
    );
    const band = signal.band ? bandLabel(signal.band) : null;
    const value =
      signal.value === null || signal.value === undefined
        ? null
        : formatMetricValue(signal.value, definition?.unit);
    const reading = value === null ? (band ?? '') : band ? `${value} · ${band}` : value;
    return {
      key: signal.key,
      label: signal.label,
      reading,
      cut: signal.kind === 'flag' ? null : formatThreshold(definition),
      isFlag: signal.kind === 'flag',
    };
  });
}

/**
 * Las filas de «por qué este veredicto».
 *
 * @param profile el `safety_profile` del run.
 * @param why la capa de lectura del servidor (`report.why`), si la hay.
 * @param thresholds los cortes que se aplicaron en ESE run.
 * @param catalog el catálogo de métricas, para la unidad y la etiqueta del corte.
 */
export function verdictWhyRows(
  profile: SafetyProfile | undefined,
  why: ReportWhy | null | undefined,
  thresholds?: Record<string, ThresholdSpec>,
  catalog?: CatalogIndex,
): VerdictWhy {
  const conditions = profile?.conditions;

  if (!conditions || conditions.length === 0) {
    return legacyRows(profile);
  }

  const decided = new Set(why?.decided_by ?? []);
  const sections: WhySection[] = (['avoid', 'conservative'] as const).map((rule) => ({
    key: rule,
    title: SECTION_TITLE[rule],
    rows: conditions
      .filter((condition) => condition.rule === rule)
      .map((condition) => {
        const state = stateOf(condition);
        return {
          key: condition.key,
          text: condition.text,
          state,
          stateLabel: STATE_LABEL[state],
          // `met` significa lo mismo en las diez: «la afirmación es cierta». En
          // «Evitar» eso dispara el sello; en «Conservador», redactadas en
          // negativo, eso es lo que falta. Cumplirse es la mala noticia en
          // ambas — un solo significado, ningún glifo bimodal.
          isBad: state === 'holds',
          reason: state === 'unknown' ? (condition.reason ?? null) : null,
          decided: decided.has(condition.key),
          signals: signalRows(condition, thresholds, catalog),
        };
      }),
  }));

  return {
    sections,
    exitSentence: why?.exit_sentence ?? '',
    modelsDisagree: why?.models_disagree ?? null,
    legacy: false,
  };
}

/**
 * Un run anterior a la matriz evaluada.
 *
 * Las de «Evitar» SÍ se pueden marcar: sus textos están persistidos en
 * `blocking_reasons`, que es un dato de ESE run y no la regla de hoy. Las de
 * «Conservador», no: cuando el perfil es «Evitar» el motor de entonces retornaba
 * antes de evaluarlas, así que no hay nada que afirmar — y la versión anterior
 * lo rellenaba con ✓ inventados.
 */
function legacyRows(profile: SafetyProfile | undefined): VerdictWhy {
  const blocking = profile?.blocking_reasons ?? [];
  const label = profile?.label;

  const avoid: WhyRow[] = AVOID_RULES.map((text) => {
    const holds = blocking.includes(text);
    return {
      key: text,
      text,
      state: holds ? 'holds' : 'clear',
      stateLabel: STATE_LABEL[holds ? 'holds' : 'clear'],
      isBad: holds,
      reason: null,
      decided: holds && label === 'avoid',
      signals: [],
    };
  });

  const conservative: WhyRow[] = CONSERVATIVE_RULES.map((text) => {
    // En «watch» los motivos SON las condiciones que faltan, con su texto en
    // negativo: ahí la inferencia describe el run. En «avoid» no se evaluaron.
    const unrecorded = label === 'avoid';
    const missing = !unrecorded && blocking.some((reason) => isNegationOf(reason, text));
    const state: ConditionState = unrecorded
      ? 'unrecorded'
      : label === 'conservative' || !missing
        ? 'clear'
        : 'holds';
    return {
      key: text,
      text: missing ? textInNegative(blocking, text) : text,
      state,
      stateLabel: STATE_LABEL[state],
      isBad: state === 'holds',
      reason: null,
      decided: false,
      signals: [],
    };
  });

  return {
    sections: [
      { key: 'avoid', title: SECTION_TITLE.avoid, rows: avoid },
      { key: 'conservative', title: SECTION_TITLE.conservative, rows: conservative },
    ],
    exitSentence: '',
    modelsDisagree: null,
    legacy: true,
  };
}

/** El motivo persistido, que está redactado en negativo, si lo hay. */
function textInNegative(blocking: readonly string[], rule: string): string {
  return blocking.find((reason) => isNegationOf(reason, rule)) ?? rule;
}

function isNegationOf(reason: string, rule: string): boolean {
  const head = rule.split(' ')[0] ?? '';
  return head.length > 0 && reason.startsWith(head);
}

/**
 * La procedencia del veredicto del dividendo, en una frase corta.
 *
 * El hero anuncia «Dividendo en riesgo» y la pregunta del dividendo puede estar
 * en verde: es el peor de dos, y sin decir cuál, el lector se queda con una
 * contradicción aparente.
 */
export function dividendSourceLabel(run: AnalysisRun | undefined): string | null {
  const source = run?.verdict?.dividend_verdict_source;
  if (!source) return null;
  if (source === 'both') return 'por la caja del dividendo y por la resistencia';
  return source === 'dividend' ? 'por la caja del dividendo' : 'por la resistencia a un golpe';
}
