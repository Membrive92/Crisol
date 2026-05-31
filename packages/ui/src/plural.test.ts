import { describe, expect, it } from 'vitest';

import { pluralize, withCount } from './plural';

describe('pluralize', () => {
  it('usa el singular para 1 y el plural para el resto (regla es)', () => {
    expect(pluralize(1, 'par enlazado', 'pares enlazados')).toBe('par enlazado');
    expect(pluralize(0, 'par enlazado', 'pares enlazados')).toBe('pares enlazados');
    expect(pluralize(2, 'par enlazado', 'pares enlazados')).toBe('pares enlazados');
  });

  it('trata el signo por valor absoluto', () => {
    expect(pluralize(-1, 'gasto', 'gastos')).toBe('gasto');
  });

  it('withCount prefija el número', () => {
    expect(withCount(1, 'transacción', 'transacciones')).toBe('1 transacción');
    expect(withCount(3, 'transacción', 'transacciones')).toBe('3 transacciones');
  });
});
