import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import type { Account, TransferPair } from '@crisol/types';

import { TransferPairCard } from './transfer-pair-card';

function makePair(overrides: Partial<TransferPair> = {}): TransferPair {
  return {
    out_transaction_id: 'tx-out',
    in_transaction_id: 'tx-in',
    amount: '500.00',
    currency: 'EUR',
    out_account_id: 'acc-a',
    in_account_id: 'acc-b',
    out_occurred_at: '2026-05-01T00:00:00Z',
    in_occurred_at: '2026-05-02T00:00:00Z',
    delta_days: 1,
    ...overrides,
  };
}

const accounts: Account[] = [
  {
    id: 'acc-a',
    user_id: 'u-1',
    name: 'Cuenta nómina',
    type: 'bank',
    nature: 'asset',
    currency: 'EUR',
    color: '#aabbcc',
    icon: null,
    opening_balance: '0.00',
    opening_balance_date: null,
    display_order: 0,
    is_archived: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'acc-b',
    user_id: 'u-1',
    name: 'Cuenta ahorro',
    type: 'savings',
    nature: 'asset',
    currency: 'EUR',
    color: '#112233',
    icon: null,
    opening_balance: '0.00',
    opening_balance_date: null,
    display_order: 1,
    is_archived: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

describe('TransferPairCard', () => {
  it('pinta importe, nombres de las dos cuentas y delta_days', () => {
    render(
      <TransferPairCard
        pair={makePair()}
        accounts={accounts}
        primaryAction={{ label: 'Deshacer', onClick: vi.fn() }}
      />,
    );
    expect(screen.getByText(/500/)).toBeDefined();
    expect(screen.getByText('Cuenta nómina')).toBeDefined();
    expect(screen.getByText('Cuenta ahorro')).toBeDefined();
    expect(screen.getByText(/Δ 1d/)).toBeDefined();
  });

  it('omite el chip de delta cuando es 0', () => {
    render(
      <TransferPairCard
        pair={makePair({ delta_days: 0 })}
        accounts={accounts}
        primaryAction={{ label: 'Deshacer', onClick: vi.fn() }}
      />,
    );
    expect(screen.queryByText(/Δ/)).toBeNull();
  });

  it('llama primaryAction.onClick al pulsar el botón', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <TransferPairCard
        pair={makePair()}
        accounts={accounts}
        primaryAction={{ label: 'Enlazar', onClick }}
      />,
    );
    await user.click(screen.getByRole('button', { name: /enlazar/i }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('muestra "Cuenta desconocida" cuando la cuenta no está en la lista', () => {
    render(
      <TransferPairCard
        pair={makePair({ out_account_id: 'acc-missing' })}
        accounts={accounts}
        primaryAction={{ label: 'Deshacer', onClick: vi.fn() }}
      />,
    );
    expect(screen.getByText('Cuenta desconocida')).toBeDefined();
  });

  it('deshabilita el botón cuando primaryAction.busy es true', () => {
    render(
      <TransferPairCard
        pair={makePair()}
        accounts={accounts}
        primaryAction={{ label: 'Deshacer', onClick: vi.fn(), busy: true }}
      />,
    );
    const button = screen.getByRole('button');
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });
});
