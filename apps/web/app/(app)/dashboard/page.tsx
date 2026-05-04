'use client';

import { useMemo, useState } from 'react';

import {
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardSummary,
} from '@finanzas/services';
import { useCurrencyStore } from '@finanzas/store';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import {
  StitchPeriodToggle,
  rangeForPeriod,
  type PeriodKey,
} from '@/components/analysis/stitch-period-toggle';
import { StitchBalanceChart } from '@/components/dashboard/stitch-balance-chart';
import { StitchKpiRow } from '@/components/dashboard/stitch-kpi-row';
import { StitchRecentActivity } from '@/components/dashboard/stitch-recent-activity';
import { StitchSecondaryMetrics } from '@/components/dashboard/stitch-secondary-metrics';
import { StitchTipCard } from '@/components/dashboard/stitch-tip-card';

export default function DashboardPage() {
  const currency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);
  const [period, setPeriod] = useState<PeriodKey>('year');

  const { dateFrom, dateTo } = useMemo(() => rangeForPeriod(period), [period]);
  const currentYear = new Date().getFullYear();

  // PHASE-8.3: una sola petición por endpoint, el backend convierte
  // per-transaction usando la tasa del día de cada `occurred_at`.
  // Modo legacy (toggle OFF) sigue filtrando por moneda activa sin
  // conversión.
  const summaryParams = convertAll
    ? { target_currency: currency, date_from: dateFrom, date_to: dateTo }
    : { currency, date_from: dateFrom, date_to: dateTo };
  const monthlyParams = convertAll
    ? { target_currency: currency, year: currentYear }
    : { currency, year: currentYear };
  const byCategoryParams = convertAll
    ? {
        target_currency: currency,
        date_from: dateFrom,
        date_to: dateTo,
        kind: 'expense' as const,
      }
    : { currency, date_from: dateFrom, date_to: dateTo, kind: 'expense' as const };

  const summaryQuery = useDashboardSummary(summaryParams);
  const monthlyQuery = useDashboardByMonth(monthlyParams);
  const expensesByCategoryQuery = useDashboardByCategory(byCategoryParams);

  const summary = summaryQuery.data;
  const monthly = monthlyQuery.data ?? [];
  const byCategory = expensesByCategoryQuery.data ?? [];
  const anyError =
    summaryQuery.isError || monthlyQuery.isError || expensesByCategoryQuery.isError;
  const unconvertible = summary?.unconvertible_count ?? 0;

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
            {convertAll
              ? `Vista cross-currency · todas las transacciones convertidas a ${currency} con la tasa del día.`
              : 'Vista general de ingresos, gastos y categorías.'}
          </p>
          {convertAll && unconvertible > 0 ? (
            <p
              style={{
                margin: `${spacing.xs}px 0 0 0`,
                color: colors.warning,
                fontSize: fontSize.xs,
              }}
            >
              ⚠ {unconvertible} {unconvertible === 1 ? 'transacción' : 'transacciones'} sin
              tasa disponible — quedan fuera del total.
            </p>
          ) : null}
        </div>
        <StitchPeriodToggle value={period} onChange={setPeriod} />
      </header>

      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
        <StitchKpiRow summary={summary} isLoading={summaryQuery.isLoading} />

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
              data={monthly}
              currency={currency}
              isLoading={monthlyQuery.isLoading}
            />
            <StitchSecondaryMetrics
              summary={summary}
              expensesByCategory={byCategory}
              currency={currency}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
            <StitchRecentActivity />
            <StitchTipCard summary={summary} />
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
