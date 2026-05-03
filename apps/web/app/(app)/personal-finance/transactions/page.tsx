'use client';

import { useState } from 'react';
import Link from 'next/link';

import {
  useCategories,
  useDeleteTransaction,
  useTransactions,
} from '@finanzas/services';
import type { TransactionListQuery } from '@finanzas/types';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { TransactionFilters } from '@/components/transactions/transaction-filters';
import { TransactionList } from '@/components/transactions/transaction-list';
import { Button } from '@/components/ui/button';
import { Pagination } from '@/components/ui/pagination';

const PAGE_SIZE = 20;

export default function TransactionsPage() {
  const [filters, setFilters] = useState<TransactionListQuery>({
    limit: PAGE_SIZE,
    offset: 0,
  });

  const { data, isLoading, isError, error, isFetching } = useTransactions(filters);
  const { data: categories } = useCategories();
  const deleteMutation = useDeleteTransaction();

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const offset = filters.offset ?? 0;
  const limit = filters.limit ?? PAGE_SIZE;

  function handleDelete(id: string) {
    if (!confirm('¿Eliminar esta transacción?')) return;
    deleteMutation.mutate(id);
  }

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: spacing.lg }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: spacing.md,
          marginBottom: spacing.lg,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <h1
            style={{
              margin: 0,
              fontSize: fontSize.xl,
              fontWeight: fontWeight.bold,
              color: colors.text,
              letterSpacing: '-0.01em',
            }}
          >
            Transacciones
          </h1>
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              color: colors.textMuted,
              fontSize: fontSize.sm,
            }}
          >
            {total} {total === 1 ? 'registro' : 'registros'}
            {isFetching ? ' · actualizando…' : ''}
          </p>
        </div>
        <Link href="/personal-finance/transactions/new">
          <Button variant="secondary">+ Nueva</Button>
        </Link>
      </header>

      <TransactionFilters value={filters} onChange={setFilters} />

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
  );
}
