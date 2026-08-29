import { StyleSheet, Text, View } from 'react-native';

import type { TopExpenseItem } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';
import {
  categoryRowAmount,
  formatAmount,
  formatCivilDate,
  isRefundInExpenseList,
} from '@crisol/ui';

export interface TopExpensesListProps {
  data: TopExpenseItem[] | undefined;
  currency: string;
  isLoading: boolean;
}

export function TopExpensesList({ data, currency, isLoading }: TopExpensesListProps) {
  const items = data ?? [];

  return (
    <View style={styles.card}>
      <Text style={styles.title}>Top gastos</Text>
      {isLoading && !data ? (
        <Text style={styles.placeholder}>Cargando…</Text>
      ) : items.length === 0 ? (
        <Text style={styles.placeholder}>Sin gastos en el periodo.</Text>
      ) : (
        items.map((item, idx) => {
          // PHASE-47.H — este endpoint devuelve el cubo de GASTO entero, así que
          // una entrada aquí es una devolución: resta, y se pinta restando.
          const devolucion = isRefundInExpenseList(item.flow);
          return (
            <View
              key={item.transaction_id}
              style={[styles.row, idx === items.length - 1 && styles.rowLast]}
            >
              <View style={styles.rowText}>
                <Text style={styles.description} numberOfLines={1}>
                  {item.description ?? 'Sin descripción'}
                </Text>
                <Text style={styles.meta}>
                  {(devolucion ? 'Devolución · ' : '') +
                    (item.category_name ?? 'Sin categoría') +
                    ' · ' +
                    formatCivilDate(item.occurred_at)}
                </Text>
              </View>
              <Text style={[styles.amount, devolucion && styles.amountRefund]}>
                {formatAmount(categoryRowAmount(item.amount, item.flow, 'expense'), currency)}
              </Text>
            </View>
          );
        })
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  title: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.sm,
  },
  placeholder: { color: colors.textMuted, fontSize: fontSize.sm },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: spacing.sm,
  },
  rowLast: { borderBottomWidth: 0 },
  rowText: { flex: 1, minWidth: 0 },
  description: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
    color: colors.text,
  },
  meta: { fontSize: fontSize.xs, color: colors.textMuted, marginTop: 2 },
  amount: { fontSize: fontSize.sm, fontWeight: fontWeight.semibold, color: colors.expense },
  amountRefund: { color: colors.success },
});
