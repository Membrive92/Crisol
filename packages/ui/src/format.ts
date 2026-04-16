/**
 * Formatters compartidos para importes, fechas y categorías.
 * Lógica pura sin dependencias de plataforma.
 */

/**
 * Formatea un importe (string decimal) como moneda localizada.
 * Usa `Intl.NumberFormat` que funciona en Node, navegador y Hermes.
 */
export function formatAmount(amount: string, currency = 'EUR', locale = 'es-ES'): string {
  const value = Number(amount);
  if (!Number.isFinite(value)) return amount;
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
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
