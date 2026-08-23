/**
 * C0 (ciclo definido por el usuario) — Aritmética PURA de los períodos de
 * CALENDARIO (`month` / `year`), compartida por web y móvil.
 *
 * Antes de C0 esto vivía duplicado y DIVERGIDO: `boundsForAnchor` en
 * `apps/web/components/analysis/stitch-period-toggle.tsx` (UTC, con ancla) y
 * `rangeForPeriod` en `apps/mobile/components/dashboard/period-toggle.tsx`
 * (hora LOCAL y siempre «ahora», sin ancla). Con meses enteros la divergencia
 * casi no asomaba; con un corte día-exacto por ciclo, web y móvil cortarían en
 * instantes distintos. Aquí queda UNA sola definición, en UTC — que es como
 * persiste `occurred_at` y como corta el backend.
 *
 * `cycle` NO entra aquí a propósito: no es un período de calendario. Su
 * aritmética vive en `cycle-period.ts` y la firma de `boundsForAnchor` la
 * excluye por tipo (no acepta `PeriodKey`, sino `'month' | 'year'`), para que
 * pasarle un ciclo sea un error de compilación y no un rango silenciosamente
 * equivocado.
 */

import type { PeriodKey } from '@crisol/types';

/**
 * Granularidad de CALENDARIO de un período, para los helpers que sólo saben de
 * meses y años (`boundsForAnchor`, `stepAnchor`, `clampAnchor`).
 *
 * `custom` cae en `year` porque un rango libre no navega y el año es la
 * ventana más amplia y menos sorprendente para acotar sus flechas.
 *
 * PHASE-47 — ya no existe un `cycle` que degradar: el ciclo del usuario ES el
 * período `month`, y quién elige entre `boundsForAnchor` y
 * `cycleBoundsForAnchor` es el llamante, mirando si hay día declarado. Esta
 * función sólo responde «¿mes o año?», que es una pregunta de granularidad y
 * no de aritmética.
 */
export function calendarPeriodFor(period: PeriodKey): 'month' | 'year' {
  return period === 'year' || period === 'custom' ? 'year' : 'month';
}

/**
 * PHASE-34 — Rango de fechas ISO `[inicio, fin]` del período (mes / año) que
 * CONTIENE el mes `anchor` (`YYYY-MM`).
 *
 * Normaliza internamente al primer mes del período, así que da igual si el
 * ancla es el mes en curso (p. ej. `2026-06` con `year` → todo 2026) o ya el
 * inicio.
 *
 * AUDIT-2026-07 (LOW): los límites se construyen en UTC (`Date.UTC`), igual
 * que el TimeSelector de /transactions. Antes usaba `new Date(año, mes, día)`
 * en hora LOCAL del navegador y emitía `toISOString()`, lo que en Europe/Madrid
 * desplazaba la frontera 1-2 h (una tx del día 1 a las 00:00 podía caer en el
 * mes anterior). Con UTC-midnight el rango coincide con el criterio del backend.
 */
export function boundsForAnchor(
  period: 'month' | 'year',
  anchor: string,
): { dateFrom: string; dateTo: string } {
  const parts = anchor.split('-');
  const year = Number(parts[0]);
  const month = Number(parts[1]); // 1-12
  const startMonthIdx = period === 'month' ? month - 1 : 0; // year
  const monthsInPeriod = period === 'month' ? 1 : 12;
  const start = new Date(Date.UTC(year, startMonthIdx, 1));
  const end = new Date(Date.UTC(year, startMonthIdx + monthsInPeriod, 0, 23, 59, 59));
  return { dateFrom: start.toISOString(), dateTo: end.toISOString() };
}
