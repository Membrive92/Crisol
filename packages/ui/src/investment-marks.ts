/**
 * Las marcas de una celda del informe, declaradas UNA vez (PHASE-44.24.E).
 *
 * Estaban definidas en **tres** sitios —`PROVENANCE_MARK`/`PROVENANCE_TITLE` en
 * `investment-metric-rows.ts`, `provenanceMark()`/`provenanceTitle()` en
 * `investment-statement-rows.ts`, y literales sueltos (`'*'`, `'≠'`, `'•'`) en
 * los dos— y sus títulos **ya divergían**: el mismo `·` era «cero imputado: el
 * filing no publica el concepto» en un sitio y «el filing no etiqueta el
 * concepto» en el otro. Publicar y etiquetar no son lo mismo, y el usuario no
 * tiene forma de saber cuál de las dos frases está leyendo.
 *
 * Y hay una consecuencia peor que la divergencia: sólo dos de las cinco
 * pestañas de matriz pintaban leyenda, así que en tres de ellas un `†` o un `≈`
 * salían sin explicación. Una marca sin leyenda es ruido tipográfico.
 *
 * Cada entrada lleva el glifo Y su título. La leyenda se DERIVA de aquí, así
 * que una marca nueva aparece explicada en las cinco pestañas sin tocarlas.
 */

export interface MarkEntry {
  /** El carácter que se pinta junto al número. */
  glyph: string;
  /** Qué significa. Es a la vez el `title` de la celda y la línea de leyenda. */
  title: string;
}

export const MARK = {
  /** Se pudo calcular, pero con un input degradado. */
  approximation: {
    glyph: '*',
    title:
      'calculada con un input degradado (normalmente el primer ejercicio, ' +
      'sin año anterior con el que promediar)',
  },
  /** El filing no la publica: sale de otras partidas por identidad contable. */
  derived: {
    glyph: '†',
    title:
      'derivada de otras partidas por una identidad contable: el emisor no la ' +
      'publica, pero se deduce sin margen de interpretación',
  },
  /** El filing no publica el concepto y la ingesta lo supone cero. */
  imputed_zero: {
    glyph: '·',
    title:
      'cero imputado: el filing no publica el concepto y la ingesta lo supone ' +
      'cero. Probablemente no exista, pero eso no se ha comprobado',
  },
  /** Un proxy razonable, no un dato publicado. */
  estimated: {
    glyph: '≈',
    title:
      'proxy estimado: la app aproxima el concepto con otro cercano, porque el ' +
      'emisor no publica ninguno equivalente',
  },
  /** Cortes US-GAAP aplicados a cuentas que no lo son. */
  uncalibrated: {
    glyph: '≠',
    title: 'los cortes son US-GAAP y estas cuentas no lo son: se aplican sin recalibrar',
  },
  /** El ejercicio del que sale el dictamen. */
  verdict_year: {
    glyph: '•',
    title:
      'ejercicio que alimenta el dictamen: el veredicto se decide con estos ' +
      'números, y los demás años están para ver de dónde vienen',
  },
} as const satisfies Record<string, MarkEntry>;

export type MarkKey = keyof typeof MARK;

/**
 * Las marcas, para pintar la leyenda de una matriz.
 *
 * Derivada, no escrita a mano: es lo que hace que añadir una marca no pueda
 * dejar una pestaña sin explicarla.
 */
export const MATRIX_LEGEND: readonly MarkEntry[] = Object.values(MARK);

/**
 * Los estados que NO son una marca sino un texto en la propia celda.
 *
 * Van aparte a propósito: un `—` no es un glifo que acompaña a un número, es lo
 * que se pinta EN LUGAR del número, y colapsarlos haría creer que un hueco es
 * una anotación sobre un valor que existe.
 */
export const TEXT_LEGEND: readonly MarkEntry[] = [
  { glyph: '—', title: 'no se pudo calcular: bajo la etiqueta se explica por qué' },
  { glyph: 'n/a', title: 'la pregunta no se plantea en este caso; el motivo, bajo la etiqueta' },
  {
    glyph: 'gris',
    title:
      'un valor sin banda: el motor no tiene un corte absoluto que aplicar. ' +
      'No significa que esté sano',
  },
];

/**
 * Lo que se pinta al pie de CUALQUIER matriz del informe.
 *
 * Los estados de texto van primero porque son sobre la celda entera («no hay
 * número») y las marcas después, que anotan un número que sí existe. La
 * distinción se explica en la guía «Cómo leer este informe», que importa las
 * dos listas por separado; aquí se pasan juntas porque una matriz puede
 * contener las dos cosas y separar las leyendas obligaría a cada pestaña a
 * decidir cuál le toca — que es exactamente cómo se llegó a que tres de las
 * cinco no pintaran ninguna.
 */
export const REPORT_LEGEND: readonly MarkEntry[] = [...TEXT_LEGEND, ...MATRIX_LEGEND];

/** El glifo de una procedencia, o `undefined` si es la normal (`sourced`). */
export function provenanceMarkOf(provenance: string | null | undefined): MarkEntry | undefined {
  if (provenance === 'derived') return MARK.derived;
  if (provenance === 'imputed_zero') return MARK.imputed_zero;
  if (provenance === 'estimated') return MARK.estimated;
  return undefined;
}
