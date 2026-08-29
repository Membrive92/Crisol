import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { RunDiff } from '@crisol/types';

import { RunComparison } from './run-comparison';

/**
 * El comparador de análisis (PHASE-44.24.F).
 *
 * Lo que se comprueba aquí es la regla que gobierna la pantalla: con el método
 * cambiado NO se pintan cambios de la empresa. Enseñarlos «con un aviso»
 * invitaría a leer un corte movido como una degradación del negocio.
 */

function diff(partial: Partial<RunDiff> = {}): RunDiff {
  return {
    comparable: true,
    base_id: 'a',
    target_id: 'b',
    base_date: '2026-01-01T00:00:00Z',
    target_date: '2026-06-01T00:00:00Z',
    method_changes: [],
    years_added: [],
    years_removed: [],
    safety_before: null,
    safety_after: null,
    dividend_before: null,
    dividend_after: null,
    questions: [],
    scores: [],
    bands: [],
    flags: [],
    restatements: [],
    caveat: null,
    ...partial,
  };
}

describe('RunComparison', () => {
  it('el MOTIVO del servidor llega a la pantalla, no una frase genérica', () => {
    // El servidor distingue cuatro causas de 404 y colapsarlas en «hace falta
    // más de un análisis» le da al usuario una explicación que puede ser falsa
    // —y además tapa un 500 o una red caída.
    render(
      <RunComparison
        diff={undefined}
        loading={false}
        reason="Hacen falta dos análisis de este valor para poder compararlos."
      />,
    );
    expect(screen.getByText(/No se ha podido comparar/)).toBeTruthy();
    expect(screen.getByText(/Hacen falta dos análisis de este valor/)).toBeTruthy();
  });

  it('un motivo DISTINTO se dice distinto', () => {
    render(
      <RunComparison
        diff={undefined}
        loading={false}
        reason="Ese análisis es el más antiguo: no hay ninguno anterior con el que compararlo."
      />,
    );
    expect(screen.getByText(/el más antiguo/)).toBeTruthy();
    expect(screen.queryByText(/Hacen falta dos análisis/)).toBeNull();
  });

  it('con el método cambiado no pinta ni una fila de empresa', () => {
    render(
      <RunComparison
        diff={diff({
          comparable: false,
          method_changes: ['el motor pasó de 1.6.0 a 1.7.0'],
          caveat: 'Los dos análisis no se calcularon con el mismo método.',
          bands: [
            {
              key: 'L1',
              band_before: 'healthy',
              band_after: 'stressed',
              value_before: '2',
              value_after: '1',
            },
          ],
        })}
        loading={false}
        reason={null}
      />,
    );
    expect(screen.getByText(/mismo método/)).toBeTruthy();
    expect(screen.getByText(/el motor pasó de 1.6.0 a 1.7.0/)).toBeTruthy();
    expect(screen.queryByText('L1')).toBeNull();
  });

  it('«nada se ha movido» sólo aparece cuando SÍ se podía comparar', () => {
    render(<RunComparison diff={diff()} loading={false} reason={null} />);
    expect(screen.getByText(/Nada se ha movido/)).toBeTruthy();
  });

  it('la dirección se dice en TEXTO, no sólo en color', () => {
    // Un rojo y un verde son indistinguibles para quien no ve el color, y la
    // dirección es justo lo que la pantalla existe para contar.
    render(
      <RunComparison
        diff={diff({
          bands: [
            {
              key: 'S2',
              band_before: 'healthy',
              band_after: 'stressed',
              value_before: '6',
              value_after: '3',
            },
          ],
        })}
        loading={false}
        reason={null}
      />,
    );
    expect(screen.getByText('empeora')).toBeTruthy();
    expect(screen.getByText('S2')).toBeTruthy();
  });

  it('una reexpresión entre las dos fechas se declara', () => {
    // Explica que los números se muevan SIN que la empresa publique un cierre
    // nuevo. Sin esto, el cambio parecería del negocio.
    render(
      <RunComparison
        diff={diff({
          restatements: [
            { fiscal_year: 2023, filing_a: '10-K 2023', filing_b: '10-K 2024', item_count: 3 },
          ],
        })}
        loading={false}
        reason={null}
      />,
    );
    expect(screen.getByText(/reexpresiones/)).toBeTruthy();
    expect(screen.getByText(/3 partidas/)).toBeTruthy();
  });
});
