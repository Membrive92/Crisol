import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

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
    flow: null,
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
    expense_nature: "auto",
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
    expense_nature: "auto",
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

  it('una transferencia SIN pareja muestra "Transferencia" (ADR-0005: el par ya no es obligatorio)', () => {
    // Antes se marcaba "Sin pareja" (estado de aviso). Con `flow` como fuente
    // de verdad, una transferencia sin emparejar es un estado normal, no un
    // error → un único badge "Transferencia".
    const unpaired = makeTx({
      category_id: 'cat-income', // is_transfer: true en las categorías del test
      transfer_pair_id: null,
      is_debt_pair: false,
    });
    render(
      <TransactionList items={[unpaired]} categories={categories} onDelete={vi.fn()} />,
    );
    expect(screen.getByText('Transferencia')).toBeDefined();
    expect(screen.queryByText('Sin pareja')).toBeNull();
    expect(screen.queryByText('Deuda')).toBeNull();
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

describe('TransactionList — selección por checkbox (PHASE-34)', () => {
  it('sin onToggleSelect NO renderiza la columna de selección', () => {
    render(<TransactionList items={[makeTx()]} categories={categories} onDelete={vi.fn()} />);
    expect(screen.queryByLabelText('Seleccionar todo')).toBeNull();
  });

  it('marca una fila → dispara onToggleSelect con su id', () => {
    const onToggleSelect = vi.fn();
    render(
      <TransactionList
        items={[makeTx({ id: 'tx-sel', category_id: 'cat-plain-income' })]}
        categories={categories}
        onDelete={vi.fn()}
        selectedIds={new Set()}
        onToggleSelect={onToggleSelect}
        onToggleSelectAll={vi.fn()}
        allSelected={false}
        someSelected={false}
      />,
    );
    fireEvent.click(screen.getByLabelText('Seleccionar transacción'));
    expect(onToggleSelect).toHaveBeenCalledWith('tx-sel');
  });

  it('el checkbox de cabecera refleja allSelected', () => {
    render(
      <TransactionList
        items={[makeTx({ id: 'a' })]}
        categories={categories}
        onDelete={vi.fn()}
        selectedIds={new Set(['a'])}
        onToggleSelect={vi.fn()}
        onToggleSelectAll={vi.fn()}
        allSelected
        someSelected
      />,
    );
    const selectAll = screen.getByLabelText('Seleccionar todo') as HTMLInputElement;
    expect(selectAll.checked).toBe(true);
  });
});
