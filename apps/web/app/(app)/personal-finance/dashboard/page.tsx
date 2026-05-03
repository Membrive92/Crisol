'use client';

import { useEffect, useState } from 'react';

import {
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardSummary,
  useUserCurrencies,
} from '@finanzas/services';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import {
  DashboardFilters,
  type DashboardFiltersValue,
} from '@/components/dashboard/dashboard-filters';
import { StitchBalanceChart } from '@/components/dashboard/stitch-balance-chart';
import { StitchKpiRow } from '@/components/dashboard/stitch-kpi-row';
import { StitchRecentActivity } from '@/components/dashboard/stitch-recent-activity';
import { StitchSecondaryMetrics } from '@/components/dashboard/stitch-secondary-metrics';
import { StitchTipCard } from '@/components/dashboard/stitch-tip-card';

const FALLBACK_CURRENCY = 'EUR';

export default function DashboardPage() {
  const [filters, setFilters] = useState<DashboardFiltersValue>({
    currency: FALLBACK_CURRENCY,
    year: new Date().getFullYear(),
  });
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
  const expensesByCategoryQuery = useDashboardByCategory({
    currency: filters.currency,
    date_from: dateFrom,
    date_to: dateTo,
    kind: 'expense',
  });

  const anyError =
    summaryQuery.isError || monthlyQuery.isError || expensesByCategoryQuery.isError;

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: spacing.lg }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: spacing.md,
          flexWrap: 'wrap',
          marginBottom: spacing.lg,
        }}
      >
        <div>
          <h1
            style={{
              margin: 0,
              fontSize: fontSize.xl,
              fontWeight: fontWeight.bold,
              color: colors.text,
              letterSpacing: '-0.01em',
            }}
          >
            Dashboard
          </h1>
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              color: colors.textMuted,
              fontSize: fontSize.sm,
            }}
          >
            Vista general de ingresos, gastos y categorías.
          </p>
        </div>
        <DashboardFilters
          value={filters}
          onChange={setFilters}
          currencies={currenciesQuery.data}
        />
      </header>

      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
        <StitchKpiRow summary={summaryQuery.data} isLoading={summaryQuery.isLoading} />

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)',
            gap: spacing.md,
            alignItems: 'start',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
            <StitchBalanceChart
              data={monthlyQuery.data ?? []}
              currency={filters.currency}
              isLoading={monthlyQuery.isLoading}
            />
            <StitchSecondaryMetrics
              summary={summaryQuery.data}
              expensesByCategory={expensesByCategoryQuery.data}
              currency={filters.currency}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
            <StitchRecentActivity />
            <StitchTipCard summary={summaryQuery.data} />
          </div>
        </div>
      </div>

      {anyError && (
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
