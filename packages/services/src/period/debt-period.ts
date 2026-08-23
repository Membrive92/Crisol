/**
 * PHASE-30.8 — Helpers PUROS del navegador de período del módulo deuda.
 *
 * El "anchor" es un mes en formato `YYYY-MM` (cualquier mes dentro del
 * período objetivo); `range` fija la granularidad. Estas funciones son
 * puras (sin `Date`, sin efectos) y se comparten entre web y móvil para
 * que la navegación —etiqueta, paso ±1 período, clamp a los límites con
 * datos— sea idéntica en ambas plataformas. Tests en
 * `debt-period.test.ts`.
 *
 * PHASE-41 — Operan sólo sobre los períodos NAVEGABLES (`month`/`year`).
 * El período `custom` (rango libre `from/to`) NO navega —sin flechas, sin
 * anchor— y nunca llega a estos helpers; el compilador lo garantiza vía
 * `NavigableRange`. Se eliminó `quarter`.
 */

/** Períodos con navegación por flechas (subconjunto de `DebtTimeRange`). */
export type NavigableRange = 'month' | 'year';

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

const PERIOD_MONTHS: Record<NavigableRange, number> = {
  month: 1,
  year: 12,
};

/*
 * C0 — Los cuatro helpers de aritmética de meses (`parseAnchor`,
 * `formatAnchor`, `toIndex`, `fromIndex`) se EXPORTAN para que
 * `cycle-period.ts` los reutilice en vez de duplicarlos. Son la definición
 * única de "un ancla `YYYY-MM` es un índice absoluto de mes"; si el ciclo se
 * escribiera su propia copia, un cambio en una no movería la otra.
 * No se reexportan desde `src/index.ts`: son internos del módulo `period/`.
 */

export interface YearMonth {
  year: number;
  /** 1-12 */
  month: number;
}

export function parseAnchor(anchor: string): YearMonth {
  const [y, m] = anchor.split('-');
  return { year: Number(y), month: Number(m) };
}

export function formatAnchor({ year, month }: YearMonth): string {
  return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}`;
}

export function toIndex({ year, month }: YearMonth): number {
  return year * 12 + (month - 1);
}

export function fromIndex(idx: number): YearMonth {
  return { year: Math.floor(idx / 12), month: (idx % 12) + 1 };
}

/** Mes inicial (1-12) del período que contiene `month`. */
function periodStartMonth(range: NavigableRange, month: number): number {
  return range === 'month' ? month : 1; // year
}

/** Índice absoluto del PRIMER mes del período que contiene `anchor`. */
function periodStartIndex(range: NavigableRange, anchor: string): number {
  const { year, month } = parseAnchor(anchor);
  return toIndex({ year, month: periodStartMonth(range, month) });
}

/** Etiqueta legible del período: "Abril 2025" / "2025". */
export function periodLabel(range: NavigableRange, anchor: string): string {
  const { year, month } = parseAnchor(anchor);
  if (range === 'month') return `${SPANISH_MONTHS[month - 1]} ${year}`;
  return `${year}`;
}

/**
 * Avanza (`+1`) o retrocede (`-1`) un período completo, devolviendo el
 * mes inicial del nuevo período (`YYYY-MM`).
 */
export function stepAnchor(
  range: NavigableRange,
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
  range: NavigableRange,
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
  range: NavigableRange,
  anchor: string,
  availableFrom: string | null,
): boolean {
  if (!availableFrom) return false;
  return periodStartIndex(range, anchor) > periodStartIndex(range, availableFrom);
}

/** ¿Hay un período posterior con datos? (flecha ▶ habilitada). */
export function canStepNext(
  range: NavigableRange,
  anchor: string,
  availableTo: string | null,
): boolean {
  if (!availableTo) return false;
  return periodStartIndex(range, anchor) < periodStartIndex(range, availableTo);
}

/**
 * PHASE-41 — Convierte dos day-strings `YYYY-MM-DD` (rango libre `custom`) en
 * los bounds ISO `[from 00:00:00Z, to 23:59:59Z]` para las queries. En UTC a
 * propósito (no `new Date('YYYY-MM-DD')`, que interpreta local y desplaza el
 * día en Europe/Madrid). Compartido web+móvil para que el rango libre sea
 * idéntico en ambas plataformas.
 */
export function boundsForCustomRange(
  fromDay: string,
  toDay: string,
): { dateFrom: string; dateTo: string } {
  const [fy, fm, fd] = fromDay.split('-').map(Number);
  const [ty, tm, td] = toDay.split('-').map(Number);
  const start = new Date(Date.UTC(fy ?? 1970, (fm ?? 1) - 1, fd ?? 1, 0, 0, 0));
  const end = new Date(Date.UTC(ty ?? 1970, (tm ?? 1) - 1, td ?? 1, 23, 59, 59));
  return { dateFrom: start.toISOString(), dateTo: end.toISOString() };
}
