'use client';

import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';
import type { AnalysisRun, Security } from '@crisol/types';

import { Card, CardTitle } from '@/components/ui/card';

import { DegradedPanel, InlineNotice } from './degraded-panel';
import { FlagList } from './flag-list';
import { formatMetricValue } from './metric-format';
import { metricRow, type MetricRowOptions } from './metric-rows';
import type { CatalogIndex, MetricIndex } from './metric-index';
import { YearMatrix, type MatrixRow } from './year-matrix';

/** Los cuatro bloques de la capa 3, con las métricas que se calculan POR AÑO.
 *  T2 y T3 quedan fuera a propósito: el motor las emite una sola vez, para el
 *  último ejercicio, así que en una matriz saldrían con N−1 huecos
 *  indistinguibles de un «no calculable». Van en Trayectoria. */
const BLOCKS = [
  {
    key: 'coverage',
    label: 'Cobertura',
    metrics: ['D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D8'],
    note: 'La primaria es el payout sobre caja libre: la caja, no el beneficio, es lo que paga el dividendo. Si el payout ajustado por retribución en acciones es muy superior al normal, el dividendo se está pagando diluyendo.',
  },
  {
    key: 'quality',
    label: 'Calidad de la caja',
    metrics: ['Q1', 'Q2', 'Q3', 'Q5'],
    note: 'Mide si la caja que paga el dividendo es real. La divergencia entre las dos formas de calcular la caja libre es la señal más útil: cuando no cuadran, una de las dos miente.',
  },
  {
    key: 'balance',
    label: 'Soporte del balance',
    metrics: ['B3'],
    note: 'Cuántos años de dividendo hay en caja. Las banderas de este bloque —la deuda compitiendo con el dividendo, los intereses con prioridad, el dividendo financiado fuera— están abajo.',
  },
] as const;

export interface TabDividendProps {
  run: AnalysisRun;
  index: MetricIndex;
  catalog: CatalogIndex;
  security: Security | undefined;
}

export function TabDividend({ run, index, catalog, security }: TabDividendProps) {
  const dividend = run.dividend_analysis;
  const years = run.years_covered;
  const verdictYear = years[years.length - 1];
  const options: MetricRowOptions = { index, catalog, thresholdsUsed: run.thresholds_used };

  if (run.dividend_verdict === 'not_applicable') {
    return (
      <DegradedPanel
        title="Sin dividendo relevante"
        reason={
          security?.is_financial
            ? 'Este valor es una financiera, y el análisis de dividendo del motor no se aplica a financieras.'
            : 'El último ejercicio no registra dividendos pagados, así que no hay política de dividendo que juzgar.'
        }
      >
        <div style={{ marginTop: spacing.md }}>
          <FlagList flags={dividend.flags ?? []} emptyLabel="Sin banderas de dividendo." />
        </div>
      </DegradedPanel>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      {BLOCKS.map((block) => (
        <Card key={block.key}>
          <CardTitle size="sm">{block.label}</CardTitle>
          <div style={{ marginTop: spacing.md, display: 'grid', gap: spacing.md }}>
            <InlineNotice>{block.note}</InlineNotice>
            <YearMatrix
              years={years}
              rows={[...block.metrics].map((key) => metricRow(key, options))}
              verdictYear={verdictYear}
              firstColumnLabel="Métrica"
            />
          </div>
        </Card>
      ))}

      <Card>
        <CardTitle size="sm">Trayectoria</CardTitle>
        <div style={{ marginTop: spacing.md, display: 'grid', gap: spacing.md }}>
          <div style={{ display: 'flex', gap: spacing.lg, flexWrap: 'wrap' }}>
            <Stat
              label="Años seguidos sin recortar"
              value={String(dividend.trajectory?.streak_no_cut ?? 0)}
              hint="Es una cota inferior: se cuenta sobre los ejercicios ingeridos, no sobre el histórico completo de la empresa."
            />
            <Stat
              label="¿Se está frenando el crecimiento?"
              value={dividend.trajectory?.momentum_slowdown ? 'Sí' : 'No'}
              hint="Compara el crecimiento reciente del dividendo con el compuesto de toda la serie."
            />
          </div>
          <YearMatrix
            years={years}
            rows={[dpsRow(run), metricRow('T2', options), metricRow('T3', options)]}
            firstColumnLabel="Concepto"
            legend="El CAGR y la estabilidad del payout se calculan una sola vez sobre toda la serie; por eso sólo tienen valor en la última columna."
          />
        </div>
      </Card>

      <Card>
        <CardTitle size="sm">Banderas del dividendo</CardTitle>
        <div style={{ marginTop: spacing.md }}>
          <FlagList
            flags={dividend.flags ?? []}
            emptyLabel="Ninguna bandera de dividendo encendida."
          />
        </div>
      </Card>
    </div>
  );
}

function dpsRow(run: AnalysisRun): MatrixRow {
  const points = run.dividend_analysis.dps_series ?? [];
  return {
    key: 'dps',
    label: 'Dividendo por acción',
    cells: run.years_covered.map((year) => {
      const point = points.find((p) => p.fiscal_year === year);
      return { text: formatMetricValue(point?.dps ?? null, 'currency_per_share') };
    }),
  };
}

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, maxWidth: 320 }}>
      <span style={{ color: colors.textMuted, fontSize: fontSize.xs }}>{label}</span>
      <span
        style={{ color: colors.text, fontSize: fontSize.lg, fontWeight: fontWeight.bold }}
      >
        {value}
      </span>
      <span style={{ color: colors.textSubtle, fontSize: fontSize.xs, lineHeight: 1.5 }}>
        {hint}
      </span>
    </div>
  );
}
