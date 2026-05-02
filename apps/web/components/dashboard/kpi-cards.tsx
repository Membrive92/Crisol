'use client';

import { colors } from '@finanzas/ui';
import { formatAmount } from '@finanzas/ui';
import type { DashboardSummary } from '@finanzas/types';

import { KpiCard } from '@/components/ui/kpi-card';

import { KpiDelta } from './kpi-delta';

export interface KpiCardsProps {
  summary: DashboardSummary | undefined;
  isLoading: boolean;
}

/**
 * Tres KPIs principales del dashboard: Saldo, Ingresos y Gastos. Cada
 * uno con delta vs periodo previo cuando el backend lo devuelve. El
 * cuarto card ("Movimientos") se mueve al sidebar de actividad.
 */
export function KpiCards({ summary, isLoading }: KpiCardsProps) {
  const currency = summary?.currency ?? 'EUR';
  const balance = summary ? Number(summary.balance) : 0;
  const balanceColor = balance >= 0 ? colors.income : colors.expense;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 16,
      }}
    >
      <KpiCard
        label="Saldo"
        value={summary && !isLoading ? formatAmount(summary.balance, currency) : '—'}
        valueColor={summary ? balanceColor : colors.text}
        footer={
          summary ? (
            <KpiDelta
              current={Number(summary.balance)}
              previous={
                summary.previous_period_balance !== null
                  ? Number(summary.previous_period_balance)
                  : null
              }
              polarity="up=good"
            />
          ) : null
        }
      />
      <KpiCard
        label="Ingresos"
        value={summary && !isLoading ? formatAmount(summary.income, currency) : '—'}
        valueColor={colors.income}
        footer={
          summary ? (
            <KpiDelta
              current={Number(summary.income)}
              previous={
                summary.previous_period_income !== null
                  ? Number(summary.previous_period_income)
                  : null
              }
              polarity="up=good"
            />
          ) : null
        }
      />
      <KpiCard
        label="Gastos"
        value={summary && !isLoading ? formatAmount(summary.expenses, currency) : '—'}
        valueColor={colors.expense}
        footer={
          summary ? (
            <KpiDelta
              current={Number(summary.expenses)}
              previous={
                summary.previous_period_expenses !== null
                  ? Number(summary.previous_period_expenses)
                  : null
              }
              polarity="up=bad"
            />
          ) : null
        }
      />
    </div>
  );
}
