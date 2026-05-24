'use client';

import { useMemo } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { DebtHistoryPoint } from '@crisol/types';
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
  'Ene',
  'Feb',
  'Mar',
  'Abr',
  'May',
  'Jun',
  'Jul',
  'Ago',
  'Sep',
  'Oct',
  'Nov',
  'Dic',
];

export interface DebtTrendChartProps {
  data: DebtHistoryPoint[];
  currency: string;
  isLoading: boolean;
}

interface ChartRow {
  month: string;
  monthLabel: string;
  // Cada segmento expone su valor en su propia clave: Recharts no
  // dibuja el tramo si el valor es `null`, así que partimos la serie
  // en dos columnas y renderizamos dos `<Line>` sobre el mismo dataset.
  historicalDebt: number | null;
  projectedDebt: number | null;
  kind: 'historical' | 'projected';
}

/**
 * Chart de evolución de la deuda total (PHASE-22+).
 *
 * Renderiza dos líneas sobre el mismo dataset:
 * - **Histórico** (sólido, `colors.primary`): puntos `kind === 'historical'`.
 * - **Proyección** (discontinuo, `colors.textSubtle`): puntos
 *   `kind === 'projected'`, asumiendo cuotas constantes.
 *
 * Para que la línea sea continua en la frontera, duplicamos el último
 * punto histórico también como primer punto proyectado — si no, queda
 * un hueco visible entre los dos tramos.
 *
 * Una `ReferenceLine` vertical marca "hoy" entre el último histórico y
 * el primer proyectado.
 */
export function DebtTrendChart({ data, currency, isLoading }: DebtTrendChartProps) {
  const chartData = useMemo<ChartRow[]>(() => {
    if (data.length === 0) return [];
    // Índice del último histórico + flag de "hay proyección" para
    // decidir si soldamos los tramos. Sin proyección no soldamos —
    // si no, el último histórico quedaría duplicado como un dot
    // suelto en el estilo de proyección.
    let lastHistoricalIdx = -1;
    let hasProjection = false;
    for (let i = 0; i < data.length; i += 1) {
      const point = data[i];
      if (!point) continue;
      if (point.kind === 'historical') {
        lastHistoricalIdx = i;
      } else {
        hasProjection = true;
      }
    }

    return data.map((point, idx) => {
      const monthIdx = parseInt(point.month.slice(5, 7), 10) - 1;
      const value = Number(point.total_debt);
      const monthLabel = SPANISH_MONTHS[monthIdx] ?? point.month;
      const isHistorical = point.kind === 'historical';
      // Para soldar los tramos: el último histórico también lo
      // exponemos en la columna `projectedDebt` y así la línea
      // discontinua arranca justo donde acaba la sólida. Sólo si
      // hay proyección — si no, no queremos un dot huérfano.
      const bridgeHistoricalIntoProjection =
        hasProjection && idx === lastHistoricalIdx;
      return {
        month: point.month,
        monthLabel,
        historicalDebt: isHistorical ? value : null,
        projectedDebt:
          !isHistorical || bridgeHistoricalIntoProjection ? value : null,
        kind: point.kind,
      };
    });
  }, [data]);

  // Mes del primer punto proyectado — sirve para pintar el ReferenceLine.
  const firstProjectedMonthLabel = useMemo(() => {
    const firstProjected = chartData.find((row) => row.kind === 'projected');
    return firstProjected?.monthLabel;
  }, [chartData]);

  const empty = !isLoading && chartData.length === 0;
  const allZero =
    !isLoading &&
    chartData.length > 0 &&
    chartData.every(
      (row) =>
        (row.historicalDebt ?? 0) === 0 && (row.projectedDebt ?? 0) === 0,
    );

  return (
    <Card style={{ padding: spacing.lg, display: 'flex', flexDirection: 'column' }}>
      <header style={{ marginBottom: spacing.lg }}>
        <h2
          style={{
            margin: 0,
            fontSize: fontSize.lg,
            fontWeight: fontWeight.semibold,
            color: colors.text,
          }}
        >
          Evolución de tu deuda
        </h2>
        <p
          style={{
            margin: `${spacing.xs}px 0 0 0`,
            fontSize: fontSize.xs,
            color: colors.textMuted,
            lineHeight: 1.4,
          }}
        >
          Histórico (sólido) + proyección al ritmo actual (discontinuo). La
          proyección asume cuotas constantes y no contempla nuevos cargos.
        </p>
      </header>

      {isLoading ? (
        <ChartSkeleton />
      ) : empty || allZero ? (
        <EmptyState />
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart
            data={chartData}
            margin={{ top: 8, right: 16, bottom: 0, left: 8 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={colors.border}
              vertical={false}
            />
            <XAxis
              dataKey="monthLabel"
              tick={{ fontSize: 11, fill: colors.textMuted, fontWeight: 500 }}
              axisLine={{ stroke: colors.border }}
              tickLine={false}
              interval="preserveStartEnd"
              minTickGap={16}
            />
            <YAxis
              tickFormatter={(v: number) => formatCompact(v, currency)}
              tick={{ fontSize: 11, fill: colors.textMuted }}
              axisLine={false}
              tickLine={false}
              width={72}
            />
            {firstProjectedMonthLabel ? (
              <ReferenceLine
                x={firstProjectedMonthLabel}
                stroke={colors.borderStrong}
                strokeDasharray="2 4"
                label="Hoy"
              />
            ) : null}
            <Tooltip
              cursor={{ stroke: colors.border, strokeDasharray: '2 2' }}
              content={({ active, payload }) => {
                if (!active || !payload || payload.length === 0) return null;
                const row = payload[0]?.payload as ChartRow | undefined;
                if (!row) return null;
                return <TrendTooltip row={row} currency={currency} />;
              }}
              animationDuration={120}
            />
            <Legend
              wrapperStyle={{
                paddingTop: spacing.sm,
                fontSize: fontSize.xs,
                color: colors.textMuted,
              }}
              iconType="plainline"
              iconSize={20}
            />
            <Line
              type="monotone"
              dataKey="historicalDebt"
              name="Histórico"
              stroke={colors.primary}
              strokeWidth={2.5}
              dot={{ r: 3, fill: colors.primary, strokeWidth: 0 }}
              activeDot={{ r: 5, fill: colors.primary, strokeWidth: 0 }}
              connectNulls={false}
              animationDuration={400}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="projectedDebt"
              name="Proyección"
              stroke={colors.textSubtle}
              strokeWidth={2}
              strokeDasharray="4 4"
              dot={{ r: 2.5, fill: colors.textSubtle, strokeWidth: 0 }}
              activeDot={{ r: 4, fill: colors.textSubtle, strokeWidth: 0 }}
              connectNulls={false}
              animationDuration={400}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}

function TrendTooltip({ row, currency }: { row: ChartRow; currency: string }) {
  // Cuando una fila es bridge (último histórico expuesto también como
  // proyección), ambos campos están rellenos. Mostramos el valor
  // histórico — es el dato real.
  const numericValue = row.historicalDebt ?? row.projectedDebt ?? 0;
  const isProjection = row.kind === 'projected';
  return (
    <div
      style={{
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.sm,
        padding: `${spacing.xs}px ${spacing.sm}px`,
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.32)',
        minWidth: 140,
      }}
    >
      <div style={{ fontSize: 11, color: colors.textMuted, marginBottom: 2 }}>
        {row.monthLabel} · {isProjection ? 'Proyección' : 'Histórico'}
      </div>
      <div
        style={{
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          color: colors.text,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {formatAmount(String(numericValue.toFixed(2)), currency)}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div
      style={{
        padding: spacing.xl,
        textAlign: 'center',
        backgroundColor: colors.surfaceMuted,
        borderRadius: radius.md,
        border: `1px dashed ${colors.border}`,
      }}
    >
      <p
        style={{
          margin: 0,
          fontSize: fontSize.sm,
          color: colors.textMuted,
          lineHeight: 1.5,
        }}
      >
        Cuando añadas una cuenta de deuda con sus datos verás aquí la
        evolución histórica y la proyección.
      </p>
    </div>
  );
}

function ChartSkeleton() {
  return (
    <div
      aria-hidden
      style={{
        height: 280,
        backgroundColor: colors.surfaceMuted,
        borderRadius: radius.md,
        border: `1px dashed ${colors.border}`,
      }}
    />
  );
}

/**
 * Formato compacto para ticks del eje Y: `1,2k €`, `1,5M €`. Mismo
 * approach que stitch-balance-chart.tsx — un eje vertical estrecho no
 * tolera los `1.234,56 €` largos del default de Intl.
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
