/**
 * Fechas CIVILES: el mes corto en castellano y el rango de dos días.
 *
 * Una fecha civil («14 de agosto de 2026») no es un instante: es lo que pone en
 * el calendario. Por eso nada de este módulo construye un `Date` — pasar un
 * day-string por `Date` lo somete al huso del dispositivo y desplaza el día en
 * cualquier huso ≠ UTC. Se formatea sobre las cadenas.
 *
 * Por qué existe, y por qué la tabla de meses NO sale de `Intl`:
 *
 * 1. `Intl.DateTimeFormat('es-ES', { month: 'short' })` depende del build de
 *    ICU. En el Node de este repo devuelve `sept` para septiembre (CLDR 42+),
 *    donde el resto de la app dice `sep`. Septiembre era el ÚNICO mes que
 *    discrepaba, y discrepaba precisamente porque nadie había comparado las dos
 *    grafías: el chart mensual de móvil pintaba «Sept 2026» y el titular del
 *    período, «sep», en la misma pantalla.
 * 2. Hermes (móvil) no comparte el ICU del navegador: la misma llamada puede
 *    devolver la forma con punto (`ago.`) o caer al inglés según plataforma.
 * 3. Cuando el texto ES el contrato, el formato no puede depender del motor.
 *
 * Esta es la ÚNICA tabla de meses cortos de `@crisol/ui` y la única de la que
 * deben salir estas etiquetas: `formatMonthLabel` (`format.ts`), el titular del
 * ciclo (`cycle-copy.ts`) y el caption de rango de los charts consumen todas de
 * aquí. Había 13 tablas repartidas por las apps antes de esto; cada copia es un
 * sitio más donde arreglar una errata y olvidarse de los otros doce.
 */

/** Meses abreviados en castellano, en minúscula. Fuente única del paquete. */
export const SHORT_MONTHS_ES = [
  'ene',
  'feb',
  'mar',
  'abr',
  'may',
  'jun',
  'jul',
  'ago',
  'sep',
  'oct',
  'nov',
  'dic',
] as const;

/** Guion de rango tipográfico (–, U+2013), no el menos del teclado (-). */
export const RANGE_DASH = '–';

const DAY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

export interface CivilDay {
  year: number;
  month: number;
  day: number;
}

/** Mes 1-12 → `ago`. Fuera de rango devuelve cadena vacía. */
export function shortMonthEs(month: number): string {
  return SHORT_MONTHS_ES[month - 1] ?? '';
}

/** `YYYY-MM-DD` → fecha civil, o `null` si no lo es. */
export function parseCivilDay(value: string): CivilDay | null {
  const match = DAY_PATTERN.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (month < 1 || month > 12) return null;
  if (day < 1 || day > 31) return null;
  return { year, month, day };
}

/**
 * Un rango de días legible: **«14 ago – 13 sep 2026»**.
 *
 * El año se dice una vez cuando el rango empieza y acaba en el mismo, y DOS
 * veces cuando cruza diciembre («14 dic 2026 – 13 ene 2027»): ahí el año no es
 * decoración, es la mitad de la información.
 *
 * Lo usan el caption del rango libre de los charts y el subtítulo del ciclo
 * (`cycleRangeLabel`). Es LA MISMA pregunta —«¿qué dos fechas abarca esto?»— y
 * estuvo escrita dos veces, en la misma pantalla de Análisis, produciendo hoy
 * la misma cadena carácter a carácter: dos copias que sólo se notan el día que
 * alguien corrige una (lección PHASE-46: duplicar una declaración no falla
 * cuando la escribes, falla cuando actualizas sólo una).
 *
 * Con un día ilegible devuelve las cadenas en crudo: son fechas, así que
 * enseñarlas tal cual no inventa nada.
 */
export function dayRangeLabel(fromDay: string, toDay: string): string {
  const from = parseCivilDay(fromDay);
  const to = parseCivilDay(toDay);
  if (!from || !to) return `${fromDay} ${RANGE_DASH} ${toDay}`;

  const left = `${from.day} ${shortMonthEs(from.month)}`;
  const right = `${to.day} ${shortMonthEs(to.month)}`;
  if (from.year === to.year) {
    return `${left} ${RANGE_DASH} ${right} ${to.year}`;
  }
  return `${left} ${from.year} ${RANGE_DASH} ${right} ${to.year}`;
}
