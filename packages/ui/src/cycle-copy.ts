/**
 * Cómo se NOMBRA el ciclo del usuario — capa PURA compartida por web y móvil.
 *
 * El usuario declara el día en que empieza su mes (su día de cobro) y a partir
 * de ahí los períodos de presentación cortan por ahí. Este módulo es lo que las
 * dos apps tienen que decir IGUAL: el nombre del preset, el titular de un ciclo,
 * su rango explícito y el aviso de las tarjetas que siguen contando por mes
 * natural.
 *
 * Vive en `@crisol/ui` porque la línea entre «puro» y «renderizado» va DESPUÉS
 * del contenido (lección PHASE-44.13): si la etiqueta se escribiera una vez en
 * web y otra en móvil, acabarían nombrando el mismo ciclo de dos formas
 * distintas, y eso no lo nota nadie hasta comparar las dos pantallas a la vez.
 *
 * La ARITMÉTICA del ciclo NO está aquí: vive en
 * `packages/services/src/period/cycle-period.ts`. `@crisol/ui` no importa otros
 * paquetes internos (ADR-0001: sólo tokens y funciones puras, sin deps
 * internas), así que `cycleRangeLabel` recibe los dos días YA calculados en vez
 * de derivarlos del ancla. Por el mismo motivo los límites del ajuste (1–28) se
 * declaran allí, junto a su validación, y no se duplican aquí.
 *
 * El FORMATO de fechas civiles (la tabla de meses cortos, el rango de dos días)
 * tampoco está aquí: vive en `civil-dates.ts`, que es el módulo del paquete para
 * eso y del que consumen también `formatMonthLabel` y el caption de rango de los
 * charts. Este fichero sólo pone el vocabulario DEL CICLO.
 */

import { dayRangeLabel, shortMonthEs } from './civil-dates';

const ANCHOR_PATTERN = /^(\d{4})-(\d{2})$/;

/** `YYYY-MM` → año y mes, o `null` si no es un ancla de mes. */
function parseAnchor(anchor: string): { year: number; month: number } | null {
  const match = ANCHOR_PATTERN.exec(anchor);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (month < 1 || month > 12) return null;
  return { year, month };
}

/** El chip del preset en los selectores de período. Idéntico en web y móvil. */
export const CYCLE_PRESET_LABEL = 'Mi ciclo';

/**
 * El titular de un ciclo: **«Ciclo del 14 ago 2026»**.
 *
 * La etiqueta ancla el ciclo a su DÍA DE COBRO (decisión D1 del plan). Ni
 * «Agosto» a secas —que mentiría el 2 de septiembre, cuando el ciclo de agosto
 * sigue abierto, y volvería a producir los «no me cuadra» que esta feature
 * existe para matar— ni sólo el rango, que no identifica nada de un vistazo.
 *
 * @param cycleStartDay Día en que abre el ciclo (el ajuste del usuario).
 * @param anchor `YYYY-MM` del mes que ABRE el ciclo.
 *
 * Con una entrada que no se pueda leer devuelve `CYCLE_PRESET_LABEL`: decir
 * menos, nunca inventar una fecha. Un «Ciclo del NaN» o un mes fabricado se
 * leen como un dato real (lección PHASE-44.16: una frase falsa cuesta más que
 * un hueco, porque el hueco se pregunta y la frase se cree).
 */
export function cycleLabel(cycleStartDay: number, anchor: string): string {
  const parsed = parseAnchor(anchor);
  // El rango válido del ajuste (1–28) lo valida `packages/services`, que es
  // donde vive esa regla; aquí sólo se comprueba lo justo para no pintar basura.
  if (!parsed || !Number.isInteger(cycleStartDay) || cycleStartDay < 1) {
    return CYCLE_PRESET_LABEL;
  }
  return `Ciclo del ${cycleStartDay} ${shortMonthEs(parsed.month)} ${parsed.year}`;
}

/**
 * El rango explícito de un ciclo: **«14 ago – 13 sep 2026»**.
 *
 * Acompaña al titular en los displays que YA son de rango (el `RangeDisplay`
 * del TimeSelector, el subtítulo del navegador de período): el titular
 * identifica el ciclo por su cobro y el rango completo queda a la vista donde
 * ya había uno.
 *
 * El año se dice una vez cuando el ciclo empieza y acaba en el mismo
 * («14 ago – 13 sep 2026») y DOS veces cuando cruza diciembre
 * («14 dic 2026 – 13 ene 2027»): ahí el año no es decoración, es la mitad de la
 * información.
 *
 * @param fromDay Primer día del ciclo, `YYYY-MM-DD`.
 * @param toDay Último día del ciclo, `YYYY-MM-DD` (el día D−1 del mes
 *   siguiente: el intervalo del backend es cerrado por los dos extremos).
 *
 * Ambos llegan ya calculados desde `cycle-period.ts` — la aritmética del ciclo
 * no se duplica aquí. Y el formato sale de `dayRangeLabel` (`civil-dates.ts`),
 * que es la misma función que pinta el caption del rango libre en los charts:
 * las dos responden «¿qué dos fechas abarca esto?» y llegaron a estar escritas
 * por separado, produciendo la misma cadena, en la misma pantalla de Análisis.
 */
export function cycleRangeLabel(fromDay: string, toDay: string): string {
  return dayRangeLabel(fromDay, toDay);
}

/**
 * El aviso de las tarjetas que NO cortan por el ciclo del usuario.
 *
 * Lo llevan las que esta entrega deja en mes natural (proyección de fin de mes,
 * insights, la serie mensual de Deuda, la evolución de patrimonio) y se enseña
 * sólo con el preset activo. Dice dos cosas y las dos hacen falta: que ESA
 * tarjeta cuenta el mes de siempre, y que por eso sus cifras pueden no cuadrar
 * con el resto de la pantalla — porque a partir de aquí no cuadran A PROPÓSITO,
 * y una diferencia que nadie nombra se lee como un fallo.
 *
 * Una sola redacción para las dos apps: escrita dos veces, divergiría.
 */
export const NATURAL_MONTH_NOTICE =
  'Esta tarjeta cuenta el mes de siempre: del día 1 al último, no desde tu día ' +
  'de cobro. Por eso sus cifras pueden no cuadrar con las del resto de la pantalla.';
