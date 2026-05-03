'use client';

import { useState } from 'react';
import Link from 'next/link';

import { useImports } from '@finanzas/services';
import type { ImportListQuery } from '@finanzas/types';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { ImportList } from '@/components/imports/import-list';
import { Button } from '@/components/ui/button';
import { Pagination } from '@/components/ui/pagination';

const PAGE_SIZE = 20;

export default function ImportsPage() {
  const [filters, setFilters] = useState<ImportListQuery>({
    limit: PAGE_SIZE,
    offset: 0,
  });

  const { data, isLoading, isError, error, isFetching } = useImports(filters);

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
            Importaciones
          </h1>
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              color: colors.textMuted,
              fontSize: fontSize.sm,
            }}
          >
            {total} {total === 1 ? 'job' : 'jobs'}
            {isFetching ? ' · actualizando…' : ''}
          </p>
        </div>
        <Link href="/personal-finance/imports/new">
          <Button variant="secondary">+ Nueva importación</Button>
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
          <ImportList items={items} />
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
