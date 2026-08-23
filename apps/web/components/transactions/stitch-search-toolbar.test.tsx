import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import type * as ServicesModule from '@crisol/services';
import type { Account, Category, TransactionListQuery } from '@crisol/types';

// El toolbar pide los periodos disponibles para el TimeSelector; lo
// mockeamos a vacío (no es lo que probamos aquí), igual que el perfil.
//
// El mock parte del módulo REAL (`importOriginal` + spread) y sólo sustituye
// los dos hooks. Un mock construido desde cero devuelve `undefined` para todo
// lo demás, así que en cuanto el TimeSelector empezó a usar una función pura de
// `@crisol/services` (`isValidCycleStartDay`) estos cinco tests se cayeron con
// un error que no tenía nada que ver con lo que prueban.
vi.mock('@crisol/services', async (importOriginal) => {
  const actual = await importOriginal<typeof ServicesModule>();
  return {
    ...actual,
    useTransactionAvailablePeriods: () => ({ data: [] }),
    useMe: () => ({ data: undefined, isLoading: false, isError: false, error: null }),
  };
});

import { StitchSearchToolbar } from './stitch-search-toolbar';

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

// ── El filtro de cuenta, que es el que la gente busca ────────────────
//
// Reportado en uso: «cuando cambio de cuenta, sigue mostrando las mismas
// transacciones». No era el filtro: la pantalla tenía DOS desplegables de
// cuenta —éste, dentro del panel plegado, y el destino de la reasignación en
// bloque, siempre visible y sin etiqueta— y se estaba usando el otro.
//
// Este test fija que el de aquí sí filtra; el arreglo del otro (etiqueta
// visible + barra plegada) vive en la página.

describe('StitchSearchToolbar · filtro de cuenta', () => {
  const withAccounts: Account[] = [
    {
      id: 'acc-bank',
      user_id: 'u-1',
      name: 'BBVA',
      type: 'bank',
      nature: 'asset',
      currency: 'EUR',
      opening_balance: '0',
      opening_balance_date: null,
      color: null,
      icon: null,
      display_order: 0,
      is_archived: false,
      is_default: true,
      counts_as_debt: true,
      apr: null,
      tae: null,
      term_months: null,
      start_date: null,
      total_to_pay: null,
      interest_only_first_payment: null,
      category_id: null,
      parent_account_id: null,
      settlement_account_id: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ];

  it('emite el account_id elegido y vuelve a la primera página', async () => {
    const onChange = vi.fn();
    render(
      <StitchSearchToolbar
        value={{ limit: 50, offset: 100 }}
        onChange={onChange}
        categories={categories}
        accounts={withAccounts}
      />,
    );
    // El filtro vive dentro del panel plegable.
    await userEvent.click(screen.getByRole('button', { name: /filtros/i }));

    await userEvent.selectOptions(screen.getByLabelText('Cuenta'), 'acc-bank');

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ account_id: 'acc-bank', offset: 0 }),
    );
  });

  it('«Todas» retira el filtro en vez de mandar una cadena vacía', async () => {
    const onChange = vi.fn();
    render(
      <StitchSearchToolbar
        value={{ limit: 50, offset: 0, account_id: 'acc-bank' }}
        onChange={onChange}
        categories={categories}
        accounts={withAccounts}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: /filtros/i }));

    await userEvent.selectOptions(screen.getByLabelText('Cuenta'), '');

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ account_id: undefined }),
    );
  });
});
