// @types/jest expone los globals (describe/it/expect) — sin import.
import { render } from '@testing-library/react-native';

import type { BudgetStatusItem, Category } from '@finanzas/types';

import { BudgetStatusCard } from './budget-status-card';

function makeItem(overrides: Partial<BudgetStatusItem> = {}): BudgetStatusItem {
  return {
    budget: {
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
    },
    spent_this_month: '60.00',
    remaining: '240.00',
    percent_used: 20,
    status: 'ok',
    unconvertible_count: 0,
    ...overrides,
  };
}

const categories: Category[] = [
  {
    id: 'cat-1',
    user_id: 'u-1',
    name: 'Comida',
    kind: 'expense',
    icon: null,
    color: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

describe('BudgetStatusCard (mobile)', () => {
  it('pinta categoría + porcentaje + status', () => {
    const { getByText } = render(
      <BudgetStatusCard item={makeItem()} categories={categories} />,
    );
    expect(getByText('Comida')).toBeTruthy();
    expect(getByText(/20% · ok/i)).toBeTruthy();
  });

  it('pinta "Global" cuando category_id es null', () => {
    const item = makeItem({ budget: { ...makeItem().budget, category_id: null } });
    const { getByText } = render(
      <BudgetStatusCard item={item} categories={categories} />,
    );
    expect(getByText(/Global/i)).toBeTruthy();
  });

  it('muestra "Excedido" cuando remaining es negativo', () => {
    const item = makeItem({
      spent_this_month: '350.00',
      remaining: '-50.00',
      percent_used: 116.67,
      status: 'over',
    });
    const { getByText } = render(
      <BudgetStatusCard item={item} categories={categories} />,
    );
    expect(getByText(/Excedido/)).toBeTruthy();
    expect(getByText(/117% · over/i)).toBeTruthy();
  });
});
