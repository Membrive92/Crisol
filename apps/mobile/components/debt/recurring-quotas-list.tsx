import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import type { RecurringQuotaRef } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

export interface RecurringQuotasListProps {
  items: RecurringQuotaRef[];
  currency: string;
  isLoading: boolean;
}

/**
 * PHASE-30.5 — Mobile parity de `recurring-quotas-list.tsx` (web).
 * Cuotas recurrentes detectadas con categoría de deuda + CTA
 * "Vincular" que navega a la lista de cuentas para crear/asociar
 * un contrato.
 */
export function RecurringQuotasList({
  items,
  currency,
  isLoading,
}: RecurringQuotasListProps) {
  const router = useRouter();
  if (isLoading) {
    return (
      <View style={[styles.card, styles.empty]}>
        <Text style={styles.emptyText}>Cargando cuotas detectadas…</Text>
      </View>
    );
  }
  if (items.length === 0) return null;
  return (
    <View style={styles.card}>
      <Text style={styles.title}>Cuotas recurrentes detectadas</Text>
      <Text style={styles.subtitle}>
        Gastos fijos que estás confirmando como pagos a deuda. Vincula los
        que tengan contrato real para que cuenten en tu patrimonio.
      </Text>
      <View style={{ gap: spacing.xs }}>
        {items.map((q) => (
          <View key={q.fixed_expense_id} style={styles.row}>
            <View style={{ flex: 1, minWidth: 0 }}>
              <Text style={styles.merchant} numberOfLines={1}>
                {q.merchant}
              </Text>
              {q.category_name ? (
                <Text style={styles.categoryName}>{q.category_name}</Text>
              ) : null}
            </View>
            <Text style={styles.amount}>
              {formatAmount(q.amount, q.currency || currency)}
              <Text style={styles.amountSuffix}> / mes</Text>
            </Text>
            <Pressable
              onPress={() => router.push('/personal-finance/accounts')}
              style={({ pressed }) => [styles.linkBtn, pressed && { opacity: 0.7 }]}
              accessibilityRole="button"
            >
              <Text style={styles.linkBtnText}>Vincular</Text>
            </Pressable>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  empty: {
    paddingVertical: spacing.md,
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
  },
  title: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  subtitle: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    lineHeight: 18,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.sm,
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
  },
  merchant: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  categoryName: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 1,
  },
  amount: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  amountSuffix: {
    fontWeight: fontWeight.regular,
    color: colors.textMuted,
    fontSize: fontSize.xs,
  },
  linkBtn: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
  },
  linkBtnText: {
    fontSize: 11,
    fontWeight: fontWeight.semibold,
    color: colors.primary,
  },
});
