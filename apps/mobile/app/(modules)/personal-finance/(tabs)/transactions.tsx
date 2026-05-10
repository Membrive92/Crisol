import { useMemo, useState } from 'react';
import {
  FlatList,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Link, useRouter } from 'expo-router';

import {
  useAccounts,
  useCategories,
  useDeleteTransaction,
  useRestoreTransaction,
  useTransactions,
  useTrashedTransactions,
} from '@finanzas/services';
import { toast } from '@finanzas/store';
import type { Account, Category, Transaction } from '@finanzas/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatDate,
  radius,
  spacing,
} from '@finanzas/ui';

import { ConfirmDialog } from '@/components/ui/confirm-dialog';

function findCategory(categories: Category[], id: string | null): Category | undefined {
  if (!id) return undefined;
  return categories.find((c) => c.id === id);
}

export default function TransactionsScreen() {
  const router = useRouter();
  // PHASE-19.4: filtro por cuenta. `null` = todas. Cuentas archivadas
  // entran (pueden tener histórico) para que el filtro siga funcionando
  // sobre transacciones antiguas.
  const [accountFilter, setAccountFilter] = useState<string | null>(null);
  const [accountPickerOpen, setAccountPickerOpen] = useState(false);
  const accountsQuery = useAccounts({ includeArchived: true });
  const accounts = accountsQuery.data ?? [];
  const txQuery = useMemo(
    () => ({ limit: 50, ...(accountFilter ? { account_id: accountFilter } : {}) }),
    [accountFilter],
  );
  const { data, isLoading, isError, refetch, isRefetching } = useTransactions(txQuery);
  const { data: categories } = useCategories();
  const deleteMutation = useDeleteTransaction();
  const restoreMutation = useRestoreTransaction();
  const trashCountQuery = useTrashedTransactions({ limit: 1 });
  const trashCount = trashCountQuery.data?.total ?? 0;

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const selectedAccount = accountFilter
    ? accounts.find((a) => a.id === accountFilter) ?? null
    : null;

  const [pendingDelete, setPendingDelete] = useState<
    { id: string; description: string | null } | null
  >(null);

  function handleDelete(id: string, description: string | null) {
    setPendingDelete({ id, description });
  }

  function confirmDelete() {
    if (!pendingDelete) return;
    const { id } = pendingDelete;
    setPendingDelete(null);
    deleteMutation.mutate(id, {
      onSuccess: () => {
        // PHASE-11.3: snackbar inline ad-hoc reemplazado por
        // toast global. La acción Deshacer dispara el restore
        // y el toast se cierra solo.
        toast.show({
          kind: 'info',
          message: 'Transacción movida a papelera.',
          action: {
            label: 'Deshacer',
            onPress: () => restoreMutation.mutate(id),
          },
        });
      },
    });
  }

  function renderItem({ item }: { item: Transaction }) {
    const category = findCategory(categories ?? [], item.category_id);
    const isIncome = category?.kind === 'income';
    const isTransfer = item.transfer_pair_id !== null;
    return (
      <TouchableOpacity
        style={styles.row}
        onPress={() =>
          router.push({
            pathname: '/(modules)/personal-finance/transaction/[id]',
            params: { id: item.id },
          })
        }
        onLongPress={() => handleDelete(item.id, item.description)}
      >
        <View style={styles.rowText}>
          <View style={styles.descriptionRow}>
            <Text style={styles.description} numberOfLines={1}>
              {item.description ?? '(sin descripción)'}
            </Text>
            {isTransfer ? (
              <View style={styles.transferBadge}>
                <Text style={styles.transferBadgeText}>Transferencia</Text>
              </View>
            ) : null}
          </View>
          <Text style={styles.meta}>
            {formatDate(item.occurred_at)} ·{' '}
            {category?.icon ? `${category.icon} ` : ''}
            {category?.name ?? 'Sin categoría'}
          </Text>
        </View>
        <Text style={[styles.amount, isIncome && styles.amountIncome]}>
          {isIncome ? '+' : ''}
          {formatAmount(item.amount, item.currency)}
        </Text>
      </TouchableOpacity>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerText}>{total} registros</Text>
        <View style={styles.headerActions}>
          <Link href="/(modules)/personal-finance/trash" asChild>
            <TouchableOpacity style={styles.trashButton}>
              <Text style={styles.trashButtonText}>Papelera</Text>
              {trashCount > 0 ? (
                <View style={styles.badge}>
                  <Text style={styles.badgeText}>{trashCount}</Text>
                </View>
              ) : null}
            </TouchableOpacity>
          </Link>
          <Link href="/(modules)/personal-finance/transaction/new" asChild>
            <TouchableOpacity style={styles.addButton}>
              <Text style={styles.addButtonText}>+ Nueva</Text>
            </TouchableOpacity>
          </Link>
        </View>
      </View>

      <View style={styles.filtersBar}>
        <Text style={styles.filtersLabel}>Cuenta:</Text>
        <Pressable
          onPress={() => setAccountPickerOpen(true)}
          style={({ pressed }) => [
            styles.filterChip,
            accountFilter !== null && styles.filterChipActive,
            pressed && { opacity: 0.7 },
          ]}
        >
          <Text
            style={[
              styles.filterChipText,
              accountFilter !== null && styles.filterChipTextActive,
            ]}
          >
            {selectedAccount
              ? `${selectedAccount.icon ? `${selectedAccount.icon} ` : ''}${selectedAccount.name}`
              : 'Todas'}
          </Text>
        </Pressable>
        {accountFilter !== null ? (
          <Pressable
            onPress={() => setAccountFilter(null)}
            style={({ pressed }) => [
              styles.clearFilter,
              pressed && { opacity: 0.7 },
            ]}
            accessibilityLabel="Quitar filtro de cuenta"
          >
            <Text style={styles.clearFilterText}>×</Text>
          </Pressable>
        ) : null}
      </View>

      {isLoading ? (
        <Text style={styles.placeholder}>Cargando…</Text>
      ) : isError ? (
        <Text style={[styles.placeholder, { color: colors.danger }]}>Error al cargar</Text>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(t) => t.id}
          renderItem={renderItem}
          ItemSeparatorComponent={() => <View style={styles.separator} />}
          refreshing={isRefetching}
          onRefresh={() => refetch()}
          ListEmptyComponent={<Text style={styles.placeholder}>Sin transacciones.</Text>}
          contentContainerStyle={items.length === 0 ? styles.emptyContent : undefined}
        />
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title="¿Mover a la papelera?"
        description={
          pendingDelete?.description
            ? `"${pendingDelete.description}" pasará a papelera. Podrás restaurarla con Deshacer en el toast o desde la papelera.`
            : 'Podrás restaurarla desde la papelera o usar Deshacer en el toast.'
        }
        confirmLabel="Mover"
        tone="danger"
        loading={deleteMutation.isPending}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />

      <AccountPickerModal
        visible={accountPickerOpen}
        accounts={accounts}
        selectedId={accountFilter}
        onSelect={(id) => {
          setAccountFilter(id);
          setAccountPickerOpen(false);
        }}
        onClose={() => setAccountPickerOpen(false)}
      />
    </View>
  );
}

interface AccountPickerModalProps {
  visible: boolean;
  accounts: Account[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onClose: () => void;
}

/**
 * Picker modal de cuenta para el filtro de transacciones. Espejo del
 * patrón usado en `fixed-expense-card.tsx`. Incluye opción "Todas" al
 * principio para limpiar el filtro.
 */
function AccountPickerModal({
  visible,
  accounts,
  selectedId,
  onSelect,
  onClose,
}: AccountPickerModalProps) {
  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <Pressable style={styles.pickerBackdrop} onPress={onClose}>
        <Pressable
          style={styles.pickerSheet}
          onPress={(e) => e.stopPropagation()}
        >
          <Text style={styles.pickerTitle}>Filtrar por cuenta</Text>
          <ScrollView style={{ maxHeight: 360 }}>
            <Pressable
              onPress={() => onSelect(null)}
              style={({ pressed }) => [
                styles.pickerItem,
                selectedId === null && styles.pickerItemSelected,
                pressed && { opacity: 0.7 },
              ]}
            >
              <Text
                style={[
                  styles.pickerItemText,
                  selectedId === null && styles.pickerItemTextSelected,
                ]}
              >
                Todas las cuentas
              </Text>
            </Pressable>
            {accounts.map((a) => {
              const selected = a.id === selectedId;
              return (
                <Pressable
                  key={a.id}
                  onPress={() => onSelect(a.id)}
                  style={({ pressed }) => [
                    styles.pickerItem,
                    selected && styles.pickerItemSelected,
                    pressed && { opacity: 0.7 },
                  ]}
                >
                  <Text
                    style={[
                      styles.pickerItemText,
                      selected && styles.pickerItemTextSelected,
                    ]}
                  >
                    {a.icon ? `${a.icon} ` : ''}
                    {a.name} ({a.currency})
                    {a.is_archived ? ' · archivada' : ''}
                  </Text>
                </Pressable>
              );
            })}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerText: { color: colors.textMuted, fontSize: fontSize.sm },
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  trashButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  trashButtonText: { color: colors.text, fontSize: fontSize.sm, fontWeight: fontWeight.medium },
  badge: {
    minWidth: 18,
    height: 18,
    paddingHorizontal: 5,
    borderRadius: 9,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: { color: colors.onPrimary, fontSize: 10, fontWeight: fontWeight.bold },
  addButton: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  addButtonText: { color: colors.surface, fontWeight: fontWeight.semibold },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    backgroundColor: colors.surface,
  },
  rowText: { flex: 1, marginRight: spacing.sm },
  descriptionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  description: {
    flexShrink: 1,
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: fontWeight.medium,
  },
  transferBadge: {
    paddingHorizontal: spacing.xs + 2,
    paddingVertical: 1,
    borderRadius: radius.sm,
    backgroundColor: colors.primarySoft,
  },
  transferBadgeText: {
    fontSize: 10,
    fontWeight: fontWeight.semibold,
    color: colors.primary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  meta: { fontSize: fontSize.sm, color: colors.textMuted, marginTop: 2 },
  amount: { fontSize: fontSize.md, fontWeight: fontWeight.semibold, color: colors.text },
  amountIncome: { color: colors.income },
  separator: { height: 1, backgroundColor: colors.border },
  placeholder: { padding: spacing.lg, textAlign: 'center', color: colors.textMuted },
  emptyContent: { flex: 1, justifyContent: 'center' },
  filtersBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  filtersLabel: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    fontWeight: fontWeight.medium,
  },
  filterChip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  filterChipActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primarySoft,
  },
  filterChipText: {
    fontSize: fontSize.xs,
    color: colors.text,
    fontWeight: fontWeight.medium,
  },
  filterChipTextActive: {
    color: colors.primary,
    fontWeight: fontWeight.semibold,
  },
  clearFilter: {
    width: 22,
    height: 22,
    borderRadius: 11,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surfaceMuted,
  },
  clearFilterText: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    lineHeight: 18,
  },
  pickerBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
  },
  pickerSheet: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    width: '100%',
    maxWidth: 420,
    borderWidth: 1,
    borderColor: colors.border,
  },
  pickerTitle: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.sm,
  },
  pickerItem: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
  },
  pickerItemSelected: {
    backgroundColor: colors.primarySoft,
  },
  pickerItemText: {
    fontSize: fontSize.sm,
    color: colors.text,
  },
  pickerItemTextSelected: {
    color: colors.primary,
    fontWeight: fontWeight.semibold,
  },
});
