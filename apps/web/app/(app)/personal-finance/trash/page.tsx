'use client';

import { useState } from 'react';
import Link from 'next/link';

import {
  useBulkPurgeTrash,
  useBulkRestoreTrash,
  useCategories,
  usePurgeTransaction,
  useRestoreTransaction,
  useTrashedTransactions,
} from '@crisol/services';
import { toast } from '@crisol/store';
import { colors, fontSize, fontWeight, layout, spacing } from '@crisol/ui';

import { TrashList } from '@/components/transactions/trash-list';
import { Button } from '@/components/ui/button';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { ChevronLeftIcon } from '@/components/ui/icons';
import { Pagination } from '@/components/ui/pagination';

const PAGE_SIZE = 20;

export default function TrashPage() {
  const [offset, setOffset] = useState(0);
  const [pendingPurgeId, setPendingPurgeId] = useState<string | null>(null);
  const [confirmingBulkRestore, setConfirmingBulkRestore] = useState(false);
  const [confirmingBulkPurge, setConfirmingBulkPurge] = useState(false);
  const trashQuery = useTrashedTransactions({ limit: PAGE_SIZE, offset });
  const { data: categories } = useCategories();
  const restoreMutation = useRestoreTransaction();
  const purgeMutation = usePurgeTransaction();
  const bulkRestoreMutation = useBulkRestoreTrash();
  const bulkPurgeMutation = useBulkPurgeTrash();

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
    setPendingPurgeId(id);
  }

  function confirmPurge() {
    const id = pendingPurgeId;
    if (!id) return;
    purgeMutation.mutate(id);
    setPendingPurgeId(null);
  }

  function confirmBulkRestore() {
    setConfirmingBulkRestore(false);
    bulkRestoreMutation.mutate(undefined, {
      onSuccess: ({ restored_count }) => {
        if (restored_count === 0) {
          toast.info('La papelera ya estaba vacía.');
          return;
        }
        toast.success(
          `Restauradas ${restored_count} ${
            restored_count === 1 ? 'transacción' : 'transacciones'
          }.`,
        );
      },
      onError: (err) => {
        toast.error(
          err instanceof Error ? `Error: ${err.message}` : 'Error al restaurar',
        );
      },
    });
  }

  function confirmBulkPurge() {
    setConfirmingBulkPurge(false);
    bulkPurgeMutation.mutate(undefined, {
      onSuccess: ({ purged_count }) => {
        if (purged_count === 0) {
          toast.info('La papelera ya estaba vacía.');
          return;
        }
        toast.success(
          `Eliminadas ${purged_count} ${
            purged_count === 1 ? 'transacción' : 'transacciones'
          } definitivamente.`,
        );
      },
      onError: (err) => {
        toast.error(
          err instanceof Error
            ? `Error: ${err.message}`
            : 'Error al eliminar',
        );
      },
    });
  }

  return (
    <div style={{ maxWidth: layout.pageWide, margin: '0 auto', padding: spacing.lg }}>
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
        <div style={{ display: 'inline-flex', gap: spacing.sm }}>
          <Button
            variant="ghost"
            onClick={() => setConfirmingBulkRestore(true)}
            disabled={total === 0 || bulkRestoreMutation.isPending}
          >
            {bulkRestoreMutation.isPending ? 'Restaurando…' : 'Restaurar todo'}
          </Button>
          <Button
            variant="ghost"
            onClick={() => setConfirmingBulkPurge(true)}
            disabled={total === 0 || bulkPurgeMutation.isPending}
            style={{ color: colors.danger, borderColor: colors.danger }}
          >
            {bulkPurgeMutation.isPending ? 'Borrando…' : 'Borrar todo'}
          </Button>
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

      <ConfirmDialog
        open={pendingPurgeId !== null}
        title="¿Eliminar permanentemente?"
        description="Esta acción no se puede deshacer. La transacción se borrará para siempre."
        confirmLabel="Eliminar para siempre"
        tone="danger"
        loading={purgeMutation.isPending}
        onConfirm={confirmPurge}
        onCancel={() => setPendingPurgeId(null)}
      />

      <ConfirmDialog
        open={confirmingBulkRestore}
        title={`¿Restaurar ${total} ${total === 1 ? 'transacción' : 'transacciones'}?`}
        description="Volverán a aparecer en el listado activo y al dashboard."
        confirmLabel="Restaurar todo"
        tone="primary"
        loading={bulkRestoreMutation.isPending}
        onConfirm={confirmBulkRestore}
        onCancel={() => setConfirmingBulkRestore(false)}
      />

      <ConfirmDialog
        open={confirmingBulkPurge}
        title={`¿Borrar ${total} ${total === 1 ? 'transacción' : 'transacciones'} para siempre?`}
        description="Esta acción NO se puede deshacer. Los datos se eliminarán de forma permanente."
        confirmLabel="Borrar para siempre"
        tone="danger"
        loading={bulkPurgeMutation.isPending}
        onConfirm={confirmBulkPurge}
        onCancel={() => setConfirmingBulkPurge(false)}
      />
    </div>
  );
}
