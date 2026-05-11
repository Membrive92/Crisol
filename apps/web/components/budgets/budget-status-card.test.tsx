import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import type { BudgetStatusItem, Category } from '@crisol/types';

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

describe('BudgetStatusCard', () => {
  it('pinta nombre de categoría + spent + remaining + porcentaje', () => {
    render(<BudgetStatusCard item={makeItem()} categories={categories} />);
    expect(screen.getByText('Comida')).toBeDefined();
    expect(screen.getByText(/20% · ok/i)).toBeDefined();
    expect(screen.getByText(/Gastado/)).toBeDefined();
    expect(screen.getByText(/Restante/)).toBeDefined();
  });

  it('pinta "Global" cuando no hay categoría', () => {
    const item = makeItem({
      budget: { ...makeItem().budget, category_id: null },
    });
    render(<BudgetStatusCard item={item} categories={categories} />);
    expect(screen.getByText(/Global/i)).toBeDefined();
  });

  it('muestra status warning con palette propio', () => {
    const item = makeItem({
      spent_this_month: '255.00',
      remaining: '45.00',
      percent_used: 85,
      status: 'warning',
    });
    render(<BudgetStatusCard item={item} categories={categories} />);
    expect(screen.getByText(/85% · warning/i)).toBeDefined();
  });

  it('muestra "Excedido" cuando remaining es negativo', () => {
    const item = makeItem({
      spent_this_month: '350.00',
      remaining: '-50.00',
      percent_used: 116.67,
      status: 'over',
    });
    render(<BudgetStatusCard item={item} categories={categories} />);
    expect(screen.getByText(/Excedido/)).toBeDefined();
    expect(screen.getByText(/117% · over/i)).toBeDefined();
  });
});
