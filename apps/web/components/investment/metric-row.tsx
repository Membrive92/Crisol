'use client';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';
import type { AnalysisRun, MetricBand, MetricResult } from '@crisol/types';

export function bandColors(band: MetricBand | null): { fg: string; bg: string } {
  if (band === 'healthy') return { fg: colors.success, bg: colors.successSoft };
  if (band === 'caution') return { fg: colors.warning, bg: colors.warningSoft };
  if (band === 'stressed') return { fg: colors.danger, bg: colors.dangerSoft };
  return { fg: colors.textMuted, bg: colors.surfaceMuted };
}

const BAND_LABEL: Record<MetricBand, string> = {
  healthy: 'Sano',
  caution: 'Vigilar',
  stressed: 'Riesgo',
};

export function BandChip({ band, label }: { band: MetricBand | null; label?: string }) {
  const { fg, bg } = bandColors(band);
  const text = label ?? (band ? BAND_LABEL[band] : '—');
  return (
    <span
      style={{
        color: fg,
        backgroundColor: bg,
        borderRadius: radius.sm,
        padding: `2px ${spacing.sm}px`,
        fontSize: fontSize.xs,
        fontWeight: fontWeight.semibold,
        whiteSpace: 'nowrap',
      }}
    >
      {text}
    </span>
  );
}

export function latestYear(run: AnalysisRun): number {
  return run.years_covered[run.years_covered.length - 1] ?? 0;
}

export function findMetric(
  metrics: MetricResult[],
  key: string,
  year: number,
): MetricResult | undefined {
  return metrics.find((m) => m.key === key && m.fiscal_year === year);
}

export function formatMetricValue(metric: MetricResult | undefined): string {
  if (!metric || metric.value === null) return '—';
  const n = Number(metric.value);
  if (Number.isNaN(n)) return metric.value;
  return n.toLocaleString('es-ES', { maximumFractionDigits: 2 });
}

/** Fila de una métrica con su banda. `metric` ausente/no-calculable se muestra
 * con su razón, nunca como un hueco silencioso. */
export function MetricRow({
  label,
  metric,
  suffix,
}: {
  label: string;
  metric: MetricResult | undefined;
  suffix?: string | undefined;
}) {
  const notComputable = !metric || metric.status === 'not_computable';
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: spacing.md,
        padding: `${spacing.sm}px 0`,
        borderBottom: `1px solid ${colors.border}`,
      }}
    >
      <span style={{ color: colors.textMuted, fontSize: fontSize.sm }}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
        {notComputable ? (
          <span
            style={{ color: colors.textSubtle, fontSize: fontSize.xs, fontStyle: 'italic' }}
            title={metric?.reason ?? undefined}
          >
            No calculable
          </span>
        ) : (
          <>
            <span
              style={{
                color: colors.text,
                fontSize: fontSize.sm,
                fontWeight: fontWeight.semibold,
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {formatMetricValue(metric)}
              {suffix ? ` ${suffix}` : ''}
            </span>
            {metric?.band ? <BandChip band={metric.band} /> : null}
          </>
        )}
      </div>
    </div>
  );
}
