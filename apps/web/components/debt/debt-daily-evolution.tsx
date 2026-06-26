'use client';

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { DailyDebtPoint } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

import { Card } from '@/components/ui/card';

export interface DebtDailyEvolutionProps {
  items: DailyDebtPoint[];
  currency: string;
  isLoading: boolean;
  /** Etiqueta del mes mostrado (p. ej. "Abril 2024") para el subtítulo. */
  monthLabel?: string;
}

interface ChartRow {
  day: number;
  emitida: number;
  /** Negativo a propósito: baja en el eje de flujo (amortización). */
  amortizadoNeg: number;
  interest: number;
  balance: number | null;
}

/**
 * PHASE-30.9 — Evolución DIARIA del saldo de deuda dentro del mes.
 *
 * Sustituye la barra única inútil que salía con `range=month`. Combo:
 * - **Línea** (`balance`, eje izq.): saldo de deuda al cierre de cada
 *   día — sube si emites deuda (aplazas), baja si amortizas.
 * - **Barras** (eje der.): `emitida` ↑ (cargos nuevos / aplazamientos) y
 *   `amortizado` ↓ (pagos de capital). El interés se muestra en el
 *   tooltip (es un coste en cash, no mueve el principal).
 *
 * Sin cuentas-pasivo declaradas, `balance` llega `null` → no hay línea y
 * las barras muestran los pagos categorizados del mes (degradación).
 */
export function DebtDailyEvolution({
  items,
  currency,
  isLoading,
  monthLabel,
}: DebtDailyEvolutionProps) {
  const data: ChartRow[] = items.map((p) => ({
    day: p.day,
    emitida: Number(p.emitida),
    amortizadoNeg: -Number(p.amortizado),
    interest: Number(p.interest),
    balance: p.balance === null ? null : Number(p.balance),
  }));
  const hasBalance = data.some((r) => r.balance !== null);
  const empty =
    !isLoading &&
    data.every((r) => r.emitida === 0 && r.amortizadoNeg === 0 && r.interest === 0);

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
        <div>
          <h2
            style={{
              margin: 0,
              fontSize: fontSize.md,
              fontWeight: fontWeight.semibold,
              color: colors.text,
              letterSpacing: '-0.01em',
            }}
          >
            Evolución de deuda
          </h2>
          <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
            {monthLabel ? `${monthLabel} · día a día` : 'Día a día'}
          </span>
        </div>
        <Legend hasBalance={hasBalance} />
      </header>

      {empty ? (
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
          Sin movimientos de deuda este mes. Las barras y la línea aparecen
          conforme registres cargos o pagos.
        </p>
      ) : (
        <div style={{ width: '100%', height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.border} vertical={false} />
              <XAxis
                dataKey="day"
                tick={{ fontSize: 11, fill: colors.textMuted }}
                axisLine={{ stroke: colors.border }}
                tickLine={false}
                interval={4}
              />
              {/* Eje izq.: saldo (línea). Sólo se usa si hay pasivos. */}
              <YAxis
                yAxisId="bal"
                tick={{ fontSize: 11, fill: colors.textMuted }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : `${v}`)}
                width={48}
              />
              {/* Eje der.: flujo diario (barras). */}
              <YAxis
                yAxisId="flow"
                orientation="right"
                tick={{ fontSize: 11, fill: colors.textMuted }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => {
                  const a = Math.abs(v);
                  return a >= 1000 ? `${(v / 1000).toFixed(1)}k` : `${v}`;
                }}
                width={44}
              />
              <Tooltip
                cursor={{ fill: colors.surfaceMuted }}
                content={<DailyTooltip currency={currency} />}
              />
              <ReferenceLine yAxisId="flow" y={0} stroke={colors.border} />
              <Bar
                yAxisId="flow"
                dataKey="emitida"
                fill={colors.expense}
                radius={[2, 2, 0, 0]}
                maxBarSize={14}
              />
              <Bar
                yAxisId="flow"
                dataKey="amortizadoNeg"
                fill={colors.income}
                radius={[0, 0, 2, 2]}
                maxBarSize={14}
              />
              {hasBalance ? (
                <Line
                  yAxisId="bal"
                  type="monotone"
                  dataKey="balance"
                  stroke={colors.primary}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              ) : null}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

function Legend({ hasBalance }: { hasBalance: boolean }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.md,
        fontSize: fontSize.xs,
        color: colors.textMuted,
        flexWrap: 'wrap',
      }}
    >
      {hasBalance ? <LegendChip color={colors.primary} label="Saldo" line /> : null}
      <LegendChip color={colors.expense} label="Emitida ↑" />
      <LegendChip color={colors.income} label="Amortizado ↓" />
    </div>
  );
}

function LegendChip({
  color,
  label,
  line,
}: {
  color: string;
  label: string;
  line?: boolean;
}) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: spacing.xs }}>
      <span
        aria-hidden
        style={{
          width: line ? 14 : 10,
          height: line ? 2 : 10,
          borderRadius: line ? 1 : 2,
          backgroundColor: color,
        }}
      />
      {label}
    </span>
  );
}

function DailyTooltip({
  active,
  payload,
  label,
  currency,
}: {
  active?: boolean;
  payload?: readonly { payload: ChartRow }[];
  label?: number | string;
  currency: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  const amortizado = Math.abs(row.amortizadoNeg);
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
      <strong style={{ fontSize: fontSize.sm, color: colors.text }}>Día {label}</strong>
      {row.balance !== null ? (
        <Row label="Saldo" value={row.balance} currency={currency} color={colors.text} />
      ) : null}
      {row.emitida > 0 ? (
        <Row label="Emitida" value={row.emitida} currency={currency} color={colors.expense} />
      ) : null}
      {amortizado > 0 ? (
        <Row label="Amortizado" value={amortizado} currency={currency} color={colors.income} />
      ) : null}
      {row.interest > 0 ? (
        <Row label="Interés" value={row.interest} currency={currency} color={colors.danger} />
      ) : null}
    </div>
  );
}

function Row({
  label,
  value,
  currency,
  color,
}: {
  label: string;
  value: number;
  currency: string;
  color: string;
}) {
  return (
    <span style={{ color: colors.textMuted }}>
      {label} ·{' '}
      <strong style={{ color, fontVariantNumeric: 'tabular-nums' }}>
        {formatAmount(value.toFixed(2), currency)}
      </strong>
    </span>
  );
}
