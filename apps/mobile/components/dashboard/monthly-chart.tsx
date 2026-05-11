import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { BarChart } from 'react-native-gifted-charts';

import type { MonthlyBucket } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';
import { formatAmount, formatMonthLabel } from '@crisol/ui';

export interface MonthlyChartProps {
  data: MonthlyBucket[] | undefined;
  isLoading: boolean;
  /** Moneda usada para formatear los valores. Default 'EUR'. */
  currency?: string;
}

/**
 * Bar chart mensual ingresos vs gastos (PHASE-18.2). Mejoras:
 * - Eje Y con formato compacto (1k €, 1,5M €).
 * - Hero card encima con el último mes con label y valores siempre
 *   visibles — no requiere tap para ver el dato más reciente.
 * - Tap en una barra hace destacar el bucket en el hero card.
 * - Reglas con dashed border más sutil.
 */
export function MonthlyChart({
  data,
  isLoading,
  currency = 'EUR',
}: MonthlyChartProps) {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  const buckets = data ?? [];
  const empty = !isLoading && buckets.length === 0;

  const chartData = useMemo(
    () =>
      buckets.flatMap((bucket, idx) => {
        const shortLabel = formatMonthLabel(bucket.month).slice(0, 3);
        const isSelected = selectedIdx === idx;
        return [
          {
            value: Number(bucket.income),
            label: shortLabel,
            spacing: 2,
            labelTextStyle: { color: colors.textMuted, fontSize: 10 },
            frontColor: isSelected ? colors.income : `${colors.income}cc`,
            onPress: () => setSelectedIdx(idx),
          },
          {
            value: Number(bucket.expenses),
            frontColor: isSelected ? colors.expense : `${colors.expense}cc`,
            onPress: () => setSelectedIdx(idx),
          },
        ];
      }),
    [buckets, selectedIdx],
  );

  // Hero: bucket seleccionado o último por defecto.
  const heroIdx = selectedIdx ?? buckets.length - 1;
  const heroBucket = heroIdx >= 0 ? buckets[heroIdx] : undefined;
  const heroLabel = heroBucket ? formatMonthLabel(heroBucket.month) : '';

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.title}>Evolución mensual</Text>
        {heroBucket ? (
          <Pressable
            onPress={() => setSelectedIdx(null)}
            hitSlop={8}
            style={styles.heroBadge}
          >
            <Text style={styles.heroLabel}>{heroLabel}</Text>
          </Pressable>
        ) : null}
      </View>

      {heroBucket ? (
        <View style={styles.heroRow}>
          <HeroValue
            label="Ingresos"
            value={formatAmount(String(heroBucket.income), currency)}
            color={colors.income}
          />
          <HeroValue
            label="Gastos"
            value={formatAmount(String(heroBucket.expenses), currency)}
            color={colors.expense}
          />
        </View>
      ) : null}

      {isLoading && !data ? (
        <Text style={styles.placeholder}>Cargando…</Text>
      ) : empty ? (
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
            xAxisThickness={1}
            xAxisColor={colors.border}
            xAxisLabelTextStyle={{ color: colors.textMuted, fontSize: 10 }}
            yAxisTextStyle={{ color: colors.textMuted, fontSize: 10 }}
            noOfSections={4}
            rulesType="dashed"
            rulesColor={colors.border}
            formatYLabel={(v) => formatCompact(Number(v), currency)}
            isAnimated
            animationDuration={400}
          />
          <View style={styles.legend}>
            <Legend color={colors.income} label="Ingresos" />
            <Legend color={colors.expense} label="Gastos" />
            <Text style={styles.legendHint}>Toca una barra para ver el detalle</Text>
          </View>
        </View>
      )}
    </View>
  );
}

function HeroValue({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <View style={styles.heroValue}>
      <View style={[styles.heroDot, { backgroundColor: color }]} />
      <View>
        <Text style={styles.heroValueLabel}>{label}</Text>
        <Text style={[styles.heroValueAmount, { color }]}>{value}</Text>
      </View>
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

/**
 * Formato compacto para ticks del eje Y: `1,2k €`, `1,5M €`. Coherente
 * con `stitch-balance-chart` (web).
 */
function formatCompact(value: number, currency: string): string {
  const symbol = currency === 'EUR' ? '€' : currency === 'USD' ? '$' : currency;
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs === 0) return `0`;
  if (abs < 1000) return `${sign}${Math.round(abs)} ${symbol}`;
  if (abs < 1_000_000) {
    const v = abs / 1000;
    return `${sign}${v.toFixed(v < 10 ? 1 : 0)}k ${symbol}`.replace('.', ',');
  }
  const v = abs / 1_000_000;
  return `${sign}${v.toFixed(v < 10 ? 1 : 0)}M ${symbol}`.replace('.', ',');
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
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  title: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  heroBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceMuted,
  },
  heroLabel: { fontSize: fontSize.xs, color: colors.textMuted, fontWeight: fontWeight.medium },
  heroRow: {
    flexDirection: 'row',
    gap: spacing.lg,
    marginBottom: spacing.md,
  },
  heroValue: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  heroDot: { width: 8, height: 8, borderRadius: 4 },
  heroValueLabel: { fontSize: fontSize.xs, color: colors.textMuted },
  heroValueAmount: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    fontVariant: ['tabular-nums'] as const,
  },
  placeholder: { color: colors.textMuted, fontSize: fontSize.sm },
  chartWrapper: { alignItems: 'flex-start' },
  legend: { flexDirection: 'row', gap: spacing.md, marginTop: spacing.sm, alignItems: 'center', flexWrap: 'wrap' },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendText: { fontSize: fontSize.xs, color: colors.textMuted },
  legendHint: { fontSize: fontSize.xs, color: colors.textSubtle, marginLeft: 'auto' },
});
