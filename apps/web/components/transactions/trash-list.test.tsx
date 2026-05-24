import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import type { Category, Transaction } from '@crisol/types';

import { TrashList } from './trash-list';

function makeTx(overrides: Partial<Transaction> = {}): Transaction {
  return {
    id: 'tx-1',
    user_id: 'u-1',
    account_id: 'acc-1',
    category_id: 'cat-1',
    transfer_pair_id: null,
    amount: '12.50',
    currency: 'EUR',
    occurred_at: '2026-04-15T12:00:00Z',
    description: 'Café del barrio',
    source: 'manual',
    receipt_id: null,
    created_at: '2026-04-15T12:00:00Z',
    updated_at: '2026-04-15T12:00:00Z',
    deleted_at: '2026-05-04T18:00:00Z',
    converted_amount: null,
    converted_currency: null,
    ...overrides,
  };
}

const categories: Category[] = [
  {
    id: 'cat-1',
    user_id: 'u-1',
    name: 'Comida',
    kind: 'expense',
    is_transfer: false,
    icon: null,
    color: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

describe('TrashList', () => {
  it('muestra mensaje vacío cuando no hay items', () => {
    render(
      <TrashList
        items={[]}
        categories={categories}
        onRestore={vi.fn()}
        onPurge={vi.fn()}
      />,
    );
    expect(screen.getByText(/papelera está vacía/i)).toBeDefined();
  });

  it('renderiza filas con descripción y categoría', () => {
    render(
      <TrashList
        items={[makeTx()]}
        categories={categories}
        onRestore={vi.fn()}
        onPurge={vi.fn()}
      />,
    );
    expect(screen.getByText('Café del barrio')).toBeDefined();
    expect(screen.getByText('Comida')).toBeDefined();
  });

  it('llama onRestore con el ID al pulsar Restaurar', async () => {
    const user = userEvent.setup();
    const onRestore = vi.fn();
    render(
      <TrashList
        items={[makeTx()]}
        categories={categories}
        onRestore={onRestore}
        onPurge={vi.fn()}
      />,
    );
    await user.click(screen.getByRole('button', { name: /restaurar/i }));
    expect(onRestore).toHaveBeenCalledWith('tx-1');
  });

  it('llama onPurge con el ID al pulsar Eliminar', async () => {
    const user = userEvent.setup();
    const onPurge = vi.fn();
    render(
      <TrashList
        items={[makeTx()]}
        categories={categories}
        onRestore={vi.fn()}
        onPurge={onPurge}
      />,
    );
    await user.click(screen.getByRole('button', { name: /eliminar/i }));
    expect(onPurge).toHaveBeenCalledWith('tx-1');
  });

  it('deshabilita los botones de la fila ocupada', () => {
    render(
      <TrashList
        items={[makeTx()]}
        categories={categories}
        onRestore={vi.fn()}
        onPurge={vi.fn()}
        busyId="tx-1"
      />,
    );
    expect(
      (screen.getByRole('button', { name: /restaurando…/i }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    expect(
      (screen.getByRole('button', { name: /eliminar/i }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
  });
});
