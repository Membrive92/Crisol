'use client';

import type { CategoryBreakdownItem } from '@finanzas/types';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';
import { formatAmount } from '@finanzas/ui';

import { Card } from '@/components/ui/card';

export interface ExpenseBreakdownProps {
  items: CategoryBreakdownItem[];
  currency: string;
  isLoading: boolean;
  /** Cuántas categorías mostrar; el resto se agrupa en "Otros". */
  topN?: number | undefined;
}

/**
 * Desglose de gastos por categoría con barra horizontal proporcional.
 * Top N por importe; el resto va a un bucket "Otros". El total
 * mostrado a la derecha es absoluto + porcentaje sobre el total de
 * gastos del periodo.
 */
export function ExpenseBreakdown({
  items,
  currency,
  isLoading,
  topN = 6,
}: ExpenseBreakdownProps) {
  const sorted = [...items].sort((a, b) => Number(b.total) - Number(a.total));
  const total = sorted.reduce((acc, x) => acc + Number(x.total), 0);
  const top = sorted.slice(0, topN);
  const rest = sorted.slice(topN);
  const restTotal = rest.reduce((acc, x) => acc + Number(x.total), 0);
  const empty = !isLoading && total === 0;

  return (
    <Card style={{ padding: spacing.md, display: 'flex', flexDirection: 'column' }}>
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
          Desglose de gastos
        </h2>
        <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
          {top.length + (rest.length > 0 ? 1 : 0)} categorías
        </span>
      </header>

      {isLoading && items.length === 0 ? (
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
          Cargando…
        </p>
      ) : empty ? (
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
          Sin gastos en el periodo.
        </p>
      ) : (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
          {top.map((item) => (
            <BreakdownRow
              key={item.category_id ?? `_no_cat_${item.category_name}`}
              label={item.category_name}
              value={Number(item.total)}
              total={total}
              currency={currency}
            />
          ))}
          {rest.length > 0 && (
            <BreakdownRow
              label={`Otros (${rest.length})`}
              value={restTotal}
              total={total}
              currency={currency}
              muted
            />
          )}
        </ul>
      )}
    </Card>
  );
}

function BreakdownRow({
  label,
  value,
  total,
  currency,
  muted = false,
}: {
  label: string;
  value: number;
  total: number;
  currency: string;
  muted?: boolean;
}) {
  const pct = total > 0 ? (value / total) * 100 : 0;
  return (
    <li>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: spacing.sm,
          marginBottom: 6,
        }}
      >
        <span
          style={{
            fontSize: fontSize.sm,
            fontWeight: muted ? fontWeight.medium : fontWeight.semibold,
            color: muted ? colors.textMuted : colors.text,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            flex: 1,
            minWidth: 0,
          }}
        >
          {label}
        </span>
        <span
          style={{
            fontSize: fontSize.sm,
            fontWeight: fontWeight.semibold,
            color: muted ? colors.textMuted : colors.text,
            fontVariantNumeric: 'tabular-nums',
            whiteSpace: 'nowrap',
          }}
        >
          {formatAmount(String(value.toFixed(2)), currency)}
        </span>
      </div>
      <div
        style={{
          width: '100%',
          height: 6,
          backgroundColor: colors.surfaceMuted,
          borderRadius: 3,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            backgroundColor: muted ? colors.borderStrong : colors.expense,
            transition: 'width 200ms ease',
          }}
        />
      </div>
      <div
        style={{
          fontSize: fontSize.xs,
          color: colors.textMuted,
          marginTop: 2,
        }}
      >
        {pct.toFixed(1)}%
      </div>
    </li>
  );
}
