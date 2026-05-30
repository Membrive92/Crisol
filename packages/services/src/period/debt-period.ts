import type { DebtTimeRange } from '@crisol/types';

/**
 * PHASE-30.8 — Helpers PUROS del navegador de período del módulo deuda.
 *
 * El "anchor" es un mes en formato `YYYY-MM` (cualquier mes dentro del
 * período objetivo); `range` fija la granularidad. Estas funciones son
 * puras (sin `Date`, sin efectos) y se comparten entre web y móvil para
 * que la navegación —etiqueta, paso ±1 período, clamp a los límites con
 * datos— sea idéntica en ambas plataformas. Tests en
 * `debt-period.test.ts`.
 */

const SPANISH_MONTHS = [
  'Enero',
  'Febrero',
  'Marzo',
  'Abril',
  'Mayo',
  'Junio',
  'Julio',
  'Agosto',
  'Septiembre',
  'Octubre',
  'Noviembre',
  'Diciembre',
] as const;

const PERIOD_MONTHS: Record<DebtTimeRange, number> = {
  month: 1,
  quarter: 3,
  year: 12,
};

interface YearMonth {
  year: number;
  /** 1-12 */
  month: number;
}

function parseAnchor(anchor: string): YearMonth {
  const [y, m] = anchor.split('-');
  return { year: Number(y), month: Number(m) };
}

function formatAnchor({ year, month }: YearMonth): string {
  return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}`;
}

function toIndex({ year, month }: YearMonth): number {
  return year * 12 + (month - 1);
}

function fromIndex(idx: number): YearMonth {
  return { year: Math.floor(idx / 12), month: (idx % 12) + 1 };
}

/** Mes inicial (1-12) del período que contiene `month`. */
function periodStartMonth(range: DebtTimeRange, month: number): number {
  if (range === 'month') return month;
  if (range === 'quarter') return Math.floor((month - 1) / 3) * 3 + 1;
  return 1; // year
}

/** Índice absoluto del PRIMER mes del período que contiene `anchor`. */
function periodStartIndex(range: DebtTimeRange, anchor: string): number {
  const { year, month } = parseAnchor(anchor);
  return toIndex({ year, month: periodStartMonth(range, month) });
}

/** Etiqueta legible del período: "Abril 2025" / "Q2 2025" / "2025". */
export function periodLabel(range: DebtTimeRange, anchor: string): string {
  const { year, month } = parseAnchor(anchor);
  if (range === 'month') return `${SPANISH_MONTHS[month - 1]} ${year}`;
  if (range === 'quarter') return `Q${Math.floor((month - 1) / 3) + 1} ${year}`;
  return `${year}`;
}

/**
 * Avanza (`+1`) o retrocede (`-1`) un período completo, devolviendo el
 * mes inicial del nuevo período (`YYYY-MM`).
 */
export function stepAnchor(
  range: DebtTimeRange,
  anchor: string,
  direction: 1 | -1,
): string {
  const startIdx = periodStartIndex(range, anchor);
  return formatAnchor(fromIndex(startIdx + direction * PERIOD_MONTHS[range]));
}

/**
 * Normaliza `anchor` al inicio de su período y lo recorta al rango con
 * datos `[availableFrom, availableTo]` (ambos `YYYY-MM | null`).
 * Devuelve el mes inicial del período resultante (`YYYY-MM`). Sin
 * límites, sólo normaliza.
 */
export function clampAnchor(
  range: DebtTimeRange,
  anchor: string,
  availableFrom: string | null,
  availableTo: string | null,
): string {
  let idx = periodStartIndex(range, anchor);
  if (availableTo) idx = Math.min(idx, periodStartIndex(range, availableTo));
  if (availableFrom) idx = Math.max(idx, periodStartIndex(range, availableFrom));
  return formatAnchor(fromIndex(idx));
}

/** ¿Hay un período anterior con datos? (flecha ◀ habilitada). */
export function canStepPrev(
  range: DebtTimeRange,
  anchor: string,
  availableFrom: string | null,
): boolean {
  if (!availableFrom) return false;
  return periodStartIndex(range, anchor) > periodStartIndex(range, availableFrom);
}

/** ¿Hay un período posterior con datos? (flecha ▶ habilitada). */
export function canStepNext(
  range: DebtTimeRange,
  anchor: string,
  availableTo: string | null,
): boolean {
  if (!availableTo) return false;
  return periodStartIndex(range, anchor) < periodStartIndex(range, availableTo);
}
