'use client';

import { useEffect, useState } from 'react';

import {
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardSummary,
  useUserCurrencies,
} from '@finanzas/services';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';
import { formatAmount } from '@finanzas/ui';

import { ComingSoonCard } from '@/components/analysis/coming-soon-card';
import { ExpenseBreakdown } from '@/components/analysis/expense-breakdown';
import { IncomeVsExpensesChart } from '@/components/analysis/income-vs-expenses-chart';
import {
  DashboardFilters,
  type DashboardFiltersValue,
} from '@/components/dashboard/dashboard-filters';
import { KpiCard } from '@/components/ui/kpi-card';

const FALLBACK_CURRENCY = 'EUR';

export default function AnalysisPage() {
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

  const summary = summaryQuery.data;
  const netCashFlow = summary ? Number(summary.balance) : 0;
  const previousNetCashFlow =
    summary?.previous_period_balance !== null && summary?.previous_period_balance !== undefined
      ? Number(summary.previous_period_balance)
      : null;
  const incomeNum = summary ? Number(summary.income) : 0;
  const savingRate = incomeNum > 0 ? (netCashFlow / incomeNum) * 100 : null;

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: spacing.lg }}>
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
          <span
            style={{
              fontSize: fontSize.xs,
              fontWeight: fontWeight.semibold,
              color: colors.primary,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Análisis financiero
          </span>
          <h1
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              fontSize: fontSize.xl,
              fontWeight: fontWeight.bold,
              color: colors.text,
              letterSpacing: '-0.01em',
            }}
          >
            Patrones e insights
          </h1>
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              color: colors.textMuted,
              fontSize: fontSize.sm,
            }}
          >
            Vista detallada de ingresos, gastos y categorías. Reusa los
            datos del dashboard con un enfoque más analítico.
          </p>
        </div>
        <DashboardFilters
          value={filters}
          onChange={setFilters}
          currencies={currenciesQuery.data}
        />
      </header>

      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        {/* Métricas principales */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1fr)',
            gap: spacing.md,
          }}
        >
          <IncomeVsExpensesChart
            data={monthlyQuery.data ?? []}
            currency={filters.currency}
            isLoading={monthlyQuery.isLoading}
          />
          <KpiCard
            label="Flujo de caja neto"
            value={summary ? formatAmount(summary.balance, filters.currency) : '—'}
            valueColor={netCashFlow >= 0 ? colors.success : colors.danger}
            footer={
              previousNetCashFlow !== null && summary ? (
                <span
                  style={{
                    fontSize: fontSize.xs,
                    color: colors.textSubtle,
                  }}
                >
                  Periodo previo:{' '}
                  {formatAmount(
                    String(previousNetCashFlow.toFixed(2)),
                    filters.currency,
                  )}
                </span>
              ) : null
            }
          />
          <KpiCard
            label="Tasa de ahorro"
            value={savingRate !== null ? `${savingRate.toFixed(1)}%` : '—'}
            valueColor={
              savingRate !== null && savingRate >= 0 ? colors.success : colors.danger
            }
            footer={
              <span style={{ fontSize: fontSize.xs, color: colors.textSubtle }}>
                Saldo / ingresos del periodo
              </span>
            }
          />
        </div>

        {/* Desglose de gastos + insights placeholder */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
            gap: spacing.md,
          }}
        >
          <ExpenseBreakdown
            items={expensesByCategoryQuery.data ?? []}
            currency={filters.currency}
            isLoading={expensesByCategoryQuery.isLoading}
          />
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
            <ComingSoonCard
              title="Smart Insights"
              description="Detección de subscripciones recurrentes, alertas de presupuesto y comparativas mes a mes con explicación natural."
            />
            <ComingSoonCard
              title="Comparación con grupos"
              description="Tu gasto promedio comparado con usuarios con perfil similar. 100% local — no se envían datos a servidores externos."
            />
          </div>
        </div>

        {/* Recurring + Vault placeholders */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
            gap: spacing.md,
          }}
        >
          <ComingSoonCard
            title="Subscripciones recurrentes"
            description="Identifica cargos periódicos (streaming, gimnasio, hosting…) para que decidas si los mantienes o los cortas."
          />
          <ComingSoonCard
            title="Vault de presupuestos"
            description="Crea presupuestos por categoría con alerta cuando te acercas al límite. Pendiente de modelo de datos."
          />
        </div>
      </div>
    </div>
  );
}

