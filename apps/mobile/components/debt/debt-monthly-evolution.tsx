import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { BarChart } from 'react-native-gifted-charts';

import type { MonthlyDebtPoint } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

const SPANISH_MONTHS = [
  'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
  'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic',
];

export interface DebtMonthlyEvolutionProps {
  items: MonthlyDebtPoint[];
  currency: string;
  isLoading: boolean;
}

/**
 * PHASE-30.5 — Mobile parity de `debt-monthly-evolution.tsx` (web).
 * Bar chart apilado capital + intereses (gifted-charts no soporta
 * stacks nativos en su API simple — usamos `stackData` con dos
 * sub-bars por mes). Hero superior muestra el mes seleccionado.
 */
export function DebtMonthlyEvolution({
  items,
  currency,
  isLoading,
}: DebtMonthlyEvolutionProps) {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const now = new Date();
  const currentMonthKey = `${now.getFullYear().toString().padStart(4, '0')}-${(now.getMonth() + 1)
    .toString()
    .padStart(2, '0')}`;

  const empty = !isLoading && items.every((p) => Number(p.capital) + Number(p.interests) === 0);

  const stackData = useMemo(
    () =>
      items.map((p, idx) => {
        const [, monthStr] = p.month.split('-');
        const monthIdx = Number.parseInt(monthStr ?? '1', 10) - 1;
        const label = SPANISH_MONTHS[monthIdx] ?? '?';
        return {
          label,
          stacks: [
            { value: Number(p.capital), color: colors.primary },
            { value: Number(p.interests), color: colors.danger },
          ],
          onPress: () => setSelectedIdx(idx),
        };
      }),
    [items],
  );

  const heroIdx = selectedIdx ?? items.findIndex((p) => p.month === currentMonthKey);
  const hero = heroIdx >= 0 ? items[heroIdx] : items[items.length - 1];
  const heroLabel = hero
    ? (() => {
        const [, monthStr] = hero.month.split('-');
        const idx = Number.parseInt(monthStr ?? '1', 10) - 1;
        return `${SPANISH_MONTHS[idx]} · ${hero.month.slice(0, 4)}`;
      })()
    : '';

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>Evolución mensual</Text>
        <View style={styles.legendRow}>
          <LegendChip color={colors.primary} label="Capital" />
          <LegendChip color={colors.danger} label="Intereses" />
        </View>
      </View>

      {empty ? (
        <Text style={styles.empty}>
          Sin pagos a deuda en este periodo. Las barras aparecen conforme
          registres pagos.
        </Text>
      ) : (
        <>
          {hero ? (
            <Pressable
              onPress={() => setSelectedIdx(null)}
              style={styles.heroRow}
              hitSlop={8}
            >
              <View style={{ flex: 1 }}>
                <Text style={styles.heroEyebrow}>{heroLabel}</Text>
                <Text style={styles.heroValue}>
                  {formatAmount(
                    (Number(hero.capital) + Number(hero.interests)).toFixed(2),
                    currency,
                  )}
                </Text>
              </View>
              <View style={styles.heroBreakdown}>
                <Text style={styles.heroBreakdownLine}>
                  <View style={[styles.dot, { backgroundColor: colors.primary }]} />{' '}
                  {formatAmount(hero.capital, currency)}
                </Text>
                <Text style={styles.heroBreakdownLine}>
                  <View style={[styles.dot, { backgroundColor: colors.danger }]} />{' '}
                  {formatAmount(hero.interests, currency)}
                </Text>
              </View>
            </Pressable>
          ) : null}

          <View style={styles.chartWrap}>
            <BarChart
              stackData={stackData}
              barWidth={14}
              spacing={10}
              hideRules
              xAxisColor={colors.border}
              yAxisColor={colors.border}
              yAxisTextStyle={{ color: colors.textMuted, fontSize: 10 }}
              xAxisLabelTextStyle={{ color: colors.textMuted, fontSize: 10 }}
              noOfSections={4}
              formatYLabel={(v) => {
                const n = Number(v);
                if (n >= 1000) return `${(n / 1000).toFixed(0)}k`;
                return String(n);
              }}
            />
          </View>
        </>
      )}
    </View>
  );
}

function LegendChip({ color, label }: { color: string; label: string }) {
  return (
    <View style={styles.legendChip}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text style={styles.legendText}>{label}</Text>
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
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  title: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  legendRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  legendChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  legendText: {
    fontSize: 11,
    color: colors.textMuted,
  },
  empty: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    lineHeight: 20,
  },
  heroRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.sm,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.sm,
  },
  heroEyebrow: {
    fontSize: 11,
    color: colors.textMuted,
    fontWeight: fontWeight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  heroValue: {
    marginTop: 2,
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    color: colors.text,
  },
  heroBreakdown: {
    alignItems: 'flex-end',
    gap: 2,
  },
  heroBreakdownLine: {
    fontSize: 11,
    color: colors.text,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 2,
  },
  chartWrap: {
    overflow: 'hidden',
    marginTop: spacing.xs,
  },
});
