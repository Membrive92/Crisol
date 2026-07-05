'use client';

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { PositionPoint } from '@crisol/types';
import { colors, fontSize, fontWeight, formatAmount, radius, spacing } from '@crisol/ui';

import { Card } from '@/components/ui/card';

export interface NetworthEvolutionCardProps {
  points: PositionPoint[];
  currency: string;
  isLoading: boolean;
}

const SHORT_MONTHS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

interface Row {
  label: string;
  net: number;
  assets: number;
  liabilities: number;
  projection: boolean;
}

function monthLabel(iso: string): string {
  const m = Number(iso.slice(5, 7)) - 1;
  return SHORT_MONTHS[m] ?? iso.slice(0, 7);
}

/**
 * PHASE-37.2 — Evolución del patrimonio: área de neto + líneas de activos y
 * pasivos. Consume `usePositionHistory`.
 */
export function NetworthEvolutionCard({ points, currency, isLoading }: NetworthEvolutionCardProps) {
  const data: Row[] = points.map((p) => ({
    label: monthLabel(p.month),
    net: Number(p.net_worth),
    assets: Number(p.total_assets),
    liabilities: Number(p.total_liabilities),
    projection: p.is_projection,
  }));
  const empty = !isLoading && data.length < 2;

  return (
    <Card style={{ padding: spacing.lg, height: '100%' }}>
      <h3
        style={{
          margin: `0 0 ${spacing.md}px 0`,
          fontSize: fontSize.lg,
          fontWeight: fontWeight.semibold,
          color: colors.text,
        }}
      >
        Evolución del patrimonio
      </h3>

      {empty ? (
        <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>
          Necesitas al menos 2 meses con datos para la serie.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={252}>
          <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
            <defs>
              <linearGradient id="nw-fill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor={colors.primary} stopOpacity={0.22} />
                <stop offset="100%" stopColor={colors.primary} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.border} vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11, fill: colors.textMuted }}
              axisLine={{ stroke: colors.border }}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tickFormatter={(v: number) => formatCompact(v, currency)}
              tick={{ fontSize: 11, fill: colors.textMuted }}
              axisLine={false}
              tickLine={false}
              width={64}
            />
            <Tooltip
              cursor={{ stroke: colors.borderStrong }}
              content={({ active, payload }) => {
                if (!active || !payload || payload.length === 0) return null;
                const row = payload[0]?.payload as Row | undefined;
                if (!row) return null;
                return <NetworthTooltip row={row} currency={currency} />;
              }}
            />
            <Area
              type="monotone"
              dataKey="net"
              name="Patrimonio neto"
              stroke={colors.primary}
              strokeWidth={2}
              fill="url(#nw-fill)"
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="assets"
              name="Activos"
              stroke={colors.success}
              strokeWidth={1.3}
              strokeDasharray="4 3"
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="liabilities"
              name="Pasivos"
              stroke={colors.danger}
              strokeWidth={1.3}
              strokeDasharray="4 3"
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}

      <div
        style={{
          display: 'flex',
          gap: spacing.md,
          marginTop: spacing.sm,
          fontSize: fontSize.xs,
          color: colors.textMuted,
          flexWrap: 'wrap',
        }}
      >
        <Legend color={colors.primary} label="Neto" solid />
        <Legend color={colors.success} label="Activos" />
        <Legend color={colors.danger} label="Pasivos" />
      </div>
    </Card>
  );
}

function Legend({ color, label, solid = false }: { color: string; label: string; solid?: boolean }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
      <span
        aria-hidden
        style={{
          width: 14,
          height: solid ? 8 : 0,
          borderTop: solid ? 'none' : `2px dashed ${color}`,
          backgroundColor: solid ? color : 'transparent',
          borderRadius: 2,
        }}
      />
      {label}
    </span>
  );
}

function NetworthTooltip({ row, currency }: { row: Row; currency: string }) {
  return (
    <div
      style={{
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.sm,
        padding: `${spacing.xs}px ${spacing.sm}px`,
        minWidth: 170,
        boxShadow: '0 8px 24px rgba(0,0,0,0.32)',
        fontVariantNumeric: 'tabular-nums',
      }}
    >
      <div style={{ fontSize: 11, color: colors.textMuted, marginBottom: 4 }}>
        {row.label}
        {row.projection ? ' · proyección' : ''}
      </div>
      <Row2 label="Neto" value={formatAmount(String(row.net.toFixed(2)), currency)} color={colors.text} bold />
      <Row2 label="Activos" value={formatAmount(String(row.assets.toFixed(2)), currency)} color={colors.success} />
      <Row2
        label="Pasivos"
        value={formatAmount(String(row.liabilities.toFixed(2)), currency)}
        color={colors.danger}
      />
    </div>
  );
}

function Row2({ label, value, color, bold = false }: { label: string; value: string; color: string; bold?: boolean }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        gap: spacing.sm,
        fontSize: fontSize.sm,
        fontWeight: bold ? fontWeight.semibold : fontWeight.medium,
        color,
      }}
    >
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}

function formatCompact(value: number, currency: string): string {
  const symbol = currency === 'EUR' ? '€' : currency === 'USD' ? '$' : currency;
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs < 1000) return `${sign}${Math.round(abs)} ${symbol}`;
  if (abs < 1_000_000) return `${sign}${(abs / 1000).toFixed(abs < 10000 ? 1 : 0)}k ${symbol}`.replace('.', ',');
  return `${sign}${(abs / 1_000_000).toFixed(1)}M ${symbol}`.replace('.', ',');
}
