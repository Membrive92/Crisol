'use client';

import { useState } from 'react';

import type { MonthlyBucket } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';
import { formatAmount } from '@finanzas/ui';

import { Card } from '@/components/ui/card';

const SPANISH_MONTHS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

type RangeKey = '6M' | '1Y' | 'ALL';

export interface StitchBalanceChartProps {
  data: MonthlyBucket[];
  currency: string;
  isLoading: boolean;
}

/**
 * Bar chart denso al estilo Stitch. Sin recharts: 12 divs verticales
 * con altura proporcional al balance del mes. La barra correspondiente
 * al mes actual se pinta con el primario sólido; el resto en
 * primary-soft. Toggle 6M / 1Y / ALL filtra el rango de meses.
 */
export function StitchBalanceChart({ data, currency, isLoading }: StitchBalanceChartProps) {
  const [range, setRange] = useState<RangeKey>('1Y');

  const monthsToShow = range === '6M' ? 6 : 12;
  const filtered = data.slice(-monthsToShow);
  const currentMonth = new Date().getMonth(); // 0..11
  const currentMonthLabel = SPANISH_MONTHS[currentMonth];

  // El "balance" puede ser negativo — para alturas trabajamos con
  // el valor absoluto y lo proporcional al máximo absoluto. Si todo es
  // 0, las barras se ven como 4% para que se intuya el contenedor.
  const absMax = Math.max(...filtered.map((b) => Math.abs(Number(b.balance))), 1);

  const empty = !isLoading && filtered.every((b) => Number(b.balance) === 0);

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
            Saldo neto por mes ({range === '6M' ? 'últimos 6 meses' : range === '1Y' ? 'año actual' : 'todo el histórico'})
          </p>
        </div>
        <RangeToggle value={range} onChange={setRange} />
      </header>

      {empty ? (
        <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>
          Sin datos en el periodo.
        </p>
      ) : (
        <>
          <div
            style={{
              position: 'relative',
              height: 220,
              width: '100%',
              display: 'flex',
              alignItems: 'flex-end',
              gap: 8,
              paddingLeft: 8,
              paddingRight: 8,
              borderBottom: `1px solid ${colors.border}`,
              borderLeft: `1px solid ${colors.border}`,
            }}
          >
            {filtered.map((bucket, idx) => {
              const value = Number(bucket.balance);
              const heightPct = (Math.abs(value) / absMax) * 100;
              const isActive = SPANISH_MONTHS[currentMonth] === SPANISH_MONTHS[(currentMonth - (monthsToShow - 1) + idx + 12) % 12];
              return (
                <Bar
                  key={bucket.month}
                  heightPct={Math.max(heightPct, 4)}
                  isActive={isActive}
                  isNegative={value < 0}
                  tooltip={formatAmount(bucket.balance, currency)}
                />
              );
            })}
          </div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              padding: `${spacing.sm}px ${spacing.sm}px 0`,
            }}
          >
            {filtered.map((bucket, idx) => {
              const monthIdx = parseInt(bucket.month.slice(5, 7), 10) - 1;
              const label = SPANISH_MONTHS[monthIdx] ?? bucket.month;
              const isActive = label === currentMonthLabel && idx === filtered.length - 1;
              return (
                <span
                  key={bucket.month}
                  style={{
                    flex: 1,
                    textAlign: 'center',
                    fontSize: fontSize.xs,
                    fontWeight: isActive ? fontWeight.semibold : fontWeight.medium,
                    color: isActive ? colors.primary : colors.textSubtle,
                  }}
                >
                  {label}
                </span>
              );
            })}
          </div>
        </>
      )}
    </Card>
  );
}

function Bar({
  heightPct,
  isActive,
  isNegative,
  tooltip,
}: {
  heightPct: number;
  isActive: boolean;
  isNegative: boolean;
  tooltip: string;
}) {
  const [hovered, setHovered] = useState(false);
  const baseColor = isActive ? colors.primary : colors.primarySoft;
  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        flex: 1,
        height: `${heightPct}%`,
        backgroundColor: hovered ? colors.primary : baseColor,
        opacity: isNegative ? 0.7 : 1,
        borderTopLeftRadius: 4,
        borderTopRightRadius: 4,
        position: 'relative',
        cursor: 'pointer',
        transition: 'background-color 120ms ease',
      }}
      title={tooltip}
    >
      {hovered ? (
        <span
          style={{
            position: 'absolute',
            top: -28,
            left: '50%',
            transform: 'translateX(-50%)',
            fontSize: 11,
            fontWeight: fontWeight.semibold,
            color: colors.text,
            backgroundColor: colors.surface,
            border: `1px solid ${colors.border}`,
            padding: '4px 8px',
            borderRadius: radius.sm,
            whiteSpace: 'nowrap',
            pointerEvents: 'none',
          }}
        >
          {tooltip}
        </span>
      ) : null}
    </div>
  );
}

function RangeToggle({
  value,
  onChange,
}: {
  value: RangeKey;
  onChange: (next: RangeKey) => void;
}) {
  return (
    <div
      style={{
        display: 'inline-flex',
        backgroundColor: colors.surfaceMuted,
        padding: 2,
        borderRadius: radius.md,
        border: `1px solid ${colors.border}`,
      }}
    >
      {(['6M', '1Y', 'ALL'] as RangeKey[]).map((opt) => {
        const active = opt === value;
        return (
          <button
            key={opt}
            type="button"
            onClick={() => onChange(opt)}
            style={{
              padding: `4px 10px`,
              backgroundColor: active ? colors.surface : 'transparent',
              color: active ? colors.text : colors.textMuted,
              border: active ? `1px solid ${colors.border}` : '1px solid transparent',
              borderRadius: radius.sm,
              fontSize: 11,
              fontWeight: fontWeight.semibold,
              cursor: 'pointer',
              letterSpacing: '0.04em',
              minWidth: 36,
            }}
          >
            {opt}
          </button>
        );
      })}
    </div>
  );
}
