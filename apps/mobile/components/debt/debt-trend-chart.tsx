import { useMemo, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { LineChart } from 'react-native-gifted-charts';

import type { DebtHistoryPoint } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

export interface DebtTrendChartProps {
  data: DebtHistoryPoint[];
  currency: string;
  isLoading: boolean;
}

const SPANISH_SHORT_MONTHS = [
  'Ene',
  'Feb',
  'Mar',
  'Abr',
  'May',
  'Jun',
  'Jul',
  'Ago',
  'Sep',
  'Oct',
  'Nov',
  'Dic',
];

function monthShort(month: string): string {
  const idx = parseInt(month.slice(5, 7), 10) - 1;
  return SPANISH_SHORT_MONTHS[idx] ?? month;
}

/**
 * Evolución de la deuda total — línea histórica + proyección
 * (PHASE-22.1). Histórico en `colors.primary`, proyección con
 * puntos atenuados; el eje X marca el punto donde acaba el
 * histórico ("hoy"). Tap en un punto lo destaca arriba.
 */
export function DebtTrendChart({ data, currency, isLoading }: DebtTrendChartProps) {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  const empty = !isLoading && data.length === 0;

  const lastHistoricalIdx = useMemo(() => {
    let last = -1;
    data.forEach((p, i) => {
      if (p.kind === 'historical') last = i;
    });
    return last;
  }, [data]);

  const chartData = useMemo(
    () =>
      data.map((point, idx) => {
        const isHistorical = point.kind === 'historical';
        const isSelected = selectedIdx === idx;
        return {
          value: Number(point.total_debt),
          label: monthShort(point.month),
          labelTextStyle: {
            color: isHistorical ? colors.textMuted : colors.textSubtle,
            fontSize: 10,
          },
          dataPointColor: isHistorical
            ? isSelected
              ? colors.primary
              : colors.primary
            : colors.textMuted,
          dataPointRadius: isSelected ? 6 : isHistorical ? 4 : 3,
          onPress: () => setSelectedIdx(idx),
          // Marca de "hoy" en el primer punto proyectado.
          showXAxisIndex: idx === lastHistoricalIdx + 1,
        };
      }),
    [data, selectedIdx, lastHistoricalIdx],
  );

  const heroIdx =
    selectedIdx ?? (lastHistoricalIdx >= 0 ? lastHistoricalIdx : data.length - 1);
  const heroPoint = heroIdx >= 0 ? data[heroIdx] : undefined;

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.title}>Evolución de tu deuda</Text>
        <Text style={styles.subtitle}>
          Histórico sólido + proyección al ritmo actual. No contempla nuevos
          cargos.
        </Text>
      </View>

      {heroPoint ? (
        <View style={styles.hero}>
          <View>
            <Text style={styles.heroLabel}>
              {heroPoint.kind === 'historical' ? 'Cierre de' : 'Proyectado para'}{' '}
              {monthShort(heroPoint.month)}{' '}
              {heroPoint.month.slice(0, 4)}
            </Text>
            <Text style={styles.heroValue}>
              {formatAmount(heroPoint.total_debt, currency)}
            </Text>
          </View>
          <View style={styles.heroSplit}>
            <View style={styles.heroSplitItem}>
              <Text style={styles.heroSplitLabel}>Principal</Text>
              <Text style={styles.heroSplitValue}>
                {formatAmount(heroPoint.principal_paid, currency)}
              </Text>
            </View>
            <View style={styles.heroSplitItem}>
              <Text style={styles.heroSplitLabel}>Intereses</Text>
              <Text style={styles.heroSplitValue}>
                {formatAmount(heroPoint.interest_paid, currency)}
              </Text>
            </View>
          </View>
        </View>
      ) : null}

      {empty ? (
        <View style={styles.empty}>
          <Text style={styles.emptyText}>
            Sin histórico todavía. Conforme registres pagos a tus deudas, esta
            gráfica se irá rellenando.
          </Text>
        </View>
      ) : (
        <View style={styles.chartWrap}>
          <LineChart
            data={chartData}
            thickness={2}
            color={colors.primary}
            curved
            yAxisColor={colors.border}
            xAxisColor={colors.border}
            xAxisLabelTextStyle={{ color: colors.textMuted, fontSize: 10 }}
            yAxisTextStyle={{ color: colors.textMuted, fontSize: 10 }}
            spacing={Math.max(40, 280 / Math.max(chartData.length, 1))}
            initialSpacing={10}
            endSpacing={10}
            hideRules={false}
            rulesType="dashed"
            rulesColor={`${colors.border}80`}
            disableScroll={chartData.length <= 12}
            yAxisLabelPrefix=""
            formatYLabel={(label) => {
              const n = Number(label);
              if (!Number.isFinite(n)) return label;
              if (Math.abs(n) >= 1000) return `${Math.round(n / 1000)}k`;
              return Math.round(n).toString();
            }}
          />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  header: {
    marginBottom: spacing.md,
  },
  title: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  subtitle: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    marginTop: spacing.xs,
    lineHeight: 16,
  },
  hero: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.md,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
    marginBottom: spacing.md,
  },
  heroLabel: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  heroValue: {
    fontSize: fontSize.xl,
    fontWeight: fontWeight.bold,
    color: colors.danger,
    marginTop: spacing.xs,
  },
  heroSplit: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  heroSplitItem: {
    alignItems: 'flex-end',
  },
  heroSplitLabel: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
  heroSplitValue: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginTop: 2,
  },
  empty: {
    padding: spacing.lg,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    textAlign: 'center',
    lineHeight: 20,
  },
  chartWrap: {
    paddingTop: spacing.sm,
  },
});
