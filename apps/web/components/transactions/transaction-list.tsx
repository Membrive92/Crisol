'use client';

import { useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { useQueries } from '@tanstack/react-query';

import { exchangeRatesQueryOptions } from '@finanzas/services';
import { useCurrencyStore } from '@finanzas/store';
import type { Category, CategoryKind, Transaction } from '@finanzas/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatConverted,
  formatDate,
  type RatesMap,
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

  // Tasa por fila: cada transacción se convierte con la tasa del día
  // de su `occurred_at`. Para no hacer N llamadas en cascada,
  // recogemos las fechas distintas de la página visible y disparamos
  // una `useQueries` por cada una. Cada query es idempotente y se
  // cachea infinitamente para fechas pasadas (ver
  // `exchangeRatesQueryOptions`), así que tras el primer scroll la
  // tabla no genera tráfico nuevo.
  const uniqueDates = useMemo(() => {
    const set = new Set<string>();
    for (const tx of items) {
      // Las fechas vienen en ISO con offset; nos quedamos con
      // `YYYY-MM-DD` para que el queryKey/cache sea estable.
      set.add(tx.occurred_at.slice(0, 10));
    }
    return Array.from(set);
  }, [items]);

  const ratesQueries = useQueries({
    queries: uniqueDates.map((date) => exchangeRatesQueryOptions(date)),
  });

  // Map fecha → mapa de tasas. Si la query aún no está lista, devuelve
  // un mapa vacío y `formatConverted` cae en `missing` para esa fila.
  const ratesByDate = useMemo(() => {
    const m = new Map<string, RatesMap>();
    uniqueDates.forEach((date, i) => {
      m.set(date, ratesQueries[i]?.data?.rates ?? {});
    });
    return m;
  }, [uniqueDates, ratesQueries]);

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
        const showConverted =
          convertAll &&
          tx.currency.toUpperCase() !== activeCurrency.toUpperCase();
        const rowDate = tx.occurred_at.slice(0, 10);
        const rowRates = ratesByDate.get(rowDate) ?? {};
        const conv = showConverted
          ? formatConverted(
              tx.amount,
              tx.currency,
              activeCurrency,
              rowRates,
              undefined,
              rowDate,
            )
          : null;
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
            {conv && (conv.isApprox || conv.isMissing) ? (
              <span
                title={conv.tooltip}
                style={{
                  fontSize: fontSize.xs,
                  color: colors.textSubtle,
                  fontVariantNumeric: 'tabular-nums',
                  whiteSpace: 'nowrap',
                  marginTop: 1,
                }}
              >
                {conv.isMissing ? '≈ —' : conv.display}
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
