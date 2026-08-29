import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { AnalysisRun, DuPontDecomposition } from '@crisol/types';

import { buildCatalogIndex, buildMetricIndex } from '@crisol/ui';
import { TabRatios } from './tab-ratios';
import legacyRun from './__fixtures__/legacy-run-1.0.0.json';

/**
 * La fila «Comprobación» del DuPont contrasta el producto de los factores con
 * el ROE: debe dar cero. El cuadre llegó en PHASE-44.10, así que un análisis
 * anterior no lo trae.
 *
 * Cuando `undefined` y `null` se trataban igual, la guarda `raw === null` no
 * saltaba (`undefined !== null`), `Number(undefined)` daba `NaN` y la celda
 * salía **en rojo** con el título «la identidad NO cierra: hay un problema en
 * los datos o en una fórmula». Es decir: la pantalla denunciaba un descuadre
 * contable inexistente en las cuentas de una empresa real. Peor que un crash,
 * porque nadie lo reporta — se lo cree.
 *
 * La descomposición de la fixture es la REAL persistida (MCD, motor 1.0.0).
 */

// Frontera de datos: JSON crudo de la BD del usuario, sin tipar.
const LEGACY_DUPONT = legacyRun.dupont as unknown as DuPontDecomposition[];

function makeRun(dupont: DuPontDecomposition[]): AnalysisRun {
  const empty = { metrics: [], flags: [] };
  return {
    id: 'run-1',
    security_id: 'sec-1',
    run_date: '2026-07-26T10:00:00Z',
    engine_version: legacyRun.engine_version,
    thresholds_version: 'a'.repeat(64),
    thresholds_used: {},
    years_covered: dupont.map((d) => d.fiscal_year),
    m_score: null,
    z_score: null,
    z_variant: null,
    f_score: null,
    accruals_ratio: null,
    fcf_payout: null,
    fcf_coverage: null,
    dividend_verdict: 'healthy',
    confidence: '0.9',
    scores_detail: {
      forensic: { ...empty, breakdowns: [] },
      base_ratios: { ...empty, dupont },
    },
    dividend_analysis: {
      ...empty,
      dps_series: [],
      trajectory: { streak_no_cut: 0, momentum_slowdown: false },
    },
    evolution: { ...empty, horizontal: [], vertical: [] },
    flags: [],
    verdict: {
      questions: [],
      safety_profile: { label: 'watch', blocking_reasons: [] },
      dividend_verdict: 'healthy',
      stress: {
        scenarios: [],
        contribution_margin: null,
        breakeven_fcf_drop: null,
        not_computable_reason: null,
      },
    },
    data_completeness: {
      value: '0.9',
      completeness_core: '0.9',
      staleness_factor: '1.0',
      imputed_core_count: 0,
      latest_fiscal_year_end: '2024-12-31',
      days_stale: 200,
    },
  };
}

function renderDuPont(dupont: DuPontDecomposition[]) {
  const run = makeRun(dupont);
  return render(
    <TabRatios
      run={run}
      index={buildMetricIndex([], run.years_covered)}
      catalog={buildCatalogIndex([])}
      sub="dupont"
      onSubChange={vi.fn()}
    />,
  );
}

describe('TabRatios · DuPont de un análisis de un motor anterior', () => {
  it('la fixture no trae los cuadres (si los trae, ya no prueba nada)', () => {
    expect(LEGACY_DUPONT.length).toBeGreaterThan(0);
    for (const point of LEGACY_DUPONT) {
      expect(point.check_three).toBeUndefined();
      expect(point.check_five).toBeUndefined();
    }
  });

  it('no pinta «NaN» ni acusa a las cuentas de un descuadre inexistente', () => {
    renderDuPont(LEGACY_DUPONT);
    expect(screen.queryByText('NaN')).toBeNull();
    expect(screen.queryByText(/la identidad NO cierra/)).toBeNull();
  });

  it('dice que el cuadre no se emitía, en vez de callarse', () => {
    renderDuPont(LEGACY_DUPONT);
    expect(
      screen.getAllByTitle(/motor anterior, que no emitía la comprobación/).length,
    ).toBeGreaterThan(0);
  });

  it('un cuadre que SÍ está y no cierra se sigue denunciando', () => {
    // El arreglo no puede silenciar el caso real: si el motor emitió el cuadre
    // y no da cero, eso sí es un problema y tiene que verse en rojo.
    const roto = LEGACY_DUPONT.map((point) => ({ ...point, check_three: '0.05' }));
    renderDuPont(roto);
    expect(screen.getAllByTitle(/la identidad NO cierra/).length).toBeGreaterThan(0);
  });

  it('un cuadre `null` sigue siendo «no verificable», nunca superado', () => {
    const sinFactor = LEGACY_DUPONT.map((point) => ({ ...point, check_three: null }));
    renderDuPont(sinFactor);
    expect(screen.getAllByText('no verificable').length).toBeGreaterThan(0);
  });
});

/**
 * El CABLEADO de `highlightKey` hasta una pestaña real (revisión adversarial):
 * `YearMatrix` aislada ya se probaba; que la pestaña pase el valor a sus
 * matrices, no.
 */
describe('TabRatios · la fila a la que se ha llegado', () => {
  it('marca la fila de `highlightKey` en la familia abierta', () => {
    const run = makeRun([]);
    const { container } = render(
      <TabRatios
        run={run}
        index={buildMetricIndex([], run.years_covered)}
        catalog={buildCatalogIndex([])}
        sub="liquidez"
        onSubChange={vi.fn()}
        highlightKey="L1"
      />,
    );
    const marcada = container.querySelector('[aria-current="true"]');
    expect(marcada).not.toBeNull();
    expect(marcada?.textContent).toContain('L1');
  });
});
