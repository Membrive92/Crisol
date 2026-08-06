import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { AnalysisRun, MetricDefinition, QuestionSignal } from '@crisol/types';

import { buildCatalogIndex } from './metric-index';
import { TabVerdict } from './tab-verdict';

/**
 * Lo que se prueba aquí es el requisito estrella del usuario: entender POR QUÉ
 * la empresa sale catalogada como sale.
 *
 * Las dos regresiones concretas que cierra:
 *  - la pantalla imprimía `M-Score · B4_dividend_funded_externally`, o sea la
 *    clave cruda de la bandera;
 *  - una financiera pintaba VERDE en «¿La contabilidad es de fiar?» por
 *    ausencia de prueba, sin que el cliente pudiera distinguirlo de la salud.
 */

const CATALOG: MetricDefinition[] = [
  {
    key: 'm_score',
    label: 'M-Score de Beneish',
    family: 'forense',
    unit: 'score',
    direction: 'lower_better',
    low_alarm: null,
    low_ok: null,
    high_ok: '-2.22',
    high_alarm: '-1.78',
    model_variant: null,
    note: '',
  },
];

function signal(partial: Partial<QuestionSignal>): QuestionSignal {
  return {
    key: 'm_score',
    label: 'M-Score de Beneish',
    kind: 'metric',
    band: 'healthy',
    value: '-2.41',
    status: 'ok',
    counted: true,
    reason: null,
    ...partial,
  };
}

function makeRun(overrides: Partial<AnalysisRun> = {}): AnalysisRun {
  const empty = { metrics: [], flags: [] };
  return {
    id: 'run-1',
    security_id: 'sec-1',
    run_date: '2026-07-30T18:04:00Z',
    engine_version: '1.1.0',
    thresholds_version: 'a'.repeat(64),
    thresholds_used: {},
    years_covered: [2023, 2024],
    m_score: '-2.41',
    z_score: '3.82',
    z_variant: "Z''(1995)",
    f_score: 7,
    accruals_ratio: '0.03',
    fcf_payout: '0.5',
    fcf_coverage: '1.9',
    dividend_verdict: 'healthy',
    confidence: '0.92',
    scores_detail: {
      forensic: { ...empty, breakdowns: [] },
      base_ratios: { ...empty, dupont: [] },
    },
    dividend_analysis: {
      ...empty,
      dps_series: [],
      trajectory: { streak_no_cut: 5, momentum_slowdown: false },
    },
    evolution: { ...empty, horizontal: [], vertical: [] },
    flags: [],
    verdict: {
      questions: [
        {
          key: 'accounting',
          question: '¿La contabilidad es de fiar?',
          verdict: 'healthy',
          red_signals: [],
          amber_signals: [],
          signals: [signal({})],
          evaluated_count: 1,
          unavailable_count: 0,
        },
      ],
      safety_profile: { label: 'conservative', blocking_reasons: [] },
      dividend_verdict: 'healthy',
      stress: {
        scenarios: [],
        contribution_margin: null,
        breakeven_fcf_drop: null,
        not_computable_reason: null,
      },
    },
    data_completeness: {
      value: '0.92',
      completeness_core: '0.92',
      staleness_factor: '1.0',
      imputed_core_count: 0,
      latest_fiscal_year_end: '2024-12-31',
      days_stale: 120,
    },
    ...overrides,
  };
}

function renderVerdict(run: AnalysisRun) {
  return render(
    <TabVerdict
      run={run}
      catalog={buildCatalogIndex(CATALOG)}
      statements={undefined}
      items={undefined}
      sub="dictamen"
      onSubChange={vi.fn()}
    />,
  );
}

describe('TabVerdict', () => {
  it('imprime las cinco condiciones de Conservador, no sólo el sello', () => {
    renderVerdict(makeRun());
    expect(screen.getByText('F-Score ≥ 7')).toBeTruthy();
    expect(screen.getByText('Accruals en verde')).toBeTruthy();
    expect(screen.getByText(/Se evita si se cumple/i)).toBeTruthy();
  });

  it('enseña la regla del semáforo, no sólo su resultado', () => {
    renderVerdict(makeRun());
    expect(screen.getByText(/si hay ≥1 señal roja/)).toBeTruthy();
  });

  it('al abrir una pregunta muestra el valor de cada señal con su unidad', async () => {
    const user = userEvent.setup();
    renderVerdict(makeRun());
    await user.click(screen.getByRole('button', { name: /¿La contabilidad es de fiar\?/ }));
    expect(screen.getByText('M-Score de Beneish')).toBeTruthy();
    expect(screen.getByText('-2,41')).toBeTruthy();
    expect(screen.getByText('sano ≤ -2,22 · riesgo > -1,78')).toBeTruthy();
  });

  it('ninguna señal se imprime como clave cruda', async () => {
    const user = userEvent.setup();
    const run = makeRun();
    const question = run.verdict.questions[0];
    if (question) {
      question.signals = [
        signal({
          key: 'B4_dividend_funded_externally',
          label: 'Dividendo financiado con deuda o emisión',
          kind: 'flag',
          band: null,
          value: null,
          status: null,
          counted: false,
          reason: 'no se ha encendido',
        }),
      ];
    }
    renderVerdict(run);
    await user.click(screen.getByRole('button', { name: /¿La contabilidad es de fiar\?/ }));
    expect(screen.queryByText(/B4_dividend_funded_externally/)).toBeNull();
    expect(screen.getByText('Dividendo financiado con deuda o emisión')).toBeTruthy();
  });

  it('una pregunta sin señales evaluadas se marca «Sin evidencia», no verde', () => {
    const run = makeRun();
    const question = run.verdict.questions[0];
    if (question) {
      question.evaluated_count = 0;
      question.unavailable_count = 1;
      question.signals = [
        signal({
          band: null,
          value: null,
          status: 'not_computable',
          counted: false,
          reason: 'modelo no aplicable a financieras',
        }),
      ];
    }
    renderVerdict(run);
    expect(screen.getByText('Sin evidencia')).toBeTruthy();
    expect(screen.getByText(/por ausencia de prueba/)).toBeTruthy();
  });

  it('declara que la valoración no entra y por qué', () => {
    renderVerdict(makeRun());
    expect(screen.getByText(/necesitan precio de mercado/)).toBeTruthy();
  });

  it('imprime el hash de umbrales completo, no truncado', () => {
    renderVerdict(makeRun());
    expect(screen.getByText(new RegExp('a'.repeat(64)))).toBeTruthy();
  });

  it('cuando faltan escenarios de stress dice por qué en vez de callarse', () => {
    const run = makeRun();
    run.verdict.stress.not_computable_reason =
      'no se pudo estimar el apalancamiento operativo con esta serie';
    renderVerdict(run);
    expect(screen.getByText(/Faltan escenarios/)).toBeTruthy();
    expect(
      screen.getByText(/no se pudo estimar el apalancamiento operativo/),
    ).toBeTruthy();
  });

  it('avisa de que el stress mide sobre caja libre y no sobre FFO', () => {
    renderVerdict(makeRun());
    expect(screen.getByText(/no sobre el FFO/)).toBeTruthy();
  });
});
