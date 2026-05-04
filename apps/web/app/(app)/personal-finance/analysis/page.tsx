'use client';

import { useMemo, useState } from 'react';

import {
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardSummary,
} from '@finanzas/services';
import { useCurrencyStore } from '@finanzas/store';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { StitchExpenseBreakdown } from '@/components/analysis/stitch-expense-breakdown';
import { StitchIncomeVsExpenses } from '@/components/analysis/stitch-income-vs-expenses';
import { StitchKeyMetrics } from '@/components/analysis/stitch-key-metrics';
import {
  StitchPeriodToggle,
  rangeForPeriod,
  type PeriodKey,
} from '@/components/analysis/stitch-period-toggle';
import { StitchSmartInsights } from '@/components/analysis/stitch-smart-insights';
import { Card } from '@/components/ui/card';
import { ListIcon } from '@/components/ui/icons';

export default function AnalysisPage() {
  const [period, setPeriod] = useState<PeriodKey>('year');
  const currency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);

  const { dateFrom, dateTo } = useMemo(() => rangeForPeriod(period), [period]);
  const currentYear = new Date().getFullYear();

  // PHASE-8.3: una petición por endpoint con `target_currency` cuando el
  // toggle global está ON; el backend convierte cada transacción con la
  // tasa de su día. Con toggle OFF, comportamiento legacy filtrado por
  // moneda activa sin conversión.
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
  const expensesByCategory = expensesByCategoryQuery.data ?? [];
  const unconvertible = summary?.unconvertible_count ?? 0;

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
        <StitchPeriodToggle value={period} onChange={setPeriod} />
      </header>

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
        />
        <StitchKeyMetrics summary={summary} currency={currency} />
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
