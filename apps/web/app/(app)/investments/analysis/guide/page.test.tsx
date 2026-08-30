import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { layout } from '@crisol/ui';

import AnalysisGuidePage from './page';

// `BackToReport` lee `?back=` con `useSearchParams`; en jsdom no hay contexto
// de router (mismo patrón que `stitch-expense-breakdown.test.tsx`).
vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
}));

/**
 * El ancho de esta pantalla (PHASE-44.24).
 *
 * La guía fijaba su propio `pageNarrow`, así que en un monitor grande era una
 * columna de 720 px flotando en el centro mientras el informe del que se viene
 * ocupaba la pantalla entera.
 */
describe('AnalysisGuidePage', () => {
  it('usa el ancho de página GLOBAL, no uno propio', () => {
    const { container } = render(<AnalysisGuidePage />);
    const page = container.firstElementChild as HTMLElement;

    expect(page.style.maxWidth).toBe(`${layout.pageWide}px`);
  });

  it('reparte las secciones en columnas para que el ancho no alargue las líneas', () => {
    // Ancho global + una sola columna = definiciones de borde a borde, que es
    // el defecto que `layout.prose` existe para evitar. Las dos mitades van
    // juntas: sin el grid, ensanchar la página empeora la legibilidad.
    render(<AnalysisGuidePage />);
    // Se sube desde el título de una sección hasta el primer ancestro en grid:
    // atarlo a la posición del hijo lo rompería al mover un bloque.
    let grid: HTMLElement | null = screen.getByText('Los colores').parentElement;
    while (grid && grid.style.display !== 'grid') grid = grid.parentElement;
    if (!grid) throw new Error('las secciones de la guía no están en un grid');

    expect(grid.style.gridTemplateColumns).toContain('auto-fill');
    expect(grid.style.gridTemplateColumns).toContain(`${layout.prose}px`);
  });
});
