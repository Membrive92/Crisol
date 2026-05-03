'use client';

import { useState } from 'react';

import {
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardSummary,
} from '@finanzas/services';
import { useCurrencyStore } from '@finanzas/store';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { StitchBalanceChart } from '@/components/dashboard/stitch-balance-chart';
import { StitchKpiRow } from '@/components/dashboard/stitch-kpi-row';
import { StitchRecentActivity } from '@/components/dashboard/stitch-recent-activity';
import { StitchSecondaryMetrics } from '@/components/dashboard/stitch-secondary-metrics';
import { StitchTipCard } from '@/components/dashboard/stitch-tip-card';
import { YearSelect } from '@/components/dashboard/year-select';

export default function DashboardPage() {
  const currency = useCurrencyStore((s) => s.currency);
  const [year, setYear] = useState(new Date().getFullYear());

  const dateFrom = new Date(year, 0, 1).toISOString();
  const dateTo = new Date(year, 11, 31, 23, 59, 59).toISOString();

  const summaryQuery = useDashboardSummary({
    currency,
    date_from: dateFrom,
    date_to: dateTo,
  });
  const monthlyQuery = useDashboardByMonth({
    currency,
    year,
  });
  const expensesByCategoryQuery = useDashboardByCategory({
    currency,
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
        <YearSelect value={year} onChange={setYear} />
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
              currency={currency}
              isLoading={monthlyQuery.isLoading}
            />
            <StitchSecondaryMetrics
              summary={summaryQuery.data}
              expensesByCategory={expensesByCategoryQuery.data}
              currency={currency}
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
