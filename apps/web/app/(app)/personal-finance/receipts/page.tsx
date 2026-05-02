'use client';

import { useState } from 'react';
import Link from 'next/link';

import { useReceipts } from '@finanzas/services';
import type { ReceiptListQuery } from '@finanzas/types';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { ReceiptList } from '@/components/receipts/receipt-list';
import { Button } from '@/components/ui/button';

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
  const hasPrev = offset > 0;
  const hasNext = offset + items.length < total;

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: spacing.lg }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: spacing.lg,
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: fontSize.xl, color: colors.text }}>
            Tickets
          </h1>
          <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
            {total} {total === 1 ? 'recibo' : 'recibos'}
          </p>
        </div>
        <Link href="/personal-finance/receipts/new">
          <Button variant="secondary">+ Subir ticket</Button>
        </Link>
      </header>

      {isLoading ? (
        <p>Cargando…</p>
      ) : isError ? (
        <p style={{ color: colors.danger }}>
          Error: {error instanceof Error ? error.message : 'desconocido'}
        </p>
      ) : (
        <>
          <ReceiptList items={items} />
          <footer
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginTop: spacing.lg,
            }}
          >
            <span style={{ color: colors.textMuted, fontSize: fontSize.sm }}>
              {isFetching ? 'Actualizando…' : ' '}
            </span>
            <div style={{ display: 'flex', gap: spacing.sm }}>
              <Button
                variant="ghost"
                disabled={!hasPrev}
                onClick={() =>
                  setFilters({ ...filters, offset: Math.max(0, offset - limit) })
                }
              >
                ← Anterior
              </Button>
              <span
                style={{
                  alignSelf: 'center',
                  fontSize: fontSize.sm,
                  fontWeight: fontWeight.medium,
                  color: colors.text,
                }}
              >
                {items.length > 0 ? `${offset + 1}–${offset + items.length}` : '0'} / {total}
              </span>
              <Button
                variant="ghost"
                disabled={!hasNext}
                onClick={() => setFilters({ ...filters, offset: offset + limit })}
              >
                Siguiente →
              </Button>
            </div>
          </footer>
        </>
      )}
    </div>
  );
}
