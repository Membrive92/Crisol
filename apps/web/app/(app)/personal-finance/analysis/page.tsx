'use client';

import { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { useRouter, useSearchParams } from 'next/navigation';

import {
  useAccountBalances,
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardSummary,
  useDebtHealth,
  useExpenseStructure,
  useMonthOutlook,
  usePositionAsOf,
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
  boundsForCustomRange,
  type PeriodKey,
} from '@/components/analysis/stitch-period-toggle';
import type { StructureFilter } from '@/components/analysis/stitch-expense-breakdown';
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

// PHASE-41 — período/ancla/filtro del desglose viajan en la URL para que al
// entrar en una categoría y volver (link "← Análisis" o el botón atrás del
// navegador) se restaure el estado en vez de caer al default anual.
function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}
function parsePeriod(v: string | null): PeriodKey {
  return v === 'month' || v === 'year' || v === 'custom' ? v : 'year';
}
function parseFilter(v: string | null): StructureFilter {
  return v === 'structural' || v === 'exceptional' ? v : 'all';
}
function analysisQuery(
  p: PeriodKey,
  a: string,
  f: StructureFilter,
  cf?: string | null,
  ct?: string | null,
): string {
  const sp = new URLSearchParams();
  sp.set('period', p);
  sp.set('anchor', a);
  if (f !== 'all') sp.set('filter', f);
  if (p === 'custom' && cf && ct) {
    sp.set('from', cf);
    sp.set('to', ct);
  }
  return sp.toString();
}

export default function AnalysisPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [period, setPeriodState] = useState<PeriodKey>(() =>
    parsePeriod(searchParams.get('period')),
  );
  const [anchorMonth, setAnchorMonthState] = useState<string>(
    () => searchParams.get('anchor') ?? currentMonth(),
  );
  const [filter, setFilterState] = useState<StructureFilter>(() =>
    parseFilter(searchParams.get('filter')),
  );
  // PHASE-41 — rango libre `custom` (`YYYY-MM-DD`), en la URL como `from`/`to`.
  const [customFrom, setCustomFromState] = useState<string | null>(() =>
    searchParams.get('from'),
  );
  const [customTo, setCustomToState] = useState<string | null>(() =>
    searchParams.get('to'),
  );
  // Un único escritor de la URL (evita carreras entre setters). Recibe los
  // valores explícitos; los setters mergean con el estado actual antes de llamar.
  function apply(next: {
    period?: PeriodKey;
    anchor?: string;
    filter?: StructureFilter;
    customFrom?: string | null;
    customTo?: string | null;
  }): void {
    const p = next.period ?? period;
    const a = next.anchor ?? anchorMonth;
    const f = next.filter ?? filter;
    const cf = next.customFrom !== undefined ? next.customFrom : customFrom;
    const ct = next.customTo !== undefined ? next.customTo : customTo;
    if (next.period !== undefined) setPeriodState(p);
    if (next.anchor !== undefined) setAnchorMonthState(a);
    if (next.filter !== undefined) setFilterState(f);
    if (next.customFrom !== undefined) setCustomFromState(next.customFrom);
    if (next.customTo !== undefined) setCustomToState(next.customTo);
    router.replace(
      `/personal-finance/analysis?${analysisQuery(p, a, f, cf, ct)}`,
      { scroll: false },
    );
  }
  // Al conmutar a "Personalizado", siembra los date-pickers con el MES ancla
  // (no el año): así el rango arranca estrecho y el cambio es visible de
  // inmediato (sembrar el año entero hacía que la vista custom saliera idéntica
  // a "Año" y pareciera que no se actualizaba). Si ya hay from/to, se respetan.
  function handleRangeChange(next: PeriodKey): void {
    if (next === 'custom' && !(customFrom && customTo)) {
      const seed = boundsForAnchor('month', anchorMonth);
      apply({
        period: 'custom',
        customFrom: seed.dateFrom.slice(0, 10),
        customTo: seed.dateTo.slice(0, 10),
      });
    } else {
      apply({ period: next });
    }
  }
  const currency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);
  // El toggle "Incluir deuda en el patrimonio neto" (menú de divisa del
  // header): ON → patrimonio = activos − pasivos; OFF → sólo activos (la deuda
  // no resta del neto). Es la palanca para ver el patrimonio "de caja".
  const includeDebt = useCurrencyStore((s) => s.includeDebtInNetWorth);
  const targetCurrency = convertAll ? currency : undefined;

  const { dateFrom, dateTo } = useMemo(
    () =>
      period === 'custom' && customFrom && customTo
        ? boundsForCustomRange(customFrom, customTo)
        : boundsForAnchor(period === 'custom' ? 'year' : period, anchorMonth),
    [period, anchorMonth, customFrom, customTo],
  );
  // Para las series por-mes usamos el año del rango custom (su inicio).
  const anchorYear = Number(
    (period === 'custom' && customFrom ? customFrom : anchorMonth).slice(0, 4),
  );

  const summaryParams = convertAll
    ? { target_currency: currency, date_from: dateFrom, date_to: dateTo }
    : { currency, date_from: dateFrom, date_to: dateTo };
  // PHASE-41 — en custom, el chart mensual se acota al rango (bordes parciales)
  // para que las barras cuadren con los KPIs de flujo; en mes/año, por año.
  const monthlyParams =
    period === 'custom'
      ? convertAll
        ? { target_currency: currency, date_from: dateFrom, date_to: dateTo }
        : { currency, date_from: dateFrom, date_to: dateTo }
      : convertAll
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
  // PHASE-41 — patrimonio A FECHA de fin del período elegido + Δ durante el
  // rango, para que el valor y el Δ reflejen el período (incluido el rango
  // libre) y no una foto de hoy. Mono-divisa (divisa de referencia).
  const positionAsOfQuery = usePositionAsOf(dateFrom, dateTo);
  const debtQuery = useDebtHealth(targetCurrency ? { targetCurrency } : {});

  const summary = summaryQuery.data;
  const monthly = monthlyQuery.data ?? [];
  const expensesByCategory = expensesByCategoryQuery.data ?? [];
  const unconvertible = summary?.unconvertible_count ?? 0;
  const balances = balancesQuery.data;
  const position = positionQuery.data;
  const positionAsOf = positionAsOfQuery.data;
  const debt = debtQuery.data;
  const refCurrency = summary?.currency ?? currency;

  // ── Tiles del strip ──────────────────────────────────────────────────
  // El patrimonio (valor + Δ) respeta el toggle: `net_worth` (con deuda) o
  // `total_assets` (sin deuda). PHASE-41: valor A FECHA de fin del período y Δ
  // DURANTE el rango (foto del período, no de hoy). Fallback a la foto actual
  // (`balances`) mientras carga. El sparkline sigue siendo la serie de 12
  // meses como contexto de tendencia (decorativo, no acotado al rango).
  const worthKey = includeDebt ? 'net_worth' : 'total_assets';
  const deltaKey = includeDebt ? 'delta_net_worth' : 'delta_assets';
  const netWorth = positionAsOf
    ? positionAsOf[worthKey]
    : balances
      ? balances[worthKey]
      : null;
  const worthSeries = (position?.points ?? []).map((p) => Number(p[worthKey]));
  const deltaPeriod = positionAsOf
    ? Number(positionAsOf[deltaKey])
    : worthSeries.length >= 2
      ? worthSeries[worthSeries.length - 1]! - worthSeries[0]!
      : null;
  // Base del % = patrimonio al INICIO del rango ≈ valor a fecha − Δ del rango.
  const worthStart =
    positionAsOf && netWorth != null && deltaPeriod != null
      ? Number(netWorth) - deltaPeriod
      : worthSeries.length >= 2
        ? worthSeries[0]!
        : null;
  const deltaPeriodPct =
    deltaPeriod != null && worthStart != null && worthStart !== 0
      ? (deltaPeriod / Math.abs(worthStart)) * 100
      : null;
  const sparkValues = worthSeries;
  // El patrimonio a fecha es mono-divisa (referencia); etiqueta el valor con SU
  // divisa para que no se muestre un importe en referencia rotulado en target.
  const worthCurrency = positionAsOf?.reference_currency ?? refCurrency;
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
          onRangeChange={handleRangeChange}
          anchor={anchorMonth}
          onAnchorChange={(a) => apply({ anchor: a })}
          availableFrom={summary?.available_from ?? null}
          availableTo={summary?.available_to ?? null}
          allowCustom
          customFrom={customFrom}
          customTo={customTo}
          onCustomRangeChange={(from, to) => apply({ customFrom: from, customTo: to })}
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
            value={netWorth != null ? formatAmount(netWorth, worthCurrency) : '—'}
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
            value={deltaPeriod != null ? fmtSignedAmount(deltaPeriod, worthCurrency) : '—'}
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
          {...(customFrom ? { customFrom } : {})}
          {...(customTo ? { customTo } : {})}
          onSelectMonth={(month) => apply({ period: 'month', anchor: month })}
        />
        <NetworthEvolutionCard
          points={position?.points ?? []}
          currency={position?.reference_currency ?? refCurrency}
          isLoading={positionQuery.isLoading}
          includeDebt={includeDebt}
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
          filter={filter}
          onFilterChange={(f) => apply({ filter: f })}
          backQuery={analysisQuery(period, anchorMonth, filter, customFrom, customTo)}
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
