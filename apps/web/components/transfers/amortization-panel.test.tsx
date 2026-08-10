import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import type { Account, AmortizationEffect, Transaction } from '@crisol/types';

const accounts: Account[] = [];
let amortizationState: AmortizationEffect | null = null;
let previewResult: AmortizationEffect | null = null;
const amortizeMutate = vi.fn();
const undoMutate = vi.fn();

vi.mock('@crisol/services', () => ({
  formatApiError: (_err: unknown, fallback: string) => fallback,
  useAccounts: () => ({ data: accounts }),
  useAmortization: () => ({ data: amortizationState, isLoading: false }),
  usePreviewAmortization: () => ({
    isPending: false,
    mutate: (
      _payload: unknown,
      opts?: { onSuccess?: (r: AmortizationEffect) => void },
    ) => {
      if (previewResult) opts?.onSuccess?.(previewResult);
    },
  }),
  useAmortize: () => ({ isPending: false, mutate: amortizeMutate }),
  useUndoAmortization: () => ({ isPending: false, mutate: undoMutate }),
}));

vi.mock('@crisol/store', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

// Importado DESPUÉS de los mocks: el componente los resuelve al cargarse.
const { AmortizationPanel } = await import('./amortization-panel');

function makeAccount(overrides: Partial<Account> = {}): Account {
  return {
    id: 'card-1',
    user_id: 'u-1',
    name: 'Tarjeta BBVA',
    type: 'credit_card',
    nature: 'liability',
    currency: 'EUR',
    opening_balance: '0.00',
    is_archived: false,
    is_default: false,
    counts_as_debt: true,
    parent_account_id: null,
    color: null,
    icon: null,
    apr: null,
    tae: null,
    term_months: null,
    start_date: null,
    total_to_pay: null,
    interest_only_first_payment: null,
    anchored_statement_balance: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  } as Account;
}

function makeTx(overrides: Partial<Transaction> = {}): Transaction {
  return {
    id: 'tx-1',
    user_id: 'u-1',
    account_id: 'bank-1',
    category_id: null,
    transfer_pair_id: null,
    amount: '400.00',
    currency: 'EUR',
    occurred_at: '2026-07-08T00:00:00Z',
    description: 'Adeudo mensual de tarjeta',
    source: 'import',
    receipt_id: null,
    created_at: '2026-07-08T00:00:00Z',
    updated_at: '2026-07-08T00:00:00Z',
    deleted_at: null,
    converted_amount: null,
    converted_currency: null,
    flow: 'TRANSFER_OUT',
    is_debt_pair: false,
    ...overrides,
  } as Transaction;
}

function makeEffect(overrides: Partial<AmortizationEffect> = {}): AmortizationEffect {
  return {
    source_transaction_id: 'tx-1',
    liability_account_id: 'card-1',
    liability_account_name: 'Tarjeta BBVA',
    amount: '400.00',
    currency: 'EUR',
    counts_as_expense: false,
    suggested_counts_as_expense: false,
    suggestion_reason: 'Ya cuentan como gasto en su mes.',
    mode: 'movement',
    installments_marked: 0,
    principal_covered: '400.00',
    principal_uncovered: '0.00',
    outstanding_before: '1000.00',
    outstanding_after: '600.00',
    counterpart_transaction_id: null,
    paired: false,
    dry_run: true,
    ...overrides,
  };
}

function reset() {
  accounts.length = 0;
  amortizationState = null;
  previewResult = null;
  amortizeMutate.mockReset();
  undoMutate.mockReset();
}

describe('AmortizationPanel', () => {
  it('sin cuentas de deuda elegibles lo dice en vez de enseñar un selector vacío', () => {
    reset();
    render(<AmortizationPanel transaction={makeTx()} />);
    expect(screen.getByText(/No tienes cuentas de deuda/)).toBeTruthy();
  });

  it('excluye la propia cuenta del movimiento y las de otra divisa', () => {
    reset();
    accounts.push(
      makeAccount({ id: 'bank-1', nature: 'liability', name: 'Es la propia' }),
      makeAccount({ id: 'usd', currency: 'USD', name: 'Tarjeta USD' }),
      makeAccount({ id: 'card-1', name: 'Tarjeta BBVA' }),
    );
    render(<AmortizationPanel transaction={makeTx()} />);
    const options = screen.getAllByRole('option').map((o) => o.textContent);
    expect(options).toContain('Tarjeta BBVA');
    expect(options).not.toContain('Es la propia');
    expect(options).not.toContain('Tarjeta USD');
  });

  it('al elegir deuda enseña el efecto y preselecciona la sugerencia del servidor', async () => {
    reset();
    accounts.push(makeAccount());
    previewResult = makeEffect({ suggested_counts_as_expense: false });
    render(<AmortizationPanel transaction={makeTx()} />);

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'card-1' } });

    await waitFor(() => {
      expect(screen.getByText(/Creará el movimiento contrario/)).toBeTruthy();
    });
    // La sugerencia llega marcada, con su motivo a la vista.
    const neutral = screen.getByRole('button', { name: 'No, es neutro' });
    expect(neutral.getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText(/Ya cuentan como gasto en su mes/)).toBeTruthy();
  });

  it('avisa cuando el pago no cubre ninguna cuota — y aun así deja registrarlo', async () => {
    reset();
    accounts.push(makeAccount({ id: 'loan-1', type: 'loan', name: 'Prestamo' }));
    previewResult = makeEffect({
      liability_account_id: 'loan-1',
      liability_account_name: 'Prestamo',
      mode: 'schedule',
      installments_marked: 0,
      principal_covered: '0.00',
      principal_uncovered: '400.00',
      outstanding_after: '1000.00',
      suggested_counts_as_expense: true,
    });
    render(<AmortizationPanel transaction={makeTx()} />);
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'loan-1' } });

    await waitFor(() => {
      expect(screen.getByText(/no bajará/)).toBeTruthy();
    });
    expect(screen.getByRole('button', { name: 'Registrar amortización' })).toBeTruthy();
  });

  it('cambiar la elección enseña qué sugería la app, sin callárselo', async () => {
    reset();
    accounts.push(makeAccount());
    previewResult = makeEffect({ suggested_counts_as_expense: false });
    render(<AmortizationPanel transaction={makeTx()} />);
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'card-1' } });
    await waitFor(() => screen.getByRole('button', { name: 'Sí, es gasto' }));

    fireEvent.click(screen.getByRole('button', { name: 'Sí, es gasto' }));
    expect(screen.getByText(/sugería «No, es neutro»/)).toBeTruthy();
  });

  it('envía la declaración del usuario, no la sugerencia', async () => {
    reset();
    accounts.push(makeAccount());
    previewResult = makeEffect({ suggested_counts_as_expense: false });
    render(<AmortizationPanel transaction={makeTx()} />);
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'card-1' } });
    await waitFor(() => screen.getByRole('button', { name: 'Sí, es gasto' }));

    fireEvent.click(screen.getByRole('button', { name: 'Sí, es gasto' }));
    fireEvent.click(screen.getByRole('button', { name: 'Registrar amortización' }));

    expect(amortizeMutate).toHaveBeenCalledTimes(1);
    expect(amortizeMutate.mock.calls[0]?.[0]).toEqual({
      source_transaction_id: 'tx-1',
      liability_account_id: 'card-1',
      counts_as_expense: true,
    });
  });

  it('ya registrada: resume lo que hizo y ofrece deshacerlo, sin selector', () => {
    reset();
    accounts.push(makeAccount());
    amortizationState = makeEffect({
      mode: 'schedule',
      installments_marked: 2,
      liability_account_name: 'Prestamo',
      counts_as_expense: true,
      dry_run: false,
    });
    render(<AmortizationPanel transaction={makeTx()} />);

    expect(screen.getByText(/amortiza Prestamo/)).toBeTruthy();
    expect(screen.getByText(/Marcó 2 cuotas/)).toBeTruthy();
    expect(screen.queryByRole('combobox')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Deshacer registro' }));
    expect(undoMutate).toHaveBeenCalledTimes(1);
    expect(undoMutate.mock.calls[0]?.[0]).toBe('tx-1');
  });
});
