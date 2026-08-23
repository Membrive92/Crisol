/**
 * Formatters compartidos para importes, fechas y categorías.
 * Lógica pura sin dependencias de plataforma.
 */

import { shortMonthEs } from './civil-dates';

/**
 * Etiqueta corta del `kind` de una categoría — usada en dropdowns,
 * badges y resúmenes. Aceptamos `string` en lugar de `CategoryKind`
 * para evitar dependencia circular con `@crisol/types` (ADR 0001).
 */
export function formatCategoryKind(kind: string | null | undefined): string {
  if (kind === 'income') return 'Ingreso';
  return 'Gasto';
}

/**
 * Formatea un importe (string decimal) como moneda localizada.
 * Usa `Intl.NumberFormat` que funciona en Node, navegador y Hermes.
 *
 * Decimales: NO se fuerzan a 2. Dejamos que `Intl.NumberFormat` aplique
 * los dígitos canónicos ISO 4217 de cada divisa (EUR/USD → 2 con coma
 * es-ES; JPY → 0 decimales). Forzar `min/maxFractionDigits=2` rompía
 * monedas de 0 decimales (JPY 1.234 se pintaba como "1.234,00 ¥").
 *
 * Redondeo: el valor se parsea con `Number()` y lo redondea `Intl`
 * (HALF_UP/HALF_EVEN según el motor), mientras que el backend usa
 * Decimal ROUND_HALF_EVEN. Esto es formato de PRESENTACIÓN: en el
 * peor caso difiere 1 céntimo en el último dígito mostrado y nunca
 * altera el valor persistido. No reimplementamos HALF_EVEN aquí.
 */
export function formatAmount(amount: string, currency = 'EUR', locale = 'es-ES'): string {
  const value = Number(amount);
  if (!Number.isFinite(value)) return amount;
  const fmt = new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
  });
  // PHASE-37 — evita el "-0,00 €" cosmético: si el valor redondea a cero a la
  // precisión de la divisa (2 en EUR/USD, 0 en JPY), se formatea 0 positivo.
  const decimals = fmt.resolvedOptions().maximumFractionDigits ?? 2;
  const factor = 10 ** decimals;
  const safe = Math.round(value * factor) / factor === 0 ? 0 : value;
  return fmt.format(safe);
}

/**
 * Formatea una fecha ISO como `DD/MM/YYYY`.
 */
export function formatDate(isoString: string, locale = 'es-ES'): string {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  return new Intl.DateTimeFormat(locale, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(date);
}

/**
 * Convierte una fecha ISO a `YYYY-MM-DD` para inputs nativos de fecha.
 *
 * Lee en **UTC**, que es la zona en la que su pareja `fromDateInputValue`
 * escribe. Hasta PHASE-47 leía con getters LOCALES y escribía en UTC — una
 * asimetría que en Madrid tapaba el desfase del importador (una fila guardada
 * a las 23:00Z se leía como el día siguiente y al guardar quedaba corregida a
 * medianoche UTC, que es por lo que 21 filas de la base real están ya bien) y
 * que en cualquier huso NEGATIVO hace lo contrario: abrir el formulario de una
 * transacción y guardarlo sin tocar nada le restaría un día, cada vez.
 *
 * Es para leer una fecha CIVIL ya almacenada. Para «¿qué día es hoy?» —que sí
 * es una pregunta local— usa `todayDayStr()` de `@crisol/services`.
 */
/**
 * Formatea una fecha CIVIL como `DD/MM/YYYY`, leyéndola en UTC.
 *
 * Una fecha civil —el día que imprime el banco, el vencimiento de una cuota, la
 * fecha de un movimiento— no tiene hora ni zona: se almacena como medianoche
 * UTC (PHASE-47). Formatearla con `formatDate`, que usa la zona del navegador,
 * la deja bien en husos positivos y muestra el día ANTERIOR en los negativos,
 * porque las 00:00Z son la tarde del día previo en América.
 *
 * `formatDate` sigue siendo lo correcto para un INSTANTE real —cuándo se creó
 * un ticket, cuándo se usó una passkey—: ahí la hora local es la que el usuario
 * reconoce. Por eso son dos funciones y no un parámetro: la diferencia no es de
 * formato, es de qué representa el dato.
 */
export function formatCivilDate(isoString: string, locale = 'es-ES'): string {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  return new Intl.DateTimeFormat(locale, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date);
}

export function toDateInputValue(isoString: string): string {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return '';
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Convierte `YYYY-MM-DD` (input date) a ISO datetime en UTC (00:00).
 */
export function fromDateInputValue(value: string): string {
  if (!value) return new Date().toISOString();
  return new Date(`${value}T00:00:00Z`).toISOString();
}

/**
 * Formatea un mes `YYYY-MM` como etiqueta legible (`Abr 2026`).
 * Si el formato es inválido devuelve el valor original.
 *
 * El nombre del mes sale de la tabla de `civil-dates.ts` y NO de `Intl`. Con
 * `Intl` septiembre salía «Sept 2026» mientras el resto de la app decía «sep»
 * — misma pantalla, dos grafías del mismo mes— y en Hermes la forma no está
 * garantizada. Ver el porqué completo en `civil-dates.ts`.
 *
 * Ya NO admite `locale`: la etiqueta es castellano fijo. El parámetro existía y
 * ningún llamante lo usaba (los tres pasan sólo el mes); mantenerlo habría sido
 * prometer una traducción que la tabla no hace.
 */
export function formatMonthLabel(yearMonth: string): string {
  const match = /^(\d{4})-(\d{2})$/.exec(yearMonth);
  if (!match) return yearMonth;
  const [, year, month] = match;
  const monthNumber = Number(month);
  if (monthNumber < 1 || monthNumber > 12) return yearMonth;
  const label = shortMonthEs(monthNumber);
  return `${label.charAt(0).toUpperCase()}${label.slice(1)} ${year}`;
}
