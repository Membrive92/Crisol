'use client';

import { Card, CardTitle } from '@/components/ui/card';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';
import type { AnalysisRun, DividendVerdict, SafetyLabel } from '@crisol/types';

import { bandColors, BandChip } from './metric-row';

const SAFETY: Record<SafetyLabel, { label: string; fg: string; bg: string }> = {
  conservative: { label: 'Conservador', fg: colors.success, bg: colors.successSoft },
  watch: { label: 'Vigilar', fg: colors.warning, bg: colors.warningSoft },
  avoid: { label: 'Evitar', fg: colors.danger, bg: colors.dangerSoft },
};

const DIVIDEND: Record<DividendVerdict, string> = {
  healthy: 'Dividendo sano',
  caution: 'Dividendo a vigilar',
  stressed: 'Dividendo en riesgo',
  not_applicable: 'Sin dividendo relevante',
};

export function VerdictCard({ run }: { run: AnalysisRun }) {
  const { verdict, data_completeness: dc } = run;
  const safety = SAFETY[verdict.safety_profile.label];
  const confidencePct = Math.round(Number(dc.value) * 100);

  return (
    <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md, flexWrap: 'wrap' }}>
        <CardTitle>Veredicto</CardTitle>
        <div style={{ display: 'flex', gap: spacing.sm, alignItems: 'center' }}>
          <span
            style={{
              color: safety.fg,
              backgroundColor: safety.bg,
              borderRadius: radius.sm,
              padding: `4px ${spacing.md}px`,
              fontSize: fontSize.sm,
              fontWeight: fontWeight.bold,
            }}
          >
            {safety.label}
          </span>
          <span style={{ color: colors.textMuted, fontSize: fontSize.sm }}>
            {DIVIDEND[verdict.dividend_verdict]}
          </span>
        </div>
      </div>

      <div style={{ display: 'grid', gap: spacing.sm }}>
        {verdict.questions.map((q) => {
          const { fg, bg } = bandColors(q.verdict);
          const signals = [...q.red_signals, ...q.amber_signals];
          return (
            <div
              key={q.key}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: spacing.xs,
                padding: spacing.md,
                borderRadius: radius.md,
                backgroundColor: bg,
                borderLeft: `3px solid ${fg}`,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm }}>
                <span style={{ color: colors.text, fontSize: fontSize.sm, fontWeight: fontWeight.semibold }}>
                  {q.question}
                </span>
                <BandChip band={q.verdict} />
              </div>
              {signals.length > 0 ? (
                <span style={{ color: fg, fontSize: fontSize.xs }}>{signals.join(' · ')}</span>
              ) : null}
            </div>
          );
        })}
      </div>

      {verdict.safety_profile.blocking_reasons.length > 0 ? (
        <div style={{ color: colors.textMuted, fontSize: fontSize.xs }}>
          {verdict.safety_profile.label === 'avoid' ? 'Motivos: ' : 'Falta para Conservador: '}
          {verdict.safety_profile.blocking_reasons.join('; ')}
        </div>
      ) : null}

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing.md,
          paddingTop: spacing.md,
          borderTop: `1px solid ${colors.border}`,
          color: colors.textMuted,
          fontSize: fontSize.xs,
        }}
      >
        <span>
          Confianza <strong style={{ color: colors.text }}>{confidencePct}%</strong>
        </span>
        <span>· completitud {Math.round(Number(dc.completeness_core) * 100)}%</span>
        {dc.imputed_core_count > 0 ? <span>· {dc.imputed_core_count} partidas imputadas</span> : null}
        {dc.days_stale !== null ? <span>· último cierre hace {dc.days_stale} días</span> : null}
      </div>
    </Card>
  );
}
