import { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { LineChart } from 'react-native-gifted-charts';
import { Stack, useLocalSearchParams, useRouter } from 'expo-router';

import { useCategoryDetail } from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatCivilDate,
  radius,
  spacing,
} from '@crisol/ui';

// PHASE-41 — se eliminó `quarter`.
type PeriodKey = 'month' | 'year';

const PERIOD_LABEL: Record<PeriodKey, string> = {
  month: 'Mes',
  year: 'Año',
};

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

function spanishMonthLabel(month: string): string {
  const idx = parseInt(month.slice(5, 7), 10) - 1;
  return SPANISH_SHORT_MONTHS[idx] ?? month;
}

function rangeForPeriod(period: PeriodKey): {
  dateFrom: string;
  dateTo: string;
} {
  const now = new Date();
  const to = now.toISOString();
  const start = new Date(now);
  if (period === 'month') start.setMonth(start.getMonth() - 1);
  else start.setFullYear(start.getFullYear() - 1);
  return { dateFrom: start.toISOString(), dateTo: to };
}

/**
 * PHASE-25 — Drill-down de una categoría desde el donut del dashboard
 * mobile. Espejo de la página web equivalente: KPIs + evolución
 * mensual (BarChart de gifted-charts) + top 10 tx.
 */
export default function CategoryDetailScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const currency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);
  const [period, setPeriod] = useState<PeriodKey>('year');
  const { dateFrom, dateTo } = useMemo(() => rangeForPeriod(period), [period]);

  const query = convertAll
    ? { target_currency: currency, date_from: dateFrom, date_to: dateTo }
    : { currency, date_from: dateFrom, date_to: dateTo };
  const { data, isLoading, isError, error } = useCategoryDetail(id, query);

  return (
    <View style={styles.container}>
      <Stack.Screen
        options={{
          title: data?.category_name ?? 'Categoría',
          headerBackTitle: 'Análisis',
        }}
      />
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.periodToggle}>
          {(['month', 'year'] as const).map((p) => (
            <Pressable
              key={p}
              onPress={() => setPeriod(p)}
              style={[styles.toggleBtn, period === p && styles.toggleBtnActive]}
            >
              <Text
                style={[
                  styles.toggleBtnText,
                  period === p && styles.toggleBtnTextActive,
                ]}
              >
                {PERIOD_LABEL[p]}
              </Text>
            </Pressable>
          ))}
        </View>

        {isError ? (
          <View style={styles.errorCard}>
            <Text style={styles.errorText}>
              {error instanceof Error ? error.message : 'Error al cargar'}
            </Text>
          </View>
        ) : isLoading || !data ? (
          <Text style={styles.placeholder}>Cargando…</Text>
        ) : (
          <>
            <View style={styles.kpis}>
              <Kpi
                label="Total"
                value={formatAmount(data.total, data.currency)}
                color={
                  data.category_kind === 'income'
                    ? colors.income
                    : colors.expense
                }
              />
              <Kpi label="Movimientos" value={String(data.count)} />
              <Kpi
                label="Ticket medio"
                value={formatAmount(data.average_amount, data.currency)}
              />
            </View>

            <View style={styles.card}>
              <Text style={styles.sectionTitle}>Evolución mensual</Text>
              <Text style={styles.sectionHint}>Últimos 12 meses</Text>
              {data.by_month.length === 0 ? (
                <Text style={styles.placeholder}>Sin actividad histórica.</Text>
              ) : (
                <View style={styles.chartWrap}>
                  <LineChart
                    data={data.by_month.map((b) => ({
                      value: Number(b.total),
                      label: spanishMonthLabel(b.month),
                      labelTextStyle: {
                        color: colors.textMuted,
                        fontSize: 10,
                      },
                      dataPointColor:
                        data.category_color ?? colors.primary,
                      dataPointRadius: 4,
                    }))}
                    thickness={2}
                    color={data.category_color ?? colors.primary}
                    curved
                    yAxisColor={colors.border}
                    xAxisColor={colors.border}
                    xAxisLabelTextStyle={{
                      color: colors.textMuted,
                      fontSize: 10,
                    }}
                    yAxisTextStyle={{ color: colors.textMuted, fontSize: 10 }}
                    spacing={Math.max(
                      36,
                      260 / Math.max(data.by_month.length, 1),
                    )}
                    initialSpacing={10}
                    endSpacing={10}
                    hideRules={false}
                    rulesType="dashed"
                    rulesColor={`${colors.border}80`}
                    disableScroll={data.by_month.length <= 12}
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

            <View style={styles.card}>
              <Text style={styles.sectionTitle}>
                Top movimientos · {data.top_transactions.length}
              </Text>
              {data.top_transactions.length === 0 ? (
                <Text style={styles.placeholder}>Sin movimientos.</Text>
              ) : (
                data.top_transactions.map((tx) => (
                  <Pressable
                    key={tx.transaction_id}
                    onPress={() =>
                      router.push(
                        `/(modules)/personal-finance/transaction/${tx.transaction_id}` as never,
                      )
                    }
                    style={styles.txRow}
                  >
                    <View style={{ flex: 1, minWidth: 0 }}>
                      <Text style={styles.txDesc} numberOfLines={1}>
                        {tx.description ?? '(sin descripción)'}
                      </Text>
                      <Text style={styles.txDate}>
                        {formatCivilDate(tx.occurred_at)}
                      </Text>
                    </View>
                    <Text style={styles.txAmount}>
                      {formatAmount(tx.amount, data.currency)}
                    </Text>
                  </Pressable>
                ))
              )}
            </View>
          </>
        )}
      </ScrollView>
    </View>
  );
}

function Kpi({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <View style={styles.kpi}>
      <Text style={styles.kpiLabel}>{label}</Text>
      <Text
        style={[styles.kpiValue, { color: color ?? colors.text }]}
        numberOfLines={1}
        adjustsFontSizeToFit
      >
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  scroll: { padding: spacing.md, paddingBottom: spacing.xxl },
  periodToggle: {
    flexDirection: 'row',
    gap: spacing.xs,
    marginBottom: spacing.md,
  },
  toggleBtn: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  toggleBtnActive: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  toggleBtnText: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    fontWeight: fontWeight.medium,
  },
  toggleBtnTextActive: {
    color: colors.primary,
    fontWeight: fontWeight.semibold,
  },
  kpis: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
  kpi: {
    flex: 1,
    padding: spacing.sm,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
  },
  kpiLabel: {
    fontSize: 10,
    color: colors.textMuted,
    marginBottom: 2,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  kpiValue: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  sectionTitle: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  sectionHint: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    marginBottom: spacing.sm,
  },
  chartWrap: {
    paddingTop: spacing.sm,
  },
  txRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: spacing.sm,
  },
  txDesc: { fontSize: fontSize.sm, color: colors.text },
  txDate: { fontSize: fontSize.xs, color: colors.textMuted, marginTop: 2 },
  txAmount: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    fontVariant: ['tabular-nums'] as const,
  },
  placeholder: {
    padding: spacing.md,
    color: colors.textMuted,
    fontSize: fontSize.sm,
  },
  errorCard: {
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderColor: colors.danger,
    borderWidth: 1,
    borderRadius: radius.md,
  },
  errorText: { color: colors.danger, fontSize: fontSize.sm },
});
