import { describe, expect, it } from 'vitest';

import type { AccountNature, CategoryRole, Transaction } from '@crisol/types';

import { buildDebtMovements, formatDayMonth, splitDebtLabel } from './debt-summary-card';

function tx(over: Partial<Transaction>): Transaction {
  return {
    id: 'tx',
    user_id: 'u',
    account_id: 'bank',
    category_id: null,
    transfer_pair_id: null,
    amount: '100.00',
    currency: 'EUR',
    occurred_at: '2026-06-01T00:00:00Z',
    description: 'Mov',
    source: 'import',
    flow: 'OUT',
    receipt_id: null,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
    deleted_at: null,
    converted_amount: null,
    converted_currency: null,
    is_debt_pair: false,
    ...over,
  };
}

const ROLES = new Map<string, CategoryRole>([
  ['cat-debt', 'DEBT_PAYMENT'],
  ['cat-normal', 'GENERIC'],
]);
const NATURES = new Map<string, AccountNature>([
  ['bank', 'asset'],
  ['card', 'liability'],
]);

describe('buildDebtMovements', () => {
  it('incluye pagos a deuda (rol DEBT_*) como "payment"', () => {
    const out = buildDebtMovements(
      [tx({ id: 'a', category_id: 'cat-debt', amount: '232.27' })],
      ROLES,
      NATURES,
    );
    expect(out).toHaveLength(1);
    expect(out[0]!.kind).toBe('payment');
    expect(out[0]!.amount).toBeCloseTo(232.27, 2);
  });

  it('incluye la pata-activo de un par de deuda como "issuance"', () => {
    const out = buildDebtMovements(
      [tx({ id: 'b', account_id: 'bank', is_debt_pair: true, category_id: 'cat-normal', flow: 'TRANSFER_IN' })],
      ROLES,
      NATURES,
    );
    expect(out).toHaveLength(1);
    expect(out[0]!.kind).toBe('issuance');
  });

  it('descarta la pata-pasivo del par (dedup a un solo registro)', () => {
    const out = buildDebtMovements(
      [tx({ id: 'liab', account_id: 'card', is_debt_pair: true, category_id: 'cat-normal' })],
      ROLES,
      NATURES,
    );
    expect(out).toHaveLength(0);
  });

  it('descarta transacciones normales (ni rol de deuda ni par)', () => {
    const out = buildDebtMovements(
      [tx({ id: 'n', category_id: 'cat-normal' })],
      ROLES,
      NATURES,
    );
    expect(out).toHaveLength(0);
  });

  it('usa el importe convertido cuando existe', () => {
    const out = buildDebtMovements(
      [tx({ id: 'c', category_id: 'cat-debt', amount: '100.00', converted_amount: '90.50' })],
      ROLES,
      NATURES,
    );
    expect(out[0]!.amount).toBeCloseTo(90.5, 2);
  });

  it('ordena del más reciente al más antiguo', () => {
    const out = buildDebtMovements(
      [
        tx({ id: 'old', category_id: 'cat-debt', occurred_at: '2026-01-10T00:00:00Z' }),
        tx({ id: 'new', category_id: 'cat-debt', occurred_at: '2026-06-10T00:00:00Z' }),
      ],
      ROLES,
      NATURES,
    );
    expect(out.map((m) => m.id)).toEqual(['new', 'old']);
  });
});

describe('formatDayMonth', () => {
  it('formatea ISO a "D mmm" en español, sin cero a la izquierda', () => {
    expect(formatDayMonth('2026-06-29T00:00:00Z')).toBe('29 jun');
    expect(formatDayMonth('2026-01-05T12:00:00Z')).toBe('5 ene');
  });
});

describe('splitDebtLabel', () => {
  it('separa la referencia con guiones y deja los últimos 4 dígitos', () => {
    expect(
      splitDebtLabel('Cargo por amortizacion de prestamo/credito 0182-1051-19-0830170370'),
    ).toEqual({ main: 'Cargo por amortizacion de prestamo/credito', ref4: '0370' });
  });

  it('separa un número de tarjeta sin separadores', () => {
    expect(splitDebtLabel('Adeudo mensual de tarjeta 4940121100185049')).toEqual({
      main: 'Adeudo mensual de tarjeta',
      ref4: '5049',
    });
  });

  it('sin número final → ref4 null y descripción completa', () => {
    expect(splitDebtLabel('Pago de préstamo')).toEqual({
      main: 'Pago de préstamo',
      ref4: null,
    });
  });

  it('descripción que es sólo un número no se queda sin etiqueta', () => {
    expect(splitDebtLabel('4940121100185049').main).toBe('4940121100185049');
  });
});
