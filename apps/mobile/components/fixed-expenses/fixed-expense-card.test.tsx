import { fireEvent, render } from '@testing-library/react-native';

import type { Category, FixedExpense } from '@crisol/types';

import { FixedExpenseCard } from './fixed-expense-card';

function makeItem(overrides: Partial<FixedExpense> = {}): FixedExpense {
  return {
    id: 's-1',
    user_id: 'u-1',
    merchant: 'netflixcom',
    raw_description: 'NETFLIX.COM',
    amount: '12.99',
    currency: 'EUR',
    cadence_days: 30,
    next_due: '2026-06-15',
    status: 'pending',
    category_id: 'cat-1',
    account_id: null,
    first_seen_at: '2026-02-15',
    last_seen_at: '2026-05-15',
    occurrence_count: 4,
    confidence: 0.97,
    auto_post: false,
    created_at: '2026-05-15T00:00:00Z',
    updated_at: '2026-05-15T00:00:00Z',
    ...overrides,
  };
}

const categories: Category[] = [
  {
    id: 'cat-1',
    user_id: 'u-1',
    name: 'Streaming',
    kind: 'expense',
    icon: null,
    color: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

describe('FixedExpenseCard (mobile)', () => {
  it('pinta description, cadencia legible y categoría', () => {
    const { getByText } = render(
      <FixedExpenseCard fixedExpense={makeItem()} categories={categories} />,
    );
    expect(getByText('NETFLIX.COM')).toBeTruthy();
    expect(getByText(/Mensual/)).toBeTruthy();
    expect(getByText(/Streaming/)).toBeTruthy();
    expect(getByText(/97%/)).toBeTruthy();
  });

  it('cadencia 365 → "Anual"', () => {
    const { getByText } = render(
      <FixedExpenseCard
        fixedExpense={makeItem({ cadence_days: 365 })}
        categories={categories}
      />,
    );
    expect(getByText(/Anual/)).toBeTruthy();
  });

  it('Sin categoría cuando category_id es null', () => {
    const { getByText } = render(
      <FixedExpenseCard
        fixedExpense={makeItem({ category_id: null })}
        categories={categories}
      />,
    );
    expect(getByText(/Sin categoría/)).toBeTruthy();
  });

  it('primaryAction.onPress se llama al tap', () => {
    const onPress = jest.fn();
    const { getByText } = render(
      <FixedExpenseCard
        fixedExpense={makeItem()}
        categories={categories}
        primaryAction={{ label: 'Confirmar', onPress }}
      />,
    );
    fireEvent.press(getByText('Confirmar'));
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('secondaryAction.onPress se llama al tap', () => {
    const onPress = jest.fn();
    const { getByText } = render(
      <FixedExpenseCard
        fixedExpense={makeItem()}
        categories={categories}
        secondaryAction={{ label: 'Descartar', onPress }}
      />,
    );
    fireEvent.press(getByText('Descartar'));
    expect(onPress).toHaveBeenCalledTimes(1);
  });
});
