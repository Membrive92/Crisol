import type { AnalysisRun, MetricBand, QuestionVerdict } from '@crisol/types';

import { formatMetricValue } from './investment-metric-format';
import { effectiveThreshold, type CatalogIndex } from './investment-metric-index';
import { questionEvidence } from './investment-run-version';
import { distanceSentence, reportSignalsOf } from './investment-signal-read';

/**
 * El Dictamen como sumario legible (PHASE-44.26).
 *
 * El feedback que lo origina, literal: «El veredicto es demasiado técnico…
 * un sumario final que resuma qué está bien y qué riesgos corre la empresa,
 * con enlaces a los datos. Ahora mismo son solo apuntes técnicos».
 *
 * Estas listas NO redactan: seleccionan por regla determinista sobre lo que el
 * run ya trae, y toda frase que aparece la compuso el servidor o es la razón
 * persistida por señal. Elegir «lo bueno» a mano sería curaduría — una opinión
 * disfrazada de resumen — así que las reglas de selección están escritas aquí,
 * con sus porqués, y las atan tests que se verificaron rompiéndolas.
 *
 * Viven en la capa compartida porque las pintan las TRES superficies (web,
 * móvil y el dictamen imprimible), y porque el orden y el corte son parte del
 * contenido: dos copias divergirían en la primera iteración (PHASE-44.13).
 */

export interface DictamenRow {
  key: string;
  label: string;
  band: MetricBand;
  /** «0,87», ya formateado en su unidad. Vacío para señales sin número. */
  value: string;
  /** «ya ha cruzado hacia el rojo», si el run registró la distancia. */
  distance: string | null;
  /**
   * Las frases persistidas que dan cuerpo a una señal sin número — hoy, los
   * escenarios de stress. Redactadas por el motor del run, nunca aquí.
   */
  sentences: readonly string[];
  /**
   * La pregunta que la puntúa no está auditada (le falta un portante).
   *
   * El riesgo se lista igual — callarlo por un tecnicismo es peor que decirlo
   * con su matiz (regla 2 de next_checks)— pero la fila lo declara, y la
   * pantalla lo pinta con la etiqueta compartida de evidencia.
   */
  unaudited: boolean;
}

export interface CleanCheck {
  label: string;
  /** La razón persistida POR SEÑAL («se comprobó y no se encendió»). */
  reason: string;
}

export interface DictamenLists {
  /** Señales rojas y ámbar, las rojas primero. Nunca se recorta una roja. */
  concerns: DictamenRow[];
  /** Cuántas ámbar quedaron fuera del tope. 0 = se enseñan todas. */
  concernsOverflow: number;
  /** Señales sanas de preguntas AUDITADAS. Un verde sin evidencia no entra. */
  strengths: DictamenRow[];
  strengthsOverflow: number;
  /**
   * Escenarios de stress que SIGUEN cubriendo, con su frase persistida.
   * Sólo si la pregunta de la resistencia está evaluada: en una financiera
   * «aguanta el golpe» bajo una pregunta gris sería un verde inventado.
   */
  scenariosHolding: string[];
  /** Banderas comprobadas y limpias, con su razón persistida. */
  clean: CleanCheck[];
  /** Condiciones de «Evitar» comprobadas y descartadas (motor ≥ 1.8.0). */
  discarded: string[];
  /**
   * Las frases del sumario, del SERVIDOR (PHASE-44.26). Vacías con un backend
   * anterior: la pantalla enseña las listas sin entrada, nunca redacta una.
   */
  concernsIntro: string;
  strengthsIntro: string;
  /** TODAS las frases de escenario persistidas, para el bloque de stress. */
  stressSentences: string[];
  /** «La caja libre podría caer un 7 %…», del servidor. */
  stressMargin: string | null;
}

/**
 * ¿La pregunta es PERMANENTEMENTE no auditable?
 *
 * Es el predicado que `next_checks` aplica en el servidor (narrative.py:531):
 * `not-audited` sin portantes declarados. La resiliencia de una financiera es
 * capital regulatorio — no está en un 10-K— y sus señales no pueden entrar ni
 * en «qué preocupa» (un stress rojo bajo una pregunta gris) ni en «qué está
 * bien». Se espeja aquí UNA vez y lo consumen las dos listas: con el predicado
 * copiado en cada selector, endurecer uno dejaría el otro con la versión débil.
 */
export function permanentlyUnauditable(question: QuestionVerdict): boolean {
  return questionEvidence(question) === 'not-audited' && !(question.load_bearing?.length ?? 0);
}

/** El tope: nunca deja fuera una roja; las ámbar se recortan a partir de 6. */
const CAP = 6;

interface Selected {
  question: QuestionVerdict;
  signal: QuestionVerdict['signals'] extends readonly (infer S)[] | undefined ? S : never;
}

function eligibleQuestions(run: AnalysisRun): QuestionVerdict[] {
  return run.verdict.questions.filter((question) => !permanentlyUnauditable(question));
}

function rowOf(run: AnalysisRun, catalog: CatalogIndex, picked: Selected): DictamenRow {
  const { question, signal } = picked;
  const read = reportSignalsOf(run.report, question.key).get(signal.key);
  const definition = effectiveThreshold(signal.key, run.thresholds_used, catalog.definition(signal.key));
  return {
    key: signal.key,
    label: signal.label,
    band: signal.band as MetricBand,
    value:
      signal.kind === 'metric' && signal.value != null
        ? formatMetricValue(signal.value, definition?.unit)
        : '',
    distance: distanceSentence(read?.distance, definition?.unit),
    sentences: read?.evidence_sentences ?? [],
    unaudited: questionEvidence(question) !== 'evaluated',
  };
}

/**
 * Las dos listas del sumario y sus acompañantes.
 *
 * **Desde PHASE-44.26 la selección la hace el SERVIDOR** (`report.summary`),
 * junto a las frases que la nombran: qué entra y en qué orden es parte de lo
 * que la frase afirma, y dos capas decidiéndolo serían dos fuentes. Lo de
 * abajo queda como FALLBACK para backends anteriores — mismo patrón que el
 * checklist legacy del sello.
 *
 * Reglas del fallback, escritas para poder discutirlas:
 * - «Qué preocupa» = toda señal que PUNTUÓ en rojo o ámbar, rojas primero (el
 *   orden dentro de cada banda es el de las preguntas, que es el del run).
 * - «Qué está bien» = toda señal que puntuó en verde, SÓLO de preguntas con
 *   evidencia evaluada y al menos una señal puntuada — un verde por ausencia
 *   de prueba no es una fortaleza (PHASE-44.9).
 * - Tope `max(6, nº de rojas)`: una empresa con muchas ámbar no reproduce el
 *   muro que motivó el rediseño, y una roja no se esconde JAMÁS por un tope.
 */
export function dictamenLists(run: AnalysisRun, catalog: CatalogIndex): DictamenLists {
  const summary = run.report?.summary;
  if (summary?.concern_keys || summary?.strength_keys) {
    // El servidor ya seleccionó y enunció; aquí sólo se buscan las señales por
    // clave para formatear el número y componer el enlace.
    const byKey = new Map<string, Selected>();
    for (const question of run.verdict.questions) {
      for (const signal of question.signals ?? []) {
        if (!byKey.has(signal.key)) byKey.set(signal.key, { question, signal } as Selected);
      }
    }
    const resolve = (keys: readonly string[] | undefined) =>
      (keys ?? [])
        .map((key) => byKey.get(key))
        .filter((picked): picked is Selected => picked !== undefined)
        .map((picked) => rowOf(run, catalog, picked));
    return {
      concerns: resolve(summary.concern_keys),
      concernsOverflow: summary.concerns_overflow ?? 0,
      strengths: resolve(summary.strength_keys),
      strengthsOverflow: summary.strengths_overflow ?? 0,
      scenariosHolding: [],
      clean: cleanChecksOf(run),
      discarded: discardedOf(run),
      concernsIntro: summary.concerns_intro ?? '',
      strengthsIntro: summary.strengths_intro ?? '',
      stressSentences: summary.stress_sentences ?? [],
      stressMargin: summary.stress_margin ?? null,
    };
  }

  const questions = eligibleQuestions(run);

  const picked = (want: (band: string | null | undefined) => boolean, auditedOnly: boolean) =>
    questions
      .filter(
        (question) =>
          !auditedOnly ||
          (questionEvidence(question) === 'evaluated' && (question.evaluated_count ?? 0) > 0),
      )
      .flatMap((question) =>
        (question.signals ?? [])
          .filter((signal) => signal.counted && want(signal.band))
          .map((signal) => ({ question, signal }) as Selected),
      );

  const reds = picked((band) => band === 'stressed', false);
  const ambers = picked((band) => band === 'caution', false);
  const cap = Math.max(CAP, reds.length);
  const concernsAll = [...reds, ...ambers];
  const concerns = concernsAll.slice(0, cap);

  const greens = picked((band) => band === 'healthy', true);
  const strengths = greens.slice(0, CAP);

  // Los escenarios que siguen cubriendo, con la misma guarda de honestidad que
  // sus hermanos rojos: sólo si la pregunta que los puntúa está evaluada.
  const resilience = questions.find((question) => question.key === 'resilience');
  const resilienceEvaluated =
    resilience !== undefined && questionEvidence(resilience) === 'evaluated';
  const scenariosHolding = resilienceEvaluated
    ? (run.verdict.stress?.scenarios ?? [])
        .filter((scenario) => {
          const after = scenario.coverage_after;
          return after !== null && Number(after) >= 1 && scenario.sentence;
        })
        .map((scenario) => scenario.sentence)
    : [];

  return {
    concerns: concerns.map((pick) => rowOf(run, catalog, pick)),
    concernsOverflow: concernsAll.length - concerns.length,
    strengths: strengths.map((pick) => rowOf(run, catalog, pick)),
    strengthsOverflow: greens.length - strengths.length,
    scenariosHolding,
    clean: cleanChecksOf(run),
    discarded: discardedOf(run),
    concernsIntro: '',
    strengthsIntro: '',
    stressSentences: [],
    stressMargin: null,
  };
}

/**
 * Banderas comprobadas y limpias, con su razón PERSISTIDA por señal — no una
 * oración plural compuesta aquí, que sería redactar en el cliente.
 */
function cleanChecksOf(run: AnalysisRun): CleanCheck[] {
  return run.verdict.questions.flatMap((question) =>
    (question.signals ?? [])
      .filter((signal) => signal.outcome === 'clear' && signal.reason)
      .map((signal) => ({ label: signal.label, reason: signal.reason as string })),
  );
}

/**
 * Condiciones de «Evitar» comprobadas y descartadas: la afirmación positiva
 * determinista. Sólo con la matriz evaluada (motor ≥ 1.8.0); un run viejo no la
 * trae y aquí simplemente no hay filas — nunca se infiere.
 */
function discardedOf(run: AnalysisRun): string[] {
  return (run.verdict.safety_profile.conditions ?? [])
    .filter((condition) => condition.rule === 'avoid' && condition.met === false)
    .map((condition) => condition.text);
}

/**
 * Los rótulos de las secciones del Dictamen, en su orden de lectura.
 *
 * Compartidos porque son contenido: si cada app escribiera los suyos, el
 * dictamen imprimible y la pantalla acabarían contando historias distintas.
 */
/** «…y n más», compartido para que las tres superficies recorten igual. */
export function overflowLabel(count: number): string | null {
  return count > 0 ? `…y ${count} más` : null;
}

export const DICTAMEN_TITLES = {
  verdictum: 'El dictamen',
  reasoned: 'El dictamen, razonado',
  concerns: 'Qué preocupa',
  strengths: 'Qué está bien (sólo lo comprobado)',
  change: 'Qué cambiaría el sello',
  audit: 'La auditoría del sello',
  auditHint: 'La matriz de reglas que produce el sello, condición a condición.',
  strengthsFootnote:
    'Aquí sólo cuenta lo auditado: una pregunta sin evidencia no aporta nada a esta lista.',
} as const;
