import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import type { Budget, Category } from '@crisol/types';

import { BudgetRow } from './budget-row';

function makeBudget(overrides: Partial<Budget> = {}): Budget {
  return {
    id: 'b-1',
    user_id: 'u-1',
    category_id: 'cat-1',
    amount: '300.00',
    currency: 'EUR',
    effective_from: '2026-05-01',
    effective_to: null,
    convert_other_currencies: false,
    created_at: '2026-05-01T00:00:00Z',
    updated_at: '2026-05-01T00:00:00Z',
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
    role: 'GENERIC',
    expense_nature: "auto",
    icon: null,
    color: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

describe('BudgetRow', () => {
  it('arranca en modo lectura con botones Editar/Cerrar', () => {
    render(
      <BudgetRow
        budget={makeBudget()}
        categories={categories}
        onSave={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByText('Comida')).toBeDefined();
    expect(screen.getByRole('button', { name: /editar/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /cerrar/i })).toBeDefined();
  });

  it('al pulsar Editar muestra input + Guardar/Cancelar', async () => {
    const user = userEvent.setup();
    render(
      <BudgetRow
        budget={makeBudget()}
        categories={categories}
        onSave={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    await user.click(screen.getByRole('button', { name: /editar/i }));
    expect(screen.getByDisplayValue('300.00')).toBeDefined();
    expect(screen.getByRole('button', { name: /guardar/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /cancelar/i })).toBeDefined();
  });

  it('Cancelar vuelve a modo lectura sin llamar onSave', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(
      <BudgetRow
        budget={makeBudget()}
        categories={categories}
        onSave={onSave}
        onDelete={vi.fn()}
      />,
    );
    await user.click(screen.getByRole('button', { name: /editar/i }));
    await user.click(screen.getByRole('button', { name: /cancelar/i }));
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /editar/i })).toBeDefined();
  });

  it('Guardar con importe válido llama onSave con el ID y el nuevo valor', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <BudgetRow
        budget={makeBudget()}
        categories={categories}
        onSave={onSave}
        onDelete={vi.fn()}
      />,
    );
    await user.click(screen.getByRole('button', { name: /editar/i }));
    const input = screen.getByDisplayValue('300.00');
    await user.clear(input);
    await user.type(input, '450');
    await user.click(screen.getByRole('button', { name: /guardar/i }));
    expect(onSave).toHaveBeenCalledWith('b-1', '450');
  });

  it('Guardar con importe inválido muestra error y no llama onSave', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(
      <BudgetRow
        budget={makeBudget()}
        categories={categories}
        onSave={onSave}
        onDelete={vi.fn()}
      />,
    );
    await user.click(screen.getByRole('button', { name: /editar/i }));
    const input = screen.getByDisplayValue('300.00');
    await user.clear(input);
    await user.type(input, '-5');
    await user.click(screen.getByRole('button', { name: /guardar/i }));
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByText(/positivo/i)).toBeDefined();
  });

  it('"Global" cuando category_id es null', () => {
    render(
      <BudgetRow
        budget={makeBudget({ category_id: null })}
        categories={categories}
        onSave={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByText('Global')).toBeDefined();
  });
});
