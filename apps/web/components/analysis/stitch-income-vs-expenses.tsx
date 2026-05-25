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

import type { MonthlyBucket } from '@crisol/types';
import { colors, fontSize, fontWeight, formatAmount, radius, spacing } from '@crisol/ui';

import { Card } from '@/components/ui/card';

const SHORT_MONTHS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

export interface StitchIncomeVsExpensesProps {
  data: MonthlyBucket[];
  currency: string;
  isLoading: boolean;
}

interface ChartRow {
  month: string;
  monthLabel: string;
  income: number;
  expenses: number;
}

/**
 * Bar chart agrupado Ingresos vs Gastos — Recharts (PHASE-18.1).
 * Dos barras por mes lado a lado, eje Y formateado, leyenda persistente
 * y tooltip pulido.
 */
export function StitchIncomeVsExpenses({
  data,
  currency,
  isLoading,
}: StitchIncomeVsExpensesProps) {
  const chartData: ChartRow[] = data.map((b) => {
    const monthIdx = parseInt(b.month.slice(5, 7), 10) - 1;
    return {
      month: b.month,
      monthLabel: SHORT_MONTHS[monthIdx] ?? b.month,
      income: Number(b.income),
      expenses: Number(b.expenses),
    };
  });
  const empty = !isLoading && chartData.every((b) => b.income === 0 && b.expenses === 0);

  return (
    <Card style={{ padding: spacing.lg }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: spacing.lg,
        }}
      >
        <h3
          style={{
            margin: 0,
            fontSize: fontSize.lg,
            fontWeight: fontWeight.semibold,
            color: colors.text,
          }}
        >
          Ingresos vs Gastos
        </h3>
      </header>

      {empty ? (
        <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>
          Sin datos en el periodo.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart
            data={chartData}
            margin={{ top: 8, right: 8, bottom: 0, left: 8 }}
            barCategoryGap="20%"
            barGap={2}
          >
            <CartesianGrid strokeDasharray="3 3" stroke={colors.border} vertical={false} />
            <XAxis
              dataKey="monthLabel"
              tick={{ fontSize: 11, fill: colors.textMuted, fontWeight: 500 }}
              axisLine={{ stroke: colors.border }}
              tickLine={false}
              interval={0}
            />
            <YAxis
              tickFormatter={(v: number) => formatCompact(v, currency)}
              tick={{ fontSize: 11, fill: colors.textMuted }}
              axisLine={false}
              tickLine={false}
              width={64}
            />
            <Tooltip
              cursor={{ fill: colors.surfaceMuted, opacity: 0.6 }}
              content={({ active, payload }) => {
                if (!active || !payload || payload.length === 0) return null;
                const firstRow = payload[0]?.payload as ChartRow | undefined;
                if (!firstRow) return null;
                const entries = payload.map((p) => ({
                  name: typeof p.name === 'string' ? p.name : String(p.name ?? ''),
                  value: typeof p.value === 'number' ? p.value : 0,
                  color: typeof p.color === 'string' ? p.color : colors.text,
                }));
                return (
                  <ComparisonTooltip
                    monthLabel={firstRow.monthLabel}
                    entries={entries}
                    currency={currency}
                  />
                );
              }}
              animationDuration={120}
            />
            <Legend
              wrapperStyle={{
                paddingTop: spacing.sm,
                fontSize: fontSize.xs,
                color: colors.textMuted,
              }}
              iconType="circle"
              iconSize={10}
            />
            <Bar
              dataKey="income"
              name="Ingresos"
              fill={colors.success}
              radius={[3, 3, 0, 0]}
              animationDuration={400}
            />
            <Bar
              dataKey="expenses"
              name="Gastos"
              fill={colors.danger}
              radius={[3, 3, 0, 0]}
              animationDuration={400}
            />
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}

interface ComparisonTooltipProps {
  monthLabel: string;
  entries: readonly { name: string; value: number; color: string }[];
  currency: string;
}

function ComparisonTooltip({ monthLabel, entries, currency }: ComparisonTooltipProps) {
  // PHASE-29.6: añadimos línea "Neto" debajo, separada por un
  // border-top, con color según signo. Se calcula a partir de los
  // entries (income − expenses) sin asumir un orden concreto.
  const income = entries.find((e) => e.name === 'Ingresos')?.value ?? 0;
  const expenses = entries.find((e) => e.name === 'Gastos')?.value ?? 0;
  const net = income - expenses;
  return (
    <div
      style={{
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.sm,
        padding: `${spacing.xs}px ${spacing.sm}px`,
        minWidth: 160,
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.32)',
      }}
    >
      <div style={{ fontSize: 11, color: colors.textMuted, marginBottom: 4 }}>
        {monthLabel}
      </div>
      {entries.map((entry) => (
        <div
          key={entry.name || String(entry.value)}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            gap: spacing.sm,
            fontSize: fontSize.sm,
            fontWeight: fontWeight.medium,
            color: entry.color,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          <span>{entry.name}</span>
          <span>{formatAmount(String(entry.value.toFixed(2)), currency)}</span>
        </div>
      ))}
      <div
        style={{
          marginTop: 4,
          paddingTop: 4,
          borderTop: `1px solid ${colors.border}`,
          display: 'flex',
          justifyContent: 'space-between',
          gap: spacing.sm,
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          color: net >= 0 ? colors.income : colors.danger,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        <span>Neto</span>
        <span>
          {net >= 0 ? '+' : ''}
          {formatAmount(String(net.toFixed(2)), currency)}
        </span>
      </div>
    </div>
  );
}

function formatCompact(value: number, currency: string): string {
  const symbol = currency === 'EUR' ? '€' : currency === 'USD' ? '$' : currency;
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs === 0) return `0 ${symbol}`;
  if (abs < 1000) return `${sign}${Math.round(abs)} ${symbol}`;
  if (abs < 1_000_000) {
    const v = abs / 1000;
    return `${sign}${v.toFixed(v < 10 ? 1 : 0)}k ${symbol}`.replace('.', ',');
  }
  const v = abs / 1_000_000;
  return `${sign}${v.toFixed(v < 10 ? 1 : 0)}M ${symbol}`.replace('.', ',');
}
