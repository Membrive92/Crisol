'use client';

import type { Category, CategoryKind, Transaction } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatDate,
} from '@crisol/ui';

import { Button } from '@/components/ui/button';
import { CategoryChip } from '@/components/ui/category-chip';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';

export interface TrashListProps {
  items: Transaction[];
  categories: Category[];
  onRestore: (id: string) => void;
  onPurge: (id: string) => void;
  busyId?: string | null;
}

interface TrashRow {
  tx: Transaction;
  category: Category | undefined;
}

function findCategory(categories: Category[], id: string | null): Category | undefined {
  if (!id) return undefined;
  return categories.find((c) => c.id === id);
}

function amountColorFor(kind: CategoryKind | null | undefined): string {
  if (kind === 'income') return colors.income;
  if (kind === 'expense') return colors.expense;
  return colors.text;
}

function relativeDeleted(deletedAt: string | null): string {
  if (!deletedAt) return '';
  const ms = Date.now() - new Date(deletedAt).getTime();
  const minutes = Math.floor(ms / 60_000);
  if (minutes < 1) return 'hace segundos';
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  const days = Math.floor(hours / 24);
  return `hace ${days} ${days === 1 ? 'día' : 'días'}`;
}

export function TrashList({
  items,
  categories,
  onRestore,
  onPurge,
  busyId,
}: TrashListProps) {
  const rows: TrashRow[] = items.map((tx) => ({
    tx,
    category: findCategory(categories, tx.category_id),
  }));

  const columns: DataTableColumn<TrashRow>[] = [
    {
      key: 'date',
      header: 'Fecha',
      width: 110,
      render: ({ tx }) => (
        <span style={{ fontSize: fontSize.sm, color: colors.text, whiteSpace: 'nowrap' }}>
          {formatDate(tx.occurred_at)}
        </span>
      ),
    },
    {
      key: 'category',
      header: 'Categoría',
      render: ({ category }) => (
        <CategoryChip
          label={category?.name ?? 'Sin categoría'}
          kind={category?.kind ?? null}
          color={category?.color ?? null}
          icon={category?.icon ?? null}
        />
      ),
    },
    {
      key: 'description',
      header: 'Descripción',
      render: ({ tx }) => (
        <span
          style={{
            fontSize: fontSize.sm,
            fontWeight: fontWeight.medium,
            color: tx.description ? colors.text : colors.textSubtle,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            display: 'inline-block',
            maxWidth: 280,
          }}
        >
          {tx.description ?? '(sin descripción)'}
        </span>
      ),
    },
    {
      key: 'deleted_at',
      header: 'Borrada',
      width: 120,
      render: ({ tx }) => (
        <span style={{ fontSize: fontSize.xs, color: colors.textMuted, whiteSpace: 'nowrap' }}>
          {relativeDeleted(tx.deleted_at)}
        </span>
      ),
    },
    {
      key: 'amount',
      header: 'Importe',
      align: 'right',
      width: 140,
      render: ({ tx, category }) => (
        <span
          style={{
            fontSize: fontSize.sm,
            fontWeight: fontWeight.semibold,
            color: amountColorFor(category?.kind),
            fontVariantNumeric: 'tabular-nums',
            whiteSpace: 'nowrap',
          }}
        >
          {formatAmount(tx.amount, tx.currency)}
        </span>
      ),
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      width: 220,
      render: ({ tx }) => (
        <span style={{ display: 'inline-flex', gap: 8 }}>
          <Button
            variant="ghost"
            onClick={() => onRestore(tx.id)}
            disabled={busyId === tx.id}
            style={{ color: colors.primary, borderColor: colors.border }}
          >
            {busyId === tx.id ? 'Restaurando…' : 'Restaurar'}
          </Button>
          <Button
            variant="ghost"
            onClick={() => onPurge(tx.id)}
            disabled={busyId === tx.id}
            style={{ color: colors.danger, borderColor: colors.border }}
          >
            Eliminar
          </Button>
        </span>
      ),
    },
  ];

  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(row) => row.tx.id}
      emptyMessage="La papelera está vacía."
    />
  );
}
