'use client';

import { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';

import {
  useAccountBalances,
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardSummary,
  useDebtHealth,
  useExpenseStructure,
  useMonthOutlook,
  usePositionHistory,
} from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import type { DtiStatus } from '@crisol/types';
import { colors, fontSize, fontWeight, formatAmount, layout, spacing } from '@crisol/ui';

import { AccountsSection } from '@/components/analysis/accounts-section';
import { DebtSummaryCard } from '@/components/analysis/debt-summary-card';
import {
  KpiStrip,
  KpiTile,
  MiniSparkline,
  type KpiStatus,
} from '@/components/analysis/kpi-strip';
import { MonthOutlookCard } from '@/components/analysis/month-outlook-card';
import { NetworthEvolutionCard } from '@/components/analysis/networth-evolution-card';
import {
  boundsForAnchor,
  type PeriodKey,
} from '@/components/analysis/stitch-period-toggle';
import { StitchSmartInsights } from '@/components/analysis/stitch-smart-insights';
import { PeriodNavigator } from '@/components/debt/period-navigator';
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
  // El toggle "Incluir deuda en el patrimonio neto" (menú de divisa del
  // header): ON → patrimonio = activos − pasivos; OFF → sólo activos (la deuda
  // no resta del neto). Es la palanca para ver el patrimonio "de caja".
  const includeDebt = useCurrencyStore((s) => s.includeDebtInNetWorth);
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
  // PHASE-37.3 — gasto estructural/puntual del rango (mismo scope de período).
  const structureParams = convertAll
    ? { target_currency: currency, date_from: dateFrom, date_to: dateTo }
    : { currency, date_from: dateFrom, date_to: dateTo };

  const summaryQuery = useDashboardSummary(summaryParams);
  const monthlyQuery = useDashboardByMonth(monthlyParams);
  const expensesByCategoryQuery = useDashboardByCategory(byCategoryParams);
  const structureQuery = useExpenseStructure(structureParams);
  // PHASE-37.4 — proyección fin de mes + runway (sin rango: siempre el mes
  // en curso). Sólo modo de divisa.
  const outlookParams = convertAll ? { target_currency: currency } : { currency };
  const outlookQuery = useMonthOutlook(outlookParams);
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
  // El patrimonio (valor + Δ + sparkline) respeta el toggle: `net_worth`
  // (con deuda) o `total_assets` (sin deuda). La serie trae ambas métricas.
  const worthKey = includeDebt ? 'net_worth' : 'total_assets';
  const netWorth = balances ? balances[worthKey] : null;
  const worthSeries = (position?.points ?? []).map((p) => Number(p[worthKey]));
  const deltaPeriod =
    worthSeries.length >= 2 ? worthSeries[worthSeries.length - 1]! - worthSeries[0]! : null;
  const deltaPeriodPct =
    deltaPeriod != null && worthSeries[0] !== 0
      ? (deltaPeriod / Math.abs(worthSeries[0]!)) * 100
      : null;
  const sparkValues = worthSeries;
  const effort = debt?.dti_ratio ?? null;
  const effortStatus: KpiStatus = debt ? EFFORT_STATUS[debt.dti_status] : 'neutral';
  const cashflow = summary?.balance ?? null;
  const cashflowDelta = summary?.cashflow_delta ?? null;
  const savingsRate =
    summary && Number(summary.income) > 0
      ? (Number(summary.balance) / Number(summary.income)) * 100
      : null;
  const savingsDeltaPp = summary?.savings_rate_delta_pp ?? null;
  // PHASE-37.3 — tasa de ahorro estructural (excluye gastos puntuales). Si
  // difiere >10pp de la bruta, un badge en el tile invita a fijarse.
  const structure = structureQuery.data;
  const savingsStructuralPct =
    structure?.savings_rate_structural != null ? structure.savings_rate_structural * 100 : null;
  const savingsDiffPp =
    savingsStructuralPct != null && savingsRate != null
      ? savingsStructuralPct - savingsRate
      : null;

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
    <div style={{ maxWidth: layout.pageWide, margin: '0 auto', padding: spacing.lg }}>
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
            delta={deltaPeriod}
            deltaText={deltaPeriodPct != null ? `${deltaPeriodPct.toFixed(1)} %` : undefined}
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
            subtitle={
              savingsStructuralPct != null
                ? `Solo fijos ${savingsStructuralPct.toFixed(0)} %`
                : 'vs periodo anterior'
            }
            badge={
              savingsDiffPp != null && Math.abs(savingsDiffPp) > 10
                ? `${savingsDiffPp >= 0 ? '+' : ''}${savingsDiffPp.toFixed(0)} pp`
                : undefined
            }
            title={
              savingsStructuralPct != null
                ? `Excluyendo gastos variables (impuestos, puntuales), tu tasa de ahorro sería ${savingsStructuralPct.toFixed(0)} %.`
                : undefined
            }
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
          onSelectMonth={(month) => {
            setAnchorMonth(month);
            setPeriod('month');
          }}
        />
        <NetworthEvolutionCard
          points={position?.points ?? []}
          currency={position?.reference_currency ?? refCurrency}
          isLoading={positionQuery.isLoading}
        />
      </div>

      {/* Desglose de gastos y Deuda, cada uno a ANCHO COMPLETO y apilados. Iban
          emparejados (8/4) pero la card de deuda es intrínsecamente más alta (su
          número + KPIs ya miden casi como toda la card de desglose), así que
          nunca cuadraban de altura. A ancho completo, cada una reparte su
          contenido en varias columnas (categorías / movimientos) y queda corta,
          sin desajuste. */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: spacing.md,
          marginBottom: spacing.md,
        }}
      >
        <StitchExpenseBreakdown
          items={expensesByCategory}
          currency={currency}
          isLoading={expensesByCategoryQuery.isLoading}
          exceptionalByCategory={structure?.exceptional_by_category}
          dateFrom={dateFrom}
          dateTo={dateTo}
        />
        <DebtSummaryCard dateFrom={dateFrom} dateTo={dateTo} />
      </div>

      {/* Fila 3: Fin de mes (outlook) + Smart Insights. */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
          gap: spacing.md,
          marginBottom: spacing.md,
        }}
      >
        <MonthOutlookCard
          data={outlookQuery.data}
          currency={refCurrency}
          isLoading={outlookQuery.isLoading}
        />
        <StitchSmartInsights
          summary={summary}
          expensesByCategory={expensesByCategory}
          structure={structure}
          outlook={outlookQuery.data}
          currency={currency}
        />
      </div>

      {/* Cuentas — sección colapsable a ancho completo. */}
      <AccountsSection />
    </div>
  );
}
