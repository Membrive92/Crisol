'use client';

import { useState } from 'react';
import Link from 'next/link';

import {
  useCategories,
  useDeleteTransaction,
  useTransactions,
} from '@finanzas/services';
import { useCurrencyStore } from '@finanzas/store';
import type { TransactionListQuery } from '@finanzas/types';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { StitchSearchToolbar } from '@/components/transactions/stitch-search-toolbar';
import { StitchTransactionsKpiRow } from '@/components/transactions/stitch-transactions-kpi-row';
import { TransactionList } from '@/components/transactions/transaction-list';
import { Button } from '@/components/ui/button';
import { Pagination } from '@/components/ui/pagination';
import { PlusIcon } from '@/components/ui/icons';

const PAGE_SIZE = 20;

export default function TransactionsPage() {
  const [filters, setFilters] = useState<TransactionListQuery>({
    limit: PAGE_SIZE,
    offset: 0,
  });
  const currency = useCurrencyStore((s) => s.currency);

  const { data, isLoading, isError, error, isFetching } = useTransactions(filters);
  const { data: categories } = useCategories();
  const deleteMutation = useDeleteTransaction();

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const offset = filters.offset ?? 0;
  const limit = filters.limit ?? PAGE_SIZE;

  // Periodo para los KPIs: el rango activo del filtro o todo el año
  // actual si no hay rango.
  const now = new Date();
  const dateFrom = filters.date_from ?? new Date(now.getFullYear(), 0, 1).toISOString();
  const dateTo =
    filters.date_to ?? new Date(now.getFullYear(), 11, 31, 23, 59, 59).toISOString();

  function handleDelete(id: string) {
    if (!confirm('¿Eliminar esta transacción?')) return;
    deleteMutation.mutate(id);
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: spacing.lg }}>
      {/* Eyebrow bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: `${spacing.sm}px 0 ${spacing.md}px`,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.xs }}>
          <span
            aria-hidden
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: colors.primary,
            }}
          />
          <span
            style={{
              fontSize: fontSize.sm,
              fontWeight: fontWeight.semibold,
              color: colors.text,
            }}
          >
            Transacciones
          </span>
          <span
            style={{
              fontSize: fontSize.sm,
              color: colors.textMuted,
              marginLeft: spacing.sm,
            }}
          >
            {total} {total === 1 ? 'registro' : 'registros'}
            {isFetching ? ' · actualizando…' : ''}
          </span>
        </div>
        <Link href="/personal-finance/transactions/new">
          <Button variant="secondary">
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <PlusIcon size={14} />
              Nueva transacción
            </span>
          </Button>
        </Link>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
        <StitchTransactionsKpiRow
          currency={currency}
          dateFrom={dateFrom}
          dateTo={dateTo}
        />

        <StitchSearchToolbar
          value={filters}
          onChange={setFilters}
          categories={categories ?? []}
        />

        {isLoading ? (
          <p style={{ color: colors.textMuted }}>Cargando…</p>
        ) : isError ? (
          <p style={{ color: colors.danger }}>
            Error: {error instanceof Error ? error.message : 'desconocido'}
          </p>
        ) : (
          <>
            <TransactionList
              items={items}
              categories={categories ?? []}
              onDelete={handleDelete}
              deletingId={
                deleteMutation.isPending ? (deleteMutation.variables as string) : null
              }
            />

            <Pagination
              total={total}
              offset={offset}
              limit={limit}
              pageItemCount={items.length}
              onChange={(nextOffset) => setFilters({ ...filters, offset: nextOffset })}
            />
          </>
        )}
      </div>
    </div>
  );
}
