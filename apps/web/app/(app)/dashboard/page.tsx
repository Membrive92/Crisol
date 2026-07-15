'use client';

import { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';

import {
  useAccountBalances,
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardSummary,
} from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import { colors, fontSize, fontWeight, layout, spacing } from '@crisol/ui';

import { boundsForAnchor, type PeriodKey } from '@/components/analysis/stitch-period-toggle';
import { PeriodNavigator } from '@/components/debt/period-navigator';
import { StitchKpiRow } from '@/components/dashboard/stitch-kpi-row';
import { Skeleton } from '@/components/ui/skeleton';

// AUDIT-2026-05: chart con recharts en chunk diferido (ssr:false).
const StitchBalanceChart = dynamic(
  () => import('@/components/dashboard/stitch-balance-chart').then((m) => m.StitchBalanceChart),
  { ssr: false, loading: () => <Skeleton height={300} /> },
);
import { StitchRecentActivity } from '@/components/dashboard/stitch-recent-activity';
import { StitchSecondaryMetrics } from '@/components/dashboard/stitch-secondary-metrics';
import { StitchTipCard } from '@/components/dashboard/stitch-tip-card';

export default function DashboardPage() {
  const currency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);
  // Toggle "incluir deuda en patrimonio" (menú de divisa del header): ON →
  // net_worth (activos − deuda); OFF → sólo activos. El mismo que gobierna
  // Análisis. Aquí alimenta el nuevo KPI de patrimonio.
  const includeDebt = useCurrencyStore((s) => s.includeDebtInNetWorth);
  const targetCurrency = convertAll ? currency : undefined;
  const [period, setPeriod] = useState<PeriodKey>('year');
  // Navegación de periodo (mismo patrón que Análisis): el ancla es el mes
  // contextual; las flechas del `PeriodNavigator` la mueven dentro de los datos.
  const [anchorMonth, setAnchorMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });

  const { dateFrom, dateTo } = useMemo(
    () => boundsForAnchor(period, anchorMonth),
    [period, anchorMonth],
  );
  const anchorYear = Number(anchorMonth.split('-')[0]);

  // PHASE-8.3: una sola petición por endpoint, el backend convierte
  // per-transaction usando la tasa del día de cada `occurred_at`.
  // Modo legacy (toggle OFF) sigue filtrando por moneda activa sin
  // conversión.
  const summaryParams = convertAll
    ? { target_currency: currency, date_from: dateFrom, date_to: dateTo }
    : { currency, date_from: dateFrom, date_to: dateTo };
  // El gráfico mensual sigue el AÑO ANCLADO (antes fijo a currentYear → no
  // reaccionaba al periodo navegado).
  const monthlyParams = convertAll
    ? { target_currency: currency, year: anchorYear }
    : { currency, year: anchorYear };
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
  // Patrimonio (stock, no depende del periodo — es una foto a fecha, igual
  // que en Análisis). Alimenta el nuevo KPI + hace que el toggle del header
  // tenga efecto aquí.
  const balancesQuery = useAccountBalances(targetCurrency ? { targetCurrency } : {});
  const balances = balancesQuery.data;
  const netWorth = balances ? balances[includeDebt ? 'net_worth' : 'total_assets'] : null;

  const summary = summaryQuery.data;
  const monthly = monthlyQuery.data ?? [];
  // El gráfico muestra SÓLO los meses del periodo navegado (Año=12, Trim=3,
  // Mes=1). `monthly` trae los 12 del año anclado; filtramos por el rango
  // `[dateFrom, dateTo]` comparando el `YYYY-MM` del bucket.
  const chartMonths = useMemo(() => {
    const fromYM = dateFrom.slice(0, 7);
    const toYM = dateTo.slice(0, 7);
    return monthly.filter((b) => b.month >= fromYM && b.month <= toYM);
  }, [monthly, dateFrom, dateTo]);
  const byCategory = expensesByCategoryQuery.data ?? [];
  const anyError =
    summaryQuery.isError || monthlyQuery.isError || expensesByCategoryQuery.isError;
  const unconvertible = summary?.unconvertible_count ?? 0;

  return (
    <div style={{ maxWidth: layout.pageWide, margin: '0 auto', padding: spacing.lg }}>
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
        <PeriodNavigator
          range={period}
          onRangeChange={setPeriod}
          anchor={anchorMonth}
          onAnchorChange={setAnchorMonth}
          availableFrom={summary?.available_from ?? null}
          availableTo={summary?.available_to ?? null}
        />
      </header>

      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
        <StitchKpiRow
          summary={summary}
          isLoading={summaryQuery.isLoading}
          netWorth={netWorth}
          includeDebt={includeDebt}
          netWorthLoading={balancesQuery.isLoading}
        />

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
              data={chartMonths}
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
