'use client';

import { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { MonthlyBucket } from '@crisol/types';
import { colors, fontSize, fontWeight, formatAmount, radius, spacing } from '@crisol/ui';

import { Card } from '@/components/ui/card';

const SPANISH_MONTHS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

export interface StitchBalanceChartProps {
  /** Buckets mensuales YA acotados al periodo navegado por el caller (el
   * dashboard filtra por rango). El chart sólo los pinta. */
  data: MonthlyBucket[];
  currency: string;
  isLoading: boolean;
}

interface ChartRow {
  month: string;
  monthLabel: string;
  balance: number;
  isCurrent: boolean;
}

/**
 * Bar chart de evolución del balance — Recharts (PHASE-18.1). Eje Y
 * compacto con ticks formateados, tooltip nativo, mes actual
 * resaltado en `colors.primary` (resto en `primarySoft`). Toggle
 * 6M/1Y/ALL filtra el rango.
 */
export function StitchBalanceChart({ data, currency, isLoading }: StitchBalanceChartProps) {
  const currentMonthIso = useMemo(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  }, []);

  const chartData: ChartRow[] = data.map((b) => {
    const monthIdx = parseInt(b.month.slice(5, 7), 10) - 1;
    return {
      month: b.month,
      monthLabel: SPANISH_MONTHS[monthIdx] ?? b.month,
      balance: Number(b.balance),
      isCurrent: b.month === currentMonthIso,
    };
  });

  const empty = !isLoading && data.every((b) => Number(b.balance) === 0);

  return (
    <Card style={{ padding: spacing.lg, display: 'flex', flexDirection: 'column' }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: spacing.md,
          marginBottom: spacing.lg,
        }}
      >
        <div>
          <h2
            style={{
              margin: 0,
              fontSize: fontSize.lg,
              fontWeight: fontWeight.semibold,
              color: colors.text,
            }}
          >
            Evolución del balance
          </h2>
          <p style={{ margin: 0, marginTop: 4, fontSize: fontSize.xs, color: colors.textMuted }}>
            Saldo neto por mes del periodo seleccionado
          </p>
        </div>
      </header>

      {empty ? (
        <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>
          Sin datos en el periodo.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart
            data={chartData}
            margin={{ top: 12, right: 8, bottom: 0, left: 8 }}
            barCategoryGap={chartData.length <= 6 ? '25%' : '12%'}
          >
            <CartesianGrid strokeDasharray="3 3" stroke={colors.border} vertical={false} />
            <XAxis
              dataKey="monthLabel"
              tick={(props) => <MonthTick {...props} chartData={chartData} />}
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
            <ReferenceLine y={0} stroke={colors.border} />
            <Tooltip
              cursor={{ fill: colors.surfaceMuted, opacity: 0.6 }}
              content={({ active, payload }) => {
                if (!active || !payload || payload.length === 0) return null;
                const row = payload[0]?.payload as ChartRow | undefined;
                if (!row) return null;
                return <BalanceTooltip row={row} currency={currency} />;
              }}
              animationDuration={120}
            />
            <Bar dataKey="balance" radius={[4, 4, 0, 0]} animationDuration={400}>
              {chartData.map((d) => (
                <Cell
                  key={d.month}
                  fill={d.isCurrent ? colors.primary : colors.primarySoft}
                  fillOpacity={d.balance < 0 ? 0.7 : 1}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}

interface MonthTickProps {
  x?: string | number | undefined;
  y?: string | number | undefined;
  payload?: { value: string } | undefined;
  chartData: ChartRow[];
  [key: string]: unknown;
}

function MonthTick({ x, y, payload, chartData }: MonthTickProps) {
  if (typeof x !== 'number' || typeof y !== 'number' || !payload) return null;
  const row = chartData.find((r) => r.monthLabel === payload.value);
  const isActive = row?.isCurrent ?? false;
  return (
    <text
      x={x}
      y={y + 14}
      textAnchor="middle"
      fontSize={11}
      fontWeight={isActive ? 600 : 500}
      fill={isActive ? colors.primary : colors.textSubtle}
    >
      {payload.value}
    </text>
  );
}

function BalanceTooltip({ row, currency }: { row: ChartRow; currency: string }) {
  return (
    <div
      style={{
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.sm,
        padding: `${spacing.xs}px ${spacing.sm}px`,
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.32)',
      }}
    >
      <div style={{ fontSize: 11, color: colors.textMuted, marginBottom: 2 }}>
        {row.monthLabel}
      </div>
      <div
        style={{
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          color: row.balance < 0 ? colors.danger : colors.text,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {formatAmount(String(row.balance.toFixed(2)), currency)}
      </div>
    </div>
  );
}

/**
 * Formato compacto para ticks del eje Y: `1,2k €`, `1,5M €`. Evita
 * los `1.234,56 €` largos del default que rompen el layout de un
 * eje vertical estrecho.
 */
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
