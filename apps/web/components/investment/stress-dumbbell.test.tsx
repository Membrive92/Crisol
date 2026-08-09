import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { StressScenario } from '@crisol/types';

import { StressDumbbell } from './stress-dumbbell';

/**
 * Lo que decide en el dibujo del stress no es el movimiento, es si el escenario
 * cruza la línea del 1,0 — por debajo, la caja libre deja de cubrir el
 * dividendo. Un dumbbell que deje esa referencia fuera del lienzo enseña
 * movimiento sin consecuencia.
 */

function scenario(over: Partial<StressScenario> = {}): StressScenario {
  return {
    key: 'ST1_revenue_-20',
    parameter: 'Ventas −20%',
    coverage_before: '2.5',
    coverage_after: '1.9',
    sentence: 'Con las ventas cayendo un 20%, la cobertura pasa de 2,5× a 1,9×.',
    label: 'escenario hipotético',
    ...over,
  };
}

describe('StressDumbbell', () => {
  it('sin escenarios calculables no dibuja nada', () => {
    const { container } = render(
      <StressDumbbell
        scenarios={[scenario({ coverage_before: null, coverage_after: null })]}
      />,
    );
    expect(container.querySelector('svg')).toBeNull();
  });

  it('la línea del 1,0 entra en el lienzo aunque TODO quede por debajo', () => {
    // Si la escala se ajustara sólo a los datos, un valor máximo de 0,6 dejaría
    // la referencia fuera y con ella la única lectura que importa.
    const { container } = render(
      <StressDumbbell
        scenarios={[scenario({ coverage_before: '0.6', coverage_after: '0.4' })]}
      />,
    );
    const svg = container.querySelector('svg');
    expect(svg?.textContent).toContain('1,0');
  });

  it('la frase que redactó el motor viaja con la marca', () => {
    const { container } = render(<StressDumbbell scenarios={[scenario()]} />);
    expect(container.querySelector('title')?.textContent).toContain('2,5× a 1,9×');
  });

  it('el valor de después se escribe, no sólo se dibuja', () => {
    const { container } = render(<StressDumbbell scenarios={[scenario()]} />);
    expect(container.querySelector('svg')?.textContent).toContain('1,9×');
  });
});
