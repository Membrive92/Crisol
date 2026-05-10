import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Stack } from 'expo-router';

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
} from '@finanzas/services';
import { toast } from '@finanzas/store';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import { FixedExpenseCard } from '../../../components/fixed-expenses/fixed-expense-card';
import { ConfirmDialog } from '../../../components/ui/confirm-dialog';

/**
 * Pantalla mobile de gastos fijos (PHASE-13.3, renombrado en PHASE-17.1).
 * Reusa hooks shared. Layout: header con descripción y botón
 * Re-escanear, sección Sugeridos (pendientes) con [Confirmar] /
 * [Descartar], Confirmados con [Pausar]/[Cancelar], y secciones
 * colapsables Cancelados/Descartados.
 */
export default function FixedExpensesScreen() {
  const { data: categories } = useCategories();
  const { data: accounts } = useAccounts();
  const pendingQuery = useFixedExpenses({ status: 'pending' });
  const confirmedQuery = useFixedExpenses({ status: 'confirmed' });
  const dismissedQuery = useFixedExpenses({ status: 'dismissed' });
  const pausedQuery = useFixedExpenses({ status: 'paused' });
  const cancelledQuery = useFixedExpenses({ status: 'cancelled' });
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
    { kind: 'cancel' | 'delete'; id: string; label: string } | null
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
          ? toast.info('No había gastos fijos vencidos.')
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
          toast.info(next ? 'Auto-añadir activado.' : 'Auto-añadir desactivado.'),
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

  function handleReactivate(id: string) {
    // PHASE-13.1: confirm sobre uno dismissed lo reactiva.
    confirmMutation.mutate(id, {
      onSuccess: () => toast.success('Gasto fijo reactivado.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al reactivar.')),
    });
  }

  function handleDismiss(id: string) {
    dismissMutation.mutate(id, {
      onSuccess: () => toast.info('Descartado — no se volverá a sugerir.'),
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

  function handleCancel(id: string, label: string) {
    setPendingAction({ kind: 'cancel', id, label });
  }

  function handleDelete(id: string, label: string) {
    setPendingAction({ kind: 'delete', id, label });
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
    <View style={styles.container}>
      <Stack.Screen options={{ title: 'Gastos fijos' }} />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.intro}>
          Detectados a partir de tus transacciones recurrentes (heurística
          local, sin enviar datos fuera). Suscripciones, hipotecas,
          préstamos, gym, seguros — cualquier gasto con patrón estable.
          El detector se ejecuta cada noche; pulsa "Re-escanear" para
          forzarlo ahora.
        </Text>

        <View style={styles.actionsRow}>
          <Pressable
            onPress={handleAutopost}
            disabled={autopostMutation.isPending}
            style={({ pressed }) => [
              styles.scanButton,
              pressed && { opacity: 0.7 },
              autopostMutation.isPending && { opacity: 0.5 },
            ]}
          >
            <Text style={styles.scanButtonText}>
              {autopostMutation.isPending ? 'Auto-añadiendo…' : 'Auto-añadir vencidos'}
            </Text>
          </Pressable>
          <Pressable
            onPress={handleScan}
            disabled={scanMutation.isPending}
            style={({ pressed }) => [
              styles.scanButton,
              pressed && { opacity: 0.7 },
              scanMutation.isPending && { opacity: 0.5 },
            ]}
          >
            <Text style={styles.scanButtonText}>
              {scanMutation.isPending ? 'Escaneando…' : 'Re-escanear'}
            </Text>
          </Pressable>
        </View>

        <Text style={styles.sectionHeading}>Sugeridos</Text>
        {pendingQuery.isLoading ? (
          <Text style={styles.placeholder}>Cargando…</Text>
        ) : pending.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyText}>
              Sin sugerencias pendientes. Cuando el detector encuentre un
              patrón nuevo aparecerá aquí.
            </Text>
          </View>
        ) : (
          pending.map((item) => (
            <FixedExpenseCard
              key={item.id}
              fixedExpense={item}
              categories={categories ?? []}
              primaryAction={{
                label: 'Confirmar',
                onPress: () => handleConfirm(item.id),
                busy: confirmingId === item.id,
              }}
              secondaryAction={{
                label: 'Descartar',
                onPress: () => handleDismiss(item.id),
                busy: dismissingId === item.id,
              }}
            />
          ))
        )}

        {confirmed.length > 0 ? (
          <>
            <Text style={[styles.sectionHeading, { marginTop: spacing.lg }]}>
              Confirmados
            </Text>
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
                  onPress: () => handlePause(item.id),
                  busy: pausingId === item.id,
                }}
                secondaryAction={{
                  label: 'Cancelar',
                  onPress: () => handleCancel(item.id, item.raw_description),
                  busy: cancellingId === item.id,
                  danger: true,
                }}
              />
            ))}
          </>
        ) : null}

        {paused.length > 0 ? (
          <>
            <Text style={[styles.sectionHeading, { marginTop: spacing.lg }]}>
              Pausados
            </Text>
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
                  onPress: () => handleResume(item.id),
                  busy: resumingId === item.id,
                }}
                secondaryAction={{
                  label: 'Cancelar',
                  onPress: () => handleCancel(item.id, item.raw_description),
                  busy: cancellingId === item.id,
                  danger: true,
                }}
              />
            ))}
          </>
        ) : null}

        {cancelled.length > 0 ? (
          <View style={{ marginTop: spacing.lg }}>
            <Pressable
              onPress={() => setShowCancelled((v) => !v)}
              style={({ pressed }) => [
                styles.toggleButton,
                pressed && { opacity: 0.7 },
              ]}
              accessibilityRole="button"
              accessibilityState={{ expanded: showCancelled }}
            >
              <Text style={styles.toggleText}>
                {showCancelled ? '▾' : '▸'} Cancelados ({cancelled.length})
              </Text>
            </Pressable>
            {showCancelled
              ? cancelled.map((item) => (
                  <FixedExpenseCard
                    key={item.id}
                    fixedExpense={item}
                    categories={categories ?? []}
                    secondaryAction={{
                      label: 'Eliminar',
                      onPress: () => handleDelete(item.id, item.raw_description),
                      busy: deletingId === item.id,
                      danger: true,
                    }}
                  />
                ))
              : null}
          </View>
        ) : null}

        {dismissed.length > 0 ? (
          <View style={{ marginTop: spacing.lg }}>
            <Pressable
              onPress={() => setShowDismissed((v) => !v)}
              style={({ pressed }) => [
                styles.toggleButton,
                pressed && { opacity: 0.7 },
              ]}
              accessibilityRole="button"
              accessibilityState={{ expanded: showDismissed }}
            >
              <Text style={styles.toggleText}>
                {showDismissed ? '▾' : '▸'} Descartados ({dismissed.length})
              </Text>
            </Pressable>
            {showDismissed
              ? dismissed.map((item) => (
                  <FixedExpenseCard
                    key={item.id}
                    fixedExpense={item}
                    categories={categories ?? []}
                    primaryAction={{
                      label: 'Reactivar',
                      onPress: () => handleReactivate(item.id),
                      busy: confirmingId === item.id,
                    }}
                    secondaryAction={{
                      label: 'Eliminar',
                      onPress: () => handleDelete(item.id, item.raw_description),
                      busy: deletingId === item.id,
                      danger: true,
                    }}
                  />
                ))
              : null}
          </View>
        ) : null}
      </ScrollView>

      <ConfirmDialog
        open={pendingAction !== null}
        title={
          pendingAction?.kind === 'cancel'
            ? '¿Cancelar gasto fijo?'
            : '¿Eliminar gasto fijo?'
        }
        description={
          pendingAction
            ? pendingAction.kind === 'cancel'
              ? `"${pendingAction.label}" quedará marcado como cancelado. Las transacciones existentes no se tocan.`
              : `"${pendingAction.label}" desaparecerá. Si el patrón persiste, volverá a aparecer como pendiente en el próximo escaneo.`
            : undefined
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
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  intro: { fontSize: fontSize.sm, color: colors.textMuted, marginBottom: spacing.md },
  actionsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    flexWrap: 'wrap',
    marginBottom: spacing.lg,
  },
  scanButton: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.primary,
    backgroundColor: 'transparent',
  },
  scanButtonText: {
    color: colors.primary,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
  },
  sectionHeading: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.sm,
  },
  placeholder: { padding: spacing.md, color: colors.textMuted },
  emptyCard: {
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderStyle: 'dashed',
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.lg,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    textAlign: 'center',
  },
  toggleButton: {
    paddingVertical: spacing.xs,
    marginBottom: spacing.sm,
    alignSelf: 'flex-start',
  },
  toggleText: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    fontWeight: fontWeight.medium,
  },
});
