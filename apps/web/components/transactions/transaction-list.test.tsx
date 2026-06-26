import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import type { Category, Transaction } from '@crisol/types';

import { TransactionList } from './transaction-list';

// TransactionList navega con useRouter al pulsar una fila; en jsdom no hay
// AppRouterContext, así que lo mockeamos a un push no-op.
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

function makeTx(overrides: Partial<Transaction> = {}): Transaction {
  return {
    id: 'tx-1',
    user_id: 'u-1',
    account_id: 'acc-1',
    category_id: 'cat-income',
    transfer_pair_id: null,
    amount: '824.77',
    currency: 'EUR',
    occurred_at: '2026-04-15T12:00:00Z',
    description: 'OPERACIÓN FINANCIADA',
    source: 'import',
    receipt_id: null,
    created_at: '2026-04-15T12:00:00Z',
    updated_at: '2026-04-15T12:00:00Z',
    deleted_at: null,
    converted_amount: null,
    converted_currency: null,
    is_debt_pair: false,
    ...overrides,
  };
}

const categories: Category[] = [
  {
    id: 'cat-income',
    user_id: 'u-1',
    name: 'Transferencia a favor',
    kind: 'income',
    is_transfer: true,
    role: 'GENERIC',
    icon: null,
    color: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'cat-plain-income',
    user_id: 'u-1',
    name: 'Nómina',
    kind: 'income',
    is_transfer: false,
    role: 'GENERIC',
    icon: null,
    color: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

describe('TransactionList — pata de deuda / transferencia', () => {
  it('marca la pata-activo de una deuda con badge "Deuda" y sin signo (+) pese a ser categoría income', () => {
    const debtLeg = makeTx({
      transfer_pair_id: 'tx-2',
      is_debt_pair: true,
    });
    const { container } = render(
      <TransactionList items={[debtLeg]} categories={categories} onDelete={vi.fn()} />,
    );
    // Badge "Deuda" (no "Transferencia") para el par activo↔pasivo.
    expect(screen.getByText('Deuda')).toBeDefined();
    expect(screen.queryByText('Transferencia')).toBeNull();
    // Importe en neutro: aunque la categoría es income, NO lleva "+".
    expect(container.textContent).not.toContain('+');
  });

  it('marca una transferencia interna con badge "Transferencia" y sin signo', () => {
    const transferLeg = makeTx({
      transfer_pair_id: 'tx-3',
      is_debt_pair: false,
    });
    const { container } = render(
      <TransactionList items={[transferLeg]} categories={categories} onDelete={vi.fn()} />,
    );
    expect(screen.getByText('Transferencia')).toBeDefined();
    expect(screen.queryByText('Deuda')).toBeNull();
    expect(container.textContent).not.toContain('+');
  });

  it('un ingreso normal (no par) sí lleva "+" y sin badge de transferencia', () => {
    const plainIncome = makeTx({
      category_id: 'cat-plain-income',
      description: 'Nómina mayo',
      transfer_pair_id: null,
      is_debt_pair: false,
    });
    const { container } = render(
      <TransactionList items={[plainIncome]} categories={categories} onDelete={vi.fn()} />,
    );
    expect(screen.queryByText('Deuda')).toBeNull();
    expect(screen.queryByText('Transferencia')).toBeNull();
    expect(container.textContent).toContain('+');
  });
});
