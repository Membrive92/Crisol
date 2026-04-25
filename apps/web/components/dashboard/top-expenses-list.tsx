'use client';

import type { TopExpenseItem } from '@finanzas/types';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';
import { formatAmount, formatDate } from '@finanzas/ui';

import { Card } from '@/components/ui/card';

export interface TopExpensesListProps {
  data: TopExpenseItem[] | undefined;
  currency: string;
  isLoading: boolean;
}

export function TopExpensesList({ data, currency, isLoading }: TopExpensesListProps) {
  const items = data ?? [];

  return (
    <Card>
      <h2
        style={{
          margin: 0,
          fontSize: fontSize.md,
          fontWeight: fontWeight.semibold,
          color: colors.text,
          marginBottom: spacing.md,
        }}
      >
        Top gastos
      </h2>
      {isLoading && !data ? (
        <p style={{ color: colors.textMuted, margin: 0 }}>Cargando…</p>
      ) : items.length === 0 ? (
        <p style={{ color: colors.textMuted, margin: 0 }}>Sin gastos en el periodo.</p>
      ) : (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
          {items.map((item) => (
            <li
              key={item.transaction_id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: `${spacing.sm}px 0`,
                borderBottom: `1px solid ${colors.border}`,
                gap: spacing.md,
              }}
            >
              <div style={{ minWidth: 0, flex: 1 }}>
                <p
                  style={{
                    margin: 0,
                    fontSize: fontSize.sm,
                    fontWeight: fontWeight.medium,
                    color: colors.text,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {item.description ?? 'Sin descripción'}
                </p>
                <p
                  style={{
                    margin: 0,
                    fontSize: fontSize.xs,
                    color: colors.textMuted,
                  }}
                >
                  {item.category_name ?? 'Sin categoría'} · {formatDate(item.occurred_at)}
                </p>
              </div>
              <span
                style={{
                  fontSize: fontSize.sm,
                  fontWeight: fontWeight.semibold,
                  color: colors.expense,
                  whiteSpace: 'nowrap',
                }}
              >
                {formatAmount(item.amount, currency)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
