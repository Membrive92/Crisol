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

// ----- Conversión de moneda (PHASE-8.2) -------------------------------------
//
// Las tasas se almacenan EUR→quote (ver módulo backend `currency`). Para
// convertir entre dos monedas cualesquiera se compone vía EUR:
//
//     amount(FROM → TO) = amount × rate(EUR→TO) / rate(EUR→FROM)
//
// Si una de las patas no aparece en el mapa devuelto por el backend, la
// conversión es "missing": el caller decide si pintar el original sin
// convertir + un badge, o esconder la fila.

export type RatesMap = Record<string, number>;

export interface ConvertAmountResult {
  value: number;
  rate: number;
  missing: boolean;
}

/**
 * Convierte un importe entre dos monedas usando un mapa EUR→quote.
 * - `from === to` → trivial, sin tasa.
 * - una pata es EUR → directa.
 * - ninguna es EUR → composición vía EUR.
 *
 * Devuelve `{ value, rate, missing }`. Cuando `missing` es true,
 * `value` es el importe original sin convertir y `rate` es 1.
 */
export function convertAmount(
  amount: number,
  fromCurrency: string,
  toCurrency: string,
  rates: RatesMap,
): ConvertAmountResult {
  const from = fromCurrency.toUpperCase();
  const to = toCurrency.toUpperCase();

  if (!Number.isFinite(amount)) {
    return { value: amount, rate: 1, missing: true };
  }
  if (from === to) {
    return { value: amount, rate: 1, missing: false };
  }

  // Si una pata es EUR ya es directa.
  if (from === 'EUR') {
    const rate = rates[to];
    if (!Number.isFinite(rate) || !rate) {
      return { value: amount, rate: 1, missing: true };
    }
    return { value: amount * rate, rate, missing: false };
  }
  if (to === 'EUR') {
    const rate = rates[from];
    if (!Number.isFinite(rate) || !rate) {
      return { value: amount, rate: 1, missing: true };
    }
    return { value: amount / rate, rate: 1 / rate, missing: false };
  }

  // Composición vía EUR — necesitamos las dos patas.
  const fromRate = rates[from];
  const toRate = rates[to];
  if (!Number.isFinite(fromRate) || !fromRate || !Number.isFinite(toRate) || !toRate) {
    return { value: amount, rate: 1, missing: true };
  }
  const composed = toRate / fromRate;
  return { value: amount * composed, rate: composed, missing: false };
}

export interface FormatConvertedResult {
  /** String listo para pintar — incluye prefijo `≈` si la conversión es real. */
  display: string;
  /** Texto del tooltip explicando origen + tasa. Vacío cuando `from === to`. */
  tooltip: string;
  /** Hay conversión real (ni `same` ni `missing`). */
  isApprox: boolean;
  /** No hay tasa disponible — el importe se muestra sin convertir. */
  isMissing: boolean;
}

/**
 * Formatea un importe con conversión a la moneda destino.
 *
 * - `from === to` → formato simple, sin prefijo `≈` ni tooltip.
 * - tasa disponible → `"≈ €1.234,56"` con tooltip
 *   `"USD 1.000,00 a 1,234567 EUR/USD el 2026-04-15"` (la fecha
 *   sólo aparece si `rateDate` se pasa).
 * - tasa no disponible → original sin convertir + tooltip `"sin tasa
 *   disponible"`. El caller puede usar `isMissing` para pintar un
 *   badge tonal en vez del prefijo.
 */
export function formatConverted(
  amount: string | number,
  fromCurrency: string,
  toCurrency: string,
  rates: RatesMap,
  locale = 'es-ES',
  rateDate?: string,
): FormatConvertedResult {
  const numeric = typeof amount === 'string' ? Number(amount) : amount;
  if (!Number.isFinite(numeric)) {
    return {
      display: typeof amount === 'string' ? amount : String(amount),
      tooltip: '',
      isApprox: false,
      isMissing: true,
    };
  }

  const from = fromCurrency.toUpperCase();
  const to = toCurrency.toUpperCase();

  if (from === to) {
    return {
      display: formatAmount(String(numeric), to, locale),
      tooltip: '',
      isApprox: false,
      isMissing: false,
    };
  }

  const { value, rate, missing } = convertAmount(numeric, from, to, rates);

  if (missing) {
    return {
      display: formatAmount(String(numeric), from, locale),
      tooltip: `Sin tasa ${from}→${to} disponible`,
      isApprox: false,
      isMissing: true,
    };
  }

  // Formato de la tasa: 6 decimales suelen ser suficientes para
  // monedas mayores; recortamos ceros finales para legibilidad.
  const rateLabel = rate.toFixed(6).replace(/\.?0+$/, '');
  const original = formatAmount(String(numeric), from, locale);
  const dateSuffix = rateDate ? ` el ${rateDate}` : '';
  const tooltip = `${original} a ${rateLabel} ${to}/${from}${dateSuffix}`;

  return {
    display: `≈ ${formatAmount(String(value), to, locale)}`,
    tooltip,
    isApprox: true,
    isMissing: false,
  };
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
