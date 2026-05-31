'use client';

import { useState } from 'react';

import {
  formatApiError,
  useAccounts,
  useAutopostFixedExpenses,
  useCancelFixedExpense,
  useCategories,
  useConfirmFixedExpense,
  useDeleteFixedExpense,
  useDismissFixedExpense,
  useFixedExpenses,
  usePauseFixedExpense,
  useResumeFixedExpense,
  useScanFixedExpenses,
  useUpdateFixedExpense,
} from '@crisol/services';
import { toast } from '@crisol/store';
import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';

import { FixedExpenseCard } from '@/components/fixed-expenses/fixed-expense-card';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { ErrorState } from '@/components/ui/error-state';
import { SkeletonCardList } from '@/components/ui/skeleton';

export default function FixedExpensesPage() {
  const { data: categories } = useCategories();
  const { data: accounts } = useAccounts();
  const pendingQuery = useFixedExpenses({ status: 'pending' });
  const confirmedQuery = useFixedExpenses({ status: 'confirmed' });
  const pausedQuery = useFixedExpenses({ status: 'paused' });
  const cancelledQuery = useFixedExpenses({ status: 'cancelled' });
  const dismissedQuery = useFixedExpenses({ status: 'dismissed' });
  const scanMutation = useScanFixedExpenses();
  const autopostMutation = useAutopostFixedExpenses();
  const updateMutation = useUpdateFixedExpense();
  const confirmMutation = useConfirmFixedExpense();
  const dismissMutation = useDismissFixedExpense();
  const pauseMutation = usePauseFixedExpense();
  const resumeMutation = useResumeFixedExpense();
  const cancelMutation = useCancelFixedExpense();
  const deleteMutation = useDeleteFixedExpense();
  const [showDismissed, setShowDismissed] = useState(false);
  const [showCancelled, setShowCancelled] = useState(false);
  const [pendingAction, setPendingAction] = useState<
    { kind: 'cancel' | 'delete'; id: string } | null
  >(null);

  const pending = pendingQuery.data ?? [];
  const confirmed = confirmedQuery.data ?? [];
  const paused = pausedQuery.data ?? [];
  const cancelled = cancelledQuery.data ?? [];
  const dismissed = dismissedQuery.data ?? [];

  function handleScan() {
    scanMutation.mutate(undefined, {
      onSuccess: (res) =>
        toast.success(
          `Re-escaneado: ${res.created} nuevos, ${res.updated} actualizados.`,
        ),
      onError: (err) => toast.error(formatApiError(err, 'Error al re-escanear.')),
    });
  }

  function handleAutopost() {
    autopostMutation.mutate(undefined, {
      onSuccess: (res) =>
        res.created === 0
          ? toast.info('No había gastos fijos vencidos pendientes.')
          : toast.success(
              `Auto-añadidas ${res.created} ${
                res.created === 1 ? 'transacción' : 'transacciones'
              }.`,
            ),
      onError: (err) => toast.error(formatApiError(err, 'Error al auto-añadir.')),
    });
  }

  function handleToggleAutoPost(id: string, next: boolean) {
    updateMutation.mutate(
      { id, data: { auto_post: next } },
      {
        onSuccess: () =>
          toast.info(
            next
              ? 'Auto-añadir activado para este gasto.'
              : 'Auto-añadir desactivado.',
          ),
        onError: (err) =>
          toast.error(formatApiError(err, 'Error al cambiar el flag.')),
      },
    );
  }

  function handleChangeAccount(id: string, accountId: string | null) {
    updateMutation.mutate(
      { id, data: { account_id: accountId } },
      {
        onSuccess: () =>
          toast.success(
            accountId
              ? 'Cuenta de cobro actualizada.'
              : 'Cuenta retirada — el autopost queda desactivado.',
          ),
        onError: (err) =>
          toast.error(formatApiError(err, 'Error al cambiar la cuenta.')),
      },
    );
  }

  function handleConfirm(id: string) {
    confirmMutation.mutate(id, {
      onSuccess: () => toast.success('Gasto fijo confirmado.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al confirmar.')),
    });
  }

  /** Reactiva un dismissed → confirmed (PHASE-13.1: el confirm de
   * uno dismissed lo reactiva). */
  function handleReactivate(id: string) {
    confirmMutation.mutate(id, {
      onSuccess: () => toast.success('Gasto fijo reactivado.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al reactivar.')),
    });
  }

  function handleDismiss(id: string) {
    dismissMutation.mutate(id, {
      onSuccess: () =>
        toast.info('Gasto fijo descartado — no se volverá a sugerir.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al descartar.')),
    });
  }

  function handlePause(id: string) {
    pauseMutation.mutate(id, {
      onSuccess: () => toast.info('Gasto fijo pausado.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al pausar.')),
    });
  }

  function handleResume(id: string) {
    resumeMutation.mutate(id, {
      onSuccess: () => toast.success('Gasto fijo reanudado.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al reanudar.')),
    });
  }

  function handleCancel(id: string) {
    setPendingAction({ kind: 'cancel', id });
  }

  function handleDelete(id: string) {
    setPendingAction({ kind: 'delete', id });
  }

  function confirmPendingAction() {
    if (!pendingAction) return;
    const { kind, id } = pendingAction;
    setPendingAction(null);
    if (kind === 'cancel') {
      cancelMutation.mutate(id, {
        onSuccess: () => toast.info('Gasto fijo cancelado.'),
        onError: (err) => toast.error(formatApiError(err, 'Error al cancelar.')),
      });
    } else {
      deleteMutation.mutate(id, {
        onSuccess: () => toast.success('Gasto fijo eliminado.'),
        onError: (err) => toast.error(formatApiError(err, 'Error al eliminar.')),
      });
    }
  }

  const confirmingId = confirmMutation.isPending
    ? (confirmMutation.variables as string)
    : null;
  const dismissingId = dismissMutation.isPending
    ? (dismissMutation.variables as string)
    : null;
  const pausingId = pauseMutation.isPending
    ? (pauseMutation.variables as string)
    : null;
  const resumingId = resumeMutation.isPending
    ? (resumeMutation.variables as string)
    : null;
  const cancellingId = cancelMutation.isPending
    ? (cancelMutation.variables as string)
    : null;
  const deletingId = deleteMutation.isPending
    ? (deleteMutation.variables as string)
    : null;

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: spacing.lg }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: spacing.md,
          flexWrap: 'wrap',
          marginBottom: spacing.xl,
        }}
      >
        <div>
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
            Gastos fijos
          </h1>
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              color: colors.textMuted,
              fontSize: fontSize.sm,
            }}
          >
            Gastos recurrentes con cantidad estable detectados a partir
            de tus transacciones (suscripciones, hipotecas, préstamos,
            cuotas de gym, seguros…). Heurística local — los datos no
            salen del equipo. El detector se ejecuta cada noche; pulsa
            "Re-escanear" para forzar la detección ahora.
          </p>
        </div>
        <div style={{ display: 'inline-flex', gap: spacing.sm }}>
          <Button
            onClick={handleAutopost}
            disabled={autopostMutation.isPending}
            variant="secondary"
          >
            {autopostMutation.isPending ? 'Auto-añadiendo…' : 'Auto-añadir vencidos'}
          </Button>
          <Button
            onClick={handleScan}
            disabled={scanMutation.isPending}
            variant="secondary"
          >
            {scanMutation.isPending ? 'Escaneando…' : 'Re-escanear'}
          </Button>
        </div>
      </header>

      <section style={{ marginBottom: spacing.xl }}>
        <h2 style={sectionHeaderStyle}>Sugeridos (revisa y confirma)</h2>
        {pendingQuery.isLoading ? (
          <SkeletonCardList rows={3} />
        ) : pendingQuery.isError ? (
          <ErrorState
            description="No se pudieron cargar los gastos fijos sugeridos."
            onRetry={() => void pendingQuery.refetch()}
            retrying={pendingQuery.isFetching}
          />
        ) : pending.length === 0 ? (
          <Card
            style={{
              padding: spacing.lg,
              textAlign: 'center',
              backgroundColor: colors.surfaceMuted,
              border: `1px dashed ${colors.border}`,
            }}
          >
            <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
              Sin sugerencias pendientes. Cuando el detector encuentre un
              patrón nuevo aparecerá aquí.
            </p>
          </Card>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
            {pending.map((item) => (
              <FixedExpenseCard
                key={item.id}
                fixedExpense={item}
                categories={categories ?? []}
                primaryAction={{
                  label: 'Confirmar',
                  onClick: () => handleConfirm(item.id),
                  busy: confirmingId === item.id,
                }}
                secondaryAction={{
                  label: 'Descartar',
                  onClick: () => handleDismiss(item.id),
                  busy: dismissingId === item.id,
                }}
              />
            ))}
          </div>
        )}
      </section>

      {confirmed.length > 0 ? (
        <section style={{ marginBottom: spacing.xl }}>
          <h2 style={sectionHeaderStyle}>Confirmados</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
            {confirmed.map((item) => (
              <FixedExpenseCard
                key={item.id}
                fixedExpense={item}
                categories={categories ?? []}
                accounts={accounts ?? []}
                onToggleAutoPost={handleToggleAutoPost}
                autoPostBusy={
                  updateMutation.isPending &&
                  (updateMutation.variables as { id: string } | undefined)?.id ===
                    item.id
                }
                onChangeAccount={handleChangeAccount}
                accountBusy={
                  updateMutation.isPending &&
                  (updateMutation.variables as { id: string } | undefined)?.id ===
                    item.id
                }
                primaryAction={{
                  label: 'Pausar',
                  onClick: () => handlePause(item.id),
                  busy: pausingId === item.id,
                }}
                secondaryAction={{
                  label: 'Cancelar',
                  onClick: () => handleCancel(item.id),
                  busy: cancellingId === item.id,
                  danger: true,
                }}
              />
            ))}
          </div>
        </section>
      ) : null}

      {paused.length > 0 ? (
        <section style={{ marginBottom: spacing.xl }}>
          <h2 style={sectionHeaderStyle}>Pausados</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
            {paused.map((item) => (
              <FixedExpenseCard
                key={item.id}
                fixedExpense={item}
                categories={categories ?? []}
                accounts={accounts ?? []}
                onChangeAccount={handleChangeAccount}
                accountBusy={
                  updateMutation.isPending &&
                  (updateMutation.variables as { id: string } | undefined)?.id ===
                    item.id
                }
                primaryAction={{
                  label: 'Reanudar',
                  onClick: () => handleResume(item.id),
                  busy: resumingId === item.id,
                }}
                secondaryAction={{
                  label: 'Cancelar',
                  onClick: () => handleCancel(item.id),
                  busy: cancellingId === item.id,
                  danger: true,
                }}
              />
            ))}
          </div>
        </section>
      ) : null}

      {cancelled.length > 0 ? (
        <section style={{ marginBottom: spacing.lg }}>
          <button
            type="button"
            onClick={() => setShowCancelled((v) => !v)}
            style={collapseToggleStyle}
            aria-expanded={showCancelled}
          >
            <span aria-hidden style={{ fontSize: fontSize.xs }}>
              {showCancelled ? '▾' : '▸'}
            </span>
            Cancelados ({cancelled.length})
          </button>
          {showCancelled ? (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: spacing.sm,
                marginTop: spacing.md,
              }}
            >
              {cancelled.map((item) => (
                <FixedExpenseCard
                  key={item.id}
                  fixedExpense={item}
                  categories={categories ?? []}
                  secondaryAction={{
                    label: 'Eliminar',
                    onClick: () => handleDelete(item.id),
                    busy: deletingId === item.id,
                    danger: true,
                  }}
                />
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      {dismissed.length > 0 ? (
        <section>
          <button
            type="button"
            onClick={() => setShowDismissed((v) => !v)}
            style={collapseToggleStyle}
            aria-expanded={showDismissed}
          >
            <span aria-hidden style={{ fontSize: fontSize.xs }}>
              {showDismissed ? '▾' : '▸'}
            </span>
            Descartados ({dismissed.length})
          </button>
          {showDismissed ? (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: spacing.sm,
                marginTop: spacing.md,
              }}
            >
              {dismissed.map((item) => (
                <FixedExpenseCard
                  key={item.id}
                  fixedExpense={item}
                  categories={categories ?? []}
                  primaryAction={{
                    label: 'Reactivar',
                    onClick: () => handleReactivate(item.id),
                    busy: confirmingId === item.id,
                  }}
                  secondaryAction={{
                    label: 'Eliminar',
                    onClick: () => handleDelete(item.id),
                    busy: deletingId === item.id,
                    danger: true,
                  }}
                />
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      <ConfirmDialog
        open={pendingAction !== null}
        title={
          pendingAction?.kind === 'cancel'
            ? '¿Cancelar gasto fijo?'
            : '¿Eliminar gasto fijo?'
        }
        description={
          pendingAction?.kind === 'cancel'
            ? 'Quedará marcado como cancelado. Las transacciones existentes no se tocan.'
            : 'Si el patrón persiste, volverá a aparecer como pendiente en el próximo escaneo.'
        }
        confirmLabel={
          pendingAction?.kind === 'cancel' ? 'Cancelar gasto' : 'Eliminar'
        }
        cancelLabel="Atrás"
        tone="danger"
        loading={
          pendingAction?.kind === 'cancel'
            ? cancelMutation.isPending
            : deleteMutation.isPending
        }
        onConfirm={confirmPendingAction}
        onCancel={() => setPendingAction(null)}
      />
    </div>
  );
}

const sectionHeaderStyle: React.CSSProperties = {
  fontSize: fontSize.lg,
  fontWeight: fontWeight.semibold,
  color: colors.text,
  marginTop: 0,
  marginBottom: spacing.md,
};

const collapseToggleStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  background: 'none',
  border: 'none',
  padding: 0,
  cursor: 'pointer',
  color: colors.textMuted,
  fontSize: fontSize.sm,
  fontWeight: fontWeight.medium,
};
