import { afterEach, describe, expect, it, vi } from 'vitest';

import { boundsForAnchor, calendarPeriodFor } from './calendar-period';
import { currentMonthAnchor, dataMaxDayStr, dataMinDayStr, todayDayStr } from './day-strings';

describe('boundsForAnchor', () => {
  it('mes → [día 1 00:00:00Z, último día 23:59:59Z]', () => {
    const { dateFrom, dateTo } = boundsForAnchor('month', '2026-02');
    expect(dateFrom).toBe('2026-02-01T00:00:00.000Z');
    expect(dateTo).toBe('2026-02-28T23:59:59.000Z');
  });

  it('año → normaliza al 1 de enero, ignorando el mes del ancla', () => {
    const { dateFrom, dateTo } = boundsForAnchor('year', '2026-07');
    expect(dateFrom).toBe('2026-01-01T00:00:00.000Z');
    expect(dateTo).toBe('2026-12-31T23:59:59.000Z');
  });

  it('usa UTC (AUDIT-2026-07): el día 1 a las 00:00Z no cae en el mes anterior', () => {
    // Con `new Date(año, mes, día)` en hora LOCAL de Europe/Madrid, el
    // `toISOString()` del 1 de enero salía como 31-dic-22:00Z.
    expect(boundsForAnchor('month', '2026-01').dateFrom).toBe('2026-01-01T00:00:00.000Z');
    expect(boundsForAnchor('year', '2026-01').dateFrom).toBe('2026-01-01T00:00:00.000Z');
  });

  it('febrero bisiesto', () => {
    expect(boundsForAnchor('month', '2024-02').dateTo).toBe('2024-02-29T23:59:59.000Z');
  });
});

describe('calendarPeriodFor', () => {
  it('conserva el comportamiento que estaba inline en las páginas', () => {
    // Antes de C0: `period === 'custom' ? 'year' : period`.
    expect(calendarPeriodFor('month')).toBe('month');
    expect(calendarPeriodFor('year')).toBe('year');
    expect(calendarPeriodFor('custom')).toBe('year');
  });

  /*
   * PHASE-47 — aquí había un caso `calendarPeriodFor('cycle')`. Ese valor
   * desapareció de `PeriodKey`: el ciclo del usuario ES `month`, y la
   * propiedad que importaba —«un ciclo dura un mes de ancla, así que navega
   * como un mes»— la cubre ahora el primer caso, porque son el mismo valor.
   */
});

describe('dataMinDayStr / dataMaxDayStr', () => {
  it('min = día 1 del primer mes con datos; sin datos, sin tope', () => {
    expect(dataMinDayStr('2026-03')).toBe('2026-03-01');
    expect(dataMinDayStr(null)).toBeNull();
    expect(dataMinDayStr(undefined)).toBeNull();
  });

  it('max = fin del último mes con datos, nunca posterior a hoy', () => {
    // Un mes cerrado y muy pasado: el tope es su último día, no hoy.
    expect(dataMaxDayStr('2020-02')).toBe('2020-02-29');
    expect(dataMaxDayStr('2020-04')).toBe('2020-04-30');
    // Un mes muy futuro: gana hoy (impura — se compara contra el reloj).
    const hoy = dataMaxDayStr(null);
    expect(dataMaxDayStr('2999-12')).toBe(hoy);
  });
});

describe('currentMonthAnchor', () => {
  it('devuelve el mes en curso en UTC con formato YYYY-MM', () => {
    const anchor = currentMonthAnchor();
    expect(anchor).toMatch(/^\d{4}-\d{2}$/);
    const now = new Date();
    expect(anchor).toBe(
      `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}`,
    );
  });
});

/*
 * Regresión de la revisión adversarial de C0. `currentMonthAnchor` nació en UTC
 * y eso ponía a móvil a abrir en un mes distinto del de web, porque web (y todo
 * el resto de la app: deuda, presupuestos, la evolución mensual) resuelve el
 * "hoy" en hora local. Son dos preguntas distintas y sólo una es de UTC.
 */
describe('currentMonthAnchor dice en qué mes vive el USUARIO, no en cuál vive UTC', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('a las 01:30 del 1 de septiembre en Madrid, el mes ya es septiembre', () => {
    // El reloj se FIJA: un test cuyo resultado dependa del día en que se
    // ejecuta es una bomba de relojería (AUDIT-2026-08).
    vi.useFakeTimers();
    // 23:30Z del 31-ago = 01:30 del 1-sep en Madrid (CEST, UTC+2).
    vi.setSystemTime(new Date('2026-08-31T23:30:00.000Z'));

    expect(currentMonthAnchor()).toBe('2026-09');
    // Y concuerda con el "hoy" del date-picker, que siempre fue local: las dos
    // funciones responden la misma pregunta y estaban en desacuerdo.
    expect(todayDayStr()).toBe('2026-09-01');
  });

  it('el último instante de diciembre en Madrid ya es del año siguiente', () => {
    vi.useFakeTimers();
    // 23:30Z del 31-dic = 00:30 del 1-ene en Madrid (CET, UTC+1).
    vi.setSystemTime(new Date('2026-12-31T23:30:00.000Z'));

    expect(currentMonthAnchor()).toBe('2027-01');
    // Esto es lo que dejaba el chart de móvil pidiendo un año y los KPIs de
    // encima resumiendo otro: el ancla decía 2026-12 y `new Date().getFullYear()`
    // decía 2027.
    expect(Number(currentMonthAnchor().slice(0, 4))).toBe(new Date().getFullYear());
  });
});
