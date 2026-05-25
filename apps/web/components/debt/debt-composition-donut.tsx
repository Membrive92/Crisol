'use client';

import { useState } from 'react';
import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts';

import type { DebtTypeBreakdown, DebtTypeBucket } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  spacing,
} from '@crisol/ui';

import { Card } from '@/components/ui/card';

const TYPE_LABEL: Record<DebtTypeBucket, string> = {
  mortgage: 'Hipoteca',
  loan: 'Préstamo',
  credit_card: 'Tarjeta',
  other: 'Otros',
};

const TYPE_COLOR: Record<DebtTypeBucket, string> = {
  mortgage: colors.primary,
  loan: colors.warning,
  credit_card: colors.danger,
  other: colors.borderStrong,
};

export interface DebtCompositionDonutProps {
  items: DebtTypeBreakdown[];
  total: string;
  currency: string;
  isLoading: boolean;
}

/**
 * PHASE-30.3 — Donut de composición de la deuda por tipo (hipoteca,
 * préstamo, tarjeta, otros). Centro muestra el total cuando no hay
 * hover; al pasar por encima muestra el tipo activo + su importe.
 */
export function DebtCompositionDonut({
  items,
  total,
  currency,
  isLoading,
}: DebtCompositionDonutProps) {
  const [activeType, setActiveType] = useState<DebtTypeBucket | null>(null);
  const empty = !isLoading && items.length === 0;
  const active = activeType
    ? items.find((i) => i.type === activeType) ?? null
    : null;

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
      <header>
        <h2
          style={{
            margin: 0,
            fontSize: fontSize.md,
            fontWeight: fontWeight.semibold,
            color: colors.text,
            letterSpacing: '-0.01em',
          }}
        >
          Composición de la deuda
        </h2>
      </header>

      {empty ? (
        <p
          style={{
            margin: 0,
            color: colors.textMuted,
            fontSize: fontSize.sm,
          }}
        >
          Sin pagos categorizados como deuda. El donut aparece cuando
          haya datos en el rango.
        </p>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '180px 1fr',
            gap: spacing.md,
            alignItems: 'center',
          }}
        >
          <div style={{ position: 'relative', height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={items}
                  dataKey={(d) => Number((d as DebtTypeBreakdown).amount)}
                  innerRadius={55}
                  outerRadius={80}
                  stroke="none"
                  isAnimationActive={false}
                  onMouseEnter={(_, idx) => {
                    const item = items[idx];
                    setActiveType(item?.type ?? null);
                  }}
                  onMouseLeave={() => setActiveType(null)}
                >
                  {items.map((it) => (
                    <Cell
                      key={it.type}
                      fill={TYPE_COLOR[it.type]}
                      opacity={
                        activeType === null || activeType === it.type ? 1 : 0.35
                      }
                    />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div
              aria-hidden
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
                pointerEvents: 'none',
              }}
            >
              <span
                style={{
                  fontSize: 10,
                  color: colors.textMuted,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                }}
              >
                {active ? TYPE_LABEL[active.type] : 'Total'}
              </span>
              <span
                style={{
                  fontSize: fontSize.md,
                  fontWeight: fontWeight.bold,
                  color: colors.text,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {formatAmount(active ? active.amount : total, currency)}
              </span>
              {active ? (
                <span
                  style={{
                    fontSize: 10,
                    color: colors.textMuted,
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {Math.round(active.percent * 100)}%
                </span>
              ) : null}
            </div>
          </div>

          <ul
            style={{
              margin: 0,
              padding: 0,
              listStyle: 'none',
              display: 'flex',
              flexDirection: 'column',
              gap: spacing.xs,
            }}
          >
            {items.map((it) => (
              <li
                key={it.type}
                onMouseEnter={() => setActiveType(it.type)}
                onMouseLeave={() => setActiveType(null)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: spacing.sm,
                  fontSize: fontSize.sm,
                  color: colors.text,
                  cursor: 'default',
                }}
              >
                <span
                  aria-hidden
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 999,
                    backgroundColor: TYPE_COLOR[it.type],
                  }}
                />
                <span style={{ flex: 1 }}>{TYPE_LABEL[it.type]}</span>
                <span
                  style={{
                    fontVariantNumeric: 'tabular-nums',
                    fontWeight: fontWeight.semibold,
                  }}
                >
                  {formatAmount(it.amount, currency)}
                </span>
                <span
                  style={{
                    fontVariantNumeric: 'tabular-nums',
                    color: colors.textMuted,
                    fontSize: fontSize.xs,
                    minWidth: 36,
                    textAlign: 'right',
                  }}
                >
                  {Math.round(it.percent * 100)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
