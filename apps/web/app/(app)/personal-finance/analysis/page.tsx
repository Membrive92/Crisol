'use client';

import { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { useRouter, useSearchParams } from 'next/navigation';

import {
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardSummary,
  useExpenseStructure,
  useExpenseStructureExplain,
} from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import { colors, fontSize, fontWeight, formatAmount, layout, spacing } from '@crisol/ui';

import { KpiStrip, KpiTile } from '@/components/analysis/kpi-strip';
import {
  boundsForAnchor,
  boundsForCustomRange,
  type PeriodKey,
} from '@/components/analysis/stitch-period-toggle';
import type { StructureFilter } from '@/components/analysis/stitch-expense-breakdown';
import { StitchSmartInsights } from '@/components/analysis/stitch-smart-insights';
import { TopMovementsCard } from '@/components/analysis/top-movements-card';
import { PeriodNavigator } from '@/components/debt/period-navigator';
import { todayDayStr } from '@/components/ui/date-picker';
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
      const today = todayDayStr();
      const to = seed.dateTo.slice(0, 10);
      apply({
        period: 'custom',
        customFrom: seed.dateFrom.slice(0, 10),
        customTo: to > today ? today : to,
      });
    } else {
      apply({ period: next });
    }
  }
  const currency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);

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
  // PHASE-43.2 — explicabilidad por categoría (por qué es fija/variable). Mismo
  // rango que el desglose; alimenta el tooltip de cada fila de la leyenda.
  const explainQuery = useExpenseStructureExplain(structureParams);

  const summary = summaryQuery.data;
  const monthly = monthlyQuery.data ?? [];
  const expensesByCategory = expensesByCategoryQuery.data ?? [];
  const unconvertible = summary?.unconvertible_count ?? 0;
  const refCurrency = summary?.currency ?? currency;

  // ── Tiles del strip (PHASE-43.3: Análisis = flujos) ───────────────────
  // Dos tiles, no cinco: el patrimonio (stock) y la tasa de esfuerzo (deuda)
  // se fueron al dashboard (ADR-0006). Aquí sólo el flujo de caja del periodo
  // (con la tasa de ahorro como sub-valor) y el coste de vida estructural/mes.
  const structure = structureQuery.data;
  const cashflow = summary?.balance ?? null;
  const cashflowDelta = summary?.cashflow_delta ?? null;
  const savingsRate =
    summary && Number(summary.income) > 0
      ? (Number(summary.balance) / Number(summary.income)) * 100
      : null;
  // PHASE-37.3 — tasa de ahorro estructural (excluye gastos puntuales). Si
  // difiere >10pp de la bruta, un badge en el tile invita a fijarse.
  const savingsStructuralPct =
    structure?.savings_rate_structural != null ? structure.savings_rate_structural * 100 : null;
  const savingsDiffPp =
    savingsStructuralPct != null && savingsRate != null
      ? savingsStructuralPct - savingsRate
      : null;
  // PHASE-43.3 — coste de vida estructural mensual (nuevo tile) + aviso si la
  // ventana de recurrencia no tiene histórico suficiente para clasificar.
  const structuralMonthlyAvg = structure?.structural_monthly_avg ?? null;
  const recurrenceAvailable = structure?.recurrence_available ?? true;
  const windowMonths = structure?.window_months_with_data ?? 0;
  const topMovements = structure?.top_exceptional ?? [];

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
          Ingresos, gastos y ahorro del periodo · cómputos client-side, sin enviar datos fuera de tu equipo.
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

      {/* KPI STRIP (PHASE-43.3) — 2 tiles de FLUJO: caja neta (con tasa de
          ahorro) + coste de vida estructural/mes. Patrimonio y esfuerzo viven
          en el dashboard (ADR-0006). */}
      <div style={{ marginBottom: spacing.md }}>
        <KpiStrip>
          <KpiTile
            label="Flujo de caja neto"
            info="Ingresos menos gastos del período: lo que te sobra (+) o te falta (−). No cuenta las transferencias entre tus propias cuentas. La tasa de ahorro es ese neto sobre tus ingresos."
            value={cashflow != null ? fmtSignedAmount(cashflow, refCurrency) : '—'}
            delta={cashflowDelta != null ? Number(cashflowDelta) : null}
            deltaText={cashflowDelta != null ? fmtSignedAmount(cashflowDelta, refCurrency) : undefined}
            subtitle={
              savingsRate != null ? `Tasa de ahorro ${savingsRate.toFixed(0)} %` : 'vs periodo anterior'
            }
            badge={
              savingsDiffPp != null && Math.abs(savingsDiffPp) > 10
                ? `Fijo ${savingsStructuralPct!.toFixed(0)} %`
                : undefined
            }
            title={
              savingsStructuralPct != null
                ? `Excluyendo gastos variables (impuestos, puntuales), tu tasa de ahorro sería ${savingsStructuralPct.toFixed(0)} %.`
                : undefined
            }
          />
          <KpiTile
            label="Gasto estructural / mes"
            info="Tu coste de vida fijo mensual: gastos recurrentes (alquiler, suministros, cuotas…), excluyendo los puntuales o excepcionales. Necesita ~6 meses de historia para ser fiable."
            value={structuralMonthlyAvg != null ? formatAmount(structuralMonthlyAvg, refCurrency) : '—'}
            subtitle={
              recurrenceAvailable
                ? 'Tu coste de vida fijo, sin puntuales'
                : `Historia insuficiente (${windowMonths}/6 meses)`
            }
            status={recurrenceAvailable ? 'neutral' : 'warning'}
          />
        </KpiStrip>
      </div>

      {recurrenceAvailable ? null : (
        <div style={{ marginBottom: spacing.md }}>
          <p
            style={{
              margin: 0,
              padding: spacing.sm,
              fontSize: fontSize.xs,
              color: colors.warning,
              backgroundColor: colors.warningSoft,
              borderRadius: 8,
              lineHeight: 1.4,
            }}
          >
            ⚠ Historia insuficiente ({windowMonths}/6 meses completos): la
            clasificación fijo/variable usa sólo tus gastos fijos confirmados y
            de deuda. La tasa de ahorro estructural puede no ser representativa
            hasta acumular más histórico.
          </p>
        </div>
      )}

      {/* Fila 1: Ingresos vs Gastos — a ancho completo (Análisis es flujos). */}
      <div style={{ marginBottom: spacing.md }}>
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
      </div>

      {/* Fila 2: Desglose de gastos a ancho completo. */}
      <div style={{ marginBottom: spacing.md }}>
        <StitchExpenseBreakdown
          items={expensesByCategory}
          currency={currency}
          isLoading={expensesByCategoryQuery.isLoading}
          exceptionalByCategory={structure?.exceptional_by_category}
          explain={explainQuery.data}
          dateFrom={dateFrom}
          dateTo={dateTo}
          filter={filter}
          onFilterChange={(f) => apply({ filter: f })}
          backQuery={analysisQuery(period, anchorMonth, filter, customFrom, customTo)}
        />
      </div>

      {/* Fila 3: Top movimientos del periodo + Smart Insights. */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 340px), 1fr))',
          gap: spacing.md,
          marginBottom: spacing.md,
        }}
      >
        <TopMovementsCard
          items={topMovements}
          currency={currency}
          isLoading={structureQuery.isLoading}
        />
        <StitchSmartInsights
          summary={summary}
          expensesByCategory={expensesByCategory}
          structure={structure}
        />
      </div>
    </div>
  );
}
