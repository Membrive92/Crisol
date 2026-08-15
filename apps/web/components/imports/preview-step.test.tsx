import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import type { ImportPreviewResponse, ImportWarning } from '@crisol/types';

import { PreviewStep } from './preview-step';

/**
 * PHASE-47.A — El aviso "este fichero puede no ser de esta cuenta" es una
 * PARADA, no un banner.
 *
 * En julio de 2026 el extracto de la tarjeta se importó a la cuenta del banco
 * sin un solo error: 19 filas OK. Un aviso que se puede ignorar pulsando
 * Importar habría cambiado nada, así que el botón está apagado hasta que cada
 * aviso lleve su tick, y las claves reconocidas viajan al backend — que vuelve
 * a comprobarlas y responde 409 si falta alguna.
 */

function makePreview(warnings: ImportWarning[] = []): ImportPreviewResponse {
  return {
    job_id: 'job-1',
    source: 'xlsx',
    total_rows: 3,
    rows: [1, 2, 3].map((n) => ({
      amount: `${n}0,00`,
      occurred_at: `0${n}/07/2026`,
      description: 'COMPRA',
      category_name: null,
      statement_balance: null,
    })),
    bank_concept_groups: [],
    warnings,
  };
}

const CROSS_ACCOUNT_WARNING: ImportWarning = {
  key: 'header_matches_other_account',
  message:
    'Este fichero tiene el mismo formato que los que importas en «Tarjeta BBVA».',
  account_id: 'acc-card',
  account_name: 'Tarjeta BBVA',
  matched_rows: 0,
  total_rows: 3,
};

function renderStep(preview: ImportPreviewResponse, onConfirm = vi.fn()) {
  render(
    <PreviewStep
      preview={preview}
      committing={false}
      reprocessing={false}
      canRetryWithVision={false}
      categories={[]}
      errorMessage={null}
      onConfirm={onConfirm}
      onRetryWithVision={vi.fn()}
      onBack={vi.fn()}
    />,
  );
  return { onConfirm };
}

describe('PreviewStep — guardarraíl de cuenta equivocada', () => {
  it('importa sin fricción cuando no hay avisos', () => {
    const { onConfirm } = renderStep(makePreview());
    const button = screen.getByRole('button', { name: /Importar 3 filas/ });
    expect(button.hasAttribute('disabled')).toBe(false);
    fireEvent.click(button);
    expect(onConfirm).toHaveBeenCalledWith({}, []);
  });

  it('apaga el botón mientras quede un aviso sin reconocer', () => {
    renderStep(makePreview([CROSS_ACCOUNT_WARNING]));
    expect(screen.getByText(/Tarjeta BBVA/)).toBeTruthy();
    const button = screen.getByRole('button', { name: /Importar 3 filas/ });
    expect(button.hasAttribute('disabled')).toBe(true);
    expect(screen.getByText(/Revisa los avisos/)).toBeTruthy();
  });

  it('al reconocerlo, importa y manda la clave al backend', () => {
    const { onConfirm } = renderStep(makePreview([CROSS_ACCOUNT_WARNING]));
    fireEvent.click(screen.getByRole('checkbox'));
    const button = screen.getByRole('button', { name: /Importar 3 filas/ });
    expect(button.hasAttribute('disabled')).toBe(false);
    fireEvent.click(button);
    expect(onConfirm).toHaveBeenCalledWith({}, ['header_matches_other_account']);
  });

  it('desmarcar vuelve a apagar el botón', () => {
    renderStep(makePreview([CROSS_ACCOUNT_WARNING]));
    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);
    fireEvent.click(checkbox);
    const button = screen.getByRole('button', { name: /Importar 3 filas/ });
    expect(button.hasAttribute('disabled')).toBe(true);
  });

  it('exige un tick por aviso: reconocer uno no desbloquea los dos', () => {
    renderStep(
      makePreview([
        CROSS_ACCOUNT_WARNING,
        {
          key: 'rows_exist_in_other_account',
          message: '3 de las 3 filas de este fichero ya existen en «Santander».',
          account_id: 'acc-other',
          account_name: 'Santander',
          matched_rows: 3,
          total_rows: 3,
        },
      ]),
    );
    const [first] = screen.getAllByRole('checkbox');
    fireEvent.click(first as HTMLElement);
    const button = screen.getByRole('button', { name: /Importar 3 filas/ });
    expect(button.hasAttribute('disabled')).toBe(true);
  });
});
