'use client';

import { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';

import {
  useAccountBalances,
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardSummary,
  useDebtHealth,
  usePositionHistory,
} from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import type { DtiStatus } from '@crisol/types';
import { colors, fontSize, fontWeight, formatAmount, spacing } from '@crisol/ui';

import { AccountsSection } from '@/components/analysis/accounts-section';
import { DebtSummaryCard } from '@/components/analysis/debt-summary-card';
import {
  KpiStrip,
  KpiTile,
  MiniSparkline,
  type KpiStatus,
} from '@/components/analysis/kpi-strip';
import { NetworthEvolutionCard } from '@/components/analysis/networth-evolution-card';
import {
  boundsForAnchor,
  type PeriodKey,
} from '@/components/analysis/stitch-period-toggle';
import { StitchSmartInsights } from '@/components/analysis/stitch-smart-insights';
import { PeriodNavigator } from '@/components/debt/period-navigator';
import { Card } from '@/components/ui/card';
import { ErrorState } from '@/components/ui/error-state';
import { Skeleton } from '@/components/ui/skeleton';

const StitchIncomeVsExpenses = dynamic(
  () =>
    import('@/components/analysis/stitch-income-vs-expenses').then(
      (m) => m.StitchIncomeVsExpenses,
    ),
  { ssr: false, loading: () => <Skeleton height={340} /> },
);
const StitchExpenseBreakdown = dynamic(
  () =>
    import('@/components/analysis/stitch-expense-breakdown').then(
      (m) => m.StitchExpenseBreakdown,
    ),
  { ssr: false, loading: () => <Skeleton height={340} /> },
);

const EFFORT_STATUS: Record<DtiStatus, KpiStatus> = {
  healthy: 'success',
  caution: 'warning',
  stressed: 'danger',
  unknown: 'neutral',
};

function fmtSignedAmount(value: string | number, currency: string): string {
  const n = Number(value);
  return `${n >= 0 ? '+' : ''}${formatAmount(String(n.toFixed(2)), currency)}`;
}

export default function AnalysisPage() {
  const [period, setPeriod] = useState<PeriodKey>('year');
  const [anchorMonth, setAnchorMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });
  const currency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);
  const targetCurrency = convertAll ? currency : undefined;

  const { dateFrom, dateTo } = useMemo(
    () => boundsForAnchor(period, anchorMonth),
    [period, anchorMonth],
  );
  const anchorYear = Number(anchorMonth.split('-')[0]);

  const summaryParams = convertAll
    ? { target_currency: currency, date_from: dateFrom, date_to: dateTo }
    : { currency, date_from: dateFrom, date_to: dateTo };
  const monthlyParams = convertAll
    ? { target_currency: currency, year: anchorYear }
    : { currency, year: anchorYear };
  const byCategoryParams = convertAll
    ? { target_currency: currency, date_from: dateFrom, date_to: dateTo, kind: 'expense' as const }
    : { currency, date_from: dateFrom, date_to: dateTo, kind: 'expense' as const };

  const summaryQuery = useDashboardSummary(summaryParams);
  const monthlyQuery = useDashboardByMonth(monthlyParams);
  const expensesByCategoryQuery = useDashboardByCategory(byCategoryParams);
  // PHASE-37 — patrimonio (stock): posición actual + serie + salud de deuda.
  // No dependen del período (son fotos a fecha); su dimensión temporal es la
  // serie y el Δ, no el filtro de rango.
  const balancesQuery = useAccountBalances(targetCurrency ? { targetCurrency } : {});
  const positionQuery = usePositionHistory(12, 0);
  const debtQuery = useDebtHealth(targetCurrency ? { targetCurrency } : {});

  const summary = summaryQuery.data;
  const monthly = monthlyQuery.data ?? [];
  const expensesByCategory = expensesByCategoryQuery.data ?? [];
  const unconvertible = summary?.unconvertible_count ?? 0;
  const balances = balancesQuery.data;
  const position = positionQuery.data;
  const debt = debtQuery.data;
  const refCurrency = summary?.currency ?? currency;

  // ── Tiles del strip ──────────────────────────────────────────────────
  const netWorth = balances?.net_worth ?? null;
  const deltaPeriod = position?.delta_period ?? null;
  const sparkValues = (position?.points ?? []).map((p) => Number(p.net_worth));
  const effort = debt?.dti_ratio ?? null;
  const effortStatus: KpiStatus = debt ? EFFORT_STATUS[debt.dti_status] : 'neutral';
  const cashflow = summary?.balance ?? null;
  const cashflowDelta = summary?.cashflow_delta ?? null;
  const savingsRate =
    summary && Number(summary.income) > 0
      ? (Number(summary.balance) / Number(summary.income)) * 100
      : null;
  const savingsDeltaPp = summary?.savings_rate_delta_pp ?? null;

  const monthlyNets = monthly.map((m) => Number(m.income) - Number(m.expenses));

  const hasError =
    summaryQuery.isError || monthlyQuery.isError || expensesByCategoryQuery.isError;
  const isRefetching =
    summaryQuery.isFetching || monthlyQuery.isFetching || expensesByCategoryQuery.isFetching;
  const isShowingStale =
    summaryQuery.isPlaceholderData || expensesByCategoryQuery.isPlaceholderData;
  function retryAll() {
    void summaryQuery.refetch();
    void monthlyQuery.refetch();
    void expensesByCategoryQuery.refetch();
  }

  return (
    <div style={{ maxWidth: 1520, margin: '0 auto', padding: spacing.lg }}>
      <header style={{ marginBottom: spacing.lg }}>
        <span
          style={{
            fontSize: 11,
            fontWeight: fontWeight.semibold,
            color: colors.primary,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            display: 'block',
            marginBottom: spacing.xs,
          }}
        >
          ANALYTICS ENGINE · LOCAL
        </span>
        <h1
          style={{
            margin: 0,
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            color: colors.text,
            letterSpacing: '-0.02em',
            lineHeight: 1.1,
          }}
        >
          Análisis financiero
        </h1>
        <p style={{ margin: `${spacing.xs}px 0 0 0`, color: colors.textMuted, fontSize: fontSize.sm }}>
          Patrones de ingresos, gastos y patrimonio · cómputos client-side, sin enviar datos fuera de tu equipo.
        </p>
        {convertAll && unconvertible > 0 ? (
          <p style={{ margin: `${spacing.xs}px 0 0 0`, color: colors.warning, fontSize: fontSize.xs }}>
            ⚠ {unconvertible} {unconvertible === 1 ? 'transacción' : 'transacciones'} sin tasa disponible — quedan fuera del total.
          </p>
        ) : null}
      </header>

      <div
        style={{
          marginBottom: spacing.md,
          display: 'flex',
          alignItems: 'center',
          gap: spacing.md,
          flexWrap: 'wrap',
        }}
      >
        <PeriodNavigator
          range={period}
          onRangeChange={setPeriod}
          anchor={anchorMonth}
          onAnchorChange={setAnchorMonth}
          availableFrom={summary?.available_from ?? null}
          availableTo={summary?.available_to ?? null}
        />
        {isShowingStale ? (
          <span style={{ fontSize: fontSize.xs, color: colors.textMuted, fontWeight: fontWeight.medium }}>
            Actualizando cifras del período…
          </span>
        ) : null}
      </div>

      {hasError ? (
        <div style={{ marginBottom: spacing.md }}>
          <ErrorState
            description="No se pudieron cargar algunos datos del análisis. Las cifras mostradas pueden estar incompletas."
            onRetry={retryAll}
            retrying={isRefetching}
            compact
          />
        </div>
      ) : null}

      {/* KPI STRIP — patrimonio (stock + Δ) + esfuerzo + flujo + ahorro. */}
      <div style={{ marginBottom: spacing.md }}>
        <KpiStrip>
          <KpiTile
            label="Patrimonio neto"
            value={netWorth != null ? formatAmount(netWorth, refCurrency) : '—'}
            sparkline={
              sparkValues.length >= 2 ? (
                <MiniSparkline
                  values={sparkValues}
                  up={sparkValues[sparkValues.length - 1]! >= sparkValues[0]!}
                />
              ) : undefined
            }
          />
          <KpiTile
            label="Δ patrimonio"
            value={deltaPeriod != null ? fmtSignedAmount(deltaPeriod, refCurrency) : '—'}
            delta={deltaPeriod != null ? Number(deltaPeriod) : null}
            deltaText={
              position?.delta_period_pct != null ? `${position.delta_period_pct.toFixed(1)} %` : undefined
            }
            subtitle="vs inicio del rango"
          />
          <KpiTile
            label="Tasa de esfuerzo"
            value={effort != null ? `${(effort * 100).toFixed(1)} %` : '—'}
            status={effortStatus}
            subtitle="BdE < 35%"
          />
          <KpiTile
            label="Flujo de caja neto"
            value={cashflow != null ? fmtSignedAmount(cashflow, refCurrency) : '—'}
            delta={cashflowDelta != null ? Number(cashflowDelta) : null}
            deltaText={cashflowDelta != null ? fmtSignedAmount(cashflowDelta, refCurrency) : undefined}
            subtitle="vs periodo anterior"
          />
          <KpiTile
            label="Tasa de ahorro"
            value={savingsRate != null ? `${savingsRate.toFixed(1)} %` : '—'}
            delta={savingsDeltaPp}
            deltaText={savingsDeltaPp != null ? `${savingsDeltaPp >= 0 ? '+' : ''}${savingsDeltaPp.toFixed(1)} pp` : undefined}
            subtitle="vs periodo anterior"
          />
        </KpiStrip>
      </div>

      {/* Fila 1: Ingresos vs Gastos + Evolución del patrimonio. */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 8fr) minmax(0, 4fr)',
          gap: spacing.md,
          marginBottom: spacing.md,
        }}
      >
        <StitchIncomeVsExpenses
          data={monthly}
          currency={currency}
          isLoading={monthlyQuery.isLoading}
          period={period}
          anchorMonth={anchorMonth}
        />
        <NetworthEvolutionCard
          points={position?.points ?? []}
          currency={position?.reference_currency ?? refCurrency}
          isLoading={positionQuery.isLoading}
        />
      </div>

      {/* Fila 2: Desglose de gastos + Deuda (resumen). */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 7fr) minmax(0, 5fr)',
          gap: spacing.md,
          marginBottom: spacing.md,
        }}
      >
        <StitchExpenseBreakdown
          items={expensesByCategory}
          currency={currency}
          isLoading={expensesByCategoryQuery.isLoading}
        />
        <DebtSummaryCard />
      </div>

      {/* Fila 3: Flujo neto mensual + Smart Insights. */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
          gap: spacing.md,
          marginBottom: spacing.md,
        }}
      >
        <Card style={{ padding: spacing.lg }}>
          <h3
            style={{
              margin: `0 0 ${spacing.sm}px 0`,
              fontSize: fontSize.md,
              fontWeight: fontWeight.semibold,
              color: colors.text,
            }}
          >
            Flujo neto mensual
          </h3>
          {monthlyNets.length >= 2 ? (
            <MiniSparkline
              values={monthlyNets}
              up={(monthlyNets[monthlyNets.length - 1] ?? 0) >= 0}
            />
          ) : (
            <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>
              Necesitas al menos 2 meses con datos.
            </p>
          )}
        </Card>
        <StitchSmartInsights
          summary={summary}
          expensesByCategory={expensesByCategory}
          currency={currency}
        />
      </div>

      {/* Cuentas — sección colapsable a ancho completo. */}
      <AccountsSection />
    </div>
  );
}
