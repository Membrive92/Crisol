import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { HorizontalSeries } from '@crisol/types';

import { DeltaHeatmap } from './delta-heatmap';

/**
 * El heatmap sustituye a una tabla de números, así que su obligación es no
 * perder nada por el camino: el signo, el valor y la distinción entre «no se
 * movió» y «no hay con qué comparar».
 */

function serie(over: Partial<HorizontalSeries> = {}): HorizontalSeries {
  return {
    key: 'revenue',
    label: 'Ventas',
    points: [
      { fiscal_year: 2023, value: '1000', yoy: null },
      { fiscal_year: 2024, value: '1300', yoy: '0.3' },
    ],
    cagr: '0.3',
    cagr_reason: null,
    ...over,
  };
}

describe('DeltaHeatmap', () => {
  it('el valor va impreso: el color no puede ser la única fuente', () => {
    // Los polos de la escala son indistinguibles bajo protanopía (ΔE 2,6
    // medido), así que quitar el número dejaría la tabla ilegible para una de
    // cada doce personas.
    render(<DeltaHeatmap series={[serie()]} years={[2023, 2024]} />);
    expect(screen.getByText('+30,0%')).toBeTruthy();
  });

  it('el signo va delante de un crecimiento, que es la mitad del dato', () => {
    render(
      <DeltaHeatmap
        series={[serie({ points: [
          { fiscal_year: 2023, value: '1000', yoy: null },
          { fiscal_year: 2024, value: '800', yoy: '-0.2' },
        ] })]}
        years={[2023, 2024]}
      />,
    );
    expect(screen.getByText('-20,0%')).toBeTruthy();
  });

  it('el primer ejercicio no se pinta: no tiene con qué compararse', () => {
    render(<DeltaHeatmap series={[serie()]} years={[2023, 2024]} />);
    // La cabecera arranca en el segundo año.
    expect(screen.queryByRole('columnheader', { name: '2023' })).toBeNull();
    expect(screen.getByRole('columnheader', { name: '2024' })).toBeTruthy();
  });

  it('una serie entera sin variación no ocupa una fila muda', () => {
    const vacia = serie({
      key: 'wc_total',
      label: 'Fondo de maniobra',
      points: [
        { fiscal_year: 2023, value: null, yoy: null },
        { fiscal_year: 2024, value: null, yoy: null },
      ],
    });
    render(<DeltaHeatmap series={[serie(), vacia]} years={[2023, 2024]} />);
    expect(screen.queryByText('Fondo de maniobra')).toBeNull();
    expect(screen.getByText('Ventas')).toBeTruthy();
  });

  it('con un solo ejercicio lo dice en vez de pintar una rejilla vacía', () => {
    render(<DeltaHeatmap series={[serie()]} years={[2024]} />);
    expect(screen.getByText(/al menos dos ejercicios consecutivos/)).toBeTruthy();
  });
});
