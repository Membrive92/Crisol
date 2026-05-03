import { StyleSheet, Text, View } from 'react-native';

import type { DashboardSummary } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';
import { formatAmount } from '@finanzas/ui';

import { KpiDelta } from '../ui/kpi-delta';

export interface KpiCardsProps {
  summary: DashboardSummary | undefined;
  isLoading: boolean;
}

/**
 * KPIs del dashboard mobile en grid 2×2: Saldo, Ingresos, Gastos,
 * Movimientos. Cada KPI con delta vs periodo previo cuando el backend
 * lo devuelve.
 */
export function KpiCards({ summary, isLoading }: KpiCardsProps) {
  const currency = summary?.currency ?? 'EUR';
  const balance = summary ? Number(summary.balance) : 0;
  const balanceColor = balance >= 0 ? colors.income : colors.expense;
  const placeholder = isLoading ? '…' : '—';

  return (
    <View style={styles.grid}>
      <Kpi
        label="Saldo"
        value={summary ? formatAmount(summary.balance, currency) : placeholder}
        color={summary ? balanceColor : colors.text}
        delta={
          summary ? (
            <KpiDelta
              current={Number(summary.balance)}
              previous={
                summary.previous_period_balance !== null
                  ? Number(summary.previous_period_balance)
                  : null
              }
              polarity="up=good"
            />
          ) : undefined
        }
      />
      <Kpi
        label="Ingresos"
        value={summary ? formatAmount(summary.income, currency) : placeholder}
        color={colors.income}
        delta={
          summary ? (
            <KpiDelta
              current={Number(summary.income)}
              previous={
                summary.previous_period_income !== null
                  ? Number(summary.previous_period_income)
                  : null
              }
              polarity="up=good"
            />
          ) : undefined
        }
      />
      <Kpi
        label="Gastos"
        value={summary ? formatAmount(summary.expenses, currency) : placeholder}
        color={colors.expense}
        delta={
          summary ? (
            <KpiDelta
              current={Number(summary.expenses)}
              previous={
                summary.previous_period_expenses !== null
                  ? Number(summary.previous_period_expenses)
                  : null
              }
              polarity="up=bad"
            />
          ) : undefined
        }
      />
      <Kpi
        label="Movimientos"
        value={summary ? String(summary.transaction_count) : placeholder}
        color={colors.text}
      />
    </View>
  );
}

function Kpi({
  label,
  value,
  color,
  delta,
}: {
  label: string;
  value: string;
  color: string;
  delta?: React.ReactNode;
}) {
  return (
    <View style={styles.card}>
      <Text style={styles.label}>{label}</Text>
      <Text style={[styles.value, { color }]} numberOfLines={1} adjustsFontSizeToFit>
        {value}
      </Text>
      {delta ? <View style={{ marginTop: spacing.xs }}>{delta}</View> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
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
  value: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    marginTop: spacing.xs,
  },
});
