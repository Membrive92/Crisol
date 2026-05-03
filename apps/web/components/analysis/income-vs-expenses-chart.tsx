'use client';

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import type { MonthlyBucket } from '@finanzas/types';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';
import { formatAmount } from '@finanzas/ui';

import { Card } from '@/components/ui/card';

export interface IncomeVsExpensesChartProps {
  data: MonthlyBucket[];
  currency: string;
  isLoading: boolean;
}

const MONTHS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

interface ChartRow {
  month: string;
  income: number;
  expenses: number;
}

/**
 * Bar chart con dos series por mes: ingresos y gastos. Layout vertical,
 * 12 buckets. Usa los colores semánticos `income`/`expense`.
 */
export function IncomeVsExpensesChart({
  data,
  currency,
  isLoading,
}: IncomeVsExpensesChartProps) {
  const rows: ChartRow[] = data.map((bucket, idx) => ({
    month: MONTHS[idx] ?? bucket.month,
    income: Number(bucket.income),
    expenses: Number(bucket.expenses),
  }));
  const empty = !isLoading && rows.every((r) => r.income === 0 && r.expenses === 0);

  return (
    <Card>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: spacing.md,
        }}
      >
        <h2
          style={{
            margin: 0,
            fontSize: fontSize.md,
            fontWeight: fontWeight.semibold,
            color: colors.text,
          }}
        >
          Ingresos vs Gastos
        </h2>
        <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
          12 meses · {currency}
        </span>
      </header>
      {isLoading && data.length === 0 ? (
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
          Cargando…
        </p>
      ) : empty ? (
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
          Sin datos en el periodo.
        </p>
      ) : (
        <div style={{ width: '100%', height: 280 }}>
          <ResponsiveContainer>
            <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.border} />
              <XAxis
                dataKey="month"
                tick={{ fontSize: 11, fill: colors.textMuted }}
                tickLine={false}
                axisLine={{ stroke: colors.border }}
              />
              <YAxis
                tick={{ fontSize: 11, fill: colors.textMuted }}
                tickLine={false}
                axisLine={{ stroke: colors.border }}
              />
              <Tooltip
                formatter={(value) => formatAmount(String(value ?? 0), currency)}
                contentStyle={{
                  backgroundColor: colors.surface,
                  border: `1px solid ${colors.border}`,
                  borderRadius: 6,
                  color: colors.text,
                }}
                cursor={{ fill: colors.surfaceMuted }}
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
