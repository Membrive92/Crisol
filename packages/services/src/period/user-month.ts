/**
 * PHASE-47 — «El mes del usuario»: UNA declaración de qué significa `month`.
 *
 * Hasta aquí el ciclo era un preset paralelo: el toggle ofrecía «Mes» y «Mi
 * ciclo» como cosas distintas, y cada pantalla decidía por su cuenta —con un
 * `period === 'cycle' ? cycleBoundsForAnchor(...) : boundsForAnchor(...)`
 * repetido en seis sitios— qué aritmética aplicar. Dos vocabularios para la
 * misma pregunta, y seis oportunidades de que uno se quedara sin actualizar.
 *
 * Ahora el día de inicio REDEFINE el mes. Si el usuario declaró que el suyo
 * empieza el 12, «Mes» va del 12 al 11 en toda la app; si no declaró nada, del
 * 1 al último, como siempre. El toggle vuelve a ser «Mes / Año / Personalizado»
 * y no hay nada que recordar pulsar.
 *
 * Lo que este módulo NO hace: aritmética. Toda vive donde vivía —
 * `cycle-period.ts` para el ciclo, `calendar-period.ts` y `debt-period.ts` para
 * el calendario—. Aquí sólo se decide CUÁL de las dos aplica, y se decide una
 * vez.
 */

import type { PeriodKey } from '@crisol/types';

import { boundsForAnchor, calendarPeriodFor } from './calendar-period';
import { boundsForCustomRange } from './debt-period';
import {
  cycleAnchorContaining,
  cycleBoundsForAnchor,
  isValidCycleStartDay,
} from './cycle-period';

/**
 * ¿El mes de este usuario corta por un ciclo propio?
 *
 * Guarda por VERDAD sobre el valor, nunca `!= null` (lección PHASE-47.E):
 * mientras el perfil carga el campo no existe, y con un backend anterior a la
 * columna llega AUSENTE — y `undefined !== null` es cierto, así que la
 * comparación estricta daría «sí hay ciclo» y se pediría un corte que el
 * servidor no conoce. `isValidCycleStartDay` rechaza por la misma puerta el
 * `undefined`, el `null`, el `0`, el `29` y un `'12'` que llegara como cadena.
 *
 * El día 1 cuenta como ciclo y es correcto que lo haga: su aritmética degenera
 * EXACTAMENTE en el mes natural (invariante 2 de `cycle-period.ts`), así que
 * ambas ramas dan el mismo resultado y no hace falta un caso especial.
 */
export function userMonthIsCycle(cycleStartDay: unknown): cycleStartDay is number {
  return isValidCycleStartDay(cycleStartDay);
}

/**
 * El día de corte que aplica a ESTE período, o `null` si corta por calendario.
 *
 * Devuelve el día en vez de un booleano porque es lo que el consumidor
 * necesita después: con `const esCiclo = ... && userMonthIsCycle(dia)` el type
 * guard estrecha dentro de la condición y se pierde en la línea siguiente, así
 * que cada llamada acababa arrastrando un `dia ?? 1` — un valor por defecto
 * que afirma un corte que nadie declaró (lección PHASE-44.11). Con `number |
 * null` el estrechamiento sobrevive y no hay default que inventar.
 *
 * Sólo `month` puede cortar por ciclo: `year` es calendario y `custom` trae
 * sus propios extremos.
 */
export function cycleDayForPeriod(
  period: PeriodKey,
  cycleStartDay?: number | null | undefined,
): number | null {
  if (period !== 'month') return null;
  return userMonthIsCycle(cycleStartDay) ? cycleStartDay : null;
}

/**
 * Bounds del AÑO del usuario que abre en `anchor`: del día `D` de enero al
 * `D − 1` de enero del año siguiente.
 *
 * **Su año se desplaza igual que su mes, y por la misma razón.** Aplicar el
 * corte a los meses y dejar el año en el calendario produce una vista
 * incoherente: el año natural 2026 empieza el 1 de enero, pero ese día
 * pertenece al período que abrió el 12 de diciembre, así que la serie tenía
 * que incluir un bucket «Dic 25» para no perder los días 1–11 de enero. El
 * usuario lo dijo mejor: «si estoy viendo gastos de 2026, no debería salir ese
 * diciembre de 2025».
 *
 * Con el año desplazado no hay bucket huérfano: los doce períodos que abren en
 * 2026 cubren su año entero, de principio a fin y sin huecos. La contrapartida,
 * dicha en voz alta: los días 1–11 de enero de 2026 pertenecen a su año 2025,
 * porque están en el período que abrió el 12 de diciembre. Es la misma
 * consecuencia que ya acepta a nivel de mes.
 */
export function userYearBounds(
  anchor: string,
  cycleStartDay?: number | null | undefined,
): { dateFrom: string; dateTo: string } {
  const year = Number(anchor.slice(0, 4));
  if (!userMonthIsCycle(cycleStartDay)) {
    return boundsForAnchor('year', `${year}-01`);
  }
  const desde = cycleBoundsForAnchor(cycleStartDay, `${year}-01`);
  const hasta = cycleBoundsForAnchor(cycleStartDay, `${year}-12`);
  return { dateFrom: desde.dateFrom, dateTo: hasta.dateTo };
}

export interface UserPeriodOptions {
  /** Día en que empieza el mes del usuario, o nada si usa el mes natural. */
  cycleStartDay?: number | null | undefined;
  /** Extremos del rango libre, sólo con `period === 'custom'`. */
  customFrom?: string | null | undefined;
  customTo?: string | null | undefined;
}

/**
 * Bounds ISO del período, eligiendo la aritmética que toca.
 *
 * Es el único sitio del frontend que decide entre «mes natural» y «mes del
 * usuario». Sustituye a las seis copias de ese ternario que había repartidas
 * por las pantallas, y que es como divergieron el Dashboard —que afirmaba
 * recibir sus bounds ya en ciclos— y la query que nunca los pedía así.
 */
export function boundsForUserPeriod(
  period: PeriodKey,
  anchor: string,
  opts: UserPeriodOptions = {},
): { dateFrom: string; dateTo: string } {
  const { cycleStartDay, customFrom, customTo } = opts;
  if (period === 'custom' && customFrom && customTo) {
    return boundsForCustomRange(customFrom, customTo);
  }
  if (period === 'month' && userMonthIsCycle(cycleStartDay)) {
    return cycleBoundsForAnchor(cycleStartDay, anchor);
  }
  if (period === 'year') {
    // El año del usuario también se desplaza; sin día declarado degenera en el
    // año natural exacto.
    return userYearBounds(anchor, cycleStartDay);
  }
  return boundsForAnchor(calendarPeriodFor(period), anchor);
}

/**
 * Ancla (`YYYY-MM`) del período que CONTIENE `day`, en la unidad del usuario.
 *
 * Existe por un fallo concreto que el rediseño destapa: hasta ahora el ciclo
 * exigía un clic, y ese clic reanclaba al ciclo en curso. Al pasar a
 * gobernarlo el perfil, ese reanclaje desaparecía con el manejador — y del día
 * 1 al D−1 la pantalla abriría un período que **aún no ha empezado** (con
 * corte el 12, el día 5 de agosto el mes en curso es el que abrió el 12 de
 * julio, no el que abrirá el 12 de agosto).
 */
export function userMonthAnchorContaining(
  day: string,
  cycleStartDay?: number | null | undefined,
): string {
  if (!userMonthIsCycle(cycleStartDay)) return day.slice(0, 7);
  return cycleAnchorContaining(day, cycleStartDay);
}
