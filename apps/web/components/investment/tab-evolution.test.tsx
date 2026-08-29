import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { AnalysisRun } from '@crisol/types';

import { buildCatalogIndex, buildMetricIndex } from '@crisol/ui';
import { TabEvolution } from './tab-evolution';

/**
 * Evolución con un run de motor anterior.
 *
 * Un run de 1.0.0 trae `evolution` sin `horizontal` (ausente, no vacío). La
 * pantalla pintaba una tabla con cabecera de años y cero filas, que se leía
 * como «esta empresa no tiene evolución». La fixture real de MCD que usa
 * `tab-verdict.test.tsx` es un recorte (preguntas y DuPont), así que aquí el
 * run se construye con lo MÍNIMO que la pestaña lee — y el caso «ausente» se
 * escribe OMITIENDO la clave, no poniéndola a `[]`, que es otro caso.
 */
function runWith(evolution: Record<string, unknown>, engine = '1.0.0'): AnalysisRun {
  return {
    engine_version: engine,
    years_covered: [2023, 2024],
    thresholds_used: {},
    evolution,
  } as unknown as AnalysisRun;
}

const YEARS = [2023, 2024];

describe('TabEvolution con un run viejo', () => {
  it('dice que la sección no existe en ese motor, en vez de una tabla vacía', () => {
    const run = runWith({});
    render(
      <TabEvolution
        run={run}
        index={buildMetricIndex([], YEARS)}
        catalog={buildCatalogIndex(undefined)}
      />,
    );
    expect(screen.getByText(/no tiene serie de evolución/)).toBeTruthy();
    expect(screen.getByText(/motor 1\.0\.0/)).toBeTruthy();
    expect(screen.queryByText('Magnitud')).toBeNull();
  });

  it('una serie VACÍA no es una serie ausente: se pinta la pestaña', () => {
    // `[]` significa «el motor la calculó y no hay magnitudes»; `undefined`,
    // «ese motor no la producía». Colapsarlos volvería a esconder el motivo.
    const run = runWith({ horizontal: [], vertical: [], metrics: [], flags: [] }, '1.7.0');
    render(
      <TabEvolution
        run={run}
        index={buildMetricIndex([], YEARS)}
        catalog={buildCatalogIndex(undefined)}
      />,
    );
    expect(screen.queryByText(/no tiene serie de evolución/)).toBeNull();
    // Y se pinta la pestaña de verdad: un test que sólo niega pasa por vacuidad.
    expect(screen.getAllByText(/Magnitud/).length).toBeGreaterThan(0);
  });
});
