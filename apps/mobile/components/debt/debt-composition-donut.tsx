import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { PieChart } from 'react-native-gifted-charts';

import type { DebtTypeBreakdown, DebtTypeBucket } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

const TYPE_LABEL: Record<DebtTypeBucket, string> = {
  mortgage: 'Hipoteca',
  loan: 'Préstamo',
  credit_card: 'Tarjeta',
  other: 'Otros',
};

const TYPE_COLOR: Record<DebtTypeBucket, string> = {
  mortgage: colors.primary,
  loan: colors.warning,
  credit_card: colors.danger,
  other: colors.borderStrong,
};

export interface DebtCompositionDonutProps {
  items: DebtTypeBreakdown[];
  total: string;
  currency: string;
  isLoading: boolean;
}

/**
 * PHASE-30.5 — Mobile parity de `debt-composition-donut.tsx` (web).
 * Donut por tipo (hipoteca/préstamo/tarjeta/otros) con leyenda
 * tappable + centro dinámico.
 */
export function DebtCompositionDonut({
  items,
  total,
  currency,
  isLoading,
}: DebtCompositionDonutProps) {
  const [activeType, setActiveType] = useState<DebtTypeBucket | null>(null);
  const empty = !isLoading && items.length === 0;
  const active = activeType
    ? items.find((i) => i.type === activeType) ?? null
    : null;

  const chartData = items.map((it) => ({
    value: Number(it.amount),
    color: TYPE_COLOR[it.type],
    focused: activeType === it.type,
    onPress: () => setActiveType(activeType === it.type ? null : it.type),
  }));

  return (
    <View style={styles.card}>
      <Text style={styles.title}>Composición de la deuda</Text>
      {empty ? (
        <Text style={styles.empty}>
          Sin pagos categorizados como deuda. El donut aparece cuando
          haya datos en el rango.
        </Text>
      ) : (
        <View style={styles.body}>
          <View style={styles.chartWrap}>
            <PieChart
              data={chartData}
              donut
              radius={70}
              innerRadius={48}
              backgroundColor={colors.surface}
              centerLabelComponent={() => (
                <View style={styles.centerLabel}>
                  <Text style={styles.centerEyebrow}>
                    {active ? TYPE_LABEL[active.type] : 'Total'}
                  </Text>
                  <Text style={styles.centerValue}>
                    {formatAmount(active ? active.amount : total, currency)}
                  </Text>
                  {active ? (
                    <Text style={styles.centerPct}>
                      {Math.round(active.percent * 100)}%
                    </Text>
                  ) : null}
                </View>
              )}
            />
          </View>

          <View style={styles.legend}>
            {items.map((it) => (
              <Pressable
                key={it.type}
                onPress={() =>
                  setActiveType((prev) => (prev === it.type ? null : it.type))
                }
                style={styles.legendRow}
              >
                <View style={[styles.dot, { backgroundColor: TYPE_COLOR[it.type] }]} />
                <Text style={styles.legendLabel}>{TYPE_LABEL[it.type]}</Text>
                <Text style={styles.legendAmount}>
                  {formatAmount(it.amount, currency)}
                </Text>
                <Text style={styles.legendPct}>{Math.round(it.percent * 100)}%</Text>
              </Pressable>
            ))}
          </View>
        </View>
      )}
    </View>
  );
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
  title: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  empty: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    lineHeight: 20,
  },
  body: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  chartWrap: {
    width: 160,
    height: 160,
    alignItems: 'center',
    justifyContent: 'center',
  },
  centerLabel: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  centerEyebrow: {
    fontSize: 10,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  centerValue: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.bold,
    color: colors.text,
  },
  centerPct: {
    fontSize: 10,
    color: colors.textMuted,
  },
  legend: {
    flex: 1,
    gap: spacing.xs,
  },
  legendRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 999,
  },
  legendLabel: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.text,
  },
  legendAmount: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  legendPct: {
    fontSize: 11,
    color: colors.textMuted,
    minWidth: 32,
    textAlign: 'right',
  },
});
