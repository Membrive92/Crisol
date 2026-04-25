'use client';

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { MonthlyBucket } from '@finanzas/types';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';
import { formatAmount, formatMonthLabel } from '@finanzas/ui';

import { Card } from '@/components/ui/card';

export interface MonthlyChartProps {
  data: MonthlyBucket[] | undefined;
  currency: string;
  isLoading: boolean;
}

interface ChartDatum {
  month: string;
  label: string;
  income: number;
  expenses: number;
}

export function MonthlyChart({ data, currency, isLoading }: MonthlyChartProps) {
  const chartData: ChartDatum[] = (data ?? []).map((bucket) => ({
    month: bucket.month,
    label: formatMonthLabel(bucket.month).replace(/\s\d{4}$/, ''),
    income: Number(bucket.income),
    expenses: Number(bucket.expenses),
  }));

  return (
    <Card>
      <h2
        style={{
          margin: 0,
          fontSize: fontSize.md,
          fontWeight: fontWeight.semibold,
          color: colors.text,
          marginBottom: spacing.md,
        }}
      >
        Evolución mensual
      </h2>
      {isLoading && !data ? (
        <p style={{ color: colors.textMuted, margin: 0 }}>Cargando…</p>
      ) : (
        <div style={{ width: '100%', height: 280 }}>
          <ResponsiveContainer>
            <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={colors.border} vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 12, fill: colors.textMuted }} />
              <YAxis tick={{ fontSize: 12, fill: colors.textMuted }} width={64} />
              <Tooltip
                formatter={(value) => formatAmount(String(value ?? 0), currency)}
                labelStyle={{ color: colors.text }}
                contentStyle={{
                  backgroundColor: colors.surface,
                  border: `1px solid ${colors.border}`,
                  borderRadius: 6,
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="income" name="Ingresos" fill={colors.income} radius={[4, 4, 0, 0]} />
              <Bar dataKey="expenses" name="Gastos" fill={colors.expense} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}
