import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { BarChart, LineChart } from 'react-native-gifted-charts';

import type { DailyDebtPoint } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

export interface DebtDailyEvolutionProps {
  items: DailyDebtPoint[];
  currency: string;
  isLoading: boolean;
  /** Etiqueta del mes (p. ej. "Abril · 2024"). */
  monthLabel?: string;
}

/**
 * PHASE-30.9 — Paridad mobile de la vista diaria del saldo de deuda.
 *
 * Con cuentas-pasivo: `LineChart` del saldo día a día (sube si emites
 * deuda, baja si amortizas) + hero con el desglose del día seleccionado
 * (emitida / amortizado / interés). Sin pasivos: cae a un `BarChart` de
 * los pagos categorizados del mes (sin línea de saldo).
 */
export function DebtDailyEvolution({
  items,
  currency,
  isLoading,
  monthLabel,
}: DebtDailyEvolutionProps) {
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const hasBalance = items.some((p) => p.balance !== null);
  const empty =
    !isLoading &&
    items.every(
      (p) => Number(p.emitida) === 0 && Number(p.amortizado) === 0 && Number(p.interest) === 0,
    );

  const lineData = useMemo(
    () =>
      items.map((p) => ({
        value: p.balance === null ? 0 : Number(p.balance),
        label: p.day % 5 === 0 || p.day === 1 ? String(p.day) : '',
        onPress: () => setSelectedDay(p.day),
      })),
    [items],
  );

  const barData = useMemo(
    () =>
      items.map((p) => ({
        value: Number(p.amortizado),
        label: p.day % 5 === 0 || p.day === 1 ? String(p.day) : '',
        frontColor: colors.income,
        onPress: () => setSelectedDay(p.day),
      })),
    [items],
  );

  const hero =
    selectedDay !== null
      ? items.find((p) => p.day === selectedDay)
      : [...items].reverse().find((p) => Number(p.emitida) || Number(p.amortizado) || Number(p.interest));

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.title}>Evolución de deuda</Text>
          <Text style={styles.subtitle}>
            {monthLabel ? `${monthLabel} · día a día` : 'Día a día'}
          </Text>
        </View>
        <View style={styles.legendRow}>
          {hasBalance ? <LegendChip color={colors.primary} label="Saldo" /> : null}
          <LegendChip color={colors.expense} label="Emitida" />
          <LegendChip color={colors.income} label="Pago" />
        </View>
      </View>

      {empty ? (
        <Text style={styles.empty}>
          Sin movimientos de deuda este mes. La línea y las barras aparecen
          conforme registres cargos o pagos.
        </Text>
      ) : (
        <>
          {hero ? (
            <Pressable onPress={() => setSelectedDay(null)} style={styles.heroRow} hitSlop={8}>
              <View style={{ flex: 1 }}>
                <Text style={styles.heroEyebrow}>Día {hero.day}</Text>
                {hero.balance !== null ? (
                  <Text style={styles.heroValue}>
                    {formatAmount(hero.balance, currency)}
                  </Text>
                ) : null}
              </View>
              <View style={styles.heroBreakdown}>
                {Number(hero.emitida) > 0 ? (
                  <Text style={styles.heroLine}>
                    <View style={[styles.dot, { backgroundColor: colors.expense }]} /> +
                    {formatAmount(hero.emitida, currency)}
                  </Text>
                ) : null}
                {Number(hero.amortizado) > 0 ? (
                  <Text style={styles.heroLine}>
                    <View style={[styles.dot, { backgroundColor: colors.income }]} /> −
                    {formatAmount(hero.amortizado, currency)}
                  </Text>
                ) : null}
                {Number(hero.interest) > 0 ? (
                  <Text style={styles.heroLine}>
                    <View style={[styles.dot, { backgroundColor: colors.danger }]} /> int.{' '}
                    {formatAmount(hero.interest, currency)}
                  </Text>
                ) : null}
              </View>
            </Pressable>
          ) : null}

          <View style={styles.chartWrap}>
            {hasBalance ? (
              <LineChart
                data={lineData}
                color={colors.primary}
                thickness={2}
                hideDataPoints
                areaChart
                startFillColor={colors.primarySoft}
                endFillColor={colors.surface}
                startOpacity={0.5}
                endOpacity={0.05}
                hideRules
                xAxisColor={colors.border}
                yAxisColor={colors.border}
                yAxisTextStyle={{ color: colors.textMuted, fontSize: 10 }}
                xAxisLabelTextStyle={{ color: colors.textMuted, fontSize: 10 }}
                noOfSections={4}
                formatYLabel={(v) => {
                  const n = Number(v);
                  return n >= 1000 ? `${(n / 1000).toFixed(0)}k` : String(n);
                }}
              />
            ) : (
              <BarChart
                data={barData}
                barWidth={6}
                spacing={4}
                hideRules
                xAxisColor={colors.border}
                yAxisColor={colors.border}
                yAxisTextStyle={{ color: colors.textMuted, fontSize: 10 }}
                xAxisLabelTextStyle={{ color: colors.textMuted, fontSize: 10 }}
                noOfSections={4}
              />
            )}
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
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  title: { fontSize: fontSize.md, fontWeight: fontWeight.semibold, color: colors.text },
  subtitle: { fontSize: 11, color: colors.textMuted, marginTop: 2 },
  legendRow: { flexDirection: 'row', gap: spacing.sm, flexWrap: 'wrap', maxWidth: 180, justifyContent: 'flex-end' },
  legendChip: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  legendText: { fontSize: 11, color: colors.textMuted },
  empty: { fontSize: fontSize.sm, color: colors.textMuted, lineHeight: 20 },
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
  heroValue: { marginTop: 2, fontSize: fontSize.lg, fontWeight: fontWeight.bold, color: colors.text },
  heroBreakdown: { alignItems: 'flex-end', gap: 2 },
  heroLine: { fontSize: 11, color: colors.text },
  dot: { width: 8, height: 8, borderRadius: 2 },
  chartWrap: { overflow: 'hidden', marginTop: spacing.xs },
});
