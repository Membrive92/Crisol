'use client';

import { colors, fontSize, fontWeight, radius } from '@finanzas/ui';

export type PeriodKey = 'month' | 'quarter' | 'year';

export interface StitchPeriodToggleProps {
  value: PeriodKey;
  onChange: (next: PeriodKey) => void;
}

const LABELS: Record<PeriodKey, string> = {
  month: 'Mes',
  quarter: 'Trimestre',
  year: 'Año',
};

/** Toggle Mes / Trimestre / Año al estilo Stitch (segmented). */
export function StitchPeriodToggle({ value, onChange }: StitchPeriodToggleProps) {
  return (
    <div
      style={{
        display: 'inline-flex',
        backgroundColor: colors.surfaceMuted,
        padding: 2,
        borderRadius: radius.md,
        border: `1px solid ${colors.border}`,
      }}
    >
      {(['month', 'quarter', 'year'] as PeriodKey[]).map((opt) => {
        const active = opt === value;
        return (
          <button
            key={opt}
            type="button"
            onClick={() => onChange(opt)}
            style={{
              padding: `6px 14px`,
              backgroundColor: active ? colors.surface : 'transparent',
              color: active ? colors.text : colors.textMuted,
              border: active ? `1px solid ${colors.borderStrong}` : '1px solid transparent',
              borderRadius: radius.sm,
              fontSize: fontSize.sm,
              fontWeight: fontWeight.semibold,
              cursor: 'pointer',
              minWidth: 70,
            }}
          >
            {LABELS[opt]}
          </button>
        );
      })}
    </div>
  );
}

export function rangeForPeriod(period: PeriodKey): { dateFrom: string; dateTo: string } {
  const now = new Date();
  if (period === 'month') {
    const start = new Date(now.getFullYear(), now.getMonth(), 1);
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59);
    return { dateFrom: start.toISOString(), dateTo: end.toISOString() };
  }
  if (period === 'quarter') {
    const q = Math.floor(now.getMonth() / 3);
    const start = new Date(now.getFullYear(), q * 3, 1);
    const end = new Date(now.getFullYear(), q * 3 + 3, 0, 23, 59, 59);
    return { dateFrom: start.toISOString(), dateTo: end.toISOString() };
  }
  // year
  const start = new Date(now.getFullYear(), 0, 1);
  const end = new Date(now.getFullYear(), 11, 31, 23, 59, 59);
  return { dateFrom: start.toISOString(), dateTo: end.toISOString() };
}
