import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import type { Category, FixedExpense } from '@finanzas/types';

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
    first_seen_at: '2026-02-15',
    last_seen_at: '2026-05-15',
    occurrence_count: 4,
    confidence: 0.97,
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

describe('FixedExpenseCard', () => {
  it('pinta description, amount, cadencia y categoría', () => {
    render(<FixedExpenseCard fixedExpense={makeItem()} categories={categories} />);
    expect(screen.getByText('NETFLIX.COM')).toBeDefined();
    expect(screen.getByText(/Mensual/)).toBeDefined();
    expect(screen.getByText(/Streaming/)).toBeDefined();
    expect(screen.getByText(/97%/)).toBeDefined();
  });

  it('llama primaryAction.onClick al pulsar', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <FixedExpenseCard
        fixedExpense={makeItem()}
        categories={categories}
        primaryAction={{ label: 'Confirmar', onClick }}
      />,
    );
    await user.click(screen.getByRole('button', { name: /confirmar/i }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('llama secondaryAction.onClick al pulsar', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <FixedExpenseCard
        fixedExpense={makeItem()}
        categories={categories}
        secondaryAction={{ label: 'Descartar', onClick }}
      />,
    );
    await user.click(screen.getByRole('button', { name: /descartar/i }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('muestra "Sin categoría" cuando category_id es null', () => {
    const item = makeItem({ category_id: null });
    render(<FixedExpenseCard fixedExpense={item} categories={categories} />);
    expect(screen.getByText(/Sin categoría/)).toBeDefined();
  });

  it('cadencia anual se muestra como "Anual"', () => {
    const item = makeItem({ cadence_days: 365 });
    render(<FixedExpenseCard fixedExpense={item} categories={categories} />);
    expect(screen.getByText(/Anual/)).toBeDefined();
  });
});
