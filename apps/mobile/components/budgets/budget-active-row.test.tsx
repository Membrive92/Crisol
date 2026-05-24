import { fireEvent, render } from '@testing-library/react-native';

import type { Budget, Category } from '@crisol/types';

import { BudgetActiveRow } from './budget-active-row';

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
    icon: null,
    color: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

describe('BudgetActiveRow (mobile)', () => {
  it('arranca en modo lectura con Editar/Cerrar visibles', () => {
    const { getByText } = render(
      <BudgetActiveRow
        budget={makeBudget()}
        categories={categories}
        onSave={jest.fn()}
        onDelete={jest.fn()}
      />,
    );
    expect(getByText('Comida')).toBeTruthy();
    expect(getByText('Editar')).toBeTruthy();
    expect(getByText('Cerrar')).toBeTruthy();
  });

  it('Editar muestra el input y los botones Guardar/Cancelar', () => {
    const { getByText, getByDisplayValue } = render(
      <BudgetActiveRow
        budget={makeBudget()}
        categories={categories}
        onSave={jest.fn()}
        onDelete={jest.fn()}
      />,
    );
    fireEvent.press(getByText('Editar'));
    expect(getByDisplayValue('300.00')).toBeTruthy();
    expect(getByText('Guardar')).toBeTruthy();
    expect(getByText('Cancelar')).toBeTruthy();
  });

  it('Guardar con valor inválido muestra error y no llama onSave', () => {
    const onSave = jest.fn();
    const { getByText, getByDisplayValue } = render(
      <BudgetActiveRow
        budget={makeBudget()}
        categories={categories}
        onSave={onSave}
        onDelete={jest.fn()}
      />,
    );
    fireEvent.press(getByText('Editar'));
    fireEvent.changeText(getByDisplayValue('300.00'), '-5');
    fireEvent.press(getByText('Guardar'));
    expect(onSave).not.toHaveBeenCalled();
    expect(getByText(/positivo/i)).toBeTruthy();
  });

  it('"Global" cuando category_id es null', () => {
    const { getByText } = render(
      <BudgetActiveRow
        budget={makeBudget({ category_id: null })}
        categories={categories}
        onSave={jest.fn()}
        onDelete={jest.fn()}
      />,
    );
    expect(getByText('Global')).toBeTruthy();
  });

  it('Tap Cerrar llama onDelete con id y label', () => {
    const onDelete = jest.fn();
    const { getByText } = render(
      <BudgetActiveRow
        budget={makeBudget()}
        categories={categories}
        onSave={jest.fn()}
        onDelete={onDelete}
      />,
    );
    fireEvent.press(getByText('Cerrar'));
    expect(onDelete).toHaveBeenCalledWith('b-1', 'Comida');
  });
});
