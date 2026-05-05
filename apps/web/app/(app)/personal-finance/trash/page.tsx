'use client';

import { useState } from 'react';
import Link from 'next/link';

import {
  useCategories,
  usePurgeTransaction,
  useRestoreTransaction,
  useTrashedTransactions,
} from '@finanzas/services';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { TrashList } from '@/components/transactions/trash-list';
import { Button } from '@/components/ui/button';
import { ChevronLeftIcon } from '@/components/ui/icons';
import { Pagination } from '@/components/ui/pagination';

const PAGE_SIZE = 20;

export default function TrashPage() {
  const [offset, setOffset] = useState(0);
  const trashQuery = useTrashedTransactions({ limit: PAGE_SIZE, offset });
  const { data: categories } = useCategories();
  const restoreMutation = useRestoreTransaction();
  const purgeMutation = usePurgeTransaction();

  const items = trashQuery.data?.items ?? [];
  const total = trashQuery.data?.total ?? 0;

  const busyId = restoreMutation.isPending
    ? (restoreMutation.variables as string)
    : purgeMutation.isPending
      ? (purgeMutation.variables as string)
      : null;

  function handleRestore(id: string) {
    restoreMutation.mutate(id);
  }

  function handlePurge(id: string) {
    if (
      !confirm(
        'Eliminar permanente esta transacción. Esta acción no se puede deshacer. ¿Continuar?',
      )
    ) {
      return;
    }
    purgeMutation.mutate(id);
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: spacing.lg }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: spacing.xl,
          gap: spacing.md,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <Link
            href="/personal-finance/transactions"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              color: colors.textMuted,
              fontSize: fontSize.sm,
              textDecoration: 'none',
              marginBottom: spacing.xs,
            }}
          >
            <ChevronLeftIcon size={14} />
            Volver a Transacciones
          </Link>
          <h1
            style={{
              margin: 0,
              fontSize: fontSize.xxl,
              fontWeight: fontWeight.bold,
              color: colors.text,
              letterSpacing: '-0.02em',
              lineHeight: 1.1,
            }}
          >
            Papelera
          </h1>
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              color: colors.textMuted,
              fontSize: fontSize.sm,
            }}
          >
            {total} {total === 1 ? 'transacción' : 'transacciones'} en papelera ·
            restaúralas o elimínalas para siempre.
          </p>
        </div>
      </div>

      {trashQuery.isLoading ? (
        <p style={{ color: colors.textMuted }}>Cargando…</p>
      ) : trashQuery.isError ? (
        <p style={{ color: colors.danger }}>
          Error:{' '}
          {trashQuery.error instanceof Error
            ? trashQuery.error.message
            : 'desconocido'}
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
          {(restoreMutation.isError || purgeMutation.isError) && (
            <p style={{ color: colors.danger, fontSize: fontSize.sm }}>
              Error al actualizar la papelera. Reintenta.
            </p>
          )}
          <TrashList
            items={items}
            categories={categories ?? []}
            onRestore={handleRestore}
            onPurge={handlePurge}
            busyId={busyId}
          />
          <Pagination
            total={total}
            offset={offset}
            limit={PAGE_SIZE}
            pageItemCount={items.length}
            onChange={setOffset}
          />
          {items.length === 0 && total === 0 && (
            <Link href="/personal-finance/transactions">
              <Button variant="ghost">Volver a Transacciones</Button>
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
