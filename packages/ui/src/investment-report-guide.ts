import type { MetricBand } from '@crisol/types';

import { bandLabel } from './investment-matrix';
import { MATRIX_LEGEND, TEXT_LEGEND, type MarkEntry } from './investment-marks';
import { EVIDENCE_LABEL, type QuestionEvidence } from './investment-run-version';

/**
 * «Cómo leer este informe» (PHASE-44.24.E).
 *
 * El informe demuestra todo y explica poco: enseña 64 métricas con su valor, su
 * banda y su corte, y da por sabido qué significa un gris, por qué una pregunta
 * sale sin color, o qué separa una vara genérica de una calibrada por sector.
 * Eso no se puede aprender de la propia pantalla.
 *
 * Capa PURA y compartida. **Los estados no se escriben aquí**: se importan de
 * donde se pintan (`bandLabel`, `EVIDENCE_LABEL`, el registro de marcas), de
 * modo que la guía no puede describir un vocabulario que la pantalla ya no usa
 * — que es exactamente cómo caducó la leyenda del forense en PHASE-44.17.
 */

export interface GuideEntry {
  /** Lo que el usuario VE en pantalla. */
  term: string;
  /** Qué significa. */
  meaning: string;
}

export interface GuideSection {
  key: string;
  title: string;
  /** El párrafo que encabeza la sección. */
  intro: string;
  entries: readonly GuideEntry[];
}

const BANDS: readonly MetricBand[] = ['healthy', 'caution', 'stressed'];

const BAND_MEANING: Record<MetricBand, string> = {
  healthy:
    'el número cae del lado bueno del corte que el motor aplica a esta métrica en este sector. No es una recomendación: es una comprobación.',
  caution:
    'el número está en la franja intermedia. Merece mirarse junto a su tendencia, que es lo que la columna de serie enseña.',
  stressed:
    'el número cruza el corte por el lado malo. En el Veredicto se dice qué pregunta arrastra y a cuánta distancia del corte está.',
};

const EVIDENCE_MEANING: Record<Exclude<QuestionEvidence, 'evaluated'>, string> = {
  'no-evidence':
    'había señales candidatas y ninguna pudo puntuar. Un verde aquí sería ausencia de prueba, no buena salud, así que se pinta gris.',
  'not-audited':
    'la pregunta tiene señales que puntúan, pero le falta alguna de las que la DECIDEN. Una contabilidad sin M-Score no está auditada aunque diez métricas menores salgan bien.',
  'not-recorded':
    'el análisis lo produjo un motor anterior, que no registraba qué señales se evaluaron. Su veredicto no se puede auditar; lo que sí quedó escrito se muestra igualmente.',
};

const ORIGIN_ENTRIES: readonly GuideEntry[] = [
  {
    term: 'vara genérica',
    meaning:
      'el corte estándar del motor, el mismo para cualquier empresa. Es lo que se aplica cuando el sector no cambia nada.',
  },
  {
    term: 'vara del sector',
    meaning:
      'el corte movido por el perfil sectorial. Una eléctrica con deuda neta 4,8× sale ámbar y una tecnológica con 2,5×, roja: el perfil no es «relajar», es medir contra el negocio que hay.',
  },
  {
    term: 'vara de financiera',
    meaning:
      'los cortes de banca. En una financiera el apalancamiento ES el negocio, así que la mayoría de las métricas se apagan con su motivo y las pocas que aplican se rebandean.',
  },
  {
    term: 'vara de la tabla',
    meaning:
      'el corte guardado en la base difiere del que el motor calcularía hoy. Manda el guardado, porque es el que se usó al analizar.',
  },
  {
    term: 'calibración anterior',
    meaning:
      'el análisis se hizo con una calibración que ya no está vigente. Sus colores no son comparables con los de un análisis nuevo.',
  },
];

/**
 * El histórico de análisis y su comparador, en lenguaje del usuario.
 *
 * Vive aquí, y no en la pantalla que lo pinta, porque lo dicen DOS sitios: el
 * texto del propio selector y la sección de esta guía. Escrito dos veces, el
 * día que el comparador cambie de reglas una de las dos versiones seguirá
 * prometiendo las de antes — y la que miente es la que nadie contrasta con la
 * pantalla que tiene al lado.
 */
export const RUN_HISTORY_COPY = {
  /** Qué es la lista. */
  intro:
    'Cada análisis es una foto: se conserva tal y como se calculó, con el motor y los cortes de aquel día. No se recalcula nunca.',
  /** Qué hace pulsar la fecha. */
  open: 'Pulsa la fecha para ABRIR ese análisis: cambia todo el informe de arriba.',
  /** Qué hace pulsar «comparar». Sólo web: en móvil no hay selector de base. */
  compare:
    'Pulsa «comparar» para contrastar el que estás viendo contra ése. Debajo aparece qué se ha movido entre los dos.',
  /**
   * La misma idea SIN nombrar el control, para la guía.
   *
   * La guía la renderizan las dos apps y móvil no tiene selector de base
   * —contrasta siempre con el inmediatamente anterior—, así que la frase de
   * web prometería ahí un botón que no existe.
   */
  compareConcept:
    'La comparación contrasta el análisis que estás viendo con otro guardado: en la web eliges cuál con «comparar»; en el móvil, con el inmediatamente anterior.',
  /** Qué se lista en la comparación. */
  contents:
    'Se listan el perfil (Conservador / Vigilar / Evitar), el veredicto del dividendo, las cuatro preguntas —su color y si estaban auditadas—, los ocho scores forenses, las métricas que cruzan un corte, las banderas que se encienden o se apagan, y las reexpresiones que la SEC registró entre las dos fechas.',
  /** Qué significa el ⚠ de una fila. */
  incomparable:
    'Un análisis marcado con ⚠ se calculó con otro motor u otra calibración. Al compararlo sólo se dirá qué cambió del MÉTODO, y ni un solo cambio de la empresa: un corte que se mueve no es un negocio que empeora, y presentarlos juntos lleva justo a la conclusión contraria.',
} as const;

export const REPORT_GUIDE: readonly GuideSection[] = [
  {
    key: 'colors',
    title: 'Los colores',
    intro:
      'Un color es el resultado de comparar un número con un corte publicado, no una opinión. Un valor SIN color no es un aprobado: es que el motor no tiene una vara absoluta que aplicarle.',
    entries: [
      ...BANDS.map((band) => ({ term: bandLabel(band), meaning: BAND_MEANING[band] })),
      {
        term: bandLabel(null),
        meaning:
          'el número se enseña pero no se juzga. Pasa cuando la métrica no aplica a este tipo de empresa, o cuando no hay corte calibrado.',
      },
    ],
  },
  {
    key: 'absences',
    title: 'Cuando falta un dato',
    intro:
      'Un hueco NUNCA es un cero. El informe distingue tres ausencias distintas y las dice por separado, porque «el emisor no lo publica», «no se pudo calcular» y «la pregunta no se plantea aquí» llevan a decisiones opuestas.',
    entries: TEXT_LEGEND.map(toEntry),
  },
  {
    key: 'marks',
    title: 'Las marcas junto a un número',
    intro:
      'Acompañan a un valor que SÍ existe y dicen de dónde salió. Un número derivado o estimado vale menos que uno publicado, y el informe no los presenta como lo mismo.',
    entries: MATRIX_LEGEND.map(toEntry),
  },
  {
    key: 'evidence',
    title: 'Por qué una pregunta puede salir sin color',
    intro:
      'Las cuatro preguntas del veredicto sólo se pintan de color cuando se han podido auditar. Hay tres formas de no poder, y se distinguen: colapsarlas convertiría un «no lo sé» en un verde.',
    entries: (Object.keys(EVIDENCE_MEANING) as (keyof typeof EVIDENCE_MEANING)[]).map((key) => ({
      term: EVIDENCE_LABEL[key],
      meaning: EVIDENCE_MEANING[key],
    })),
  },
  {
    key: 'origin',
    title: 'De dónde sale cada corte',
    intro:
      'Junto a cada corte se dice con qué vara se está midiendo. El mismo número puede ser verde con una y rojo con otra, así que sin esa etiqueta el color no es auditable.',
    entries: ORIGIN_ENTRIES,
  },
  {
    key: 'order',
    title: 'En qué orden leerlo',
    intro:
      'El informe no se lee de arriba abajo: se lee desde el Veredicto hacia atrás. Cada señal enlaza con la fila que la produce, así que la ruta natural es titular → pregunta → señal → matriz.',
    entries: [
      {
        term: 'Veredicto',
        meaning:
          'el titular, las cuatro preguntas con su evidencia, y qué miraría a continuación. Es el único sitio donde se dice a qué distancia del corte está cada señal.',
      },
      {
        term: 'Ratios · Evolución · Forense · Dividendo',
        meaning:
          'el detalle que sostiene cada respuesta, en matriz métrica × ejercicio. Tocar la etiqueta de una fila abre qué mide y cómo se lee.',
      },
      {
        term: 'Estados',
        meaning:
          'las cuentas tal como las publica el emisor, con la marca de qué partidas no venían y se dedujeron. Es el suelo de todo lo demás.',
      },
    ],
  },
  {
    key: 'why',
    title: 'Por qué el veredicto dice lo que dice',
    intro:
      'El sello no es una nota media de las cuatro preguntas: sale de reglas fijas sobre los scores forenses y la bandera del dividendo. La card «Por qué este veredicto» las enseña todas, cumplidas o no, con el número que las hace ciertas o falsas.',
    entries: [
      {
        term: 'se cumple',
        meaning:
          'la afirmación de esa línea es cierta en este análisis. En la lista de «Evitar» eso es lo que dispara el sello; en la de «Conservador», que están redactadas en negativo, es lo que falta para conseguirlo.',
      },
      {
        term: 'sin poder comprobar',
        meaning:
          'no hay dato para afirmarla ni para negarla, y al lado se dice por qué. No cuenta como superada: el verde se gana, no se hereda de un hueco.',
      },
      {
        term: 'decidió el veredicto',
        meaning:
          'esa señal es la que hizo cierta una condición de «Evitar». No es lo mismo que estar en rojo: una señal puede teñir su pregunta sin estar en la matriz del sello.',
      },
      {
        term: '¿Puntúa?',
        meaning:
          'si la señal contó para el color de su pregunta. Un «no» NO significa que esté bien: significa que no pudo contar, y la fila dice por qué.',
      },
    ],
  },
  {
    key: 'comparison',
    title: 'Los análisis guardados y qué compara',
    intro: `${RUN_HISTORY_COPY.intro} ${RUN_HISTORY_COPY.open}`,
    entries: [
      {
        term: 'comparar dos análisis',
        meaning: `${RUN_HISTORY_COPY.compareConcept} ${RUN_HISTORY_COPY.contents}`,
      },
      { term: '⚠ junto a «comparar»', meaning: RUN_HISTORY_COPY.incomparable },
      {
        term: 'nada se ha movido',
        meaning:
          'los dos análisis dicen lo mismo. Con dos ejecuciones del mismo día sobre los mismos ejercicios es lo esperable: la comparación cobra sentido cuando el emisor publica un cierre nuevo o reexpresa uno anterior.',
      },
    ],
  },
];

/**
 * Lo que el informe NO cubre, declarado en voz alta (PHASE-44.24.E).
 *
 * Compartido porque lo pintan tres sitios: el veredicto de web, el de móvil y
 * el dictamen imprimible. Una copia por sitio es cómo se llega a que la versión
 * impresa prometa un alcance distinto del que la pantalla declara.
 */
export const REPORT_SCOPE: readonly GuideEntry[] = [
  {
    term: 'Valoración',
    meaning:
      'ni PER, ni precio/ventas, ni precio/valor contable, ni precio/caja libre, ni EV/EBITDA, ni descuento de dividendos. Todos necesitan precio de mercado, y el motor no lo recibe a propósito: un score que se mueve con la cotización no sería reproducible al reejecutar un análisis antiguo.',
  },
  {
    term: 'Comparación con el sector',
    meaning: 'el sector sólo elige umbrales; no hay fuente de múltiplos de comparables.',
  },
  {
    term: 'Reexpresiones',
    meaning: 'se detectan y se listan aparte, pero todavía no entran en el dictamen.',
  },
  {
    term: 'Retribución de directivos y calendario de vencimientos',
    meaning:
      'viven en el proxy statement y en las notas, no en el 10-K estructurado que se ingiere.',
  },
];

function toEntry(entry: MarkEntry): GuideEntry {
  return { term: entry.glyph, meaning: entry.title };
}
