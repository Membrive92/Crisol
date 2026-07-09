import { StyleSheet, Text, View } from 'react-native';
import { LineChart } from 'react-native-gifted-charts';

import { usePositionHistory } from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import { colors, fontSize, fontWeight, formatAmount, formatMonthLabel, radius, spacing } from '@crisol/ui';

/**
 * PHASE-37.6 (parity 37.1) — Evolución del patrimonio: valor actual + Δ del
 * rango + serie mensual (12 meses). Respeta el toggle "incluir deuda"
 * (net_worth vs total_assets), igual que web NetworthEvolutionCard. En modo
 * nativo (la serie no convierte divisas, misma limitación que web).
 */
export function NetworthEvolutionCard() {
  const storeCurrency = useCurrencyStore((s) => s.currency);
  const includeDebt = useCurrencyStore((s) => s.includeDebtInNetWorth);
  const { data, isLoading } = usePositionHistory(12, 0);

  const ref = data?.reference_currency ?? storeCurrency;
  const worthKey = includeDebt ? 'net_worth' : 'total_assets';
  const points = data?.points ?? [];
  const series = points.map((p) => Number(p[worthKey]));
  const current = series.length > 0 ? series[series.length - 1]! : null;
  const first = series.length > 0 ? series[0]! : null;
  const delta = current !== null && first !== null ? current - first : null;
  const deltaPct = delta !== null && first !== null && first !== 0 ? (delta / Math.abs(first)) * 100 : null;
  const up = delta !== null && delta >= 0;

  const chartData = points.map((p, i) => ({
    value: Number(p[worthKey]),
    label: i % 3 === 0 ? formatMonthLabel(p.month).slice(0, 3) : '',
    labelTextStyle: { color: colors.textMuted, fontSize: 10 },
  }));

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.title}>Evolución del patrimonio</Text>
        {delta !== null ? (
          <Text style={[styles.delta, { color: up ? colors.success : colors.danger }]}>
            {up ? '▲' : '▼'} {formatAmount(String(Math.abs(delta).toFixed(2)), ref)}
            {deltaPct !== null ? ` · ${up ? '+' : '-'}${Math.abs(deltaPct).toFixed(1)}%` : ''}
          </Text>
        ) : null}
      </View>

      <Text style={styles.value}>
        {current !== null ? formatAmount(String(current.toFixed(2)), ref) : '—'}
      </Text>

      {isLoading && !data ? (
        <Text style={styles.placeholder}>Cargando…</Text>
      ) : chartData.length < 2 ? (
        <Text style={styles.placeholder}>Necesitas al menos 2 meses con datos.</Text>
      ) : (
        <View style={styles.chartWrapper}>
          <LineChart
            data={chartData}
            height={140}
            adjustToWidth
            initialSpacing={8}
            endSpacing={8}
            thickness={2}
            color={up ? colors.success : colors.danger}
            hideDataPoints
            areaChart
            startFillColor={up ? colors.successSoft : colors.dangerSoft}
            endFillColor={colors.surface}
            startOpacity={0.5}
            endOpacity={0.05}
            yAxisThickness={0}
            xAxisThickness={1}
            xAxisColor={colors.border}
            yAxisTextStyle={{ color: colors.textMuted, fontSize: 10 }}
            noOfSections={3}
            rulesType="dashed"
            rulesColor={colors.border}
            formatYLabel={(v) => formatCompact(Number(v), ref)}
            isAnimated
            animationDuration={400}
          />
        </View>
      )}
    </View>
  );
}

function formatCompact(value: number, currency: string): string {
  const symbol = currency === 'EUR' ? '€' : currency === 'USD' ? '$' : currency;
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs === 0) return '0';
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
    marginBottom: spacing.xs,
  },
  title: { fontSize: fontSize.md, fontWeight: fontWeight.semibold, color: colors.text },
  delta: { fontSize: fontSize.xs, fontWeight: fontWeight.semibold, fontVariant: ['tabular-nums'] as const },
  value: {
    fontSize: fontSize.xl,
    fontWeight: fontWeight.bold,
    color: colors.text,
    fontVariant: ['tabular-nums'] as const,
    marginBottom: spacing.sm,
  },
  placeholder: { color: colors.textMuted, fontSize: fontSize.sm },
  chartWrapper: { marginTop: spacing.xs },
});
