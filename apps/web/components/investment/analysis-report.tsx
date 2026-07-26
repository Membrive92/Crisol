'use client';

import { colors, fontSize, spacing } from '@crisol/ui';
import type { AnalysisRun } from '@crisol/types';

import { latestYear } from './metric-row';
import { MetricsCard } from './metrics-card';
import { VerdictCard } from './verdict-card';

const FORENSIC_ROWS = [
  { label: 'M-Score (Beneish)', key: 'm_score' },
  { label: "Z''-Score (Altman)", key: 'z_score' },
  { label: 'F-Score (Piotroski)', key: 'f_score' },
  { label: 'Accruals', key: 'accruals' },
  { label: 'F5 — deuda emergente', key: 'F5' },
  { label: 'F6 — dilución', key: 'F6' },
  { label: 'X-Score (Zmijewski)', key: 'FZ' },
  { label: 'C-Score (Montier)', key: 'F7' },
];

const QUALITY_ROWS = [
  { label: 'Margen neto', key: 'R4' },
  { label: 'Margen de caja libre', key: 'R7' },
  { label: 'ROIC', key: 'R9' },
  { label: 'Rent. bruta / activos', key: 'R10' },
  { label: 'Cobertura de intereses', key: 'S2' },
  { label: 'Deuda neta / EBITDA', key: 'S4' },
  { label: 'Ratio de liquidez', key: 'L1' },
];

const DIVIDEND_ROWS = [
  { label: 'Payout sobre FCF', key: 'D2' },
  { label: 'Cobertura FCF', key: 'D3' },
  { label: 'Payout ajustado por SBC', key: 'D4' },
  { label: 'Retorno total / FCF', key: 'D5' },
  { label: 'Rentabilidad por dividendo', key: 'D8' },
  { label: 'Conversión CFO/beneficio', key: 'Q1' },
  { label: 'Conversión FCF/EBITDA', key: 'Q2' },
];

/** El informe completo derivado de un `AnalysisRun`. */
export function AnalysisReport({ run }: { run: AnalysisRun }) {
  const year = latestYear(run);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <VerdictCard run={run} />
      <div
        style={{
          display: 'grid',
          gap: spacing.lg,
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 480px))',
        }}
      >
        <MetricsCard
          title="Forense (contabilidad)"
          metrics={run.scores_detail.forensic.metrics}
          year={year}
          rows={FORENSIC_ROWS}
        />
        <MetricsCard
          title="Calidad y solvencia"
          metrics={run.scores_detail.base_ratios.metrics}
          year={year}
          rows={QUALITY_ROWS}
        />
        <MetricsCard
          title="Dividendo"
          metrics={run.dividend_analysis.metrics}
          year={year}
          rows={DIVIDEND_ROWS}
        />
      </div>
      <p style={{ color: colors.textSubtle, fontSize: fontSize.xs, margin: 0 }}>
        Motor v{run.engine_version} · ejercicios {run.years_covered.join(', ')} · umbrales{' '}
        {run.thresholds_version.slice(0, 8)}
      </p>
    </div>
  );
}
