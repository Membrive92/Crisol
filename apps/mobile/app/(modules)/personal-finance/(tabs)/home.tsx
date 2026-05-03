import { useEffect, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import {
  authApi,
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardSummary,
  useDashboardTopExpenses,
  useUserCurrencies,
} from '@finanzas/services';
import { useAuthStore } from '@finanzas/store';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import {
  CategoryDonut,
  type DonutKindFilter,
} from '../../../../components/dashboard/category-donut';
import {
  DashboardFilters,
  type DashboardFiltersValue,
} from '../../../../components/dashboard/dashboard-filters';
import { KpiCards } from '../../../../components/dashboard/kpi-cards';
import { MonthlyChart } from '../../../../components/dashboard/monthly-chart';
import { TopExpensesList } from '../../../../components/dashboard/top-expenses-list';
import { FabLink } from '../../../../components/ui/fab';

const TOP_EXPENSES_LIMIT = 5;
const FALLBACK_CURRENCY = 'EUR';

export default function HomeScreen() {
  const { user, refreshToken, logout: clearAuth } = useAuthStore();
  const [filters, setFilters] = useState<DashboardFiltersValue>({
    currency: FALLBACK_CURRENCY,
    year: new Date().getFullYear(),
  });
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
    if (!list.includes(filters.currency)) {
      setFilters((prev) => ({ ...prev, currency: list[0] ?? FALLBACK_CURRENCY }));
    }
    setCurrencyHydrated(true);
  }, [currenciesQuery.data, currencyHydrated, filters.currency]);

  const dateFrom = new Date(filters.year, 0, 1).toISOString();
  const dateTo = new Date(filters.year, 11, 31, 23, 59, 59).toISOString();

  const summaryQuery = useDashboardSummary({
    currency: filters.currency,
    date_from: dateFrom,
    date_to: dateTo,
  });
  const monthlyQuery = useDashboardByMonth({
    currency: filters.currency,
    year: filters.year,
  });
  const byCategoryQuery = useDashboardByCategory({
    currency: filters.currency,
    date_from: dateFrom,
    date_to: dateTo,
    ...(donutKind === 'all' ? {} : { kind: donutKind }),
  });
  const topExpensesQuery = useDashboardTopExpenses({
    currency: filters.currency,
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

  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />}
      >
        <View style={styles.header}>
          <View style={{ flex: 1 }}>
            <Text style={styles.greeting}>Hola, {user?.display_name ?? 'usuario'}</Text>
            <Text style={styles.subtitle}>Resumen financiero</Text>
          </View>
          <Pressable onPress={handleLogout} style={styles.logoutButton}>
            <Text style={styles.logoutText}>Salir</Text>
          </Pressable>
        </View>

        <DashboardFilters
          value={filters}
          onChange={setFilters}
          currencies={currenciesQuery.data}
        />
        <KpiCards summary={summaryQuery.data} isLoading={summaryQuery.isLoading} />
        <MonthlyChart data={monthlyQuery.data} isLoading={monthlyQuery.isLoading} />
        <CategoryDonut
          data={byCategoryQuery.data}
          currency={filters.currency}
          isLoading={byCategoryQuery.isLoading}
          kind={donutKind}
          onKindChange={setDonutKind}
        />
        <TopExpensesList
          data={topExpensesQuery.data}
          currency={filters.currency}
          isLoading={topExpensesQuery.isLoading}
        />

        {(summaryQuery.isError ||
          monthlyQuery.isError ||
          byCategoryQuery.isError ||
          topExpensesQuery.isError) && (
          <Text style={styles.errorText}>Error cargando alguna sección del dashboard.</Text>
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
