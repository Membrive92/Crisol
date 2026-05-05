import { useEffect, useMemo, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Link } from 'expo-router';

import {
  authApi,
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardSummary,
  useDashboardTopExpenses,
  useUserCurrencies,
} from '@finanzas/services';
import { useAuthStore, useCurrencyStore } from '@finanzas/store';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import {
  CategoryDonut,
  type DonutKindFilter,
} from '../../../../components/dashboard/category-donut';
import { CurrencyPicker } from '../../../../components/dashboard/currency-picker';
import { KpiCards } from '../../../../components/dashboard/kpi-cards';
import { MonthlyChart } from '../../../../components/dashboard/monthly-chart';
import {
  PeriodToggle,
  rangeForPeriod,
  type PeriodKey,
} from '../../../../components/dashboard/period-toggle';
import { SavingsRateCard } from '../../../../components/dashboard/savings-rate-card';
import { SmartInsights } from '../../../../components/dashboard/smart-insights';
import { TopExpensesList } from '../../../../components/dashboard/top-expenses-list';
import { FabLink } from '../../../../components/ui/fab';

const TOP_EXPENSES_LIMIT = 5;
const FALLBACK_CURRENCY = 'EUR';

/**
 * Pantalla **Análisis** — paridad con `apps/web/app/(app)/personal-finance/analysis`.
 * Período toggleable Mes/Trimestre/Año, tasa de ahorro, smart insights.
 * El gráfico mensual sigue ligado al año en curso (`useDashboardByMonth`
 * sólo acepta `year`).
 */
export default function AnalysisScreen() {
  const { user, refreshToken, logout: clearAuth } = useAuthStore();
  // PHASE-11.2: la moneda activa vive en `useCurrencyStore`
  // (cross-platform vía AsyncStorage). Antes era `useState` local —
  // se perdía entre sesiones y no se compartía con otras pantallas.
  const currency = useCurrencyStore((s) => s.currency);
  const setCurrency = useCurrencyStore((s) => s.setCurrency);
  const [period, setPeriod] = useState<PeriodKey>('year');
  const [donutKind, setDonutKind] = useState<DonutKindFilter>('all');
  const [currencyHydrated, setCurrencyHydrated] = useState(false);

  const currenciesQuery = useUserCurrencies();

  useEffect(() => {
    if (currencyHydrated) return;
    const list = currenciesQuery.data;
    if (!list) return;
    if (list.length === 0) {
      setCurrencyHydrated(true);
      return;
    }
    // Sólo sobrescribir el store si la moneda persistida no está
    // en las del usuario — respeta su selección explícita previa.
    if (!list.includes(currency)) {
      setCurrency(list[0] ?? FALLBACK_CURRENCY);
    }
    setCurrencyHydrated(true);
  }, [currenciesQuery.data, currencyHydrated, currency, setCurrency]);

  const { dateFrom, dateTo } = useMemo(() => rangeForPeriod(period), [period]);
  const currentYear = new Date().getFullYear();

  const summaryQuery = useDashboardSummary({
    currency,
    date_from: dateFrom,
    date_to: dateTo,
  });
  const monthlyQuery = useDashboardByMonth({
    currency,
    year: currentYear,
  });
  const byCategoryQuery = useDashboardByCategory({
    currency,
    date_from: dateFrom,
    date_to: dateTo,
    ...(donutKind === 'all' ? {} : { kind: donutKind }),
  });
  const topExpensesQuery = useDashboardTopExpenses({
    currency,
    date_from: dateFrom,
    date_to: dateTo,
    limit: TOP_EXPENSES_LIMIT,
  });

  const refreshing =
    summaryQuery.isFetching ||
    monthlyQuery.isFetching ||
    byCategoryQuery.isFetching ||
    topExpensesQuery.isFetching;

  function handleRefresh() {
    void summaryQuery.refetch();
    void monthlyQuery.refetch();
    void byCategoryQuery.refetch();
    void topExpensesQuery.refetch();
  }

  async function handleLogout() {
    try {
      if (refreshToken) {
        await authApi.logout(refreshToken);
      }
    } finally {
      clearAuth();
    }
  }

  const expensesByCategory = byCategoryQuery.data ?? [];

  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />}
      >
        <View style={styles.header}>
          <View style={{ flex: 1 }}>
            <Text style={styles.greeting}>Hola, {user?.display_name ?? 'usuario'}</Text>
            <Text style={styles.subtitle}>Análisis financiero</Text>
          </View>
          <View style={styles.headerActions}>
            <Link href="/(modules)/personal-finance/budgets" asChild>
              <Pressable style={styles.headerButton}>
                <Text style={styles.headerButtonText}>Presupuestos</Text>
              </Pressable>
            </Link>
            <Link href="/(modules)/personal-finance/subscriptions" asChild>
              <Pressable style={styles.headerButton}>
                <Text style={styles.headerButtonText}>Subscripciones</Text>
              </Pressable>
            </Link>
            <Pressable onPress={handleLogout} style={styles.logoutButton}>
              <Text style={styles.logoutText}>Salir</Text>
            </Pressable>
          </View>
        </View>

        <CurrencyPicker
          value={currency}
          onChange={setCurrency}
          currencies={currenciesQuery.data}
        />
        <PeriodToggle value={period} onChange={setPeriod} />

        <KpiCards summary={summaryQuery.data} isLoading={summaryQuery.isLoading} />
        <SavingsRateCard summary={summaryQuery.data} />
        <MonthlyChart data={monthlyQuery.data} isLoading={monthlyQuery.isLoading} />
        <CategoryDonut
          data={byCategoryQuery.data}
          currency={currency}
          isLoading={byCategoryQuery.isLoading}
          kind={donutKind}
          onKindChange={setDonutKind}
        />
        <TopExpensesList
          data={topExpensesQuery.data}
          currency={currency}
          isLoading={topExpensesQuery.isLoading}
        />
        <SmartInsights
          summary={summaryQuery.data}
          expensesByCategory={expensesByCategory}
          currency={currency}
        />

        {(summaryQuery.isError ||
          monthlyQuery.isError ||
          byCategoryQuery.isError ||
          topExpensesQuery.isError) && (
          <Text style={styles.errorText}>Error cargando alguna sección del análisis.</Text>
        )}
      </ScrollView>

      <FabLink
        href="/(modules)/personal-finance/transaction/new"
        ariaLabel="Añadir transacción"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xl },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  greeting: { fontSize: fontSize.xl, fontWeight: fontWeight.semibold, color: colors.text },
  subtitle: { fontSize: fontSize.sm, color: colors.textMuted, marginTop: 2 },
  headerActions: { flexDirection: 'row', gap: spacing.xs, alignItems: 'center' },
  headerButton: {
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 6,
  },
  headerButtonText: {
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: fontWeight.medium,
  },
  logoutButton: {
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 6,
  },
  logoutText: { fontSize: fontSize.sm, color: colors.danger, fontWeight: fontWeight.medium },
  errorText: { color: colors.danger, fontSize: fontSize.sm, marginTop: spacing.sm },
});
