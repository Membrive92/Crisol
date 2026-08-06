import type { MetricDefinition, MetricUnit } from '@crisol/types';

/**
 * Formateo de valores del engine POR UNIDAD (PHASE-44.9).
 *
 * Antes existía un único `formatMetricValue` que hacía `toLocaleString` a secas,
 * así que un margen del 42 % se leía `0,42`, un DSO de 45 días `45` y una
 * cobertura de 6,8 veces `6,8` — tres escalas distintas presentadas igual. La
 * unidad la declara el catálogo del engine; aquí sólo se aplica.
 */

const DECIMALS: Record<MetricUnit, number> = {
  percent: 1,
  times: 2,
  days: 0,
  years: 1,
  pp: 2,
  score: 2,
  count: 0,
  currency_per_share: 2,
};

function toNumber(value: string | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function decimal(value: number, digits: number): string {
  return value.toLocaleString('es-ES', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/**
 * Un valor del engine, con su escala.
 *
 * @param value - string decimal tal y como llega de la API (nunca `number`).
 * @param unit - la unidad declarada por el catálogo. Sin catálogo cargado se
 *   pasa `undefined` y se cae a un formato neutro — que es peor, pero honesto.
 */
export function formatMetricValue(
  value: string | null | undefined,
  unit: MetricUnit | undefined,
): string {
  const n = toNumber(value);
  if (n === null) return '—';
  if (unit === undefined) return decimal(n, 2);
  const digits = DECIMALS[unit];
  switch (unit) {
    case 'percent':
      return `${decimal(n * 100, digits)} %`;
    case 'times':
      return `${decimal(n, digits)}×`;
    case 'days':
      return `${decimal(n, digits)} días`;
    case 'years':
      return `${decimal(n, digits)} años`;
    case 'pp':
      return `${decimal(n, digits)} pp`;
    case 'count':
    case 'score':
    case 'currency_per_share':
      return decimal(n, digits);
  }
}

/**
 * El corte contra el que se juzga una métrica, en lenguaje llano.
 *
 * Es la mitad del «por qué»: sin él, un chip ámbar es un color sin argumento.
 * Devuelve `null` cuando la métrica no tiene banda — y entonces quien pinta debe
 * decir «sin banda», nunca dejar el hueco (un `null` de banda NO es «sana»).
 */
export function formatThreshold(definition: MetricDefinition | undefined): string | null {
  if (!definition || definition.direction === null) return null;
  const unit = definition.unit;
  const fmt = (v: string | null) => (v === null ? null : formatMetricValue(v, unit));
  const lowAlarm = fmt(definition.low_alarm);
  const lowOk = fmt(definition.low_ok);
  const highOk = fmt(definition.high_ok);
  const highAlarm = fmt(definition.high_alarm);

  if (definition.direction === 'higher_better') {
    if (lowOk && lowAlarm) return `sano ≥ ${lowOk} · riesgo < ${lowAlarm}`;
    return lowOk ? `sano ≥ ${lowOk}` : null;
  }
  if (definition.direction === 'lower_better') {
    if (highOk && highAlarm) return `sano ≤ ${highOk} · riesgo > ${highAlarm}`;
    return highOk ? `sano ≤ ${highOk}` : null;
  }
  if (lowOk && highOk) return `sano entre ${lowOk} y ${highOk}`;
  return null;
}

/** Un importe de una partida canónica, en millones y con su signo. */
export function formatStatementAmount(value: string | null): string {
  const n = toNumber(value);
  if (n === null) return '—';
  const millions = n / 1_000_000;
  const digits = Math.abs(millions) >= 100 ? 0 : 1;
  return millions.toLocaleString('es-ES', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** Una variación interanual o un peso common-size, como porcentaje con signo. */
export function formatPercentDelta(value: string | null): string {
  const n = toNumber(value);
  if (n === null) return '—';
  const pct = n * 100;
  const sign = pct > 0 ? '+' : '';
  return `${sign}${decimal(pct, 1)} %`;
}

/** Un peso common-size (siempre positivo, sin signo). */
export function formatWeight(value: string | null): string {
  const n = toNumber(value);
  if (n === null) return '—';
  return `${decimal(n * 100, 1)} %`;
}
