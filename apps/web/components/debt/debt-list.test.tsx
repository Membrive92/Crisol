import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import type { Account, AccountBalance } from '@crisol/types';

// DebtList resuelve apr/term cruzando AccountBalance con Account vía estos
// hooks; los mockeamos para renderizar sin red.
const { useAccountsMock, useCategoriesMock } = vi.hoisted(() => ({
  useAccountsMock: vi.fn(),
  useCategoriesMock: vi.fn(),
}));

vi.mock('@crisol/services', () => ({
  useAccounts: () => useAccountsMock(),
  useCategories: () => useCategoriesMock(),
}));

vi.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

import { DebtList } from './debt-list';

function makeBalance(overrides: Partial<AccountBalance> = {}): AccountBalance {
  return {
    account_id: 'acc-1',
    name: 'Cuenta',
    type: 'credit_card',
    nature: 'liability',
    currency: 'EUR',
    color: null,
    icon: null,
    opening_balance: '0.00',
    movements_balance: '0.00',
    current_balance: '0.00',
    ...overrides,
  };
}

function makeAccount(overrides: Partial<Account> = {}): Account {
  return {
    id: 'acc-1',
    user_id: 'u-1',
    name: 'Cuenta',
    type: 'credit_card',
    nature: 'liability',
    currency: 'EUR',
    color: null,
    icon: null,
    opening_balance: '0.00',
    opening_balance_date: null,
    apr: null,
    tae: null,
    term_months: null,
    start_date: null,
    display_order: 0,
    is_archived: false,
    is_default: false,
    counts_as_debt: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

describe('DebtList — agrupación de compras a plazos (PHASE-35)', () => {
  it('anida las compras a plazos bajo su tarjeta padre y suma el total', () => {
    const card = makeBalance({
      account_id: 'card',
      name: 'Tarjeta BBVA',
      current_balance: '100.00',
    });
    const childA = makeBalance({
      account_id: 'buy-a',
      name: 'Sofá a plazos',
      parent_account_id: 'card',
      current_balance: '300.00',
    });
    const childB = makeBalance({
      account_id: 'buy-b',
      name: 'Portátil a plazos',
      parent_account_id: 'card',
      current_balance: '200.00',
    });
    const loan = makeBalance({
      account_id: 'loan',
      name: 'Préstamo coche',
      type: 'loan',
      current_balance: '5000.00',
    });

    useAccountsMock.mockReturnValue({
      data: [
        makeAccount({ id: 'card', name: 'Tarjeta BBVA' }),
        makeAccount({ id: 'buy-a', name: 'Sofá a plazos', parent_account_id: 'card' }),
        makeAccount({ id: 'buy-b', name: 'Portátil a plazos', parent_account_id: 'card' }),
        makeAccount({ id: 'loan', name: 'Préstamo coche', type: 'loan' }),
      ],
    });
    useCategoriesMock.mockReturnValue({ data: [] });

    render(<DebtList liabilities={[card, childA, childB, loan]} loading={false} />);

    // Padre, hijas y deuda independiente: todos visibles, cada uno una vez.
    expect(screen.getByText('Tarjeta BBVA')).toBeTruthy();
    expect(screen.getByText('Sofá a plazos')).toBeTruthy();
    expect(screen.getByText('Portátil a plazos')).toBeTruthy();
    expect(screen.getByText('Préstamo coche')).toBeTruthy();

    // Las dos hijas se etiquetan como "Compra a plazos".
    expect(screen.getAllByText('Compra a plazos')).toHaveLength(2);

    // El padre muestra el contador y el total combinado (100 + 300 + 200).
    expect(screen.getByText('2 compras a plazos')).toBeTruthy();
    expect(screen.getByText(/Con plazos:/)).toBeTruthy();
    expect(screen.getByText(/600/)).toBeTruthy();
  });

  it('una compra a plazos huérfana (sin su tarjeta) se muestra a nivel superior', () => {
    const orphan = makeBalance({
      account_id: 'orphan',
      name: 'Compra huérfana',
      parent_account_id: 'missing-card',
      current_balance: '50.00',
    });
    useAccountsMock.mockReturnValue({
      data: [makeAccount({ id: 'orphan', name: 'Compra huérfana', parent_account_id: 'missing-card' })],
    });
    useCategoriesMock.mockReturnValue({ data: [] });

    render(<DebtList liabilities={[orphan]} loading={false} />);

    // Se renderiza igualmente (no se pierde) aunque su padre no esté.
    expect(screen.getByText('Compra huérfana')).toBeTruthy();
  });
});

// ── PHASE-47.E · deuda pagada aparte ─────────────────────────────────
//
// Una deuda a cero ya no es deuda. Mezclada con las vivas, la lista crece sin
// parar y cuesta ver lo que de verdad debes: el usuario acabó con seis
// contratos de los que sólo dos tenían saldo. Se separan, pero no se ocultan —
// saber qué terminaste de pagar es parte de la foto.

describe('DebtList · deuda pagada', () => {
  it('saca las saldadas de la lista principal y las agrupa aparte', () => {
    useAccountsMock.mockReturnValue({ data: [] });
    useCategoriesMock.mockReturnValue({ data: [] });

    render(
      <DebtList
        loading={false}
        liabilities={[
          makeBalance({ account_id: 'viva', name: 'Prestamo', current_balance: '-22762.46' }),
          makeBalance({ account_id: 'pagada', name: 'Compra financiada', current_balance: '0.00' }),
        ]}
      />,
    );

    expect(screen.getByText('1 pasivo activo')).toBeTruthy();
    expect(screen.getByText(/Deuda pagada \(1\)/)).toBeTruthy();
    // Las dos siguen estando; lo que cambia es dónde.
    expect(screen.getByText('Prestamo')).toBeTruthy();
    expect(screen.getByText('Compra financiada')).toBeTruthy();
  });

  it('una tarjeta a cero con una compra a plazos viva sigue siendo deuda viva', () => {
    // El saldo se mira sumando las hijas: si no, la tarjeta caería a «pagada»
    // arrastrando consigo una deuda que sí tiene saldo.
    useAccountsMock.mockReturnValue({ data: [] });
    useCategoriesMock.mockReturnValue({ data: [] });

    render(
      <DebtList
        loading={false}
        liabilities={[
          makeBalance({ account_id: 'tarjeta', name: 'Tarjeta', current_balance: '0.00' }),
          makeBalance({
            account_id: 'plazos',
            name: 'Compra a plazos',
            current_balance: '-500.00',
            parent_account_id: 'tarjeta',
          }),
        ]}
      />,
    );

    expect(screen.getByText('1 pasivo activo')).toBeTruthy();
    expect(screen.queryByText(/Deuda pagada/)).toBeNull();
  });

  it('sin ninguna saldada no pinta la sección', () => {
    useAccountsMock.mockReturnValue({ data: [] });
    useCategoriesMock.mockReturnValue({ data: [] });

    render(
      <DebtList
        loading={false}
        liabilities={[makeBalance({ account_id: 'viva', current_balance: '-100.00' })]}
      />,
    );

    expect(screen.queryByText(/Deuda pagada/)).toBeNull();
  });
});
