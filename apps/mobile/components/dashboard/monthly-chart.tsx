import { StyleSheet, Text, View } from 'react-native';
import { BarChart } from 'react-native-gifted-charts';

import type { MonthlyBucket } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';
import { formatMonthLabel } from '@finanzas/ui';

export interface MonthlyChartProps {
  data: MonthlyBucket[] | undefined;
  isLoading: boolean;
}

export function MonthlyChart({ data, isLoading }: MonthlyChartProps) {
  const chartData = (data ?? []).flatMap((bucket) => {
    const shortLabel = formatMonthLabel(bucket.month).slice(0, 3);
    return [
      {
        value: Number(bucket.income),
        label: shortLabel,
        spacing: 2,
        labelTextStyle: { color: colors.textMuted, fontSize: 10 },
        frontColor: colors.income,
      },
      {
        value: Number(bucket.expenses),
        frontColor: colors.expense,
      },
    ];
  });

  return (
    <View style={styles.card}>
      <Text style={styles.title}>Evolución mensual</Text>
      {isLoading && !data ? (
        <Text style={styles.placeholder}>Cargando…</Text>
      ) : chartData.length === 0 ? (
        <Text style={styles.placeholder}>Sin datos.</Text>
      ) : (
        <View style={styles.chartWrapper}>
          <BarChart
            data={chartData}
            barWidth={10}
            spacing={6}
            initialSpacing={6}
            height={180}
            yAxisThickness={0}
            xAxisThickness={0}
            xAxisLabelTextStyle={{ color: colors.textMuted, fontSize: 10 }}
            yAxisTextStyle={{ color: colors.textMuted, fontSize: 10 }}
            noOfSections={4}
            rulesType="solid"
            rulesColor={colors.border}
          />
          <View style={styles.legend}>
            <Legend color={colors.income} label="Ingresos" />
            <Legend color={colors.expense} label="Gastos" />
          </View>
        </View>
      )}
    </View>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <View style={styles.legendItem}>
      <View style={[styles.legendDot, { backgroundColor: color }]} />
      <Text style={styles.legendText}>{label}</Text>
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
  title: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.sm,
  },
  placeholder: { color: colors.textMuted, fontSize: fontSize.sm },
  chartWrapper: { alignItems: 'flex-start' },
  legend: { flexDirection: 'row', gap: spacing.md, marginTop: spacing.sm },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendText: { fontSize: fontSize.xs, color: colors.textMuted },
});
