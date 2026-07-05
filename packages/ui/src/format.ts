/**
 * Formatters compartidos para importes, fechas y categorías.
 * Lógica pura sin dependencias de plataforma.
 */

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
 */
export function toDateInputValue(isoString: string): string {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return '';
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
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
 */
export function formatMonthLabel(yearMonth: string, locale = 'es-ES'): string {
  const match = /^(\d{4})-(\d{2})$/.exec(yearMonth);
  if (!match) return yearMonth;
  const [, year, month] = match;
  const date = new Date(Number(year), Number(month) - 1, 1);
  if (Number.isNaN(date.getTime())) return yearMonth;
  const label = new Intl.DateTimeFormat(locale, {
    month: 'short',
    year: 'numeric',
  }).format(date);
  return label.charAt(0).toUpperCase() + label.slice(1);
}
