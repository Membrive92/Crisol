import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { PositionPoint } from '@crisol/types';

import { NetworthEvolutionCard } from './networth-evolution-card';

function point(month: string, net: number): PositionPoint {
  return {
    month,
    total_assets: String(net + 1000),
    total_liabilities: '1000',
    net_worth: String(net),
    is_projection: false,
  };
}

describe('NetworthEvolutionCard', () => {
  it('muestra empty state con menos de 2 puntos y no crashea', () => {
    render(<NetworthEvolutionCard points={[]} currency="EUR" isLoading={false} />);
    expect(screen.getByText(/al menos 2 meses/i)).toBeTruthy();
  });

  it('renderiza el título y la leyenda con una serie válida', () => {
    const points = Array.from({ length: 12 }, (_, i) => point(`2026-${String(i + 1).padStart(2, '0')}-01`, 1000 + i * 100));
    render(<NetworthEvolutionCard points={points} currency="EUR" isLoading={false} />);
    expect(screen.getByText('Evolución del patrimonio')).toBeTruthy();
    expect(screen.getByText('Neto')).toBeTruthy();
    expect(screen.getByText('Activos')).toBeTruthy();
    expect(screen.getByText('Pasivos')).toBeTruthy();
  });
});
