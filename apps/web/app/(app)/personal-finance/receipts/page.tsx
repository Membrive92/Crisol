'use client';

import { useState } from 'react';
import Link from 'next/link';

import { useReceipts } from '@finanzas/services';
import type { ReceiptListQuery } from '@finanzas/types';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { ReceiptList } from '@/components/receipts/receipt-list';
import { Button } from '@/components/ui/button';
import { Pagination } from '@/components/ui/pagination';

const PAGE_SIZE = 20;

export default function ReceiptsPage() {
  const [filters, setFilters] = useState<ReceiptListQuery>({
    limit: PAGE_SIZE,
    offset: 0,
  });
  const { data, isLoading, isError, error, isFetching } = useReceipts(filters);

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const offset = filters.offset ?? 0;
  const limit = filters.limit ?? PAGE_SIZE;

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
            Tickets
          </h1>
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              color: colors.textMuted,
              fontSize: fontSize.sm,
            }}
          >
            {total} {total === 1 ? 'recibo' : 'recibos'}
            {isFetching ? ' · actualizando…' : ''}
          </p>
        </div>
        <Link href="/personal-finance/receipts/new">
          <Button variant="secondary">+ Subir ticket</Button>
        </Link>
      </header>

      {isLoading ? (
        <p style={{ color: colors.textMuted }}>Cargando…</p>
      ) : isError ? (
        <p style={{ color: colors.danger }}>
          Error: {error instanceof Error ? error.message : 'desconocido'}
        </p>
      ) : (
        <>
          <ReceiptList items={items} />
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
