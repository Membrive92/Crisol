import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Stack, useRouter } from 'expo-router';

import {
  useAccountBalances,
  useAccounts,
  useDebtCategorySummary,
  useDebtHealth,
  useDebtHistory,
} from '@crisol/services';
import type { Account, DebtTimeRange } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  radius,
  spacing,
} from '@crisol/ui';

import { DebtPaymentWizard } from '../../../components/accounts/debt-payment-wizard';
import { DebtCompositionDonut } from '../../../components/debt/debt-composition-donut';
import { DebtList } from '../../../components/debt/debt-list';
import { DebtMonthlyEvolution } from '../../../components/debt/debt-monthly-evolution';
import { DebtTrendChart } from '../../../components/debt/debt-trend-chart';
import { EffortRatioSection } from '../../../components/debt/effort-ratio-section';
import { PaymentsSummaryCard } from '../../../components/debt/payments-summary-card';
import { RecurringQuotasList } from '../../../components/debt/recurring-quotas-list';

/**
 * Pantalla `/debt` — paridad mobile de PHASE-30.3 (PHASE-30.5).
 *
 * Mismo modelo en dos capas:
 * - Capa 1 (arriba): KPIs derivados del flujo de categorías.
 * - Capa 2 (debajo, colapsable): pasivos declarados + cuadro de
 *   amortización vía link al detalle del préstamo.
 */
export default function DebtScreen() {
  const router = useRouter();
  const [range, setRange] = useState<DebtTimeRange>('ytd');
  const [layer2Open, setLayer2Open] = useState(false);
  const [payingDebt, setPayingDebt] = useState<Account | null>(null);

  const summaryQuery = useDebtCategorySummary(range);
  const healthQuery = useDebtHealth();
  const balancesQuery = useAccountBalances();
  const accountsQuery = useAccounts({ includeArchived: false });
  const historyQuery = useDebtHistory({ monthsBack: 12, monthsAhead: 12 });

  const summary = summaryQuery.data;
  const health = healthQuery.data;
  const balances = balancesQuery.data?.items ?? [];
  const accounts = accountsQuery.data ?? [];
  const liabilities = balances.filter((b) => b.nature === 'liability');

  const referenceCurrency =
    summary?.reference_currency ??
    health?.reference_currency ??
    historyQuery.data?.reference_currency ??
    balancesQuery.data?.reference_currency ??
    'EUR';

  const monthlyIncome = summary?.monthly_income_avg ?? '0';
  const monthlyDebtPayment = health?.monthly_debt_payment ?? '0';
  const monthlyDebtPaymentExtended =
    summary && summary.effort_ratio_extended !== null
      ? (summary.effort_ratio_extended * Number(monthlyIncome)).toFixed(2)
      : monthlyDebtPayment;

  // Capa 2 se auto-abre cuando hay liabilities reales — coherente con
  // el comportamiento de la web.
  const hasLiabilities = liabilities.length > 0;
  const expanded = layer2Open || hasLiabilities;

  return (
    <>
      <Stack.Screen options={{ title: 'Deuda' }} />
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <View style={{ flex: 1 }}>
            <Text style={styles.eyebrow}>DEUDA</Text>
            <Text style={styles.title}>Deuda</Text>
            <Text style={styles.subtitle}>
              Cuánto destinas a deuda vs ingresos, qué es interés puro
              y cómo evoluciona mes a mes.
            </Text>
          </View>
          <Pressable
            style={({ pressed }) => [styles.addButton, pressed && { opacity: 0.85 }]}
            onPress={() => router.push('/personal-finance/accounts')}
          >
            <Text style={styles.addButtonText}>Añadir deuda</Text>
          </Pressable>
        </View>

        <EffortRatioSection
          strictRatio={summary?.effort_ratio_strict ?? null}
          strictStatus={summary?.effort_ratio_strict_status ?? 'unknown'}
          extendedRatio={summary?.effort_ratio_extended ?? null}
          extendedStatus={summary?.effort_ratio_extended_status ?? 'unknown'}
          monthlyIncome={monthlyIncome}
          monthlyDebtPayment={monthlyDebtPayment}
          monthlyDebtPaymentExtended={monthlyDebtPaymentExtended}
          currency={referenceCurrency}
          isLoading={summaryQuery.isLoading}
        />

        <PaymentsSummaryCard
          range={range}
          onRangeChange={setRange}
          totalPayments={summary?.total_payments ?? '0'}
          interestsAndFees={summary?.interests_and_fees ?? '0'}
          capitalAmortized={summary?.capital_amortized ?? '0'}
          currency={referenceCurrency}
          isLoading={summaryQuery.isLoading}
        />

        <DebtCompositionDonut
          items={summary?.by_type ?? []}
          total={summary?.total_payments ?? '0'}
          currency={referenceCurrency}
          isLoading={summaryQuery.isLoading}
        />

        <DebtMonthlyEvolution
          items={summary?.monthly_series ?? []}
          currency={referenceCurrency}
          isLoading={summaryQuery.isLoading}
        />

        <RecurringQuotasList
          items={summary?.recurring_quotas ?? []}
          currency={referenceCurrency}
          isLoading={summaryQuery.isLoading}
        />

        <View style={styles.layer2Wrap}>
          <Pressable
            onPress={() => setLayer2Open((o) => !o)}
            style={styles.layer2Header}
            accessibilityRole="button"
            accessibilityState={{ expanded }}
          >
            <View style={{ flex: 1 }}>
              <Text style={styles.layer2Title}>Detalle por contrato</Text>
              <Text style={styles.layer2Subtitle}>
                {hasLiabilities
                  ? 'Tus pasivos declarados con sus cuotas y cuadros.'
                  : 'Sin contratos declarados. Añade un préstamo / hipoteca / tarjeta cuando tengas uno.'}
              </Text>
            </View>
            <Text style={[styles.layer2Caret, expanded && styles.layer2CaretOpen]}>▾</Text>
          </Pressable>
          {expanded ? (
            <View style={styles.layer2Body}>
              {historyQuery.data && historyQuery.data.items.length > 0 ? (
                <DebtTrendChart
                  data={historyQuery.data.items}
                  currency={referenceCurrency}
                  isLoading={historyQuery.isLoading}
                />
              ) : null}
              <DebtList
                balances={balances}
                accounts={accounts}
                isLoading={balancesQuery.isLoading || accountsQuery.isLoading}
                onPayDebt={setPayingDebt}
              />
            </View>
          ) : null}
        </View>
      </ScrollView>

      {payingDebt ? (
        <DebtPaymentWizard
          liabilityAccount={payingDebt}
          visible={payingDebt !== null}
          onClose={() => setPayingDebt(null)}
        />
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.md,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: fontWeight.semibold,
    color: colors.primary,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  title: {
    fontSize: fontSize.xl,
    fontWeight: fontWeight.bold,
    color: colors.text,
    marginTop: spacing.xs,
  },
  subtitle: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    marginTop: spacing.xs,
    lineHeight: 20,
  },
  addButton: {
    backgroundColor: colors.primary,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: 8,
  },
  addButtonText: {
    color: colors.onPrimary,
    fontWeight: fontWeight.semibold,
    fontSize: fontSize.sm,
  },
  layer2Wrap: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  layer2Header: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    gap: spacing.sm,
  },
  layer2Title: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  layer2Subtitle: {
    marginTop: 2,
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
  layer2Caret: {
    fontSize: fontSize.lg,
    color: colors.textMuted,
    transform: [{ rotate: '0deg' }],
  },
  layer2CaretOpen: {
    transform: [{ rotate: '180deg' }],
  },
  layer2Body: {
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.md,
    gap: spacing.md,
  },
});
