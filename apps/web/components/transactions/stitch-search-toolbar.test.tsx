import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import type { Account, Category, TransactionListQuery } from '@crisol/types';

// El toolbar pide los periodos disponibles para el TimeSelector; lo
// mockeamos a vacío (no es lo que probamos aquí).
vi.mock('@crisol/services', () => ({
  useTransactionAvailablePeriods: () => ({ data: [] }),
}));

import { StitchSearchToolbar } from './stitch-search-toolbar';

const categories: Category[] = [
  {
    id: 'cat-1',
    user_id: 'u-1',
    name: 'Comida',
    kind: 'expense',
    is_transfer: false,
    role: 'GENERIC',
    icon: null,
    color: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];
const accounts: Account[] = [];

function renderToolbar(value: TransactionListQuery, onChange = vi.fn()) {
  render(
    <StitchSearchToolbar
      value={value}
      onChange={onChange}
      categories={categories}
      accounts={accounts}
    />,
  );
  return onChange;
}

describe('StitchSearchToolbar — filtro de categoría / sin categoría', () => {
  it('seleccionar "Sin categoría" emite uncategorized:true sin category_id', async () => {
    const user = userEvent.setup();
    const onChange = renderToolbar({ limit: 20, offset: 0 });
    await user.click(screen.getByRole('button', { name: /filtros/i }));
    await user.selectOptions(screen.getByLabelText('Categoría'), '__uncategorized__');

    const arg = onChange.mock.calls.at(-1)?.[0] as TransactionListQuery;
    expect(arg.uncategorized).toBe(true);
    expect(arg.category_id).toBeUndefined();
  });

  it('seleccionar una categoría normal emite category_id sin uncategorized', async () => {
    const user = userEvent.setup();
    // Partimos de "sin categoría" activo para comprobar que se limpia.
    const onChange = renderToolbar({ limit: 20, offset: 0, uncategorized: true });
    await user.click(screen.getByRole('button', { name: /filtros/i }));
    await user.selectOptions(screen.getByLabelText('Categoría'), 'cat-1');

    const arg = onChange.mock.calls.at(-1)?.[0] as TransactionListQuery;
    expect(arg.category_id).toBe('cat-1');
    expect(arg.uncategorized).toBeUndefined();
  });

  it('con uncategorized activo el select muestra "Sin categoría"', async () => {
    renderToolbar({ limit: 20, offset: 0, uncategorized: true });
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /filtros/i }));
    const select = screen.getByLabelText('Categoría') as HTMLSelectElement;
    expect(select.value).toBe('__uncategorized__');
  });
});
