'use client';

import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { MonthlyDebtPoint } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

import { Card } from '@/components/ui/card';

const SPANISH_MONTHS = [
  'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
  'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic',
];

export interface DebtMonthlyEvolutionProps {
  items: MonthlyDebtPoint[];
  currency: string;
  isLoading: boolean;
}

interface ChartRow {
  month: string;
  monthLabel: string;
  capital: number;
  interests: number;
  isCurrent: boolean;
}

/**
 * PHASE-30.3 — Bar chart apilado de la evolución mensual de pagos a
 * deuda (capital + intereses). Muestra exactamente los meses que el
 * backend devuelve (12 para `12m`, ytd para YTD, 1 para month). El
 * mes actual queda resaltado con un `ReferenceLine` vertical para
 * que el usuario lo identifique de un vistazo.
 */
export function DebtMonthlyEvolution({
  items,
  currency,
  isLoading,
}: DebtMonthlyEvolutionProps) {
  const now = new Date();
  const currentMonthKey = `${now.getFullYear().toString().padStart(4, '0')}-${(now.getMonth() + 1).toString().padStart(2, '0')}`;
  const data: ChartRow[] = items.map((p) => {
    const [year, month] = p.month.split('-').map((s) => Number.parseInt(s, 10));
    const monthIdx = (month ?? 1) - 1;
    const monthName = SPANISH_MONTHS[monthIdx] ?? '?';
    return {
      month: p.month,
      monthLabel:
        year === now.getFullYear()
          ? monthName
          : `${monthName} ${String(year).slice(-2)}`,
      capital: Number(p.capital),
      interests: Number(p.interests),
      isCurrent: p.month === currentMonthKey,
    };
  });
  const empty = !isLoading && data.every((r) => r.capital + r.interests === 0);

  return (
    <Card
      style={{
        padding: spacing.lg,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.md,
        minHeight: 280,
      }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: spacing.sm,
          flexWrap: 'wrap',
        }}
      >
        <h2
          style={{
            margin: 0,
            fontSize: fontSize.md,
            fontWeight: fontWeight.semibold,
            color: colors.text,
            letterSpacing: '-0.01em',
          }}
        >
          Evolución mensual
        </h2>
        <Legend />
      </header>

      {empty ? (
        <p
          style={{
            margin: 0,
            color: colors.textMuted,
            fontSize: fontSize.sm,
          }}
        >
          Sin pagos a deuda en este periodo. Las barras aparecen
          conforme registres pagos.
        </p>
      ) : (
        <div style={{ width: '100%', height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.border} vertical={false} />
              <XAxis
                dataKey="monthLabel"
                tick={{ fontSize: 11, fill: colors.textMuted }}
                axisLine={{ stroke: colors.border }}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: colors.textMuted }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => {
                  if (v >= 1000) return `${(v / 1000).toFixed(0)}k`;
                  return v.toString();
                }}
                width={48}
              />
              <Tooltip
                cursor={{ fill: colors.surfaceMuted }}
                content={<MonthlyTooltip currency={currency} />}
              />
              <Bar dataKey="capital" stackId="a" fill={colors.primary} radius={[0, 0, 0, 0]} />
              <Bar dataKey="interests" stackId="a" fill={colors.danger} radius={[4, 4, 0, 0]} />
              {(() => {
                const currentLabel = data.find((r) => r.isCurrent)?.monthLabel;
                return currentLabel ? (
                  <ReferenceLine
                    x={currentLabel}
                    stroke={colors.text}
                    strokeDasharray="2 4"
                    strokeOpacity={0.4}
                  />
                ) : null;
              })()}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

function Legend() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.md,
        fontSize: fontSize.xs,
        color: colors.textMuted,
      }}
    >
      <LegendChip color={colors.primary} label="Capital" />
      <LegendChip color={colors.danger} label="Intereses" />
    </div>
  );
}

function LegendChip({ color, label }: { color: string; label: string }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: spacing.xs,
      }}
    >
      <span
        aria-hidden
        style={{
          width: 10,
          height: 10,
          borderRadius: 2,
          backgroundColor: color,
        }}
      />
      {label}
    </span>
  );
}

function MonthlyTooltip({
  active,
  payload,
  label,
  currency,
}: {
  active?: boolean;
  payload?: readonly { dataKey: string; value: number }[];
  label?: string;
  currency: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const capital = payload.find((p) => p.dataKey === 'capital')?.value ?? 0;
  const interests = payload.find((p) => p.dataKey === 'interests')?.value ?? 0;
  const total = capital + interests;
  return (
    <div
      style={{
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.sm,
        padding: spacing.sm,
        fontSize: fontSize.xs,
        boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
      }}
    >
      <strong
        style={{
          fontSize: fontSize.sm,
          color: colors.text,
          fontWeight: fontWeight.semibold,
        }}
      >
        {label}
      </strong>
      <span style={{ color: colors.textMuted }}>
        Capital ·{' '}
        <strong style={{ color: colors.text, fontVariantNumeric: 'tabular-nums' }}>
          {formatAmount(capital.toFixed(2), currency)}
        </strong>
      </span>
      <span style={{ color: colors.textMuted }}>
        Intereses ·{' '}
        <strong style={{ color: colors.text, fontVariantNumeric: 'tabular-nums' }}>
          {formatAmount(interests.toFixed(2), currency)}
        </strong>
      </span>
      <span style={{ color: colors.textMuted, marginTop: 2 }}>
        Total ·{' '}
        <strong style={{ color: colors.text, fontVariantNumeric: 'tabular-nums' }}>
          {formatAmount(total.toFixed(2), currency)}
        </strong>
      </span>
    </div>
  );
}
