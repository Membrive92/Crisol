import { Alert, FlatList, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Link, useRouter } from 'expo-router';

import {
  useCategories,
  useDeleteTransaction,
  useRestoreTransaction,
  useTransactions,
  useTrashedTransactions,
} from '@finanzas/services';
import { toast } from '@finanzas/store';
import type { Category, Transaction } from '@finanzas/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatDate,
  radius,
  spacing,
} from '@finanzas/ui';

function findCategory(categories: Category[], id: string | null): Category | undefined {
  if (!id) return undefined;
  return categories.find((c) => c.id === id);
}

export default function TransactionsScreen() {
  const router = useRouter();
  const { data, isLoading, isError, refetch, isRefetching } = useTransactions({ limit: 50 });
  const { data: categories } = useCategories();
  const deleteMutation = useDeleteTransaction();
  const restoreMutation = useRestoreTransaction();
  const trashCountQuery = useTrashedTransactions({ limit: 1 });
  const trashCount = trashCountQuery.data?.total ?? 0;

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  function handleDelete(id: string, description: string | null) {
    Alert.alert(
      'Mover a papelera',
      description ? `"${description}" pasará a papelera.` : '¿Mover esta transacción a papelera?',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Mover',
          style: 'destructive',
          onPress: () =>
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
            }),
        },
      ],
    );
  }

  function renderItem({ item }: { item: Transaction }) {
    const category = findCategory(categories ?? [], item.category_id);
    const isIncome = category?.kind === 'income';
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
          <Text style={styles.description} numberOfLines={1}>
            {item.description ?? '(sin descripción)'}
          </Text>
          <Text style={styles.meta}>
            {formatDate(item.occurred_at)} · {category?.name ?? 'Sin categoría'}
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

    </View>
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
  description: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: fontWeight.medium,
  },
  meta: { fontSize: fontSize.sm, color: colors.textMuted, marginTop: 2 },
  amount: { fontSize: fontSize.md, fontWeight: fontWeight.semibold, color: colors.text },
  amountIncome: { color: colors.income },
  separator: { height: 1, backgroundColor: colors.border },
  placeholder: { padding: spacing.lg, textAlign: 'center', color: colors.textMuted },
  emptyContent: { flex: 1, justifyContent: 'center' },
});
