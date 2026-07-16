import { describe, expect, it } from 'vitest';

import { boundsForAnchor, boundsForCustomRange } from './stitch-period-toggle';

describe('boundsForCustomRange (PHASE-41)', () => {
  it('convierte from/to a límites ISO en UTC (00:00:00Z … 23:59:59Z)', () => {
    const { dateFrom, dateTo } = boundsForCustomRange('2026-06-15', '2026-07-15');
    expect(dateFrom).toBe('2026-06-15T00:00:00.000Z');
    expect(dateTo).toBe('2026-07-15T23:59:59.000Z');
  });

  it('respeta el día exacto (no snapea al mes)', () => {
    const { dateFrom, dateTo } = boundsForCustomRange('2026-01-31', '2026-02-01');
    expect(dateFrom).toBe('2026-01-31T00:00:00.000Z');
    expect(dateTo).toBe('2026-02-01T23:59:59.000Z');
  });
});

describe('boundsForAnchor sin quarter (PHASE-41)', () => {
  it('month → mes natural completo', () => {
    const { dateFrom, dateTo } = boundsForAnchor('month', '2026-02');
    expect(dateFrom).toBe('2026-02-01T00:00:00.000Z');
    // 2026 no bisiesto → febrero 28.
    expect(dateTo).toBe('2026-02-28T23:59:59.000Z');
  });

  it('year → año natural completo (independiente del mes ancla)', () => {
    const { dateFrom, dateTo } = boundsForAnchor('year', '2026-07');
    expect(dateFrom).toBe('2026-01-01T00:00:00.000Z');
    expect(dateTo).toBe('2026-12-31T23:59:59.000Z');
  });
});
