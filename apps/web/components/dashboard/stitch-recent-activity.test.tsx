import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';

import type { Category, Transaction } from '@crisol/types';

// Hooks de datos mockeados: el widget sólo usa `.data`/`.isLoading`.
const { useTransactionsMock, useCategoriesMock } = vi.hoisted(() => ({
  useTransactionsMock: vi.fn(),
  useCategoriesMock: vi.fn(),
}));

vi.mock('@crisol/services', () => ({
  useTransactions: () => useTransactionsMock(),
  useCategories: () => useCategoriesMock(),
}));

// next/link necesita AppRouterContext en runtime; en jsdom lo reducimos a
// sus children (sólo nos interesa el contenido renderizado).
vi.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

import { StitchRecentActivity } from './stitch-recent-activity';

function makeTx(overrides: Partial<Transaction> = {}): Transaction {
  return {
    id: 'tx-1',
    user_id: 'u-1',
    account_id: 'acc-1',
    category_id: 'cat-nomina',
    transfer_pair_id: null,
    amount: '1500.00',
    currency: 'EUR',
    occurred_at: '2026-04-15T12:00:00Z',
    description: 'Movimiento',
    source: 'import',
    receipt_id: null,
    created_at: '2026-04-15T12:00:00Z',
    updated_at: '2026-04-15T12:00:00Z',
    deleted_at: null,
    converted_amount: null,
    converted_currency: null,
    flow: null,
    is_debt_pair: false,
    ...overrides,
  };
}

const categories: Category[] = [
  {
    id: 'cat-transfer-income',
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
    id: 'cat-nomina',
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

function setItems(items: Transaction[]) {
  useTransactionsMock.mockReturnValue({
    data: { items, total: items.length, limit: 4, offset: 0 },
    isLoading: false,
  });
}

describe('StitchRecentActivity — pata de deuda/transferencia', () => {
  beforeEach(() => {
    useCategoriesMock.mockReturnValue({ data: categories });
  });

  it('la pata-activo de una operación financiada se pinta neutra (sin "+") pese a ser income', () => {
    setItems([
      makeTx({
        id: 'tx-debt',
        category_id: 'cat-transfer-income',
        transfer_pair_id: 'tx-2',
        is_debt_pair: true,
        amount: '824.77',
        description: 'OPERACIÓN FINANCIADA',
      }),
    ]);
    const { container } = render(<StitchRecentActivity />);
    expect(container.textContent).toContain('OPERACIÓN FINANCIADA');
    // El único origen posible de "+" sería el signo del importe; al ser
    // pata de deuda no debe llevarlo.
    expect(container.textContent).not.toContain('+');
  });

  it('un ingreso normal (no par) sí lleva "+"', () => {
    setItems([
      makeTx({
        id: 'tx-income',
        category_id: 'cat-nomina',
        transfer_pair_id: null,
        is_debt_pair: false,
        amount: '1500.00',
        description: 'Nómina mayo',
      }),
    ]);
    const { container } = render(<StitchRecentActivity />);
    expect(container.textContent).toContain('+');
  });
});
