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
});
