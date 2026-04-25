'use client';

import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';
import { formatAmount } from '@finanzas/ui';
import type { DashboardSummary } from '@finanzas/types';

import { Card } from '@/components/ui/card';

export interface KpiCardsProps {
  summary: DashboardSummary | undefined;
  isLoading: boolean;
}

export function KpiCards({ summary, isLoading }: KpiCardsProps) {
  const currency = summary?.currency ?? 'USD';
  const balance = summary ? Number(summary.balance) : 0;
  const balanceColor = balance >= 0 ? colors.income : colors.expense;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: spacing.md,
        marginBottom: spacing.lg,
      }}
    >
      <Kpi
        label="Balance"
        value={summary ? formatAmount(summary.balance, currency) : '—'}
        valueColor={summary ? balanceColor : colors.text}
        loading={isLoading}
      />
      <Kpi
        label="Ingresos"
        value={summary ? formatAmount(summary.income, currency) : '—'}
        valueColor={colors.income}
        loading={isLoading}
      />
      <Kpi
        label="Gastos"
        value={summary ? formatAmount(summary.expenses, currency) : '—'}
        valueColor={colors.expense}
        loading={isLoading}
      />
      <Kpi
        label="Movimientos"
        value={summary ? String(summary.transaction_count) : '—'}
        valueColor={colors.text}
        loading={isLoading}
      />
    </div>
  );
}

function Kpi({
  label,
  value,
  valueColor,
  loading,
}: {
  label: string;
  value: string;
  valueColor: string;
  loading: boolean;
}) {
  return (
    <Card>
      <p
        style={{
          margin: 0,
          fontSize: fontSize.xs,
          fontWeight: fontWeight.medium,
          color: colors.textMuted,
          textTransform: 'uppercase',
          letterSpacing: 0.5,
        }}
      >
        {label}
      </p>
      <p
        style={{
          margin: `${spacing.xs}px 0 0`,
          fontSize: fontSize.xl,
          fontWeight: fontWeight.bold,
          color: loading ? colors.textSubtle : valueColor,
        }}
      >
        {loading ? '…' : value}
      </p>
    </Card>
  );
}
