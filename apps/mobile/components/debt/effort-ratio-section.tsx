import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { EffortStatus } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

export interface EffortRatioSectionProps {
  strictRatio: number | null;
  strictStatus: EffortStatus;
  extendedRatio: number | null;
  extendedStatus: EffortStatus;
  monthlyIncome: string;
  monthlyDebtPayment: string;
  monthlyDebtPaymentExtended: string;
  currency: string;
  isLoading: boolean;
}

type Mode = 'strict' | 'extended';

/**
 * PHASE-30.5 — Mobile parity de `effort-ratio-section.tsx` (web).
 * Mismo modelo mental: toggle estricta/ampliada + gauge horizontal
 * con bandas BdE 30/35%, captura "X € de Y € netos".
 */
export function EffortRatioSection({
  strictRatio,
  strictStatus,
  extendedRatio,
  extendedStatus,
  monthlyIncome,
  monthlyDebtPayment,
  monthlyDebtPaymentExtended,
  currency,
  isLoading,
}: EffortRatioSectionProps) {
  const [mode, setMode] = useState<Mode>('strict');
  const ratio = mode === 'strict' ? strictRatio : extendedRatio;
  const status = mode === 'strict' ? strictStatus : extendedStatus;
  const numerator =
    mode === 'strict' ? monthlyDebtPayment : monthlyDebtPaymentExtended;
  const tone = effortTone(status);
  const pct = ratio !== null ? Math.max(0, Math.min(50, ratio * 100)) : null;
  const thumbLeftPct = pct !== null ? (pct / 50) * 100 : null;
  const bandHealthyEnd = 60; // 30/50
  const bandCautionEnd = 70; // 35/50

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>Tasa de esfuerzo</Text>
          <Text style={styles.subtitle}>
            {mode === 'strict'
              ? '% de tus ingresos netos que va sólo a cuotas de deuda. BdE recomienda < 35%.'
              : 'Incluye gastos fijos confirmados (suministros, seguros, suscripciones).'}
          </Text>
        </View>
        <ModeToggle mode={mode} onChange={setMode} />
      </View>

      <View style={styles.valueRow}>
        <Text style={styles.bigValue}>
          {isLoading || pct === null ? '—' : `${pct.toFixed(1)} %`}
        </Text>
        <View style={[styles.statusChip, { backgroundColor: tone.bg }]}>
          <Text style={[styles.statusChipText, { color: tone.fg }]}>{tone.label}</Text>
        </View>
      </View>

      <View style={styles.gaugeTrack}>
        <View style={styles.gaugeBands}>
          <View style={{ width: `${bandHealthyEnd}%`, backgroundColor: colors.successSoft }} />
          <View
            style={{
              width: `${bandCautionEnd - bandHealthyEnd}%`,
              backgroundColor: colors.warningSoft,
            }}
          />
          <View
            style={{
              width: `${100 - bandCautionEnd}%`,
              backgroundColor: colors.dangerSoft,
            }}
          />
        </View>
        {thumbLeftPct !== null ? (
          <View style={[styles.gaugeThumb, { left: `${thumbLeftPct}%` }]} />
        ) : null}
      </View>
      <View style={styles.gaugeTicks}>
        <Text style={styles.tick}>0%</Text>
        <Text style={[styles.tick, { marginLeft: `${bandHealthyEnd - 6}%` }]}>30%</Text>
        <Text style={[styles.tick, { marginLeft: 'auto', marginRight: `${100 - bandCautionEnd - 6}%` }]}>
          35%
        </Text>
        <Text style={styles.tick}>50%</Text>
      </View>

      <Text style={styles.caption}>
        <Text style={styles.captionStrong}>{formatAmount(numerator, currency)}</Text>{' '}
        de tus{' '}
        <Text style={styles.captionStrong}>{formatAmount(monthlyIncome, currency)}</Text>{' '}
        netos mensuales van a {mode === 'strict' ? 'deuda' : 'deuda + gastos fijos'}.
      </Text>
    </View>
  );
}

function ModeToggle({ mode, onChange }: { mode: Mode; onChange: (m: Mode) => void }) {
  return (
    <View style={styles.toggleRow}>
      <ToggleBtn active={mode === 'strict'} onPress={() => onChange('strict')} label="Estricta" />
      <ToggleBtn active={mode === 'extended'} onPress={() => onChange('extended')} label="Ampliada" />
    </View>
  );
}

function ToggleBtn({ active, onPress, label }: { active: boolean; onPress: () => void; label: string }) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.toggleBtn, active && styles.toggleBtnActive]}
      accessibilityRole="tab"
      accessibilityState={{ selected: active }}
    >
      <Text style={[styles.toggleBtnText, active && styles.toggleBtnTextActive]}>{label}</Text>
    </Pressable>
  );
}

function effortTone(status: EffortStatus): { bg: string; fg: string; label: string } {
  switch (status) {
    case 'healthy':
      return { bg: colors.successSoft, fg: colors.success, label: 'Saludable' };
    case 'caution':
      return { bg: colors.warningSoft, fg: colors.warning, label: 'Precaución' };
    case 'stressed':
      return { bg: colors.dangerSoft, fg: colors.danger, label: 'Sobreendeud.' };
    default:
      return { bg: colors.surfaceMuted, fg: colors.textMuted, label: 'Sin datos' };
  }
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    gap: spacing.md,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
  },
  title: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  subtitle: {
    marginTop: spacing.xs,
    fontSize: fontSize.xs,
    color: colors.textMuted,
    lineHeight: 18,
  },
  toggleRow: {
    flexDirection: 'row',
    padding: 2,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  toggleBtn: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
  },
  toggleBtnActive: {
    backgroundColor: colors.surface,
  },
  toggleBtnText: {
    fontSize: 11,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
  },
  toggleBtnTextActive: {
    color: colors.text,
  },
  valueRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: spacing.sm,
  },
  bigValue: {
    fontSize: fontSize.xxl,
    fontWeight: fontWeight.bold,
    color: colors.text,
    letterSpacing: -0.5,
  },
  statusChip: {
    paddingVertical: 2,
    paddingHorizontal: 8,
    borderRadius: 999,
  },
  statusChipText: {
    fontSize: 11,
    fontWeight: fontWeight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  gaugeTrack: {
    height: 12,
    borderRadius: 999,
    overflow: 'hidden',
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.border,
    position: 'relative',
  },
  gaugeBands: {
    flexDirection: 'row',
    position: 'absolute',
    left: 0,
    right: 0,
    top: 0,
    bottom: 0,
  },
  gaugeThumb: {
    position: 'absolute',
    top: -2,
    bottom: -2,
    width: 4,
    backgroundColor: colors.text,
    borderRadius: 2,
    transform: [{ translateX: -2 }],
  },
  gaugeTicks: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 2,
  },
  tick: {
    fontSize: 10,
    color: colors.textMuted,
  },
  caption: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    lineHeight: 20,
  },
  captionStrong: {
    color: colors.text,
    fontWeight: fontWeight.semibold,
  },
});
