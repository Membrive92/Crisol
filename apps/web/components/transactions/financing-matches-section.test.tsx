import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import type { FinancingMatch, TransferPair } from '@crisol/types';

let matches: FinancingMatch[] = [];
const convertMutate = vi.fn();
const toastSuccess = vi.fn();

vi.mock('@crisol/services', () => ({
  formatApiError: (_err: unknown, fallback: string) => fallback,
  useFinancingMatches: () => ({ data: matches, isLoading: false }),
  useConvertToDebt: () => ({ isPending: false, mutate: convertMutate }),
}));

vi.mock('@crisol/store', () => ({
  toast: { success: toastSuccess, error: vi.fn() },
}));

// Importado DESPUÉS de los mocks: el componente los resuelve al cargarse.
const { FinancingMatchesSection } = await import('./financing-matches-section');

function makeMatch(overrides: Partial<FinancingMatch> = {}): FinancingMatch {
  return {
    transaction_id: 'tx-1',
    description: 'Recibo anterior jun-26 Otras financiaciones',
    amount: '700.26',
    currency: 'EUR',
    occurred_at: '2026-07-04T22:00:00Z',
    counted_as_income: true,
    liability_id: 'liab-1',
    liability_name: 'Compra finaciada recibo junio',
    schedule_principal: '700.26',
    reason:
      'El cuadro de «Compra finaciada recibo junio» tiene un capital de 700.26 EUR, el mismo importe que este abono.',
    ...overrides,
  };
}

describe('FinancingMatchesSection', () => {
  it('no pinta nada cuando no hay propuestas', () => {
    matches = [];
    const { container } = render(<FinancingMatchesSection />);
    // Cero ruido: una sección vacía en la pantalla principal entrena a
    // ignorarla, y cuando de verdad haya algo ya no se mira.
    expect(container.innerHTML).toBe('');
  });

  it('avisa de que ese abono está contando como ingreso HOY', () => {
    // Es la información que motiva el gesto: sin ella la propuesta parece
    // burocracia, y con ella el usuario ve qué número está mal.
    matches = [makeMatch({ counted_as_income: true })];
    render(<FinancingMatchesSection />);
    expect(screen.getByText(/Ahora suma como ingreso/i)).toBeTruthy();
  });

  it('no acusa de contar como ingreso a un abono que ya es neutro', () => {
    matches = [makeMatch({ counted_as_income: false })];
    render(<FinancingMatchesSection />);
    expect(screen.queryByText(/Ahora suma como ingreso/i)).toBeNull();
    // Pero sigue proponiéndose: es neutro y aún así le falta su deuda detrás.
    expect(screen.getByRole('button', { name: /Es una financiación/i })).toBeTruthy();
  });

  it('enlaza contra la deuda propuesta, no contra otra cosa', () => {
    matches = [makeMatch()];
    render(<FinancingMatchesSection />);
    fireEvent.click(screen.getByRole('button', { name: /Es una financiación/i }));
    expect(convertMutate).toHaveBeenCalledWith(
      { source_transaction_id: 'tx-1', destination_account_id: 'liab-1' },
      expect.anything(),
    );
  });

  it('no promete que se haya retirado ninguna otra fila', () => {
    // PHASE-47.F: enlazar ya no borra el cargo que compensa al abono — las dos
    // líneas se quedan y se cancelan solas en el saldo. Prometer un borrado que
    // no ocurre manda al usuario a buscarlo a la papelera.
    matches = [makeMatch()];
    convertMutate.mockImplementation(
      (_payload: unknown, opts?: { onSuccess?: (p: TransferPair) => void }) => {
        opts?.onSuccess?.({} as TransferPair);
      },
    );
    render(<FinancingMatchesSection />);
    fireEvent.click(screen.getByRole('button', { name: /Es una financiación/i }));
    expect(toastSuccess).toHaveBeenCalledWith(expect.stringContaining('ya no cuenta como ingreso'));
    expect(toastSuccess).not.toHaveBeenCalledWith(expect.stringContaining('espejo'));
  });
});
