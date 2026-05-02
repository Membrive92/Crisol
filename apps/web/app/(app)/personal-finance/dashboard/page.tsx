'use client';

import { useState } from 'react';

import {
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardSummary,
  useDashboardTopExpenses,
} from '@finanzas/services';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import {
  CategoryDonut,
  type DonutKindFilter,
} from '@/components/dashboard/category-donut';
import {
  DashboardFilters,
  type DashboardFiltersValue,
} from '@/components/dashboard/dashboard-filters';
import { KpiCards } from '@/components/dashboard/kpi-cards';
import { MonthlyChart } from '@/components/dashboard/monthly-chart';
import { TopExpensesList } from '@/components/dashboard/top-expenses-list';

const TOP_EXPENSES_LIMIT = 5;

export default function DashboardPage() {
  const [filters, setFilters] = useState<DashboardFiltersValue>({
    currency: 'EUR',
    year: new Date().getFullYear(),
  });
  const [donutKind, setDonutKind] = useState<DonutKindFilter>('all');

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
    // 'all' = sin filtro de kind: backend devuelve todas las categorías
    // (income + expense) y el bucket "Sin categoría". Income/Expense lo
    // restringen como antes.
    ...(donutKind === 'all' ? {} : { kind: donutKind }),
  });
  const topExpensesQuery = useDashboardTopExpenses({
    currency: filters.currency,
    date_from: dateFrom,
    date_to: dateTo,
    limit: TOP_EXPENSES_LIMIT,
  });

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: spacing.lg }}>
      <header style={{ marginBottom: spacing.lg }}>
        <h1 style={{ margin: 0, fontSize: fontSize.xl, color: colors.text }}>Dashboard</h1>
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
          Vista general de ingresos, gastos y categorías.
        </p>
      </header>

      <DashboardFilters value={filters} onChange={setFilters} />

      <KpiCards summary={summaryQuery.data} isLoading={summaryQuery.isLoading} />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
          gap: spacing.md,
          marginBottom: spacing.md,
        }}
      >
        <MonthlyChart
          data={monthlyQuery.data}
          currency={filters.currency}
          isLoading={monthlyQuery.isLoading}
        />
        <CategoryDonut
          data={byCategoryQuery.data}
          currency={filters.currency}
          isLoading={byCategoryQuery.isLoading}
          kind={donutKind}
          onKindChange={setDonutKind}
        />
      </div>

      <TopExpensesList
        data={topExpensesQuery.data}
        currency={filters.currency}
        isLoading={topExpensesQuery.isLoading}
      />

      {(summaryQuery.isError ||
        monthlyQuery.isError ||
        byCategoryQuery.isError ||
        topExpensesQuery.isError) && (
        <p
          style={{
            color: colors.danger,
            marginTop: spacing.md,
            fontSize: fontSize.sm,
            fontWeight: fontWeight.medium,
          }}
        >
          Error cargando alguna sección del dashboard.
        </p>
      )}
    </div>
  );
}
