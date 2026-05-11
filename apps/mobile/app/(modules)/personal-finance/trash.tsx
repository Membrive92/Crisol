import { useState } from 'react';
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { Stack } from 'expo-router';

import {
  useCategories,
  usePurgeTransaction,
  useRestoreTransaction,
  useTrashedTransactions,
} from '@crisol/services';
import type { Category, Transaction } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatDate,
  radius,
  spacing,
} from '@crisol/ui';

import { ConfirmDialog } from '@/components/ui/confirm-dialog';

function findCategory(categories: Category[], id: string | null): Category | undefined {
  if (!id) return undefined;
  return categories.find((c) => c.id === id);
}

function relativeDeleted(deletedAt: string | null): string {
  if (!deletedAt) return '';
  const ms = Date.now() - new Date(deletedAt).getTime();
  const minutes = Math.floor(ms / 60_000);
  if (minutes < 1) return 'hace segundos';
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  const days = Math.floor(hours / 24);
  return `hace ${days} ${days === 1 ? 'día' : 'días'}`;
}

/**
 * Pantalla de papelera. Reusa los hooks shared de PHASE-10.2; cada
 * fila ofrece [Restaurar] (sin confirm — reversible) y [Eliminar]
 * (con `Alert.alert` destructivo nativo).
 */
export default function TrashScreen() {
  const trashQuery = useTrashedTransactions({ limit: 50 });
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
  const [pendingPurgeId, setPendingPurgeId] = useState<string | null>(null);

  function handlePurge(id: string) {
    setPendingPurgeId(id);
  }

  function confirmPurge() {
    const id = pendingPurgeId;
    if (!id) return;
    setPendingPurgeId(null);
    purgeMutation.mutate(id);
  }

  function renderItem({ item }: { item: Transaction }) {
    const category = findCategory(categories ?? [], item.category_id);
    const disabled = busyId === item.id;

    return (
      <View style={styles.row}>
        <View style={styles.rowText}>
          <Text style={styles.description} numberOfLines={1}>
            {item.description ?? '(sin descripción)'}
          </Text>
          <Text style={styles.meta}>
            {formatDate(item.occurred_at)} · {category?.name ?? 'Sin categoría'}
          </Text>
          <Text style={styles.deletedAt}>Borrada {relativeDeleted(item.deleted_at)}</Text>
        </View>
        <View style={styles.rowRight}>
          <Text style={styles.amount}>{formatAmount(item.amount, item.currency)}</Text>
          <View style={styles.actions}>
            <Pressable
              onPress={() => restoreMutation.mutate(item.id)}
              disabled={disabled}
              style={({ pressed }) => [
                styles.actionButton,
                pressed && styles.actionPressed,
                disabled && styles.actionDisabled,
              ]}
            >
              <Text style={[styles.actionText, { color: colors.primary }]}>
                {restoreMutation.isPending && busyId === item.id
                  ? 'Restaurando…'
                  : 'Restaurar'}
              </Text>
            </Pressable>
            <Pressable
              onPress={() => handlePurge(item.id)}
              disabled={disabled}
              style={({ pressed }) => [
                styles.actionButton,
                pressed && styles.actionPressed,
                disabled && styles.actionDisabled,
              ]}
            >
              <Text style={[styles.actionText, { color: colors.danger }]}>Eliminar</Text>
            </Pressable>
          </View>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ title: 'Papelera' }} />
      <View style={styles.header}>
        <Text style={styles.headerText}>
          {total} {total === 1 ? 'transacción' : 'transacciones'} en papelera
        </Text>
      </View>

      {trashQuery.isLoading ? (
        <Text style={styles.placeholder}>Cargando…</Text>
      ) : trashQuery.isError ? (
        <Text style={[styles.placeholder, { color: colors.danger }]}>Error al cargar</Text>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(t) => t.id}
          renderItem={renderItem}
          ItemSeparatorComponent={() => <View style={styles.separator} />}
          refreshing={trashQuery.isRefetching}
          onRefresh={() => trashQuery.refetch()}
          ListEmptyComponent={
            <Text style={styles.placeholder}>La papelera está vacía.</Text>
          }
          contentContainerStyle={items.length === 0 ? styles.emptyContent : undefined}
        />
      )}

      {(restoreMutation.isError || purgeMutation.isError) && (
        <Text style={styles.errorBar}>
          Error al actualizar la papelera. Reintenta.
        </Text>
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
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerText: { color: colors.textMuted, fontSize: fontSize.sm },
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: spacing.md,
    backgroundColor: colors.surface,
    gap: spacing.sm,
  },
  rowText: { flex: 1 },
  rowRight: { alignItems: 'flex-end', gap: spacing.xs },
  description: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: fontWeight.medium,
  },
  meta: { fontSize: fontSize.sm, color: colors.textMuted, marginTop: 2 },
  deletedAt: { fontSize: fontSize.xs, color: colors.textSubtle, marginTop: 2 },
  amount: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  actions: { flexDirection: 'row', gap: spacing.xs, marginTop: spacing.xs },
  actionButton: {
    paddingVertical: 4,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  actionPressed: { backgroundColor: colors.surfaceMuted },
  actionDisabled: { opacity: 0.5 },
  actionText: { fontSize: fontSize.xs, fontWeight: fontWeight.semibold },
  separator: { height: 1, backgroundColor: colors.border },
  placeholder: { padding: spacing.lg, textAlign: 'center', color: colors.textMuted },
  emptyContent: { flex: 1, justifyContent: 'center' },
  errorBar: {
    padding: spacing.sm,
    color: colors.danger,
    fontSize: fontSize.sm,
    backgroundColor: colors.dangerSoft,
    textAlign: 'center',
  },
});
