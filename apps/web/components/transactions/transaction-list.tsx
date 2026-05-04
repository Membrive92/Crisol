'use client';

import { useRouter } from 'next/navigation';

import { useCurrencyStore } from '@finanzas/store';
import type { Category, CategoryKind, Transaction } from '@finanzas/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatDate,
} from '@finanzas/ui';

import { Button } from '@/components/ui/button';
import { CategoryChip } from '@/components/ui/category-chip';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';
import { OriginBadge } from '@/components/ui/origin-badge';

export interface TransactionListProps {
  items: Transaction[];
  categories: Category[];
  onDelete: (id: string) => void;
  deletingId?: string | null;
}

interface TransactionRow {
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

function amountSignFor(kind: CategoryKind | null | undefined): string {
  if (kind === 'income') return '+';
  if (kind === 'expense') return '-';
  return '';
}

export function TransactionList({
  items,
  categories,
  onDelete,
  deletingId,
}: TransactionListProps) {
  const router = useRouter();
  const activeCurrency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);

  const rows: TransactionRow[] = items.map((tx) => ({
    tx,
    category: findCategory(categories, tx.category_id),
  }));

  const columns: DataTableColumn<TransactionRow>[] = [
    {
      key: 'date',
      header: 'Fecha',
      width: 120,
      render: ({ tx }) => (
        <span
          style={{
            fontSize: fontSize.sm,
            color: colors.text,
            whiteSpace: 'nowrap',
          }}
        >
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
      key: 'origin',
      header: 'Origen',
      render: ({ tx }) => <OriginBadge source={tx.source} />,
    },
    {
      key: 'amount',
      header: 'Importe',
      align: 'right',
      width: 160,
      render: ({ tx, category }) => {
        // PHASE-8.4: el backend convierte per-row cuando el toggle
        // está ON (la página pasa `target_currency`). La fila trae
        // `converted_amount` listo, o `null` si no hay tasa para esa
        // fecha — en cuyo caso pintamos "≈ —" como señal de missing.
        const currenciesDiffer =
          tx.currency.toUpperCase() !== activeCurrency.toUpperCase();
        const showConverted = convertAll && currenciesDiffer;
        const convertedDisplay = (() => {
          if (!showConverted) return null;
          if (tx.converted_amount == null || tx.converted_currency == null) {
            return { text: '≈ —', tooltip: 'Sin tasa para esa fecha' };
          }
          return {
            text: `≈ ${formatAmount(tx.converted_amount, tx.converted_currency)}`,
            tooltip: `${tx.currency} ${formatAmount(tx.amount, tx.currency)} convertido a ${tx.converted_currency} con la tasa del ${tx.occurred_at.slice(0, 10)}`,
          };
        })();
        return (
          <span
            style={{
              display: 'inline-flex',
              flexDirection: 'column',
              alignItems: 'flex-end',
              lineHeight: 1.15,
            }}
          >
            <span
              style={{
                fontSize: fontSize.sm,
                fontWeight: fontWeight.semibold,
                color: amountColorFor(category?.kind),
                fontVariantNumeric: 'tabular-nums',
                whiteSpace: 'nowrap',
              }}
            >
              {amountSignFor(category?.kind)}
              {formatAmount(tx.amount, tx.currency)}
            </span>
            {convertedDisplay ? (
              <span
                title={convertedDisplay.tooltip}
                style={{
                  fontSize: fontSize.xs,
                  color: colors.textSubtle,
                  fontVariantNumeric: 'tabular-nums',
                  whiteSpace: 'nowrap',
                  marginTop: 1,
                }}
              >
                {convertedDisplay.text}
              </span>
            ) : null}
          </span>
        );
      },
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      width: 100,
      render: ({ tx }) => (
        <span onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
          <Button
            variant="ghost"
            onClick={() => onDelete(tx.id)}
            disabled={deletingId === tx.id}
            style={{ color: colors.danger, borderColor: colors.border }}
          >
            {deletingId === tx.id ? 'Borrando…' : 'Borrar'}
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
      onRowClick={(row) =>
        router.push(`/personal-finance/transactions/${row.tx.id}` as never)
      }
      emptyMessage="Sin transacciones con los filtros actuales."
    />
  );
}
