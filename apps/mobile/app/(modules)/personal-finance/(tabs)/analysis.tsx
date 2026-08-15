import { useEffect, useMemo, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Link } from 'expo-router';

import {
  authApi,
  boundsForCustomRange,
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardSummary,
  useDashboardTopExpenses,
  useExpenseStructure,
  useMonthOutlook,
  useUserCurrencies,
} from '@crisol/services';
import { useAuthStore, useCurrencyStore } from '@crisol/store';
import {
  colors,
  deferredBreakdownNotice,
  fontSize,
  fontWeight,
  spacing,
} from '@crisol/ui';

import { BalancesCard } from '../../../../components/accounts/balances-card';
import {
  CategoryDonut,
  type DonutKindFilter,
} from '../../../../components/dashboard/category-donut';
import { CurrencyPicker } from '../../../../components/dashboard/currency-picker';
import { DebtHealthCard } from '../../../../components/dashboard/debt-health-card';
import { KpiCards } from '../../../../components/dashboard/kpi-cards';
import { MonthlyChart } from '../../../../components/dashboard/monthly-chart';
import { MonthOutlookCard } from '../../../../components/dashboard/month-outlook-card';
import { NetworthEvolutionCard } from '../../../../components/dashboard/networth-evolution-card';
import {
  PeriodToggle,
  rangeForPeriod,
  type PeriodKey,
} from '../../../../components/dashboard/period-toggle';
import { SavingsRateCard } from '../../../../components/dashboard/savings-rate-card';
import { SmartInsights } from '../../../../components/dashboard/smart-insights';
import { TopExpensesList } from '../../../../components/dashboard/top-expenses-list';
import { DateInput } from '../../../../components/ui/date-input';
import { ErrorState } from '../../../../components/ui/error-state';
import { FabLink } from '../../../../components/ui/fab';

const TOP_EXPENSES_LIMIT = 5;
const FALLBACK_CURRENCY = 'EUR';

/**
 * Pantalla **Análisis** — paridad con `apps/web/app/(app)/personal-finance/analysis`.
 * Período toggleable Mes/Año, tasa de ahorro, smart insights.
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
  // PHASE-14.4: convertAll vive en el mismo store cross-platform
  // (PHASE-11.2). Cuando ON, las queries del dashboard pasan
  // `target_currency` y el backend convierte cada tx con la tasa de
  // su día (mismo flujo que web).
  const convertAll = useCurrencyStore((s) => s.convertAll);
  const setConvertAll = useCurrencyStore((s) => s.setConvertAll);
  const [period, setPeriod] = useState<PeriodKey>('year');
  // PHASE-41 — rango libre (`period='custom'`): day-strings `YYYY-MM-DD`,
  // sembrados desde el período actual al conmutar a "Rango".
  const [customFrom, setCustomFrom] = useState<string | null>(null);
  const [customTo, setCustomTo] = useState<string | null>(null);
  const [donutKind, setDonutKind] = useState<DonutKindFilter>('all');

  function seedCustom(): { from: string; to: string } {
    const now = new Date();
    const y = now.getFullYear();
    if (period === 'year') {
      return { from: `${y}-01-01`, to: `${y}-12-31` };
    }
    const m = now.getMonth() + 1;
    const mm = String(m).padStart(2, '0');
    const lastDay = new Date(Date.UTC(y, m, 0)).getUTCDate();
    return {
      from: `${y}-${mm}-01`,
      to: `${y}-${mm}-${String(lastDay).padStart(2, '0')}`,
    };
  }

  function handlePeriodChange(next: PeriodKey): void {
    if (next === 'custom' && !(customFrom && customTo)) {
      const seed = seedCustom();
      setCustomFrom(seed.from);
      setCustomTo(seed.to);
    }
    setPeriod(next);
  }

  function handleCustomRangeChange(from: string, to: string): void {
    if (from) setCustomFrom(from);
    if (to) setCustomTo(to);
  }
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

  const { dateFrom, dateTo } = useMemo(
    () =>
      period === 'custom' && customFrom && customTo
        ? boundsForCustomRange(customFrom, customTo)
        : rangeForPeriod(period === 'custom' ? 'year' : period),
    [period, customFrom, customTo],
  );
  const currentYear = new Date().getFullYear();

  // PHASE-14.4: cuando convertAll=true pedimos `target_currency` y el
  // backend convierte cada tx con la tasa de su día. Cuando false,
  // comportamiento legacy filtrado por moneda activa.
  const summaryParams = convertAll
    ? { target_currency: currency, date_from: dateFrom, date_to: dateTo }
    : { currency, date_from: dateFrom, date_to: dateTo };
  // PHASE-41 — en custom, el chart mensual se acota al rango (bordes parciales)
  // para cuadrar con los KPIs; en mes/año, por año natural.
  const monthlyParams =
    period === 'custom'
      ? convertAll
        ? { target_currency: currency, date_from: dateFrom, date_to: dateTo }
        : { currency, date_from: dateFrom, date_to: dateTo }
      : convertAll
        ? { target_currency: currency, year: currentYear }
        : { currency, year: currentYear };
  const byCategoryParams = convertAll
    ? {
        target_currency: currency,
        date_from: dateFrom,
        date_to: dateTo,
        ...(donutKind === 'all' ? {} : { kind: donutKind }),
      }
    : {
        currency,
        date_from: dateFrom,
        date_to: dateTo,
        ...(donutKind === 'all' ? {} : { kind: donutKind }),
      };
  const topExpensesParams = convertAll
    ? {
        target_currency: currency,
        date_from: dateFrom,
        date_to: dateTo,
        limit: TOP_EXPENSES_LIMIT,
      }
    : {
        currency,
        date_from: dateFrom,
        date_to: dateTo,
        limit: TOP_EXPENSES_LIMIT,
      };

  // PHASE-37.6 (parity 37.3/37.4) — gasto estructural (impacto de puntuales) +
  // proyección fin de mes + runway. El outlook no tiene rango (mes en curso).
  const structureParams = convertAll
    ? { target_currency: currency, date_from: dateFrom, date_to: dateTo }
    : { currency, date_from: dateFrom, date_to: dateTo };
  const outlookParams = convertAll ? { target_currency: currency } : { currency };

  const summaryQuery = useDashboardSummary(summaryParams);

  // PHASE-47.E — la diferencia entre el donut (que mantiene lo aplazado) y los
  // KPI (que lo excluyen), dicha en voz alta. La redacción vive en
  // `@crisol/ui` para que las dos pantallas no la cuenten distinto.
  const deferredNotice = deferredBreakdownNotice(
    summaryQuery.data?.deferred_expenses,
    currency,
  );
  const monthlyQuery = useDashboardByMonth(monthlyParams);
  const byCategoryQuery = useDashboardByCategory(byCategoryParams);
  const topExpensesQuery = useDashboardTopExpenses(topExpensesParams);
  const structureQuery = useExpenseStructure(structureParams);
  const outlookQuery = useMonthOutlook(outlookParams);

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
  const hasError =
    summaryQuery.isError ||
    monthlyQuery.isError ||
    byCategoryQuery.isError ||
    topExpensesQuery.isError;

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
            <Link href="/(modules)/personal-finance/fixed-expenses" asChild>
              <Pressable style={styles.headerButton}>
                <Text style={styles.headerButtonText}>Gastos fijos</Text>
              </Pressable>
            </Link>
            <Link href="/(modules)/personal-finance/categories" asChild>
              <Pressable style={styles.headerButton}>
                <Text style={styles.headerButtonText}>Categorías</Text>
              </Pressable>
            </Link>
            <Link href="/(modules)/personal-finance/accounts" asChild>
              <Pressable style={styles.headerButton}>
                <Text style={styles.headerButtonText}>Cuentas</Text>
              </Pressable>
            </Link>
            <Pressable onPress={handleLogout} style={styles.logoutButton}>
              <Text style={styles.logoutText}>Salir</Text>
            </Pressable>
          </View>
        </View>

        <View style={styles.currencyRow}>
          <CurrencyPicker
            value={currency}
            onChange={setCurrency}
            currencies={currenciesQuery.data}
          />
          <Pressable
            onPress={() => setConvertAll(!convertAll)}
            style={({ pressed }) => [
              styles.convertChip,
              convertAll && styles.convertChipActive,
              pressed && { opacity: 0.7 },
            ]}
            accessibilityRole="switch"
            accessibilityState={{ checked: convertAll }}
          >
            <Text
              style={[
                styles.convertChipText,
                convertAll && styles.convertChipTextActive,
              ]}
            >
              {convertAll ? '✓ Convertir todo' : 'Convertir todo'}
            </Text>
          </Pressable>
        </View>
        <PeriodToggle
          value={period}
          onChange={handlePeriodChange}
          options={['month', 'year', 'custom']}
        />
        {period === 'custom' ? (
          <View style={styles.customRow}>
            <DateInput
              value={customFrom ?? ''}
              maximumDate={customTo ? new Date(customTo) : undefined}
              onChange={(from) => handleCustomRangeChange(from, customTo ?? '')}
            />
            <Text style={styles.customDash}>–</Text>
            <DateInput
              value={customTo ?? ''}
              minimumDate={customFrom ? new Date(customFrom) : undefined}
              onChange={(to) => handleCustomRangeChange(customFrom ?? '', to)}
            />
          </View>
        ) : null}

        {hasError ? (
          <View style={{ marginBottom: spacing.md }}>
            <ErrorState
              description="No se pudieron cargar algunas secciones del análisis. Las cifras pueden estar incompletas."
              onRetry={handleRefresh}
              retrying={refreshing}
            />
          </View>
        ) : null}

        <BalancesCard />
        <DebtHealthCard />
        <NetworthEvolutionCard />
        <KpiCards summary={summaryQuery.data} isLoading={summaryQuery.isLoading} />
        <SavingsRateCard summary={summaryQuery.data} />
        <MonthOutlookCard data={outlookQuery.data} currency={currency} />
        <MonthlyChart
          data={monthlyQuery.data}
          isLoading={monthlyQuery.isLoading}
          currency={currency}
        />
        <CategoryDonut
          data={byCategoryQuery.data}
          currency={currency}
          isLoading={byCategoryQuery.isLoading}
          kind={donutKind}
          onKindChange={setDonutKind}
          exceptionalByCategory={structureQuery.data?.exceptional_by_category}
        />
        {/* PHASE-47.E — el donut MANTIENE las compras aplazadas (el gasto se
            hizo) y los KPI de arriba las excluyen (el dinero no salió). Sin
            este aviso, quien sume el donut se encuentra cientos de euros de
            más que el KPI y no tiene forma de saber por qué. */}
        {deferredNotice ? (
          <Text
            testID="deferred-notice"
            style={{
              fontSize: fontSize.xs,
              color: colors.textMuted,
              lineHeight: 18,
              paddingHorizontal: spacing.md,
              marginBottom: spacing.md,
            }}
          >
            {deferredNotice}
          </Text>
        ) : null}
        <TopExpensesList
          data={topExpensesQuery.data}
          currency={currency}
          isLoading={topExpensesQuery.isLoading}
        />
        <SmartInsights
          summary={summaryQuery.data}
          expensesByCategory={expensesByCategory}
          structure={structureQuery.data}
          outlook={outlookQuery.data}
          currency={currency}
        />
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
  customRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginBottom: spacing.md,
  },
  customDash: { color: colors.textMuted, fontSize: fontSize.sm },
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
  currencyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  convertChip: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    borderRadius: 999,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  convertChipActive: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  convertChipText: {
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: fontWeight.medium,
  },
  convertChipTextActive: {
    color: colors.primary,
    fontWeight: fontWeight.semibold,
  },
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
});
