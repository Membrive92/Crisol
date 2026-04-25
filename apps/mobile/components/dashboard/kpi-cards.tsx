import { StyleSheet, Text, View } from 'react-native';

import type { DashboardSummary } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';
import { formatAmount } from '@finanzas/ui';

export interface KpiCardsProps {
  summary: DashboardSummary | undefined;
  isLoading: boolean;
}

export function KpiCards({ summary, isLoading }: KpiCardsProps) {
  const currency = summary?.currency ?? 'USD';
  const balance = summary ? Number(summary.balance) : 0;
  const balanceColor = balance >= 0 ? colors.income : colors.expense;
  const placeholder = isLoading ? '…' : '—';

  return (
    <View style={styles.grid}>
      <Kpi
        label="Balance"
        value={summary ? formatAmount(summary.balance, currency) : placeholder}
        color={summary ? balanceColor : colors.text}
      />
      <Kpi
        label="Ingresos"
        value={summary ? formatAmount(summary.income, currency) : placeholder}
        color={colors.income}
      />
      <Kpi
        label="Gastos"
        value={summary ? formatAmount(summary.expenses, currency) : placeholder}
        color={colors.expense}
      />
      <Kpi
        label="Movimientos"
        value={summary ? String(summary.transaction_count) : placeholder}
        color={colors.text}
      />
    </View>
  );
}

function Kpi({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <View style={styles.card}>
      <Text style={styles.label}>{label}</Text>
      <Text style={[styles.value, { color }]} numberOfLines={1} adjustsFontSizeToFit>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginBottom: spacing.md },
  card: {
    flexBasis: '48%',
    flexGrow: 1,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  label: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.medium,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  value: { fontSize: fontSize.lg, fontWeight: fontWeight.bold, marginTop: spacing.xs },
});
