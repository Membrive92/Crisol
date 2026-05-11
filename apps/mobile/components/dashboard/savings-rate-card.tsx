import { StyleSheet, Text, View } from 'react-native';

import type { DashboardSummary } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

export interface SavingsRateCardProps {
  summary: DashboardSummary | undefined;
}

/**
 * Tasa de ahorro = balance / income, con barra de progreso.
 * Equivalente al sub-card "Saving rate" de `StitchKeyMetrics` en web.
 */
export function SavingsRateCard({ summary }: SavingsRateCardProps) {
  const balance = summary ? Number(summary.balance) : 0;
  const income = summary ? Number(summary.income) : 0;
  const rate = income > 0 ? (balance / income) * 100 : null;
  const clamped = rate !== null ? Math.max(0, Math.min(100, rate)) : 0;
  const positive = rate !== null && rate >= 0;

  return (
    <View style={styles.card}>
      <Text style={styles.label}>TASA DE AHORRO</Text>
      <Text style={[styles.value, { color: positive ? colors.primary : colors.danger }]}>
        {rate !== null ? `${rate.toFixed(1)}%` : '—'}
      </Text>
      <View style={styles.barTrack}>
        <View style={[styles.barFill, { width: `${clamped}%` }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  label: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.medium,
    color: colors.textMuted,
    letterSpacing: 0.5,
  },
  value: {
    fontSize: fontSize.xxl,
    fontWeight: fontWeight.bold,
    marginTop: spacing.xs,
  },
  barTrack: {
    marginTop: spacing.md,
    width: '100%',
    height: 6,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.sm,
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    backgroundColor: colors.primary,
  },
});
