import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { KpiStrip, KpiTile } from './kpi-strip';

function deltaColorOf(props: Parameters<typeof KpiTile>[0], text: string): string {
  const { unmount } = render(<KpiTile {...props} />);
  const color = screen.getByText(text).style.color;
  unmount();
  return color;
}

describe('KpiTile', () => {
  it('renderiza label y valor', () => {
    render(<KpiTile label="Patrimonio neto" value="1.234 €" />);
    expect(screen.getByText('Patrimonio neto')).toBeTruthy();
    expect(screen.getByText('1.234 €')).toBeTruthy();
  });

  it('sin delta no pinta el texto del Δ', () => {
    render(<KpiTile label="X" value="1" />);
    expect(screen.queryByText('+5 €')).toBeNull();
  });

  it('el color del Δ depende del signo, e invertDeltaColor lo invierte', () => {
    const up = deltaColorOf({ label: 'X', value: '1', delta: 5, deltaText: '+5 €' }, '+5 €');
    const down = deltaColorOf({ label: 'X', value: '1', delta: -5, deltaText: '-5 €' }, '-5 €');
    // Subir vs bajar → colores distintos (success vs danger).
    expect(up).not.toBe(down);

    // Con invertDeltaColor, subir usa el color de "bajar" y viceversa.
    const upInv = deltaColorOf(
      { label: 'X', value: '1', delta: 5, deltaText: '+5 €', invertDeltaColor: true },
      '+5 €',
    );
    const downInv = deltaColorOf(
      { label: 'X', value: '1', delta: -5, deltaText: '-5 €', invertDeltaColor: true },
      '-5 €',
    );
    expect(upInv).toBe(down);
    expect(downInv).toBe(up);
  });
});

describe('KpiStrip', () => {
  it('renderiza los tiles que recibe como children', () => {
    render(
      <KpiStrip>
        <KpiTile label="A" value="1" />
        <KpiTile label="B" value="2" />
        <KpiTile label="C" value="3" />
        <KpiTile label="D" value="4" />
        <KpiTile label="E" value="5" />
      </KpiStrip>,
    );
    for (const label of ['A', 'B', 'C', 'D', 'E']) {
      expect(screen.getByText(label)).toBeTruthy();
    }
  });
});
