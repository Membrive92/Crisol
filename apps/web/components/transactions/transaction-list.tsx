'use client';

import Link from 'next/link';

import type { Category, Transaction } from '@finanzas/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatDate,
  radius,
  spacing,
} from '@finanzas/ui';

import { Button } from '../ui/button';

export interface TransactionListProps {
  items: Transaction[];
  categories: Category[];
  onDelete: (id: string) => void;
  deletingId?: string | null;
}

function findCategory(categories: Category[], id: string | null): Category | undefined {
  if (!id) return undefined;
  return categories.find((c) => c.id === id);
}

export function TransactionList({
  items,
  categories,
  onDelete,
  deletingId,
}: TransactionListProps) {
  if (items.length === 0) {
    return (
      <div
        style={{
          padding: spacing.xl,
          textAlign: 'center',
          color: colors.textMuted,
          backgroundColor: colors.surfaceMuted,
          borderRadius: radius.md,
        }}
      >
        Sin transacciones con los filtros actuales.
      </div>
    );
  }

  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {items.map((t) => {
        const category = findCategory(categories, t.category_id);
        const isIncome = category?.kind === 'income';
        return (
          <li
            key={t.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: spacing.md,
              padding: spacing.md,
              borderBottom: `1px solid ${colors.border}`,
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: fontSize.md,
                  fontWeight: fontWeight.medium,
                  color: colors.text,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {t.description ?? '(sin descripción)'}
              </div>
              <div style={{ fontSize: fontSize.sm, color: colors.textMuted }}>
                {formatDate(t.occurred_at)} · {category?.name ?? 'Sin categoría'}
              </div>
            </div>
            <div
              style={{
                fontSize: fontSize.md,
                fontWeight: fontWeight.semibold,
                color: isIncome ? colors.income : colors.text,
                whiteSpace: 'nowrap',
              }}
            >
              {isIncome ? '+' : ''}
              {formatAmount(t.amount, t.currency)}
            </div>
            <div style={{ display: 'flex', gap: spacing.sm }}>
              <Link href={{ pathname: `/personal-finance/transactions/${t.id}` }}>
                <Button variant="secondary">Editar</Button>
              </Link>
              <Button
                variant="danger"
                onClick={() => onDelete(t.id)}
                disabled={deletingId === t.id}
              >
                {deletingId === t.id ? 'Borrando…' : 'Borrar'}
              </Button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
