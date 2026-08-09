import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { AnalysisRun, DpsPoint, MetricResult, Security } from '@crisol/types';

import { buildCatalogIndex, buildMetricIndex } from '@crisol/ui';
import { TabDividend } from './tab-dividend';

/**
 * PHASE-44.19 — `dividend_verdict === 'not_applicable'` colapsa DOS situaciones
 * (`synthesis.py:520`): una financiera, aunque reparta, y una empresa que no
 * reparte. La pestaña se ocultaba entera con esa etiqueta, y con ella ocho
 * métricas que el motor YA había calculado con valor y banda — entre ellas las
 * cuatro de calidad de la caja, que **no dependen del dividendo en absoluto**.
 */

const YEARS = [2023, 2024];

function metric(key: string, fiscal_year: number, value: string | null): MetricResult {
  return {
    key,
    fiscal_year,
    value,
    band: value === null ? null : 'healthy',
    status: value === null ? 'not_computable' : 'ok',
    provenance: 'sourced',
    reason: value === null ? 'no aplica' : null,
  };
}

/** Q1..Q3 y Q5 son las de calidad de la caja: se calculan siempre. */
const QUALITY = ['Q1', 'Q2', 'Q3', 'Q5'].flatMap((key) =>
  YEARS.map((year) => metric(key, year, '1.20')),
);

function makeRun(dps: (string | null)[]): AnalysisRun {
  const empty = { metrics: [], flags: [] };
  const dps_series: DpsPoint[] = YEARS.map((fiscal_year, i) => ({
    fiscal_year,
    dps: dps[i] ?? null,
  }));
  return {
    id: 'run-1',
    security_id: 'sec-1',
    run_date: '2026-08-09T10:00:00Z',
    engine_version: '1.3.0',
    thresholds_version: 'a'.repeat(64),
    thresholds_used: {},
    years_covered: YEARS,
    m_score: null,
    z_score: null,
    z_variant: null,
    f_score: null,
    accruals_ratio: null,
    fcf_payout: null,
    fcf_coverage: null,
    dividend_verdict: 'not_applicable',
    confidence: '0.9',
    scores_detail: {
      forensic: { ...empty, breakdowns: [] },
      base_ratios: { ...empty, dupont: [] },
    },
    dividend_analysis: {
      metrics: QUALITY,
      flags: [],
      dps_series,
      trajectory: { streak_no_cut: 0, momentum_slowdown: false },
    },
    evolution: { ...empty, horizontal: [], vertical: [] },
    flags: [],
    verdict: {
      questions: [],
      safety_profile: { label: 'watch', blocking_reasons: [] },
      dividend_verdict: 'not_applicable',
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
      days_stale: 100,
    },
  };
}

function renderTab(run: AnalysisRun, security?: Partial<Security>) {
  return render(
    <TabDividend
      run={run}
      index={buildMetricIndex(run.dividend_analysis.metrics, YEARS)}
      catalog={buildCatalogIndex([])}
      security={security as Security | undefined}
    />,
  );
}

describe('TabDividend cuando el motor dice «no aplica»', () => {
  it('una empresa que NO reparte conserva la calidad de la caja', () => {
    // El caso que estaba roto: la calidad de la caja mide si el beneficio se
    // convierte en caja, y eso no depende de que se reparta o no.
    renderTab(makeRun([null, null]));
    expect(screen.getByText(/Sin dividendo que juzgar/)).toBeTruthy();
    expect(screen.getByText(/La calidad de la caja sí se calcula/)).toBeTruthy();
    // Y sus filas están de verdad en el DOM, no sólo la promesa de la nota.
    // Sin catálogo la etiqueta de la fila es la propia clave.
    for (const key of ['Q1', 'Q2', 'Q3', 'Q5']) {
      expect(screen.getByText(key)).toBeTruthy();
    }
  });

  it('una financiera que SÍ reparte no pierde la pestaña', () => {
    renderTab(makeRun(['0.80', '0.90']), { is_financial: true });
    expect(screen.queryByText(/Sin dividendo que juzgar/)).toBeNull();
    // Y se dice por qué faltan las de caja libre, en vez de esconderlo todo.
    expect(screen.getByText(/no significa lo que significa en una industrial/)).toBeTruthy();
  });

  it('una empresa normal que reparte no ve el aviso de financiera', () => {
    renderTab(makeRun(['0.80', '0.90']), { is_financial: false });
    expect(screen.queryByText(/es una .*financiera/)).toBeNull();
    expect(screen.queryByText(/Sin dividendo que juzgar/)).toBeNull();
  });
});
