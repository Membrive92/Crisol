'use client';

import { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';

import {
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardSummary,
} from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';

import { PositionHero } from '@/components/analysis/position-hero';
import { StitchKeyMetrics } from '@/components/analysis/stitch-key-metrics';
import {
  boundsForAnchor,
  type PeriodKey,
} from '@/components/analysis/stitch-period-toggle';
import { StitchSmartInsights } from '@/components/analysis/stitch-smart-insights';
// PHASE-34 — navegador de período (granularidad + flechas ◀▶ acotadas a
// datos). Widget genérico reutilizado del módulo de deuda (PHASE-30.8).
import { PeriodNavigator } from '@/components/debt/period-navigator';
import { Card } from '@/components/ui/card';
import { ErrorState } from '@/components/ui/error-state';
import { ListIcon } from '@/components/ui/icons';
import { Skeleton } from '@/components/ui/skeleton';

// AUDIT-2026-05: las cards con recharts se cargan en un chunk aparte
// (ssr:false) para no inflar el JS inicial de la ruta. El Skeleton cubre
// el breve hueco hasta que el chunk hidrata.
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

export default function AnalysisPage() {
  const [period, setPeriod] = useState<PeriodKey>('year');
  // PHASE-34 — mes ancla `YYYY-MM` del período mostrado. Por defecto el mes
  // en curso → período actual (comportamiento previo). El `PeriodNavigator`
  // lo mueve, acotado a los meses con datos.
  const [anchorMonth, setAnchorMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });
  const currency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);

  const { dateFrom, dateTo } = useMemo(
    () => boundsForAnchor(period, anchorMonth),
    [period, anchorMonth],
  );
  // La gráfica Ingresos vs Gastos muestra los 12 meses del AÑO del período
  // navegado (no siempre el año en curso).
  const anchorYear = Number(anchorMonth.split('-')[0]);

  // PHASE-8.3: una petición por endpoint con `target_currency` cuando el
  // toggle global está ON; el backend convierte cada transacción con la
  // tasa de su día. Con toggle OFF, comportamiento legacy filtrado por
  // moneda activa sin conversión.
  const summaryParams = convertAll
    ? { target_currency: currency, date_from: dateFrom, date_to: dateTo }
    : { currency, date_from: dateFrom, date_to: dateTo };
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

  const summary = summaryQuery.data;
  const monthly = monthlyQuery.data ?? [];
  const expensesByCategory = expensesByCategoryQuery.data ?? [];
  const unconvertible = summary?.unconvertible_count ?? 0;

  const hasError =
    summaryQuery.isError ||
    monthlyQuery.isError ||
    expensesByCategoryQuery.isError;
  const isRefetching =
    summaryQuery.isFetching ||
    monthlyQuery.isFetching ||
    expensesByCategoryQuery.isFetching;
  // AUDIT-2026-07 — `placeholderData: previous` mantiene visibles las cifras
  // del período anterior mientras el nuevo fetch está en curso (o si falla).
  // Señalamos ese estado para que un fetch lento/fallido no se lea como "no
  // cambió nada" al navegar el período (los widgets period-scoped son summary
  // + desglose por categoría).
  const isShowingStale =
    summaryQuery.isPlaceholderData || expensesByCategoryQuery.isPlaceholderData;
  function retryAll() {
    void summaryQuery.refetch();
    void monthlyQuery.refetch();
    void expensesByCategoryQuery.refetch();
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: spacing.lg }}>
      {/* Eyebrow + título + toggle */}
      <header
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: spacing.md,
          flexWrap: 'wrap',
          marginBottom: spacing.xl,
        }}
      >
        <div>
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
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              color: colors.textMuted,
              fontSize: fontSize.sm,
            }}
          >
            Patrones detallados de ingresos, gastos y categorías ·
            cómputos client-side, sin enviar datos fuera de tu equipo.
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
      </header>

      {/* PHASE-34 — navegador de período: granularidad (Mes / Trimestre /
          Año) + flechas ◀▶ acotadas a los meses con datos. Gobierna las
          cifras del Análisis (summary + desglose por categoría). */}
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
          <span
            style={{
              fontSize: fontSize.xs,
              color: colors.textMuted,
              fontWeight: fontWeight.medium,
            }}
          >
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

      {/* PHASE-29.5: PositionHero fusiona BalancesCard + DebtHealthCard
          en una única card con 3 secciones (patrimonio neto, salud de
          deuda, cuentas activas). Independiente del periodo (snapshot
          actual). Las cards legacy siguen vivas en /dashboard. */}
      <div style={{ marginBottom: spacing.md }}>
        {/* AUDIT-2026-07 — rótulo explícito: este bloque es un snapshot y NO
            reacciona al navegador de período (a diferencia del resto de la
            pantalla), para eliminar la expectativa de que cambie al togglear. */}
        <span
          style={{
            display: 'block',
            fontSize: 11,
            fontWeight: fontWeight.semibold,
            color: colors.textSubtle,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            marginBottom: spacing.xs,
          }}
        >
          Posición actual · no depende del período
        </span>
        <PositionHero />
      </div>

      {/* Bento principal: chart + métricas */}
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
        <StitchKeyMetrics summary={summary} currency={currency} monthly={monthly} />
      </div>

      {/* Bento secundario: desglose + insights */}
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
        <StitchSmartInsights
          summary={summary}
          expensesByCategory={expensesByCategory}
          currency={currency}
        />
      </div>

      {/* Comparativa Peer Group — placeholder honesto */}
      <Card
        style={{
          padding: spacing.xl,
          backgroundColor: colors.surfaceMuted,
          border: `1px dashed ${colors.border}`,
          textAlign: 'center',
        }}
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: spacing.sm,
            color: colors.textSubtle,
            marginBottom: spacing.sm,
          }}
        >
          <ListIcon size={16} />
          <span
            style={{
              fontSize: 11,
              fontWeight: fontWeight.semibold,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Próximamente
          </span>
        </span>
        <h3
          style={{
            margin: 0,
            fontSize: fontSize.lg,
            fontWeight: fontWeight.semibold,
            color: colors.text,
            marginBottom: spacing.xs,
          }}
        >
          Comparación con grupos similares
        </h3>
        <p
          style={{
            margin: 0,
            fontSize: fontSize.sm,
            color: colors.textMuted,
            maxWidth: 540,
            marginLeft: 'auto',
            marginRight: 'auto',
            lineHeight: 1.5,
          }}
        >
          Tu gasto medio comparado con usuarios de perfil parecido.
          Computado 100% en local — los perfiles agregados no salen del
          equipo.
        </p>
      </Card>
    </div>
  );
}
