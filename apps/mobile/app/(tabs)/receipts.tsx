import { FlatList, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Link, useRouter } from 'expo-router';

import { useReceipts } from '@finanzas/services';
import type { Receipt } from '@finanzas/types';
import { colors, fontSize, fontWeight, formatDate, radius, spacing } from '@finanzas/ui';

const STATUS_LABEL: Record<Receipt['status'], string> = {
  pending: 'Pendiente',
  confirmed: 'Confirmado',
  rejected: 'Rechazado',
};

const STATUS_COLOR: Record<Receipt['status'], string> = {
  pending: colors.primary,
  confirmed: colors.success,
  rejected: colors.danger,
};

function pickMerchant(receipt: Receipt): string | null {
  const ext = receipt.extraction as Record<string, unknown>;
  const value = ext['merchant'];
  return typeof value === 'string' ? value : null;
}

function pickTotal(receipt: Receipt): string | null {
  const ext = receipt.extraction as Record<string, unknown>;
  const total = ext['total'];
  const currency = ext['currency'] ?? 'EUR';
  if (typeof total !== 'string') return null;
  return `${total} ${typeof currency === 'string' ? currency : ''}`.trim();
}

export default function ReceiptsScreen() {
  const router = useRouter();
  const { data, isLoading, isError, refetch, isRefetching } = useReceipts({ limit: 50 });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  function renderItem({ item }: { item: Receipt }) {
    const merchant = pickMerchant(item);
    const totalText = pickTotal(item);
    return (
      <TouchableOpacity
        style={styles.row}
        onPress={() => router.push({ pathname: '/receipt/[id]', params: { id: item.id } })}
      >
        <View style={styles.rowText}>
          <Text style={styles.merchant} numberOfLines={1}>
            {merchant ?? '(sin comercio)'}
          </Text>
          <Text style={styles.meta}>
            {formatDate(item.created_at)} · {totalText ?? '—'}
          </Text>
        </View>
        <View style={[styles.badge, { backgroundColor: STATUS_COLOR[item.status] }]}>
          <Text style={styles.badgeText}>{STATUS_LABEL[item.status]}</Text>
        </View>
      </TouchableOpacity>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerText}>{total} {total === 1 ? 'ticket' : 'tickets'}</Text>
        <Link href="/receipt/new" asChild>
          <TouchableOpacity style={styles.addButton}>
            <Text style={styles.addButtonText}>+ Capturar</Text>
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
          keyExtractor={(r) => r.id}
          renderItem={renderItem}
          ItemSeparatorComponent={() => <View style={styles.separator} />}
          refreshing={isRefetching}
          onRefresh={() => refetch()}
          ListEmptyComponent={
            <Text style={styles.placeholder}>Aún no has subido tickets.</Text>
          }
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
  merchant: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: fontWeight.medium as '500',
  },
  meta: { fontSize: fontSize.sm, color: colors.textMuted, marginTop: 2 },
  badge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.sm,
  },
  badgeText: {
    color: colors.surface,
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold as '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  separator: { height: 1, backgroundColor: colors.border },
  placeholder: { padding: spacing.lg, textAlign: 'center', color: colors.textMuted },
  emptyContent: { flex: 1, justifyContent: 'center' },
});
