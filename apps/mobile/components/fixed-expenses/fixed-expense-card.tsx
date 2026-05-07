import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { Category, FixedExpense } from '@finanzas/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatDate,
  radius,
  spacing,
} from '@finanzas/ui';

export interface FixedExpenseCardAction {
  label: string;
  onPress: () => void;
  busy?: boolean;
  danger?: boolean;
}

export interface FixedExpenseCardProps {
  fixedExpense: FixedExpense;
  categories: Category[];
  primaryAction?: FixedExpenseCardAction;
  secondaryAction?: FixedExpenseCardAction;
}

const CADENCE_LABEL: Record<number, string> = {
  7: 'Semanal',
  14: 'Quincenal',
  30: 'Mensual',
  90: 'Trimestral',
  180: 'Semestral',
  365: 'Anual',
};

function findCategory(categories: Category[], id: string | null): Category | undefined {
  if (!id) return undefined;
  return categories.find((c) => c.id === id);
}

/**
 * Card de gasto fijo mobile equivalente a la versión web. Misma
 * propuesta: callers controlan acciones vía primaryAction /
 * secondaryAction props (Confirmar+Descartar para pending,
 * Pausar+Cancelar para confirmed, etc.).
 */
export function FixedExpenseCard({
  fixedExpense: item,
  categories,
  primaryAction,
  secondaryAction,
}: FixedExpenseCardProps) {
  const category = findCategory(categories, item.category_id);
  const cadenceLabel = CADENCE_LABEL[item.cadence_days] ?? `${item.cadence_days}d`;
  const confidencePct = Math.round(item.confidence * 100);

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <View style={{ flex: 1, marginRight: spacing.sm }}>
          <Text style={styles.title} numberOfLines={1}>
            {item.raw_description}
          </Text>
          <Text style={styles.meta}>
            {cadenceLabel} · {category?.name ?? 'Sin categoría'} · confianza{' '}
            {confidencePct}%
          </Text>
        </View>
        <Text style={styles.amount}>{formatAmount(item.amount, item.currency)}</Text>
      </View>

      <View style={styles.divider} />

      <View style={styles.footer}>
        <Text style={styles.footerText} numberOfLines={2}>
          Próximo cargo:{' '}
          <Text style={styles.footerStrong}>{formatDate(item.next_due)}</Text>
          {' · '}
          {item.occurrence_count}{' '}
          {item.occurrence_count === 1 ? 'cargo' : 'cargos'}
        </Text>
        <View style={styles.actions}>
          {secondaryAction ? (
            <Pressable
              onPress={secondaryAction.onPress}
              disabled={secondaryAction.busy}
              style={({ pressed }) => [
                styles.actionButton,
                pressed && styles.pressed,
                secondaryAction.busy && styles.disabled,
              ]}
            >
              <Text
                style={[
                  styles.actionText,
                  { color: secondaryAction.danger ? colors.danger : colors.text },
                ]}
              >
                {secondaryAction.busy ? '…' : secondaryAction.label}
              </Text>
            </Pressable>
          ) : null}
          {primaryAction ? (
            <Pressable
              onPress={primaryAction.onPress}
              disabled={primaryAction.busy}
              style={({ pressed }) => [
                styles.primaryButton,
                pressed && styles.pressed,
                primaryAction.busy && styles.disabled,
              ]}
            >
              <Text style={styles.primaryButtonText}>
                {primaryAction.busy ? '…' : primaryAction.label}
              </Text>
            </Pressable>
          ) : null}
        </View>
      </View>
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
    marginBottom: spacing.sm,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  title: { fontSize: fontSize.md, fontWeight: fontWeight.semibold, color: colors.text },
  meta: { fontSize: fontSize.xs, color: colors.textMuted, marginTop: 2 },
  amount: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: spacing.xs,
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  footerText: { fontSize: fontSize.xs, color: colors.textMuted, flex: 1 },
  footerStrong: { color: colors.text, fontWeight: fontWeight.medium },
  actions: { flexDirection: 'row', gap: spacing.xs },
  actionButton: {
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  actionText: { fontSize: fontSize.xs, fontWeight: fontWeight.semibold },
  primaryButton: {
    paddingVertical: 6,
    paddingHorizontal: spacing.sm + 2,
    borderRadius: radius.sm,
    backgroundColor: colors.primary,
  },
  primaryButtonText: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    color: colors.onPrimary,
  },
  pressed: { opacity: 0.7 },
  disabled: { opacity: 0.5 },
});
