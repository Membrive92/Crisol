import { FlatList, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Link, useRouter } from 'expo-router';

import {
  useCategories,
  useDeleteTransaction,
  useTransactions,
} from '@finanzas/services';
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

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  function handleDelete(id: string) {
    deleteMutation.mutate(id);
  }

  function renderItem({ item }: { item: Transaction }) {
    const category = findCategory(categories ?? [], item.category_id);
    const isIncome = category?.kind === 'income';
    return (
      <TouchableOpacity
        style={styles.row}
        onPress={() => router.push({ pathname: '/transaction/[id]', params: { id: item.id } })}
        onLongPress={() => handleDelete(item.id)}
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
        <Link href="/transaction/new" asChild>
          <TouchableOpacity style={styles.addButton}>
            <Text style={styles.addButtonText}>+ Nueva</Text>
          </TouchableOpacity>
        </Link>
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
  addButton: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  addButtonText: { color: colors.surface, fontWeight: fontWeight.semibold as '600' },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    backgroundColor: colors.surface,
  },
  rowText: { flex: 1, marginRight: spacing.sm },
  description: { fontSize: fontSize.md, color: colors.text, fontWeight: fontWeight.medium as '500' },
  meta: { fontSize: fontSize.sm, color: colors.textMuted, marginTop: 2 },
  amount: { fontSize: fontSize.md, fontWeight: fontWeight.semibold as '600', color: colors.text },
  amountIncome: { color: colors.income },
  separator: { height: 1, backgroundColor: colors.border },
  placeholder: { padding: spacing.lg, textAlign: 'center', color: colors.textMuted },
  emptyContent: { flex: 1, justifyContent: 'center' },
});
