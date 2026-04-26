import { describe, expect, it } from 'vitest';

import { queryKeys } from './keys';

describe('queryKeys', () => {
  it('tiene raíces estables para categories y transactions', () => {
    expect(queryKeys.categories.all).toEqual(['categories']);
    expect(queryKeys.transactions.all).toEqual(['transactions']);
  });

  it('genera la misma key para listas con el mismo contenido en distinto orden', () => {
    const a = queryKeys.transactions.list({ category_id: 'c1', search: 'café', limit: 10 });
    const b = queryKeys.transactions.list({ limit: 10, search: 'café', category_id: 'c1' });
    expect(a).toEqual(b);
  });

  it('ignora valores string vacío en filtros', () => {
    const keyCompact = queryKeys.transactions.list({ search: 'foo' });
    const keyVerbose = queryKeys.transactions.list({
      search: 'foo',
      date_from: '',
    });
    expect(keyCompact).toEqual(keyVerbose);
  });

  it('detalle incluye el id como último segmento', () => {
    expect(queryKeys.transactions.detail('abc')).toEqual(['transactions', 'detail', 'abc']);
    expect(queryKeys.categories.detail('xyz')).toEqual(['categories', 'detail', 'xyz']);
  });

  it('dashboard.all es estable', () => {
    expect(queryKeys.dashboard.all).toEqual(['dashboard']);
  });

  it('dashboard.summary normaliza el orden de filtros', () => {
    const a = queryKeys.dashboard.summary({ currency: 'USD', date_from: '2026-01-01' });
    const b = queryKeys.dashboard.summary({ date_from: '2026-01-01', currency: 'USD' });
    expect(a).toEqual(b);
  });

  it('dashboard.byMonth conserva year', () => {
    const key = queryKeys.dashboard.byMonth({ year: 2026, currency: 'EUR' });
    expect(key).toEqual([
      'dashboard',
      'by-month',
      { currency: 'EUR', year: 2026 },
    ]);
  });

  it('imports.all es estable', () => {
    expect(queryKeys.imports.all).toEqual(['imports']);
  });

  it('imports.list normaliza el orden de filtros', () => {
    const a = queryKeys.imports.list({ limit: 50, offset: 0 });
    const b = queryKeys.imports.list({ offset: 0, limit: 50 });
    expect(a).toEqual(b);
  });

  it('imports.detail incluye el id como último segmento', () => {
    expect(queryKeys.imports.detail('job-1')).toEqual(['imports', 'detail', 'job-1']);
  });

  it('receipts.all es estable', () => {
    expect(queryKeys.receipts.all).toEqual(['receipts']);
  });

  it('receipts.list normaliza el orden de filtros', () => {
    const a = queryKeys.receipts.list({ limit: 10, offset: 0 });
    const b = queryKeys.receipts.list({ offset: 0, limit: 10 });
    expect(a).toEqual(b);
  });

  it('receipts.detail incluye el id', () => {
    expect(queryKeys.receipts.detail('r1')).toEqual(['receipts', 'detail', 'r1']);
  });
});
